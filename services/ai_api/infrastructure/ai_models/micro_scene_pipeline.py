"""Micro-scene livestream video pipeline.

This module implements the MVP from docs/gen.md:
split a long seller script into short scenes, synthesize audio per scene,
turn a keyframe into a short clip, optionally run Wav2Lip for host scenes,
and concatenate the scene clips into one vertical video.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import shutil
import subprocess
import unicodedata
import wave
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

from services.ai_api.application.ports.livestream_pipeline import (
    GeneratedScene,
    LivestreamPipelineResult,
    ProgressCallback,
)
from services.ai_api.domain.entities.scene import SceneChunk, SceneType

logger = logging.getLogger(__name__)


DEFAULT_NEGATIVE_PROMPT = """
distorted face, different person, changed hairstyle, changed outfit,
extra fingers, broken hands, warped product, wrong logo, fake text,
unreadable label, duplicated product, heavy motion blur, low quality,
overly cinematic, fantasy style, deformed mouth, bad teeth
""".strip()


IMAGE_PROMPT_TEMPLATE = """
Create a vertical 9:16 ecommerce livestream keyframe.

CHARACTER LOCK:
- same person as the provided model reference image
- same face identity, same hairstyle, same outfit
- natural skin texture, realistic Vietnamese livestream host
- no face change, no age change, no hairstyle change

PRODUCT LOCK:
- use the provided product reference image as the accurate product source
- product package shape and main color must stay accurate
- do not invent new label text or logo
- if product text is unclear, leave space for overlay instead of generating fake text

SCENE:
{visual_goal}

HOST ACTION:
{host_action}

PRODUCT ACTION:
{product_action}

CAMERA:
{camera}, vertical livestream framing, stable tripod, clean ecommerce layout

LIGHTING:
soft studio lighting, bright but natural, product-focused, clean background

STYLE:
realistic ecommerce livestream, modern Vietnamese shop, clean and trustworthy

SAFE ZONE:
leave empty space at lower third for price/comment overlays

NEGATIVE PROMPT:
{negative_prompt}
""".strip()


MOTION_PROMPT_TEMPLATE = """
Create a very short seamless livestream motion clip.

SCENE TYPE:
{scene_type}

MOTION:
{motion_prompt}

STRICT MOTION RULES:
- subtle movement only
- natural blinking
- small head movement
- calm breathing
- stable camera
- no large body movement
- no fast hand gesture
- no scene change
- first and last frame should be visually similar for looping

DURATION:
{duration_sec} seconds

ASPECT RATIO:
9:16 vertical livestream video
""".strip()


VEO_PROMPT_TEMPLATE = """
{aspect_ratio} ecommerce livestream video, target duration {duration_target_sec} seconds.

[REFERENCE INPUTS]
Use the provided model reference image for the host's general appearance,
outfit, framing, and livestream setup.
Use the provided product reference image for product shape, color, and packaging.
Do not treat the combined reference image as a split-screen layout.

[VISUAL LOCK]
Vietnamese livestream host for {product_name}. {brand_style}
Keep the same reference host look, visible facial appearance, hairstyle,
outfit, background, lighting, camera angle, and body framing across scenes.
Product context: {product_description}

[SCENE GOAL]
{visual_goal}

[HOST ACTION]
{host_action}

[PRODUCT ACTION]
{product_action}

[SPEECH / MOUTH MOTION]
The host appears to speak this Vietnamese line naturally:
"{speech_text}"
Keep the spoken-language feeling Vietnamese, friendly, and livestream-native.

[MOTION]
{motion_prompt}
Subtle movement only: natural blinking, small head nod, calm breathing, tiny hand movement.
No large gesture. No body turn. No scene transition. Stable camera.
The first and last frames should be visually similar for looping or stitching.

[PRODUCT RULES]
Use the uploaded product reference only as visual truth.
Do not invent product label text, price, logo, or readable claims.
If exact text is needed, leave clean space for later overlay.

