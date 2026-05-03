"""Model type enum - Identifies which AI model pipeline to use."""

from enum import Enum


class ModelType(str, Enum):
    """Types of AI model pipelines available in the service."""

    VIDEO_GEN = "video_gen"    # Video generation (text/image → video)
    TTS = "tts"                # Text-to-Speech synthesis
