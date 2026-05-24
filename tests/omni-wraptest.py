"""Local OmniVoice Vietnamese batch TTS for Cocoon livecommerce scenes.

Default input:
    data/cocoon_livecommerce_script_v2.json

Recommended one-speaker run:
    python tests/omni-wraptest.py --ref-audio data/voices/host_ref.wav

Quick smoke without loading OmniVoice:
    python tests/omni-wraptest.py --dry-run --max-scenes 3
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import random
import re
import sys
import traceback
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = PROJECT_ROOT / "data" / "cocoon_livecommerce_script_v2.json"
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "data" / "outputs" / "omni_tts"
DEFAULT_MODEL_ID = "k2-fsa/OmniVoice"
DEFAULT_SAMPLE_RATE = 24000
DEFAULT_LANGUAGE_ID = "vi"

VALID_ENGLISH_INSTRUCT_ITEMS = {
    "american accent",
    "australian accent",
    "british accent",
    "canadian accent",
    "child",
    "chinese accent",
    "elderly",
    "female",
    "high pitch",
    "indian accent",
    "japanese accent",
    "korean accent",
    "low pitch",
    "male",
    "middle-aged",
    "moderate pitch",
    "portuguese accent",
    "russian accent",
    "teenager",
    "very high pitch",
    "very low pitch",
    "whisper",
    "young adult",
}

INSTRUCT_ALIASES = {
    "adult": "young adult",
    "medium pitch": "moderate pitch",
    "normal pitch": "moderate pitch",
}


@dataclass(frozen=True)
class PreparedScene:
    scene: dict[str, Any]
    scene_id: str
    voiceover: str
    audio_filename: str
    text_filename: str


def main() -> int:
    args = parse_args()
    set_deterministic_seed(args.seed)

    data = load_script(args.input)
    job_id = safe_filename(data.get("job_id") or "cocoon_omni_tts")
    scenes = prepare_scenes(
        data.get("scenes", []),
        start_from_scene_id=args.start_scene,
        max_scenes=args.max_scenes,
    )

    if not scenes:
        raise SystemExit("No valid scenes with voiceover found.")

    output_dir = args.output_root / job_id
    audio_dir = output_dir / "audio"
    text_dir = output_dir / "text"
    audio_dir.mkdir(parents=True, exist_ok=True)
    text_dir.mkdir(parents=True, exist_ok=True)

    safe_instruct, dropped = sanitize_instruct(args.instruct)
    validate_voice_args(args, safe_instruct)

    print("job_id:", job_id)
    print("input:", args.input)
    print("output:", output_dir)
    print("scenes:", len(scenes))
    print("voice_mode:", args.voice_mode)
    print("language_id:", args.language_id)
    if args.voice_mode == "clone":
        print("ref_audio:", args.ref_audio)
    if args.voice_mode == "design":
        print("instruct:", safe_instruct)
        if dropped:
            print("dropped unsupported instruct items:", ", ".join(dropped))

    write_voice_profile(
        output_dir / "voice_profile.json",
        args=args,
        safe_instruct=safe_instruct,
        dropped_instruct=dropped,
    )

    if args.dry_run:
        write_text_files(scenes, text_dir)
        write_manifest(
            output_dir / "tts_manifest.csv",
            build_dry_run_rows(scenes, audio_dir, text_dir, args, safe_instruct),
        )
        print("dry-run ok; no audio generated")
        return 0

    model = load_omnivoice_model(args)
    manifest_rows, errors = generate_audio_batch(
        model=model,
        scenes=scenes,
        audio_dir=audio_dir,
        text_dir=text_dir,
        args=args,
        safe_instruct=safe_instruct,
    )

    manifest_path = output_dir / "tts_manifest.csv"
    errors_path = output_dir / "tts_errors.json"
    write_manifest(manifest_path, manifest_rows)
    errors_path.write_text(json.dumps(errors, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.zip:
        zip_path = zip_outputs(output_dir)
        print("zip:", zip_path)

    ok_count = sum(1 for row in manifest_rows if row.get("status") == "ok")
    print("done")
    print("ok:", ok_count)
    print("errors:", len(errors))
    print("manifest:", manifest_path)
    return 1 if errors else 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate one consistent OmniVoice Vietnamese TTS wav per scene.",
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--model-id", default=DEFAULT_MODEL_ID)
    parser.add_argument("--language-id", default=DEFAULT_LANGUAGE_ID)
    parser.add_argument("--sample-rate", type=int, default=DEFAULT_SAMPLE_RATE)
    parser.add_argument("--voice-mode", choices=["clone", "design"], default="clone")
    parser.add_argument("--ref-audio", type=Path, default=None)
    parser.add_argument("--ref-text", default=None)
    parser.add_argument(
        "--instruct",
        default="female, young adult, moderate pitch",
        help="Only used with --voice-mode design. Must use OmniVoice allow-list items.",
    )
    parser.add_argument("--num-step", type=int, default=32)
    parser.add_argument("--speed", type=float, default=1.0)
    parser.add_argument("--duration", type=float, default=None)
    parser.add_argument("--max-scenes", type=int, default=None)
    parser.add_argument("--start-scene", default=None)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--device", choices=["auto", "cuda", "cpu"], default="auto")
    parser.add_argument("--no-asr", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--zip", action="store_true")
    return parser.parse_args()


def load_script(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Input JSON not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def prepare_scenes(
    scenes: list[dict[str, Any]],
    *,
    start_from_scene_id: str | None,
    max_scenes: int | None,
) -> list[PreparedScene]:
    prepared: list[PreparedScene] = []
    start_enabled = start_from_scene_id is None

    for scene in scenes:
        scene_id = safe_filename(scene.get("scene_id", "scene"))
        if start_from_scene_id and scene_id == start_from_scene_id:
            start_enabled = True
        if not start_enabled:
            continue

        text = normalize_text(scene.get("voiceover", ""))
        if not text:
            continue

        prepared.append(
            PreparedScene(
                scene=scene,
                scene_id=scene_id,
                voiceover=text,
                audio_filename=f"{scene_id}.wav",
                text_filename=f"{scene_id}.txt",
            )
        )

    if max_scenes is not None:
        prepared = prepared[:max_scenes]

    return prepared


def validate_voice_args(args: argparse.Namespace, safe_instruct: str | None) -> None:
    if args.dry_run:
        return

    if args.voice_mode == "clone":
        if args.ref_audio is None:
            raise SystemExit(
                "Strict one-speaker mode requires --ref-audio. "
                "Use a 3-10s Vietnamese host sample wav/mp3/flac."
            )
        if not args.ref_audio.exists():
            raise FileNotFoundError(f"Reference audio not found: {args.ref_audio}")

    if args.voice_mode == "design" and not safe_instruct:
        raise SystemExit("Design mode needs at least one valid OmniVoice instruct item.")


def load_omnivoice_model(args: argparse.Namespace):
    try:
        import torch
        from omnivoice import OmniVoice
    except ImportError as exc:
        raise SystemExit(
            "Missing OmniVoice dependencies. Install locally with:\n"
            "  pip install omnivoice soundfile torch tqdm"
        ) from exc

    if args.device == "cuda" or (args.device == "auto" and torch.cuda.is_available()):
        device_map = "cuda:0"
        dtype = torch.float16
    else:
        device_map = "cpu"
        dtype = torch.float32

    print("device_map:", device_map)
    print("dtype:", dtype)
    return OmniVoice.from_pretrained(
        args.model_id,
        device_map=device_map,
        dtype=dtype,
        load_asr=not args.no_asr,
    )


def generate_audio_batch(
    *,
    model: Any,
    scenes: list[PreparedScene],
    audio_dir: Path,
    text_dir: Path,
    args: argparse.Namespace,
    safe_instruct: str | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    try:
        import soundfile as sf
    except ImportError as exc:
        raise SystemExit("Missing soundfile. Install with: pip install soundfile") from exc

    rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    iterator = progress_iter(scenes, "Generating OmniVoice TTS")
    for item in iterator:
        audio_path = audio_dir / item.audio_filename
        text_path = text_dir / item.text_filename
        text_path.write_text(item.voiceover, encoding="utf-8")

        if args.resume and audio_path.exists():
            rows.append(manifest_row(item, audio_path, text_path, args, safe_instruct, "skipped"))
            print("SKIP", item.scene_id, "exists")
            continue

        try:
            audio = call_omnivoice_generate(
                model=model,
                text=item.voiceover,
                args=args,
                safe_instruct=safe_instruct,
            )
            wav, sample_rate = unpack_audio(audio, fallback_sample_rate=args.sample_rate)
            sf.write(audio_path, wav, sample_rate)
            rows.append(manifest_row(item, audio_path, text_path, args, safe_instruct, "ok"))
            print("OK", item.scene_id, "->", audio_path.name)
        except Exception as exc:
            errors.append(
                {
                    "scene_id": item.scene_id,
                    "audio_filename": str(audio_path),
                    "error": repr(exc),
                    "traceback": traceback.format_exc(),
                }
            )
            row = manifest_row(item, audio_path, text_path, args, safe_instruct, "error")
            row["error"] = repr(exc)
            rows.append(row)
            print("ERROR", item.scene_id, repr(exc))

    return rows, errors


def call_omnivoice_generate(
    *,
    model: Any,
    text: str,
    args: argparse.Namespace,
    safe_instruct: str | None,
) -> Any:
    kwargs: dict[str, Any] = {
        "text": text,
        "language_id": args.language_id,
        "num_step": args.num_step,
        "speed": args.speed,
    }

    if args.duration is not None:
        kwargs["duration"] = args.duration

    if args.voice_mode == "clone":
        kwargs["ref_audio"] = str(args.ref_audio)
        if args.ref_text:
            kwargs["ref_text"] = args.ref_text
    elif args.voice_mode == "design" and safe_instruct:
        kwargs["instruct"] = safe_instruct

    try:
        return model.generate(**kwargs)
    except TypeError as exc:
        msg = str(exc)
        fallback_keys = ("language_id", "num_step", "speed", "duration")
        if not any(key in msg for key in fallback_keys) and "unexpected keyword" not in msg:
            raise

        print("Fallback: installed OmniVoice does not accept all generation kwargs.")
        minimal_kwargs: dict[str, Any] = {"text": text}
        if args.voice_mode == "clone":
            minimal_kwargs["ref_audio"] = str(args.ref_audio)
            if args.ref_text:
                minimal_kwargs["ref_text"] = args.ref_text
        elif args.voice_mode == "design" and safe_instruct:
            minimal_kwargs["instruct"] = safe_instruct
        return model.generate(**minimal_kwargs)


def unpack_audio(audio: Any, *, fallback_sample_rate: int) -> tuple[Any, int]:
    sample_rate = fallback_sample_rate
    wav = audio

    if isinstance(audio, dict):
        wav = audio.get("audio") or audio.get("wav") or audio.get("waveform")
        sample_rate = int(audio.get("sample_rate") or audio.get("sampling_rate") or sample_rate)
    if isinstance(audio, tuple):
        wav = audio[0]
        if len(audio) > 1 and isinstance(audio[1], int):
            sample_rate = audio[1]
    elif isinstance(audio, list):
        wav = audio[0]

    if hasattr(wav, "detach"):
        wav = wav.detach().cpu().float().numpy()

    return wav, sample_rate


def manifest_row(
    item: PreparedScene,
    audio_path: Path,
    text_path: Path,
    args: argparse.Namespace,
    safe_instruct: str | None,
    status: str,
) -> dict[str, Any]:
    return {
        "scene_id": item.scene_id,
        "clip_id": item.scene.get("clip_id"),
        "order": item.scene.get("order"),
        "scene_type": item.scene.get("scene_type"),
        "duration_target_sec": item.scene.get("duration_target_sec"),
        "language_id": args.language_id,
        "voice_mode": args.voice_mode,
        "ref_audio": str(args.ref_audio) if args.voice_mode == "clone" else "",
        "instruct": safe_instruct if args.voice_mode == "design" else "",
        "audio_filename": str(audio_path),
        "text_filename": str(text_path),
        "text": item.voiceover,
        "status": status,
    }


def build_dry_run_rows(
    scenes: list[PreparedScene],
    audio_dir: Path,
    text_dir: Path,
    args: argparse.Namespace,
    safe_instruct: str | None,
) -> list[dict[str, Any]]:
    return [
        manifest_row(
            item,
            audio_dir / item.audio_filename,
            text_dir / item.text_filename,
            args,
            safe_instruct,
            "dry_run",
        )
        for item in scenes
    ]


def write_text_files(scenes: list[PreparedScene], text_dir: Path) -> None:
    for item in scenes:
        (text_dir / item.text_filename).write_text(item.voiceover, encoding="utf-8")


def write_manifest(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_voice_profile(
    path: Path,
    *,
    args: argparse.Namespace,
    safe_instruct: str | None,
    dropped_instruct: list[str],
) -> None:
    payload = {
        "policy": "single_speaker",
        "voice_mode": args.voice_mode,
        "language_id": args.language_id,
        "model_id": args.model_id,
        "ref_audio": str(args.ref_audio) if args.ref_audio else None,
        "ref_text": args.ref_text,
        "instruct": safe_instruct if args.voice_mode == "design" else None,
        "dropped_instruct": dropped_instruct,
        "seed": args.seed,
        "num_step": args.num_step,
        "speed": args.speed,
        "duration": args.duration,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def zip_outputs(output_dir: Path) -> Path:
    zip_path = output_dir.with_suffix(".zip")
    if zip_path.exists():
        zip_path.unlink()

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in output_dir.rglob("*"):
            if path.is_file():
                zf.write(path, arcname=str(path.relative_to(output_dir)))
    return zip_path


def sanitize_instruct(instruct: str) -> tuple[str | None, list[str]]:
    raw_items = [item.strip().lower() for item in instruct.split(",") if item.strip()]
    kept: list[str] = []
    dropped: list[str] = []

    for item in raw_items:
        mapped = INSTRUCT_ALIASES.get(item, item)
        if mapped in VALID_ENGLISH_INSTRUCT_ITEMS:
            if mapped not in kept:
                kept.append(mapped)
        else:
            dropped.append(item)

    return ", ".join(kept) if kept else None, dropped


def safe_filename(name: object) -> str:
    value = str(name or "scene").strip()
    value = re.sub(r"[^a-zA-Z0-9_.-]+", "_", value)
    return value or "scene"


def normalize_text(text: object) -> str:
    value = str(text or "").strip()
    return re.sub(r"\s+", " ", value)


def set_deterministic_seed(seed: int) -> None:
    os.environ.setdefault("PYTHONHASHSEED", str(seed))
    random.seed(seed)
    try:
        import torch

        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)
    except ImportError:
        pass


def progress_iter(items: list[PreparedScene], desc: str):
    try:
        from tqdm import tqdm

        return tqdm(items, desc=desc)
    except ImportError:
        print(desc)
        return items


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("Interrupted", file=sys.stderr)
        raise SystemExit(130)