[NEGATIVE]
{negative_prompt}
""".strip()


VEO_SAFE_NEGATIVE_PROMPT = """
changed outfit, changed hairstyle, warped product, wrong product shape,
fake logo, unreadable product text, invented label, extra fingers,
broken hands, heavy camera movement, fast cuts, scene change,
heavy motion blur, low quality, fantasy style
""".strip()


MOTION_RULES: dict[SceneType, str] = {
    "HOST_TALK": "small head nod, natural blinking, slight mouth-ready expression",
    "HOST_PHONE_READING": "looking down at phone, small nod, natural blinking, calm breathing",
    "PRODUCT_CLOSEUP": "slow camera push-in, product remains centered and accurate",
    "PRODUCT_BEAUTY": "subtle light movement, product stays still, clean background",
    "CTA": "static product shot with animated text overlay, no AI product redraw",
    "TRANSITION": "short soft fade transition",
}


@dataclass
class MicroScenePipelineConfig:
    """Runtime config for local media tools and output formatting."""

    output_width: int = 720
    output_height: int = 1280
    fps: int = 25
    tts_provider: str = "auto"
    tts_voice: str = "vi-VN-HoaiMyNeural"
    enable_wav2lip: bool = False
    wav2lip_dir: str = "/content/Wav2Lip"
    wav2lip_checkpoint: str = "/content/Wav2Lip/checkpoints/Wav2Lip-SD-GAN.pt"
    wav2lip_resize_factor: int = 2
    wav2lip_pads: tuple[int, int, int, int] = (0, 20, 0, 0)

    # Google GenAI client (Imagen 3 + Veo 2) — None means use local only
    genai_client: object | None = None
    genai_aspect_ratio: str = "16:9"
    genai_use_imagen: bool = False
    genai_skip_wav2lip: bool = True
    genai_enhance_prompt: bool = True


def split_sentence_to_chunks(text: str, max_words: int = 12) -> list[str]:
    """Split Vietnamese seller copy into short chunks for stable rendering."""

    normalized = re.sub(r"\s+", " ", text.strip())
    if not normalized:
        return []

    parts = re.split(r"(?<=[.!?])\s+|[,;]\s*", normalized)
    chunks: list[str] = []

    for part in parts:
        words = part.strip().split()
        if not words:
            continue

        current: list[str] = []
        for word in words:
            current.append(word)
            if len(current) >= max_words:
                chunks.append(" ".join(current))
                current = []

        if current:
            chunks.append(" ".join(current))

    return chunks


def classify_scene_type(text: str, order: int) -> SceneType:
    """Classify a text chunk into a simple visual scene type."""

    lower = _strip_accents(text.lower())

    if any(k in lower for k in ["comment", "binh luan", "hoi", "inbox"]):
        return "HOST_PHONE_READING"

    if any(
        k in lower
        for k in [
            "gia",
            "sale",
            "uu dai",
            "chot",
            "mua",
            "dat hang",
            "click",
        ]
    ):
        return "CTA"

    if any(
        k in lower
        for k in [
            "san pham",
            "thiet ke",
            "chat lieu",
            "thanh phan",
            "cong dung",
            "serum",
            "kem",
            "mau",
        ]
    ):
        return "PRODUCT_CLOSEUP" if order > 1 else "HOST_TALK"

    return "HOST_TALK"


def should_lipsync(scene_type: str) -> bool:
    """Return whether this scene benefits from Wav2Lip."""

    return scene_type in {"HOST_TALK", "HOST_PHONE_READING"}


def split_script_to_scenes(
    product_name: str,
    product_description: str,
    brand_style: str,
    script: str,
) -> list[SceneChunk]:
    """Rule-based fallback scene splitter from docs/gen.md."""

    chunks = split_sentence_to_chunks(script, max_words=12)
    scenes: list[SceneChunk] = []

    for i, chunk in enumerate(chunks, start=1):
        scene_type = classify_scene_type(chunk, i)
        motion = MOTION_RULES.get(scene_type, "subtle motion")
        is_product_scene = scene_type in {"PRODUCT_CLOSEUP", "PRODUCT_BEAUTY", "CTA"}
        visual_goal = (
            f"Livestream scene for {product_name}. {product_description or brand_style}"
        ).strip()

        scene = SceneChunk(
            scene_id=f"S{i:03d}",
            order=i,
            scene_type=scene_type,
            text=chunk,
            visual_goal=visual_goal,
            emotion="friendly" if scene_type == "HOST_TALK" else "helpful",
            camera="medium shot" if scene_type.startswith("HOST") else "product close-up",
            host_action=motion if scene_type.startswith("HOST") else "none",
            product_action="show product clearly" if is_product_scene else "none",
            duration_target_sec=3.0,
            image_prompt=IMAGE_PROMPT_TEMPLATE.format(
                visual_goal=visual_goal,
                host_action=motion if scene_type.startswith("HOST") else "none",
                product_action="show product clearly" if is_product_scene else "none",
                camera="medium shot" if scene_type.startswith("HOST") else "product close-up",
                negative_prompt=DEFAULT_NEGATIVE_PROMPT,
            ),
            negative_prompt=DEFAULT_NEGATIVE_PROMPT,
            motion_prompt=MOTION_PROMPT_TEMPLATE.format(
                scene_type=scene_type,
                motion_prompt=motion,
                duration_sec=3.0,
            ),
            overlay_text=chunk if scene_type == "CTA" else None,
            use_lipsync=should_lipsync(scene_type),
            use_product_overlay=is_product_scene,
        )
        scenes.append(scene)

    return scenes


def build_veo_prompt(
    *,
    scene: SceneChunk,
    product_name: str,
    product_description: str,
    brand_style: str,
    aspect_ratio: str = "9:16",
) -> str:
    """Build the Google Veo-specific prompt used by the API path."""

    motion_prompt = MOTION_RULES.get(scene.scene_type, "subtle livestream motion")
    if scene.motion_prompt and "ASPECT RATIO:" not in scene.motion_prompt:
        motion_prompt = scene.motion_prompt

    return VEO_PROMPT_TEMPLATE.format(
        aspect_ratio=aspect_ratio,
        duration_target_sec=max(5, int(scene.duration_target_sec)),
        product_name=product_name or "the uploaded product",
        product_description=product_description
        or "Use only the uploaded product image as factual visual reference.",
        brand_style=brand_style or "clean ecommerce livestream style",
        visual_goal=scene.visual_goal,
        host_action=scene.host_action or "natural livestream host presence",
        product_action=scene.product_action or "keep product visible and accurate",
        speech_text=scene.text.replace('"', "'"),
        motion_prompt=motion_prompt,
        negative_prompt=VEO_SAFE_NEGATIVE_PROMPT,
    )


def _dimensions_for_aspect_ratio(aspect_ratio: str) -> tuple[int, int]:
    """Return a practical HD canvas for the configured Veo aspect ratio."""

    normalized = aspect_ratio.strip().lower().replace(" ", "")
    if normalized == "16:9":
        return 1280, 720
    if normalized == "9:16":
        return 720, 1280
    if normalized == "1:1":
        return 1024, 1024
    return 1280, 720


def _make_veo_reference_image(
    model_image_path: str,
    product_image_path: str,
    output_path: str,
    *,
    aspect_ratio: str = "16:9",
) -> str:
    """Create one economical reference sheet from model + product uploads."""

    width, height = _dimensions_for_aspect_ratio(aspect_ratio)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    if width >= height:
        model_width = int(width * 0.55)
        product_width = width - model_width
        filter_complex = (
            f"[0:v]scale={model_width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={model_width}:{height},setsar=1[m];"
            f"[1:v]scale={product_width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={product_width}:{height}:(ow-iw)/2:(oh-ih)/2:color=white,setsar=1[p];"
            f"color=c=white:s={width}x{height}[bg];"
            f"[bg][m]overlay=0:0[tmp];[tmp][p]overlay={model_width}:0,format=rgb24"
        )
    else:
        model_height = int(height * 0.62)
        product_height = height - model_height
        filter_complex = (
            f"[0:v]scale={width}:{model_height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{model_height},setsar=1[m];"
            f"[1:v]scale={width}:{product_height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{product_height}:(ow-iw)/2:(oh-ih)/2:color=white,setsar=1[p];"
            f"color=c=white:s={width}x{height}[bg];"
            f"[bg][m]overlay=0:0[tmp];[tmp][p]overlay=0:{model_height},format=rgb24"
        )

    try:
        _ensure_ffmpeg()
        _run(
            [
                "ffmpeg",
                "-y",
                "-i",
                model_image_path,
                "-i",
                product_image_path,
                "-filter_complex",
                filter_complex,
                "-frames:v",
                "1",
                str(output),
            ]
        )
    except Exception:
        logger.exception("Could not create combined Veo reference; using model image")
        shutil.copy2(model_image_path, output)

    return str(output)


def get_media_duration(path: str, fallback: float | None = None) -> float:
    """Return media duration in seconds using ffprobe."""

    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "json",
        path,
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        return float(data["format"]["duration"])
    except (FileNotFoundError, subprocess.CalledProcessError, KeyError, ValueError) as exc:
        if fallback is not None:
            logger.warning("Could not probe duration for %s, using %.2fs: %s", path, fallback, exc)
            return fallback
        raise RuntimeError("ffprobe is required to read generated media duration") from exc


async def synthesize_edge_tts(
    text: str,
    output_path: str,
    voice: str = "vi-VN-HoaiMyNeural",
) -> str:
    """Generate an audio file using Edge-TTS."""

    try:
        import edge_tts
    except ImportError as exc:
        raise RuntimeError("edge-tts is not installed") from exc

    communicate = edge_tts.Communicate(text=text, voice=voice, rate="+0%", volume="+0%")
    await communicate.save(output_path)
    return output_path


def write_silent_wav(text: str, output_path: str, sample_rate: int = 22050) -> str:
    """Create a deterministic silent WAV fallback for offline/local runs."""

    words = max(1, len(text.split()))
    duration_sec = min(max(words * 0.34, 1.0), 5.0)
    total_frames = int(duration_sec * sample_rate)

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with wave.open(output_path, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(b"\x00\x00" * total_frames)

    return output_path


def generate_tts(
    text: str,
    output_path: str,
    voice: str,
    provider: str = "auto",
) -> str:
    """Generate scene audio, falling back to silence in auto mode."""

    provider = provider.lower()
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    if provider == "silent":
        return write_silent_wav(text, output_path)

    try:
        asyncio.run(synthesize_edge_tts(text, output_path, voice=voice))
        return output_path
    except Exception:
        if provider == "edge":
            raise
        logger.exception("Edge-TTS failed; using silent fallback audio")
        return write_silent_wav(text, output_path)


def make_base_video_from_image(
    image_path: str,
    audio_path: str,
    output_path: str,
    width: int = 720,
    height: int = 1280,
    fps: int = 25,
    fallback_duration_sec: float = 3.0,
) -> str:
    """Create a vertical video from a static keyframe and mux scene audio."""

    _ensure_ffmpeg()
    duration = get_media_duration(audio_path, fallback=fallback_duration_sec) + 0.15
    vf = (
        f"scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},fps={fps},format=yuv420p"
    )

    cmd = [
        "ffmpeg",
        "-y",
        "-loop",
        "1",
        "-i",
        image_path,
        "-i",
        audio_path,
        "-t",
        str(duration),
        "-vf",
        vf,
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "23",
        "-c:a",
        "aac",
        "-ar",
        "44100",
        "-ac",
        "2",
        "-shortest",
        "-movflags",
        "+faststart",
        output_path,
    ]
    _run(cmd)
    return output_path


def make_product_zoom_video(
    image_path: str,
    audio_path: str,
    output_path: str,
    width: int = 720,
    height: int = 1280,
    fps: int = 25,
    fallback_duration_sec: float = 3.0,
) -> str:
    """Create a subtle product zoom video while preserving the uploaded product image."""

    _ensure_ffmpeg()
    duration = get_media_duration(audio_path, fallback=fallback_duration_sec) + 0.15
    frames = max(1, int(duration * fps))
    vf = (
        f"scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},"
        "zoompan=z='min(zoom+0.0008,1.06)':"
        f"d={frames}:"
        "x='iw/2-(iw/zoom/2)':"
        "y='ih/2-(ih/zoom/2)':"
        f"s={width}x{height}:fps={fps},format=yuv420p"
    )

    cmd = [
        "ffmpeg",
        "-y",
        "-loop",
        "1",
        "-i",
        image_path,
        "-i",
        audio_path,
        "-t",
        str(duration),
        "-vf",
        vf,
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "23",
        "-c:a",
        "aac",
        "-ar",
        "44100",
        "-ac",
        "2",
        "-shortest",
        "-movflags",
        "+faststart",
        output_path,
    ]
    _run(cmd)
    return output_path


def mux_audio_to_video(
    video_path: str,
    audio_path: str,
    output_path: str,
    width: int = 720,
    height: int = 1280,
    fps: int = 25,
    fallback_duration_sec: float = 3.0,
) -> str:
    """Mux TTS audio into a Veo-generated video (which has no audio).

    Also normalizes resolution and fps to match the pipeline standard.
    """
    _ensure_ffmpeg()
    duration = get_media_duration(audio_path, fallback=fallback_duration_sec)
    vf = (
        f"scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},fps={fps},format=yuv420p"
    )
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        video_path,
        "-i",
        audio_path,
        "-t",
        str(duration + 0.15),
        "-vf",
        vf,
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "23",
        "-c:a",
        "aac",
        "-ar",
        "44100",
        "-ac",
        "2",
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-shortest",
        "-movflags",
        "+faststart",
        output_path,
    ]
    _run(cmd)
    return output_path


def run_wav2lip(
    wav2lip_dir: str,
    checkpoint_path: str,
    face_video_or_image: str,
    audio_path: str,
    output_path: str,
    pads: tuple[int, int, int, int] = (0, 20, 0, 0),
    resize_factor: int = 2,
) -> str:
    """Run Wav2Lip inference and copy its result to the scene output path."""

    wav2lip_path = Path(wav2lip_dir)
    result_path = wav2lip_path / "results" / "result_voice.mp4"

    cmd = [
        "python",
        "inference.py",
        "--checkpoint_path",
        checkpoint_path,
        "--face",
        face_video_or_image,
        "--audio",
        audio_path,
        "--pads",
        str(pads[0]),
        str(pads[1]),
        str(pads[2]),
        str(pads[3]),
        "--resize_factor",
        str(resize_factor),
    ]

    _run(cmd, cwd=wav2lip_dir)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(result_path, output_path)
    return output_path


def add_text_overlay(input_video: str, output_video: str, text: str) -> str:
    """Add a simple lower-third overlay to a scene clip."""

    _ensure_ffmpeg()
    safe_text = _escape_drawtext(text)
    vf = (
        "drawbox=x=40:y=h-260:w=w-80:h=170:color=black@0.45:t=fill,"
        f"drawtext=text='{safe_text}':fontcolor=white:fontsize=42:"
        "x=(w-text_w)/2:y=h-210:box=0"
    )

    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        input_video,
        "-vf",
        vf,
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "23",
        "-c:a",
        "aac",
        "-ar",
        "44100",
        "-ac",
        "2",
        "-movflags",
        "+faststart",
        output_video,
    ]
    _run(cmd)
    return output_video


def normalize_video(
    input_path: str,
    output_path: str,
    width: int = 720,
    height: int = 1280,
    fps: int = 25,
) -> str:
    """Normalize a video to the pipeline's common concat settings."""

    _ensure_ffmpeg()
    vf = (
        f"scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},fps={fps},format=yuv420p"
    )
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        input_path,
        "-vf",
        vf,
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "23",
        "-c:a",
        "aac",
        "-ar",
        "44100",
        "-ac",
        "2",
        "-movflags",
        "+faststart",
        output_path,
    ]
    _run(cmd)
    return output_path


