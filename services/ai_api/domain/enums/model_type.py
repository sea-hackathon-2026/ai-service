"""Model type enum - Identifies which AI model pipeline to use."""

from enum import StrEnum


class ModelType(StrEnum):
    """Types of AI model pipelines available in the service."""

    VIDEO_GEN = "video_gen"  # Video generation (text/image to video)
    LIVESTREAM_VIDEO = "livestream_video"  # Script/images to micro-scene video
    TTS = "tts"  # Text-to-Speech synthesis
