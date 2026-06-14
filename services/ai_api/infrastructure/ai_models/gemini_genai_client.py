"""Google GenAI client for Imagen 3 (image) and Veo 2 (video) generation.

This module wraps the ``google-genai`` SDK to provide a simple, fail-safe
interface used by :class:`MicroSceneVideoPipeline`.  Every public method
returns ``None`` on failure so the pipeline can transparently fall back
to the local FFmpeg-based approach.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

logger = logging.getLogger(__name__)

# Lazy-loaded SDK client
_genai_module = None


def _get_genai():
    """Lazy-import google.genai to avoid hard dependency at module load."""
    global _genai_module
    if _genai_module is None:
        try:
            from google import genai  # type: ignore[attr-defined]

            _genai_module = genai
        except ImportError as exc:
            raise ImportError(
                "google-genai is not installed. Run: pip install google-genai>=1.0.0"
            ) from exc
    return _genai_module


class GeminiGenAIClient:
    """Wrapper over google-genai SDK for image + video generation.

    All methods are *best-effort*: they return ``None`` on any SDK or
    network error so the caller can fall back to a local pipeline.
    """

    def __init__(
        self,
        api_key: str,
        imagen_model: str = "imagen-3.0-generate-002",
        veo_model: str = "veo-2.0-generate-001",
    ) -> None:
        self._api_key = api_key
        self._imagen_model = imagen_model
        self._veo_model = veo_model
        self._client = None
        self._available: bool | None = None  # cached after first check

    # ── Public API ──────────────────────────────────────────────────────

    def is_available(self) -> bool:
        """Return True if the API key is set and the SDK can connect.

        Result is cached after the first successful / failed probe.
        """
        if not self._api_key:
            return False

        if self._available is not None:
            return self._available

        try:
            client = self._get_client()
            # Quick probe: list models to verify key is valid
            # This is cheap and validates auth without generating content
            _ = client.models.list(config={"page_size": 1})
            self._available = True
            logger.info("GenAI API key validated — Imagen 3 + Veo 2 available")
        except Exception as exc:
            self._available = False
            logger.warning("GenAI API key check failed: %s — using local pipeline", exc)

        return self._available

    def generate_image(
        self,
        prompt: str,
        output_path: str,
        *,
        aspect_ratio: str = "9:16",
        number_of_images: int = 1,
    ) -> str | None:
        """Generate an image with Imagen 3 and save to *output_path*.

        Returns the saved file path on success, ``None`` on any error.
        """
        try:
            client = self._get_client()
            genai = _get_genai()

            logger.info(
                "Imagen 3: generating image (model=%s, aspect=%s)…",
                self._imagen_model,
                aspect_ratio,
            )

            response = client.models.generate_images(
                model=self._imagen_model,
                prompt=prompt,
                config=genai.types.GenerateImagesConfig(
                    number_of_images=number_of_images,
                    aspect_ratio=aspect_ratio,
                    safety_filter_level="BLOCK_ONLY_HIGH",
                ),
            )

            if not response.generated_images:
                logger.warning("Imagen 3 returned no images")
                return None

            image = response.generated_images[0].image
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            image.save(output_path)
            logger.info("Imagen 3: saved keyframe → %s", output_path)
            return output_path

        except Exception as exc:
            logger.warning("Imagen 3 generation failed: %s", exc)
            return None

    def generate_video(
        self,
        prompt: str,
        output_path: str,
        *,
        reference_image_path: str | None = None,
        reference_image_paths: list[str] | None = None,
        aspect_ratio: str = "16:9",
        duration_seconds: int = 5,
        negative_prompt: str | None = None,
        enhance_prompt: bool = True,
        generate_audio: bool = False,
        poll_interval: int = 10,
        max_wait: int = 300,
    ) -> str | None:
        """Generate a video with Veo 2 and save to *output_path*.

        If *reference_image_path* is given, the video is conditioned on
        that image (image-to-video). If *reference_image_paths* is given
        with a Veo 3.1 model, up to three images are passed as asset
        references. Otherwise the first valid image is used as the source
        image for image-to-video. If no image is available, the request is
        text-to-video only.

        Returns the saved file path on success, ``None`` on any error.
        """
        try:
            client = self._get_client()
            genai = _get_genai()

            logger.info(
                "Veo 2: generating video (model=%s, %ds, aspect=%s)…",
                self._veo_model,
                duration_seconds,
                aspect_ratio,
            )

            # Build the generation config
            gen_config = {
                "aspect_ratio": aspect_ratio,
                "number_of_videos": 1,
                "duration_seconds": duration_seconds,
                "enhance_prompt": enhance_prompt,
            }
            if generate_audio:
                gen_config["generate_audio"] = True
            if negative_prompt:
                gen_config["negative_prompt"] = negative_prompt

            # Build the request
            request_kwargs = {
                "model": self._veo_model,
                "prompt": prompt,
            }

            valid_reference_paths = [
                str(path) for path in (reference_image_paths or []) if path and Path(path).exists()
            ]
            if (
                not valid_reference_paths
                and reference_image_path
                and Path(reference_image_path).exists()
            ):
                valid_reference_paths = [reference_image_path]

            supports_multi_reference = "3.1" in self._veo_model
            if supports_multi_reference and valid_reference_paths:
                gen_config["reference_images"] = [
                    genai.types.VideoGenerationReferenceImage(
                        image=genai.types.Image.from_file(location=path),
                        reference_type="asset",
                    )
                    for path in valid_reference_paths[:3]
                ]
            elif valid_reference_paths:
                request_kwargs["image"] = genai.types.Image.from_file(
                    location=valid_reference_paths[0]
                )

            request_kwargs["config"] = genai.types.GenerateVideosConfig(**gen_config)

            # Start async generation
            operation = client.models.generate_videos(**request_kwargs)

            # Poll until done
            start = time.time()
            while not operation.done:
                if time.time() - start > max_wait:
                    logger.warning("Veo 2: timed out after %ds", max_wait)
                    return None
                elapsed = int(time.time() - start)
                if elapsed % 30 == 0 and elapsed > 0:
                    logger.info("Veo 2: still generating… %ds elapsed", elapsed)
                time.sleep(poll_interval)
                operation = client.operations.get(operation)

            # Extract generated video
            if not operation.response or not operation.response.generated_videos:
                logger.warning("Veo 2 returned no videos")
                return None

            video = operation.response.generated_videos[0].video
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            try:
                client.files.download(file=video)
            except Exception:
                logger.debug("Veo video download helper unavailable; using direct save")
            video.save(output_path)
            logger.info(
                "Veo 2: saved video → %s (%.1fs)",
                output_path,
                time.time() - start,
            )
            return output_path

        except Exception as exc:
            logger.warning("Veo 2 generation failed: %s", exc)
            return None

    # ── Internal ────────────────────────────────────────────────────────

    def _get_client(self):
        """Lazy-create the GenAI client."""
        if self._client is None:
            genai = _get_genai()
            self._client = genai.Client(api_key=self._api_key)
        return self._client