def concat_scene_clips(scene_video_paths: Sequence[str], output_path: str) -> str:
    """Concatenate rendered scene clips into one final MP4."""

    _ensure_ffmpeg()
    if not scene_video_paths:
        raise ValueError("Cannot concatenate an empty scene list")

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    list_path = output.parent / "concat_list.txt"

    with list_path.open("w", encoding="utf-8") as f:
        for path in scene_video_paths:
            f.write(f"file '{Path(path).resolve().as_posix()}'\n")

    copy_cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(list_path),
        "-c",
        "copy",
        str(output),
    ]

    try:
        _run(copy_cmd)
    except subprocess.CalledProcessError:
        logger.warning("Fast concat failed; retrying with re-encode")
        reencode_cmd = [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(list_path),
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "23",
            "-c:a",
            "aac",
            "-ar",
            "44100",
            "-ac",
            "2",
            "-movflags",
            "+faststart",
            str(output),
        ]
        _run(reencode_cmd)

    return str(output)


class MicroSceneVideoPipeline:
    """Local MVP implementation for the livestream video generator."""

    def __init__(
        self,
        config: MicroScenePipelineConfig,
        public_url_prefix: str = "/outputs",
    ) -> None:
        self._config = config
        self._public_url_prefix = public_url_prefix.rstrip("/")

    def plan_scenes(
        self,
        product_name: str,
        product_description: str,
        brand_style: str,
        script: str,
    ) -> list[SceneChunk]:
        """Create a micro-scene plan. This is rule-based until an LLM planner is wired."""

        return split_script_to_scenes(
            product_name=product_name,
            product_description=product_description,
            brand_style=brand_style,
            script=script,
        )

    def generate(
        self,
        *,
        job_id: str,
        product_name: str,
        product_description: str,
        brand_style: str,
        script: str,
        model_image_path: str,
        product_image_path: str,
        job_dir: str,
        voice: str | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> LivestreamPipelineResult:
        """Render all scenes and concatenate them into the final livestream video."""

        job_path = Path(job_dir)
        job_path.mkdir(parents=True, exist_ok=True)

        self._notify(progress_callback, "planning_scenes", 0.10, "Splitting script")
        scenes = self.plan_scenes(product_name, product_description, brand_style, script)
        if not scenes:
            raise ValueError("Script did not produce any scenes")

        plan_dir = job_path / "plan"
        plan_dir.mkdir(parents=True, exist_ok=True)
        scene_plan_path = plan_dir / "scene_plan.json"
        scene_plan_path.write_text(
            json.dumps([scene.model_dump() for scene in scenes], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        generated_scenes: list[GeneratedScene] = []
        scene_paths: list[str] = []
        total = len(scenes)

        for idx, scene in enumerate(scenes):
            progress = 0.20 + (idx / total) * 0.65
            self._notify(
                progress_callback,
                "generating_scenes",
                progress,
                f"Generating {scene.scene_id}",
            )
            scene_video = self.generate_scene_clip(
                scene=scene,
                job_dir=str(job_path),
                product_name=product_name,
                product_description=product_description,
                brand_style=brand_style,
                model_image_path=model_image_path,
                product_image_path=product_image_path,
                voice=voice or self._config.tts_voice,
            )
            scene_paths.append(scene_video)
            generated_scenes.append(
                GeneratedScene(
                    scene=scene,
                    video_path=scene_video,
                    public_url=f"{self._public_url_prefix}/livestream/{job_id}/scenes/{scene.scene_id}/scene_final.mp4",
                )
            )

        self._notify(progress_callback, "post_processing", 0.90, "Concatenating final video")
        final_dir = job_path / "final"
        final_path = final_dir / "final_video.mp4"
        concat_scene_clips(scene_paths, str(final_path))
        duration_sec = get_media_duration(
            str(final_path), fallback=sum(s.duration_target_sec for s in scenes)
        )

        self._notify(progress_callback, "done", 1.0, "Done")
        return LivestreamPipelineResult(
            final_video_path=str(final_path),
            final_video_url=f"{self._public_url_prefix}/livestream/{job_id}/final/final_video.mp4",
            scene_plan_path=str(scene_plan_path),
            scenes=generated_scenes,
            duration_sec=duration_sec,
        )

    def generate_scene_clip(
        self,
        *,
        scene: SceneChunk,
        job_dir: str,
        model_image_path: str,
        product_image_path: str,
        voice: str,
        product_name: str = "",
        product_description: str = "",
        brand_style: str = "",
    ) -> str:
        """Render one scene into scene_final.mp4.

        Strategy:
          1. If a GenAI client is available, use a Veo-specific prompt and
             uploaded references. Imagen is optional and off by default.
          2. On *any* GenAI failure, transparently fall back to the local
             pipeline (static image + FFmpeg).
        """

        scene_dir = Path(job_dir) / "scenes" / scene.scene_id
        scene_dir.mkdir(parents=True, exist_ok=True)

        audio_path = scene_dir / "audio.wav"
        keyframe_path = scene_dir / "keyframe.png"
        base_video_path = scene_dir / "base.mp4"
        lipsync_video_path = scene_dir / "lipsync.mp4"
        final_scene_path = scene_dir / "scene_final.mp4"

        # ── TTS audio (always local) ──
        generate_tts(
            scene.text,
            str(audio_path),
            voice=voice,
            provider=self._config.tts_provider,
        )

        source_image = (
            product_image_path
            if scene.scene_type in {"PRODUCT_CLOSEUP", "PRODUCT_BEAUTY", "CTA"}
            else model_image_path
        )

        genai = self._config.genai_client
        genai_available = (
            genai is not None and hasattr(genai, "is_available") and genai.is_available()
        )
        render_width, render_height = (
            _dimensions_for_aspect_ratio(self._config.genai_aspect_ratio)
            if genai_available
            else (self._config.output_width, self._config.output_height)
        )

        common_kwargs = {
            "width": render_width,
            "height": render_height,
            "fps": self._config.fps,
            "fallback_duration_sec": scene.duration_target_sec,
        }

        # ── Try GenAI (Veo, optional Imagen) first ──
        used_genai_video = False
        if genai_available:
            try:
                veo_prompt = build_veo_prompt(
                    scene=scene,
                    product_name=product_name,
                    product_description=product_description,
                    brand_style=brand_style,
                    aspect_ratio=self._config.genai_aspect_ratio,
                )
                (scene_dir / "veo_prompt.txt").write_text(veo_prompt, encoding="utf-8")
                veo_reference_path = scene_dir / "veo_reference.png"

                # Step A: prepare the image reference for Veo.
                logger.info("[%s] Preparing Veo reference image", scene.scene_id)
                if self._config.genai_use_imagen:
                    img_result = genai.generate_image(
                        prompt=scene.image_prompt or veo_prompt,
                        output_path=str(keyframe_path),
                        aspect_ratio=self._config.genai_aspect_ratio,
                    )
                    if img_result:
                        shutil.copy2(keyframe_path, veo_reference_path)
                    else:
                        logger.info(
                            "[%s] Imagen returned nothing, using references", scene.scene_id
                        )
                        _make_veo_reference_image(
                            model_image_path,
                            product_image_path,
                            str(veo_reference_path),
                            aspect_ratio=self._config.genai_aspect_ratio,
                        )
                else:
                    _make_veo_reference_image(
                        model_image_path,
                        product_image_path,
                        str(veo_reference_path),
                        aspect_ratio=self._config.genai_aspect_ratio,
                    )

                # Step B: generate video with Veo (image-to-video).
                logger.info("[%s] Trying Veo for scene video", scene.scene_id)
                veo_video_path = scene_dir / "veo_raw.mp4"
                vid_result = genai.generate_video(
                    prompt=veo_prompt,
                    output_path=str(veo_video_path),
                    reference_image_path=str(veo_reference_path),
                    reference_image_paths=[model_image_path, product_image_path],
                    aspect_ratio=self._config.genai_aspect_ratio,
                    duration_seconds=max(5, int(scene.duration_target_sec)),
                    negative_prompt=VEO_SAFE_NEGATIVE_PROMPT,
                    enhance_prompt=self._config.genai_enhance_prompt,
                    generate_audio=False,
                )
                if vid_result:
                    # Veo video has no audio → mux TTS audio in
                    mux_audio_to_video(
                        str(veo_video_path),
                        str(audio_path),
                        str(base_video_path),
                        **common_kwargs,
                    )
                    used_genai_video = True
                    logger.info("[%s] Veo video + TTS muxed", scene.scene_id)
                else:
                    logger.info("[%s] Veo returned nothing, falling back to local", scene.scene_id)

            except Exception:
                logger.exception(
                    "[%s] GenAI pipeline failed, falling back to local", scene.scene_id
                )

        # ── Fallback: local pipeline (static image + FFmpeg) ──
        if not used_genai_video:
            if not keyframe_path.exists():
                shutil.copy2(source_image, keyframe_path)

            if scene.scene_type in {"PRODUCT_CLOSEUP", "PRODUCT_BEAUTY"}:
                make_product_zoom_video(
                    str(keyframe_path),
                    str(audio_path),
                    str(base_video_path),
                    **common_kwargs,
                )
            else:
                make_base_video_from_image(
                    str(keyframe_path),
                    str(audio_path),
                    str(base_video_path),
                    **common_kwargs,
                )

        # ── Wav2Lip for local fallback / non-Veo clips ──
        current_video = str(base_video_path)
        if self._can_run_wav2lip(scene) and not (
            used_genai_video and self._config.genai_skip_wav2lip
        ):
            run_wav2lip(
                wav2lip_dir=self._config.wav2lip_dir,
                checkpoint_path=self._config.wav2lip_checkpoint,
                face_video_or_image=str(base_video_path),
                audio_path=str(audio_path),
                output_path=str(lipsync_video_path),
                pads=self._config.wav2lip_pads,
                resize_factor=self._config.wav2lip_resize_factor,
            )
            current_video = str(lipsync_video_path)

        # ── Overlay text ──
        if scene.overlay_text:
            try:
                add_text_overlay(current_video, str(final_scene_path), scene.overlay_text)
            except subprocess.CalledProcessError:
                logger.exception(
                    "Failed to add overlay for %s; using clip without overlay", scene.scene_id
                )
                shutil.copy2(current_video, final_scene_path)
        else:
            shutil.copy2(current_video, final_scene_path)

        return str(final_scene_path)

    def _can_run_wav2lip(self, scene: SceneChunk) -> bool:
        if not self._config.enable_wav2lip:
            return False
        if not scene.use_lipsync or not should_lipsync(scene.scene_type):
            return False

        wav2lip_dir = Path(self._config.wav2lip_dir)
        checkpoint = Path(self._config.wav2lip_checkpoint)
        inference_file = wav2lip_dir / "inference.py"
        if not wav2lip_dir.exists() or not checkpoint.exists() or not inference_file.exists():
            logger.warning("Wav2Lip is enabled but files are missing; skipping lip-sync")
            return False
        return True

    @staticmethod
    def _notify(
        callback: ProgressCallback | None,
        status: str,
        progress: float,
        current_step: str,
    ) -> None:
        if callback:
            callback(status, progress, current_step)


def _ensure_ffmpeg() -> None:
    if _ffmpeg_executable() is None:
        raise RuntimeError("ffmpeg is required for livestream video generation")


def _run(cmd: Sequence[str], cwd: str | None = None) -> subprocess.CompletedProcess[str]:
    executable_cmd = list(cmd)
    if executable_cmd and executable_cmd[0] == "ffmpeg":
        ffmpeg = _ffmpeg_executable()
        if ffmpeg:
            executable_cmd[0] = ffmpeg
    logger.debug("Running command: %s", " ".join(executable_cmd))
    return subprocess.run(executable_cmd, cwd=cwd, check=True, text=True, capture_output=True)


def _ffmpeg_executable() -> str | None:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        return ffmpeg
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def _escape_drawtext(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
        .replace(":", "\\:")
        .replace("'", "\\'")
        .replace("%", "\\%")
        .replace("\n", " ")
    )


def _strip_accents(text: str) -> str:
    normalized = unicodedata.normalize("NFD", text)
    stripped = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    return stripped.replace("\u0111", "d").replace("\u0110", "D")


def scene_plan_to_dicts(scenes: Iterable[SceneChunk]) -> list[dict]:
    """Small helper for API responses and tests."""

    return [scene.model_dump() for scene in scenes]
