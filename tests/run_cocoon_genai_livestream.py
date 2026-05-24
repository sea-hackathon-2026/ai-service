"""Run Cocoon livecommerce v2 through the Google GenAI livestream pipeline.

This runner consumes the hand-authored scene JSON directly instead of asking
the pipeline to split the script again.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import Settings
from app.domain.entities.scene import SceneChunk, SceneType
from app.infrastructure.ai_models.gemini_genai_client import GeminiGenAIClient
from app.infrastructure.ai_models.micro_scene_pipeline import (
    DEFAULT_NEGATIVE_PROMPT,
    MOTION_RULES,
    MicroScenePipelineConfig,
    MicroSceneVideoPipeline,
    concat_scene_clips,
    get_media_duration,
)


DEFAULT_SCRIPT = PROJECT_ROOT / "data" / "cocoon_livecommerce_script_v2.json"
DEFAULT_INPUT_DIR = PROJECT_ROOT / "data" / "inputs"
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "data" / "outputs" / "genai_livestream"

HOST_SCENE_TYPES = {
    "HOOK",
    "PRODUCT_PIN",
    "BRAND_TRUST",
    "DEMO",
    "BENEFIT",
    "BENEFIT_DEMO",
    "BENEFIT_PROOF",
    "COMPARE_PROOF",
    "FAQ_ANSWER",
    "RESET",
}

CTA_SCENE_TYPES = {"CTA", "CTA_RESET", "OFFER_SUMMARY", "FINAL_CTA"}
PRODUCT_SCENE_TYPES = {"PRODUCT_CLOSEUP", "PRODUCT_BEAUTY"}


def main() -> int:
    args = parse_args()
    settings = Settings()

    script = json.loads(args.script.read_text(encoding="utf-8"))
    job_id = args.job_id or safe_filename(script.get("job_id") or "cocoon_genai_livestream")
    output_dir = args.output_root / f"{job_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    output_dir.mkdir(parents=True, exist_ok=True)

    setup_logging(output_dir / "run.log")
    logger = logging.getLogger("cocoon_genai")

    model_image = args.input_dir / "model.png"
    default_product_image = args.input_dir / "product.png"
    if not model_image.exists():
        raise FileNotFoundError(f"Missing model image: {model_image}")
    if not default_product_image.exists():
        raise FileNotFoundError(f"Missing default product image: {default_product_image}")

    api_key = settings.gemini_api_key or os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY/gemini_api_key is missing from environment.")

    logger.info("Job: %s", job_id)
    logger.info("Script: %s", args.script)
    logger.info("Input dir: %s", args.input_dir)
    logger.info("Output dir: %s", output_dir)
    logger.info("Veo model: %s", settings.genai_veo_model)
    logger.info("Aspect ratio: %s", args.aspect_ratio)
    logger.info("Use Imagen: %s", args.use_imagen)

    genai_client = GeminiGenAIClient(
        api_key=api_key,
        imagen_model=settings.genai_imagen_model,
        veo_model=settings.genai_veo_model,
    )

    pipeline_config = MicroScenePipelineConfig(
        output_width=1280 if args.aspect_ratio == "16:9" else settings.livestream_output_width,
        output_height=720 if args.aspect_ratio == "16:9" else settings.livestream_output_height,
        fps=settings.livestream_fps,
        tts_provider=args.tts_provider,
        tts_voice=settings.livestream_tts_voice,
        enable_wav2lip=False,
        wav2lip_dir=settings.wav2lip_dir,
        wav2lip_checkpoint=settings.wav2lip_checkpoint,
        wav2lip_resize_factor=settings.wav2lip_resize_factor,
        wav2lip_pads=settings.wav2lip_pads,
        genai_client=genai_client,
        genai_aspect_ratio=args.aspect_ratio,
        genai_use_imagen=args.use_imagen,
        genai_skip_wav2lip=True,
        genai_enhance_prompt=True,
    )
    pipeline = MicroSceneVideoPipeline(
        config=pipeline_config,
        public_url_prefix=f"/static/outputs/genai_livestream/{output_dir.name}",
    )

    raw_scenes = script.get("scenes", [])
    if args.max_scenes:
        raw_scenes = raw_scenes[: args.max_scenes]
        logger.warning("MAX_SCENES active: running first %d scenes only", len(raw_scenes))

    scenes = [scene_from_json(scene) for scene in raw_scenes]
    (output_dir / "source_script.json").write_text(
        json.dumps(script, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "mapped_scene_plan.json").write_text(
        json.dumps([scene.model_dump() for scene in scenes], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    scene_outputs: list[dict[str, Any]] = []
    scene_video_paths: list[str] = []

    for idx, (raw_scene, scene) in enumerate(zip(raw_scenes, scenes), start=1):
        scene_id = scene.scene_id
        product_image = resolve_product_image(args.input_dir, scene_id, default_product_image)
        logger.info(
            "[%s/%s] Start %s (%s -> %s), product_image=%s",
            idx,
            len(scenes),
            scene_id,
            raw_scene.get("scene_type"),
            scene.scene_type,
            product_image,
        )

        try:
            final_scene = pipeline.generate_scene_clip(
                scene=scene,
                job_dir=str(output_dir),
                model_image_path=str(model_image),
                product_image_path=str(product_image),
                voice=settings.livestream_tts_voice,
                product_name="Cocoon livecommerce",
                product_description="Vietnamese vegan cosmetics product set for a clean ecommerce livestream.",
                brand_style="clean Vietnamese ecommerce livestream",
            )
            duration = get_media_duration(final_scene, fallback=scene.duration_target_sec)
            scene_video_paths.append(final_scene)
            scene_outputs.append(
                {
                    "scene_id": scene_id,
                    "original_scene_type": raw_scene.get("scene_type"),
                    "mapped_scene_type": scene.scene_type,
                    "video_path": final_scene,
                    "duration_sec": duration,
                    "status": "ok",
                }
            )
            logger.info("[%s] OK -> %s (%.2fs)", scene_id, final_scene, duration)
        except Exception as exc:
            logger.exception("[%s] Failed", scene_id)
            scene_outputs.append(
                {
                    "scene_id": scene_id,
                    "original_scene_type": raw_scene.get("scene_type"),
                    "mapped_scene_type": scene.scene_type,
                    "video_path": None,
                    "status": "error",
                    "error": repr(exc),
                }
            )
            if not args.continue_on_error:
                raise

    if not scene_video_paths:
        raise RuntimeError("No scene videos were generated.")

    final_dir = output_dir / "final"
    final_dir.mkdir(parents=True, exist_ok=True)
    final_video = final_dir / "final_video.mp4"
    concat_scene_clips(scene_video_paths, str(final_video))
    final_duration = get_media_duration(str(final_video), fallback=0.0)

    result = {
        "job_id": job_id,
        "output_dir": str(output_dir),
        "final_video": str(final_video),
        "duration_sec": final_duration,
        "scene_count": len(scene_video_paths),
        "scenes": scene_outputs,
    }
    (output_dir / "result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    logger.info("DONE final_video=%s duration=%.2fs", final_video, final_duration)
    print(str(final_video))
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--script", type=Path, default=DEFAULT_SCRIPT)
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--job-id", default=None)
    parser.add_argument("--aspect-ratio", default="9:16", choices=["16:9", "9:16"])
    parser.add_argument("--tts-provider", default="auto", choices=["auto", "edge", "silent"])
    parser.add_argument("--use-imagen", action="store_true")
    parser.add_argument("--max-scenes", type=int, default=None)
    parser.add_argument("--continue-on-error", action="store_true")
    return parser.parse_args()


def setup_logging(log_path: Path) -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers.clear()

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)

    root.addHandler(file_handler)
    root.addHandler(stream_handler)


def scene_from_json(raw: dict[str, Any]) -> SceneChunk:
    scene_type = map_scene_type(str(raw.get("scene_type", "")))
    motion = MOTION_RULES.get(scene_type, "subtle livestream motion")
    voiceover = normalize_text(raw.get("voiceover", ""))
    visual_goal = normalize_text(raw.get("visual_goal", ""))
    start_anchor = normalize_text(raw.get("start_anchor", ""))
    end_anchor = normalize_text(raw.get("end_anchor", ""))
    host_action = (
        f"{start_anchor}. {end_anchor}".strip()
        if scene_type.startswith("HOST") or scene_type == "CTA"
        else "none"
    )
    product_action = (
        "show product clearly and keep packaging accurate"
        if raw.get("needs_product_overlay") or scene_type in {"PRODUCT_CLOSEUP", "CTA"}
        else "none"
    )

    return SceneChunk(
        scene_id=safe_filename(raw.get("scene_id", "scene")),
        order=int(raw.get("order") or 0),
        scene_type=scene_type,
        text=voiceover,
        visual_goal=visual_goal,
        emotion="friendly",
        camera="medium close-up, fixed front camera",
        host_action=host_action or motion,
        product_action=product_action,
        duration_target_sec=float(raw.get("duration_target_sec") or 5.0),
        image_prompt="",
        negative_prompt=DEFAULT_NEGATIVE_PROMPT,
        motion_prompt=build_motion_prompt(raw, motion),
        overlay_text=None,
        use_lipsync=bool(raw.get("needs_lipsync", True)),
        use_product_overlay=bool(raw.get("needs_product_overlay", False)),
    )


def map_scene_type(raw_type: str) -> SceneType:
    upper = raw_type.upper()
    if upper == "HOST_PHONE_READING":
        return "HOST_PHONE_READING"
    if upper in PRODUCT_SCENE_TYPES:
        return "PRODUCT_CLOSEUP"
    if upper in CTA_SCENE_TYPES:
        return "CTA"
    if upper in HOST_SCENE_TYPES:
        return "HOST_TALK"
    return "HOST_TALK"


def build_motion_prompt(raw: dict[str, Any], fallback_motion: str) -> str:
    parts = [
        fallback_motion,
        normalize_text(raw.get("visual_goal", "")),
        f"Start: {normalize_text(raw.get('start_anchor', ''))}",
        f"End: {normalize_text(raw.get('end_anchor', ''))}",
    ]
    return "\n".join(part for part in parts if part and part != "Start: " and part != "End: ")


def resolve_product_image(input_dir: Path, scene_id: str, default_product_image: Path) -> Path:
    for suffix in (".png", ".jpg", ".jpeg", ".webp"):
        candidate = input_dir / f"product-{scene_id}{suffix}"
        if candidate.exists():
            return candidate
    return default_product_image


def normalize_text(value: Any) -> str:
    return " ".join(str(value or "").split())


def safe_filename(value: Any) -> str:
    text = str(value or "scene").strip()
    cleaned = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in text)
    return cleaned or "scene"


if __name__ == "__main__":
    raise SystemExit(main())
