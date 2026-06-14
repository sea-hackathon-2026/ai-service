"""Unit tests for the micro-scene livestream pipeline helpers."""

from __future__ import annotations

from services.ai_api.domain.entities.scene import SceneChunk
from services.ai_api.infrastructure.ai_models.micro_scene_pipeline import (
    _dimensions_for_aspect_ratio,
    build_veo_prompt,
)


def test_build_veo_prompt_keeps_vietnamese_speech_and_16_9() -> None:
    scene = SceneChunk(
        scene_id="S001",
        order=1,
        scene_type="HOST_TALK",
        text="Dạ em chào cả nhà, hôm nay mình có deal tốt nha.",
        visual_goal="Host smiles and opens the livestream.",
        emotion="friendly",
        camera="medium shot",
        host_action="small nod and natural blinking",
        product_action="product visible on table",
        duration_target_sec=3,
        negative_prompt="distorted face",
        motion_prompt="",
        use_lipsync=True,
    )

    prompt = build_veo_prompt(
        scene=scene,
        product_name="Cocoon",
        product_description="Vietnamese vegan cosmetics",
        brand_style="clean ecommerce livestream",
    )

    assert prompt.startswith("9:16 ecommerce livestream video")
    assert "Dạ em chào cả nhà" in prompt
    assert "Keep the spoken-language feeling Vietnamese" in prompt
    assert "9:16 vertical" not in prompt


def test_dimensions_for_aspect_ratio_defaults_to_16_9_canvas() -> None:
    assert _dimensions_for_aspect_ratio("16:9") == (1280, 720)
    assert _dimensions_for_aspect_ratio("9:16") == (720, 1280)
    assert _dimensions_for_aspect_ratio("bad-value") == (1280, 720)
