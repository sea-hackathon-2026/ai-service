"""
Wrap Test - Gemini VEO Pipeline Test via Browser Automation.

Full pipeline:
  input.json + knowledge_base.json
  → LLM generates master_script.json (extended scenes for longer video)
  → Build VEO prompt queue per scene
  → Playwright opens Chrome → auto-upload images + paste prompt → wait → download
  → Collect all videos + screenshots → return result summary

Usage:
  python tests/wraptest.py                          # Full pipeline
  python tests/wraptest.py --step generate-script   # Only generate master script
  python tests/wraptest.py --step build-prompts     # Only build prompt queue
  python tests/wraptest.py --step run-veo           # Only run browser automation
  python tests/wraptest.py --step full              # Full pipeline (default)

Config:
  All paths and settings are loaded from .env at project root.
  Override with environment variables or by editing .env directly.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import shutil
import sys
import time
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any

# ─── Resolve project root ────────────────────────────────────────────────────
# Works regardless of where the script is invoked from.
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

# Add project root to sys.path so we can import app modules if needed
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# ─── Load .env ────────────────────────────────────────────────────────────────
try:
    from dotenv import load_dotenv
except ImportError:
    # Minimal fallback: parse .env manually
    def load_dotenv(dotenv_path=None, **kwargs):
        env_file = Path(dotenv_path) if dotenv_path else PROJECT_ROOT / ".env"
        if not env_file.exists():
            return
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key, value = key.strip(), value.strip()
            if not os.environ.get(key):
                os.environ[key] = value

load_dotenv(dotenv_path=str(PROJECT_ROOT / ".env"))

# ─── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("wraptest")


# =============================================================================
# 1. CONFIG LOADER
# =============================================================================

class WrapTestConfig:
    """Centralized config loaded from .env + input.json.
    
    All paths are resolved relative to PROJECT_ROOT.
    """

    def __init__(self) -> None:
        # ── VEO Browser Automation ──
        self.gemini_veo_url: str = os.getenv(
            "GEMINI_VEO_URL", "https://gemini.google.com/"
        ).strip() or "https://gemini.google.com/"
        self.gemini_video_tool_label: str = os.getenv(
            "GEMINI_VIDEO_TOOL_LABEL", "Tạo video"
        )
        self.gemini_aspect_ratio: str = os.getenv("GEMINI_ASPECT_RATIO", "9:16")
        self.gemini_aspect_label: str = os.getenv(
            "GEMINI_ASPECT_LABEL", "Dọc (9:16)"
        )
        self.chrome_cdp_url: str = os.getenv("CHROME_CDP_URL", "").strip()
        self.chrome_user_data_dir: str = os.getenv("CHROME_USER_DATA_DIR", "")
        self.chrome_executable_path: str = os.getenv("CHROME_EXECUTABLE_PATH", "")
        self.veo_download_dir: Path = self._resolve(
            os.getenv("VEO_DOWNLOAD_DIR", "./data/outputs/veo_downloads")
        )
        self.veo_timeout_sec: int = int(os.getenv("VEO_TIMEOUT_SEC", "600"))
        self.veo_scene_limit: int = int(os.getenv("VEO_SCENE_LIMIT", "0"))
        self.screenshot_dir: Path = self._resolve(
            os.getenv("VEO_SCREENSHOT_DIR", "./data/outputs/screenshots")
        )

        # ── LLM Provider ──
        self.llm_provider: str = os.getenv("LLM_PROVIDER", "gemini").lower()
        self.gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
        self.openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
        self.llm_model_name: str = os.getenv("LLM_MODEL_NAME", "gemini-2.0-flash")
        self.llm_temperature: float = float(os.getenv("LLM_TEMPERATURE", "0.7"))

        # ── Pipeline Input ──
        self.input_path: Path = self._resolve(
            os.getenv("PIPELINE_INPUT_PATH", "./data/inputs/input.json")
        )

        # ── Output dirs ──
        self.output_dir: Path = self._resolve("./data/outputs/wraptest")
        self.master_script_path: Path = self.output_dir / "master_script.json"
        self.prompt_queue_path: Path = self.output_dir / "external_prompt_queue.json"

        # ── Ensure directories ──
        self.veo_download_dir.mkdir(parents=True, exist_ok=True)
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _resolve(self, path_str: str) -> Path:
        """Resolve path relative to PROJECT_ROOT."""
        p = Path(path_str)
        if p.is_absolute():
            return p
        return (PROJECT_ROOT / p).resolve()

    def load_input(self) -> dict[str, Any]:
        """Load and resolve paths in input.json."""
        if not self.input_path.exists():
            raise FileNotFoundError(f"Input file not found: {self.input_path}")

        data = json.loads(self.input_path.read_text(encoding="utf-8"))

        # Resolve relative image paths
        for key in ("model_image", "product_image", "knowledge_base_path"):
            if key in data and data[key]:
                resolved = self._resolve(data[key])
                data[f"{key}_resolved"] = str(resolved)
                if not resolved.exists():
                    logger.warning("File not found: %s → %s", key, resolved)

        return data

    def load_knowledge_base(self, kb_path: str | None = None) -> dict[str, Any]:
        """Load knowledge_base.json."""
        if kb_path:
            path = Path(kb_path) if Path(kb_path).is_absolute() else self._resolve(kb_path)
        else:
            input_data = self.load_input()
            path = Path(input_data.get("knowledge_base_path_resolved", ""))

        if not path.exists():
            raise FileNotFoundError(f"Knowledge base not found: {path}")

        return json.loads(path.read_text(encoding="utf-8"))

    def summary(self) -> str:
        """Print config summary."""
        return (
            f"=== WrapTest Config ===\n"
            f"  VEO URL:        {self.gemini_veo_url}\n"
            f"  Chrome CDP:     {self.chrome_cdp_url or '(disabled)'}\n"
            f"  Video tool:     {self.gemini_video_tool_label}\n"
            f"  Aspect ratio:   {self.gemini_aspect_label}\n"
            f"  LLM Provider:   {self.llm_provider}\n"
            f"  LLM Model:      {self.llm_model_name}\n"
            f"  Input:          {self.input_path}\n"
            f"  Output:         {self.output_dir}\n"
            f"  Downloads:      {self.veo_download_dir}\n"
            f"  Screenshots:    {self.screenshot_dir}\n"
            f"  VEO Timeout:    {self.veo_timeout_sec}s\n"
            f"  Scene limit:    {self.veo_scene_limit or 'all'}\n"
            f"========================"
        )


# =============================================================================
# 2. LLM SCRIPT GENERATOR
# =============================================================================

# Prompt template from docs/wrap-test.md Section 3
SCRIPT_GENERATION_PROMPT = """
You are an AI livestream video director and ecommerce script planner.

TASK:
Generate a complete livestream video script JSON from the provided model description, product knowledge base, and content goal.

The output will be used to generate short AI videos with Gemini/Veo, then stitched into a full livestream loop.

STRICT RULES:
1. Output valid JSON only. No markdown, no explanation, no code fences.
2. Do not generate one long script. Split into micro-scenes.
3. Each scene must be 4–6 seconds.
4. Each voiceover line must be short enough for one video segment.
5. Every scene must have one clear visual purpose only.
6. Keep visual consistency across all scenes.
7. Use the exact same base model description in every video prompt.
8. Use low motion only: blink, small nod, small hand movement.
9. Avoid actions that start in one scene and end in another.
10. Product label and exact text should not be hallucinated by the video model. If exact price/name is needed, mark it as overlay_text.
11. Create enough scenes for:
   - opening (1-2 scenes)
   - brand trust (1-2 scenes)
   - product introduction for EACH product (2-3 scenes per product)
   - product benefit (1-2 scenes per product)
   - pricing/promotion (1-2 scenes)
   - comment reading loop (1-2 scenes)
   - FAQ answer loop (2-3 scenes)
   - CTA loop (1-2 scenes)
12. For product facts, only use information from the knowledge base.
13. Generate AT LEAST 12 scenes to create a longer, more complete video.

INPUT:
Model base description:
{model_base_description}

Product knowledge base:
{knowledge_base_json}

Content goal:
{content_goal}

OUTPUT JSON FORMAT:
{{
  "job_id": "cocoon_test_001",
  "base_visual_lock": "<model description used across all scenes>",
  "global_rules": {{
    "aspect_ratio": "9:16",
    "camera": "medium close-up, fixed camera, direct front view",
    "motion_level": "low",
    "scene_duration_sec": 5,
    "transition": "0.2s crossfade",
    "consistency_rule": "All scenes must use the same face, hairstyle, outfit, background, lighting, camera angle, and body framing."
  }},
  "playlist": [
    {{
      "clip_id": "A_MAIN_SALES_LOOP",
      "purpose": "...",
      "scenes": ["S001", "S002"]
    }}
  ],
  "scenes": [
    {{
      "scene_id": "S001",
      "clip_id": "A_MAIN_SALES_LOOP",
      "order": 1,
      "scene_type": "HOST_TALK | PRODUCT_CLOSEUP | HOST_PHONE_READING | FAQ_ANSWER | CTA",
      "duration_target_sec": 5,
      "voiceover": "Vietnamese voiceover line",
      "visual_goal": "what viewer sees",
      "overlay_text": "optional text overlay or null",
      "start_anchor": "first frame state",
      "end_anchor": "last frame state",
      "needs_lipsync": true,
      "needs_product_overlay": false
    }}
  ]
}}
""".strip()


VEO_PROMPT_TEMPLATE = """
Vertical 9:16 ecommerce livestream video, target duration {duration_target_sec} seconds.

[VISUAL LOCK]
{base_visual_lock}

[CONSISTENCY RULES]
Use the same face identity, same hairstyle, same outfit, same background, same lighting, same camera angle, and same medium close-up framing across all scenes.
Do not change the model's facial structure, age, outfit, hairstyle, or background.
Camera is fixed. No zoom unless explicitly requested.
Motion level is low.

[SCENE GOAL]
{visual_goal}

[START FRAME]
{start_anchor}

[END FRAME]
{end_anchor}

[MOTION]
Subtle movement only: natural blinking, small head nod, calm breathing, tiny hand movement.
No large gesture. No body turn. No scene transition.
The first and last frames should be visually similar so the clip can be looped or stitched.

[PRODUCT RULES]
Use the uploaded product reference image only as visual reference.
Do not invent new product label text.
Do not distort product packaging.
If exact price or product text is needed, leave space for later overlay.

[NEGATIVE]
distorted face, different person, changed hairstyle, changed outfit, warped product, fake logo, unreadable text, extra fingers, broken hands, heavy camera movement, cinematic cut, scene change
""".strip()


def call_llm(prompt: str, config: WrapTestConfig) -> str:
    """Call LLM with flexible provider switching.
    
    Supports: gemini, openai, local (fallback).
    """
    provider = config.llm_provider

    if provider == "gemini":
        return _call_gemini(prompt, config)
    elif provider == "openai":
        return _call_openai(prompt, config)
    elif provider == "local":
        return _call_local_fallback(prompt, config)
    else:
        logger.warning("Unknown LLM provider '%s', trying gemini → openai → local", provider)
        for fn in [_call_gemini, _call_openai, _call_local_fallback]:
            try:
                return fn(prompt, config)
            except Exception as e:
                logger.warning("Provider failed: %s", e)
                continue
        raise RuntimeError("All LLM providers failed")


def _call_gemini(prompt: str, config: WrapTestConfig) -> str:
    """Call Gemini API via google-generativeai or REST."""
    api_key = config.gemini_api_key
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not set in .env")

    # Try google-generativeai SDK first
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(config.llm_model_name)
        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                temperature=config.llm_temperature,
            ),
        )
        return response.text
    except ImportError:
        pass

    # Fallback: REST API via httpx
    try:
        import httpx
    except ImportError:
        import urllib.request
        import urllib.parse

        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{config.llm_model_name}:generateContent?key={api_key}"
        )
        payload = json.dumps({
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": config.llm_temperature},
        }).encode()
        req = urllib.request.Request(
            url, data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode())
        return data["candidates"][0]["content"]["parts"][0]["text"]

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{config.llm_model_name}:generateContent?key={api_key}"
    )
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": config.llm_temperature},
    }
    resp = httpx.post(url, json=payload, timeout=120)
    resp.raise_for_status()
    data = resp.json()
    return data["candidates"][0]["content"]["parts"][0]["text"]


def _call_openai(prompt: str, config: WrapTestConfig) -> str:
    """Call OpenAI API."""
    api_key = config.openai_api_key
    if not api_key:
        raise ValueError("OPENAI_API_KEY is not set in .env")

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=config.llm_model_name if "gpt" in config.llm_model_name else "gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=config.llm_temperature,
        )
        return response.choices[0].message.content
    except ImportError:
        pass

    # Fallback: REST
    import httpx
    resp = httpx.post(
        "https://api.openai.com/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": config.llm_temperature,
        },
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def _call_local_fallback(prompt: str, config: WrapTestConfig) -> str:
    """Local fallback: generate a minimal master_script from knowledge base without LLM."""
    logger.info("Using local rule-based fallback (no LLM)")
    raise NotImplementedError("Local fallback generates script directly, not via LLM call")


def _extract_json_from_response(text: str) -> dict:
    """Extract JSON from LLM response, handling code fences."""
    # Try direct parse
    text = text.strip()
    
    # Remove markdown code fences
    if text.startswith("```"):
        # Find the first newline after opening fence
        first_nl = text.index("\n")
        # Find the last closing fence
        last_fence = text.rfind("```")
        if last_fence > first_nl:
            text = text[first_nl + 1:last_fence].strip()
    
    return json.loads(text)


def generate_master_script(config: WrapTestConfig) -> dict:
    """Generate master_script.json from input + knowledge base via LLM.
    
    Falls back to rule-based generation if LLM fails.
    """
    input_data = config.load_input()
    knowledge_base = config.load_knowledge_base()

    model_description = input_data.get("description", "")
    content_goal = (
        "Tạo video loop livestream giới thiệu bộ sản phẩm Cocoon, "
        "có host nói, cảnh cầm sản phẩm, cảnh đọc comment, cảnh CTA. "
        "Tone chuyên nghiệp, tự nhiên, đáng tin. "
        "Audience: người xem livestream quan tâm chăm sóc da và tóc. "
        "CTA: bấm vào giỏ hàng hoặc comment số điện thoại để được hỗ trợ lên đơn."
    )

    prompt = SCRIPT_GENERATION_PROMPT.format(
        model_base_description=model_description,
        knowledge_base_json=json.dumps(knowledge_base, ensure_ascii=False, indent=2),
        content_goal=content_goal,
    )

    try:
        logger.info("Calling LLM (%s / %s) to generate master script...",
                     config.llm_provider, config.llm_model_name)
        response_text = call_llm(prompt, config)
        master_script = _extract_json_from_response(response_text)
        logger.info("LLM generated %d scenes", len(master_script.get("scenes", [])))
    except Exception as exc:
        logger.warning("LLM generation failed (%s), using rule-based fallback", exc)
        master_script = _generate_fallback_script(input_data, knowledge_base)

    # Save master script
    config.master_script_path.write_text(
        json.dumps(master_script, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info("Saved master_script.json → %s", config.master_script_path)
    return master_script


def _generate_fallback_script(
    input_data: dict, knowledge_base: dict
) -> dict:
    """Rule-based fallback when LLM is unavailable.
    
    Generates a comprehensive script with many scenes from knowledge base data.
    """
    model_desc = input_data.get("description", "Vietnamese livestream host")
    products = knowledge_base.get("products", [])
    pricing = knowledge_base.get("pricing", {})
    faq = knowledge_base.get("faq", [])
    scripts = knowledge_base.get("livestream_scripts", {})

    scenes = []
    order = 0

    # Opening scenes
    order += 1
    scenes.append({
        "scene_id": f"S{order:03d}",
        "clip_id": "A_MAIN_SALES_LOOP",
        "order": order,
        "scene_type": "HOST_TALK",
        "duration_target_sec": 5,
        "voiceover": scripts.get("opening",
            "Dạ em xin chào cả nhà đang xem live Cocoon hôm nay nha."),
        "visual_goal": "Host mở đầu livestream, nhìn thẳng camera, mỉm cười nhẹ.",
        "overlay_text": None,
        "start_anchor": "Host facing camera, hands relaxed near product table.",
        "end_anchor": "Host facing camera, same pose, small smile.",
        "needs_lipsync": True,
        "needs_product_overlay": False,
    })

    # Brand trust
    order += 1
    brand_desc = knowledge_base.get("description", "")
    certs = ", ".join(knowledge_base.get("certifications", [])[:3])
    scenes.append({
        "scene_id": f"S{order:03d}",
        "clip_id": "A_MAIN_SALES_LOOP",
        "order": order,
        "scene_type": "HOST_TALK",
        "duration_target_sec": 5,
        "voiceover": f"Cocoon là mỹ phẩm thuần chay Việt Nam, lành tính và không thử nghiệm trên động vật.",
        "visual_goal": "Host giới thiệu triết lý thương hiệu, giữ ánh mắt tự nhiên.",
        "overlay_text": certs or "Thuần chay • Cruelty-Free • CGMP",
        "start_anchor": "Host facing camera, product visible on table.",
        "end_anchor": "Host facing camera, product still visible.",
        "needs_lipsync": True,
        "needs_product_overlay": True,
    })

    # Product scenes (2-3 per product)
    for product in products:
        pid = product.get("id", "")
        name = product.get("name", "")
        desc = product.get("description", "")
        benefits = product.get("benefits", [])
        price_info = pricing.get(pid, {})

        # Product intro
        order += 1
        scenes.append({
            "scene_id": f"S{order:03d}",
            "clip_id": "A_MAIN_SALES_LOOP",
            "order": order,
            "scene_type": "PRODUCT_CLOSEUP",
            "duration_target_sec": 5,
            "voiceover": desc[:100] if desc else f"Sản phẩm {name}.",
            "visual_goal": f"Cận cảnh sản phẩm {name} trên bàn livestream.",
            "overlay_text": name,
            "start_anchor": "Product centered on table, clean background.",
            "end_anchor": "Product centered, same angle, slight camera push-in.",
            "needs_lipsync": False,
            "needs_product_overlay": True,
        })

        # Product benefit
        if benefits:
            order += 1
            benefit_text = benefits[0] if benefits else ""
            scenes.append({
                "scene_id": f"S{order:03d}",
                "clip_id": "A_MAIN_SALES_LOOP",
                "order": order,
                "scene_type": "HOST_TALK",
                "duration_target_sec": 5,
                "voiceover": benefit_text,
                "visual_goal": f"Host giới thiệu công dụng {name}, cầm sản phẩm nhẹ nhàng.",
                "overlay_text": None,
                "start_anchor": "Host holding product, facing camera.",
                "end_anchor": "Host holding product, same pose.",
                "needs_lipsync": True,
                "needs_product_overlay": True,
            })

        # Pricing
        if price_info:
            order += 1
            livestream_price = price_info.get("livestream_price", "")
            promo = price_info.get("promotion", "")
            scenes.append({
                "scene_id": f"S{order:03d}",
                "clip_id": "A_MAIN_SALES_LOOP",
                "order": order,
                "scene_type": "CTA",
                "duration_target_sec": 5,
                "voiceover": promo or f"Giá livestream chỉ {livestream_price:,}đ.",
                "visual_goal": f"Host chỉ vào giá sản phẩm {name} trên bàn.",
                "overlay_text": f"{name} - Giá live: {livestream_price:,}đ" if livestream_price else name,
                "start_anchor": "Host facing camera, product visible.",
                "end_anchor": "Host facing camera, product visible.",
                "needs_lipsync": True,
                "needs_product_overlay": True,
            })

    # Comment reading loop
    order += 1
    scenes.append({
        "scene_id": f"S{order:03d}",
        "clip_id": "B_COMMENT_READING_LOOP",
        "order": order,
        "scene_type": "HOST_PHONE_READING",
        "duration_target_sec": 5,
        "voiceover": "Dạ câu hỏi này em trả lời ngay cho mình nha.",
        "visual_goal": "Host nhìn xuống điện thoại như đang đọc comment livestream.",
        "overlay_text": "Đang trả lời comment...",
        "start_anchor": "Host holding phone, looking slightly down.",
        "end_anchor": "Host still holding phone, looking slightly down.",
        "needs_lipsync": True,
        "needs_product_overlay": False,
    })

    # FAQ scenes
    for i, faq_item in enumerate(faq[:3]):
        order += 1
        scenes.append({
            "scene_id": f"S{order:03d}",
            "clip_id": "B_COMMENT_READING_LOOP",
            "order": order,
            "scene_type": "FAQ_ANSWER",
            "duration_target_sec": 5,
            "voiceover": faq_item.get("a", "")[:120],
            "visual_goal": "Host trả lời câu hỏi, nhìn camera tự nhiên.",
            "overlay_text": faq_item.get("q", ""),
            "start_anchor": "Host facing camera, phone in hand.",
            "end_anchor": "Host facing camera, nodding gently.",
            "needs_lipsync": True,
            "needs_product_overlay": False,
        })

    # CTA loop
    order += 1
    scenes.append({
        "scene_id": f"S{order:03d}",
        "clip_id": "C_CTA_LOOP",
        "order": order,
        "scene_type": "CTA",
        "duration_target_sec": 5,
        "voiceover": scripts.get("cta_general",
            "Cả nhà bấm vào giỏ hàng góc dưới để em hỗ trợ chốt đơn nha."),
        "visual_goal": "Host nhìn camera, mỉm cười và chỉ nhẹ xuống góc dưới màn hình.",
        "overlay_text": "Chốt đơn tại giỏ hàng",
        "start_anchor": "Host facing camera, product visible on table.",
        "end_anchor": "Host facing camera, product visible on table.",
        "needs_lipsync": True,
        "needs_product_overlay": True,
    })

    # Build playlist
    main_scenes = [s["scene_id"] for s in scenes if s["clip_id"] == "A_MAIN_SALES_LOOP"]
    comment_scenes = [s["scene_id"] for s in scenes if s["clip_id"] == "B_COMMENT_READING_LOOP"]
    cta_scenes = [s["scene_id"] for s in scenes if s["clip_id"] == "C_CTA_LOOP"]

    master_script = {
        "job_id": "cocoon_test_001",
        "base_visual_lock": model_desc,
        "global_rules": {
            "aspect_ratio": "9:16",
            "camera": "medium close-up, fixed camera, direct front view",
            "motion_level": "low",
            "scene_duration_sec": 5,
            "transition": "0.2s crossfade",
            "consistency_rule": (
                "All scenes must use the same face, hairstyle, outfit, "
                "background, lighting, camera angle, and body framing."
            ),
        },
        "playlist": [
            {"clip_id": "A_MAIN_SALES_LOOP", "purpose": "Loop chính giới thiệu sản phẩm", "scenes": main_scenes},
            {"clip_id": "B_COMMENT_READING_LOOP", "purpose": "Loop đọc comment", "scenes": comment_scenes},
            {"clip_id": "C_CTA_LOOP", "purpose": "Loop chốt đơn", "scenes": cta_scenes},
        ],
        "scenes": scenes,
    }

    logger.info("Fallback generated %d scenes from knowledge base", len(scenes))
    return master_script


# =============================================================================
# 3. PROMPT BUILDER
# =============================================================================

def build_prompt_queue(config: WrapTestConfig) -> dict:
    """Build external_prompt_queue.json from master_script.json."""

    if not config.master_script_path.exists():
        raise FileNotFoundError(
            f"master_script.json not found at {config.master_script_path}. "
            "Run --step generate-script first."
        )

    master = json.loads(config.master_script_path.read_text(encoding="utf-8"))
    base_visual_lock = master.get("base_visual_lock", "")
    scenes = master.get("scenes", [])

    prompt_queue_scenes = []
    for scene in scenes:
        veo_prompt = VEO_PROMPT_TEMPLATE.format(
            duration_target_sec=scene.get("duration_target_sec", 5),
            base_visual_lock=base_visual_lock,
            visual_goal=scene.get("visual_goal", ""),
            start_anchor=scene.get("start_anchor", ""),
            end_anchor=scene.get("end_anchor", ""),
        )

        prompt_queue_scenes.append({
            "scene_id": scene["scene_id"],
            "scene_type": scene.get("scene_type", "HOST_TALK"),
            "voiceover": scene.get("voiceover", ""),
            "veo_prompt": veo_prompt,
            "needs_lipsync": scene.get("needs_lipsync", False),
            "needs_product_overlay": scene.get("needs_product_overlay", False),
        })

    prompt_queue = {
        "job_id": master.get("job_id", "cocoon_test_001"),
        "current_scene_index": 0,
        "download_dir": str(config.veo_download_dir),
        "external_video_dir": str(config.veo_download_dir),
        "total_scenes": len(prompt_queue_scenes),
        "scenes": prompt_queue_scenes,
    }

    config.prompt_queue_path.write_text(
        json.dumps(prompt_queue, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info(
        "Built prompt queue with %d scenes → %s",
        len(prompt_queue_scenes),
        config.prompt_queue_path,
    )
    return prompt_queue


# =============================================================================
# 4. VEO BROWSER AUTOMATION (Playwright) – gemini.google.com
# =============================================================================

STEALTH_JS = """
// ─── Anti-detection: mask Playwright/automation signals ───
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
Object.defineProperty(navigator, 'languages', { get: () => ['vi-VN', 'vi', 'en-US', 'en'] });
Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });

// Patch chrome.runtime to avoid "chrome not found" signals
if (!window.chrome) { window.chrome = {}; }
if (!window.chrome.runtime) { window.chrome.runtime = {}; }

// Remove Playwright-injected CDP bindings
delete window.__playwright;
delete window.__pw_manual;
""".strip()


def _take_screenshot(page, config: WrapTestConfig, name: str) -> str:
    """Take a screenshot and save to screenshot dir."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{ts}_{name}.png"
    filepath = config.screenshot_dir / filename
    try:
        page.screenshot(path=str(filepath))
        logger.info("Screenshot saved: %s", filepath)
    except Exception as e:
        logger.warning("Screenshot failed: %s", e)
    return str(filepath)


def _inject_stealth(page) -> None:
    """Inject anti-detection JavaScript into the page."""
    try:
        page.evaluate(STEALTH_JS)
    except Exception:
        pass  # Non-critical


def _find_element(page, selectors: list[str], timeout: int = 5000,
                  state: str = "visible", label: str = "element"):
    """Try multiple selectors and return the first match."""
    for selector in selectors:
        try:
            el = page.wait_for_selector(selector, timeout=timeout, state=state)
            if el:
                logger.debug("  Found %s via: %s", label, selector)
                return el
        except Exception:
            continue
    return None


def _strip_accents(text: str) -> str:
    """Normalize UI text so Vietnamese/English selectors can share one path."""
    normalized = unicodedata.normalize("NFD", text or "")
    stripped = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    return stripped.replace("\u0111", "d").replace("\u0110", "D").lower()


def _visible_text_matches(text: str, needles: list[str]) -> bool:
    haystack = _strip_accents(text)
    return any(_strip_accents(needle) in haystack for needle in needles if needle)


def _click_visible_text(
    page,
    needles: list[str],
    *,
    selectors: str = "button,[role='button'],a,span,div",
    timeout: int = 5000,
    label: str = "visible text",
) -> bool:
    """Click the first visible element whose text/aria-label matches a needle."""
    deadline = time.time() + timeout / 1000
    while time.time() < deadline:
        handle = page.evaluate_handle(
            """({selectors, needles}) => {
                const strip = (text) => (text || "")
                    .normalize("NFD")
                    .replace(/[\\u0300-\\u036f]/g, "")
                    .replace(/đ/g, "d")
                    .replace(/Đ/g, "D")
                    .toLowerCase();
                const wanted = needles.map(strip).filter(Boolean);
                const isVisible = (el) => {
                    const rect = el.getBoundingClientRect();
                    const style = window.getComputedStyle(el);
                    return rect.width > 0 && rect.height > 0
                        && style.visibility !== "hidden"
                        && style.display !== "none";
                };
                for (const el of document.querySelectorAll(selectors)) {
                    if (!isVisible(el)) continue;
                    const text = strip(`${el.innerText || ""} ${el.textContent || ""} ${el.getAttribute("aria-label") || ""} ${el.getAttribute("title") || ""}`);
                    if (wanted.some((needle) => text.includes(needle))) {
                        return el.closest("button,[role='button'],a") || el;
                    }
                }
                return null;
            }""",
            {"selectors": selectors, "needles": needles},
        )
        element = handle.as_element()
        if element:
            try:
                element.scroll_into_view_if_needed(timeout=1000)
            except Exception:
                pass
            try:
                element.click(timeout=2000)
            except Exception:
                element.click(force=True, timeout=2000)
            logger.debug("  Clicked %s via visible text: %s", label, needles)
            return True
        time.sleep(0.25)
    return False


def _click_exact_visible_text(
    page,
    labels: list[str],
    *,
    selectors: str = "button,[role='button'],[role='menuitem'],a,[role='link'],span,div",
    timeout: int = 5000,
    label: str = "exact visible text",
) -> bool:
    """Click a visible element whose normalized text exactly equals one label."""
    deadline = time.time() + timeout / 1000
    while time.time() < deadline:
        handle = page.evaluate_handle(
            """({selectors, labels}) => {
                const strip = (text) => (text || "")
                    .normalize("NFD")
                    .replace(/[\\u0300-\\u036f]/g, "")
                    .replace(/đ/g, "d")
                    .replace(/Đ/g, "D")
                    .replace(/\\s+/g, " ")
                    .trim()
                    .toLowerCase();
                const wanted = labels.map(strip).filter(Boolean);
                const isVisible = (el) => {
                    const rect = el.getBoundingClientRect();
                    const style = window.getComputedStyle(el);
                    return rect.width > 0 && rect.height > 0
                        && style.visibility !== "hidden"
                        && style.display !== "none";
                };
                for (const el of document.querySelectorAll(selectors)) {
                    if (!isVisible(el)) continue;
                    const raw = `${el.innerText || ""} ${el.getAttribute("aria-label") || ""} ${el.getAttribute("title") || ""}`;
                    const text = strip(raw);
                    if (wanted.includes(text)) {
                        return el.closest("button,[role='button'],[role='menuitem'],a,[role='link']") || el;
                    }
                }
                return null;
            }""",
            {"selectors": selectors, "labels": labels},
        )
        element = handle.as_element()
        if element:
            try:
                element.scroll_into_view_if_needed(timeout=1000)
            except Exception:
                pass
            try:
                element.click(timeout=2000)
            except Exception:
                element.click(force=True, timeout=2000)
            logger.debug("  Clicked %s via exact text: %s", label, labels)
            return True
        time.sleep(0.25)
    return False


def _gemini_plus_menu_open(page) -> bool:
    """Detect Gemini's plus/upload menu."""
    try:
        return bool(page.evaluate(
            """() => {
                const strip = (text) => (text || "")
                    .normalize("NFD")
                    .replace(/[\\u0300-\\u036f]/g, "")
                    .replace(/đ/g, "d")
                    .replace(/Đ/g, "D")
                    .toLowerCase();
                const isVisible = (el) => {
                    const rect = el.getBoundingClientRect();
                    const style = window.getComputedStyle(el);
                    return rect.width > 0 && rect.height > 0
                        && style.visibility !== "hidden"
                        && style.display !== "none";
                };
                const roots = Array.from(document.querySelectorAll(
                    "[role='menu'],[role='listbox'],.cdk-overlay-pane,.mat-mdc-menu-panel"
                )).filter(isVisible);
                return roots.some((root) => {
                    const text = strip(root.innerText || root.textContent || "");
                    return text.includes("upload")
                        || text.includes("tai tep")
                        || text.includes("drive")
                        || text.includes("create video")
                        || text.includes("tao video");
                });
            }"""
        ))
    except Exception:
        return False


def _click_video_composer_upload_slot(page) -> bool:
    """Click the wide image-upload button in Gemini's video composer."""
    try:
        points = page.evaluate(
            """() => {
                const isVisible = (el) => {
                    const rect = el.getBoundingClientRect();
                    const style = window.getComputedStyle(el);
                    return rect.width > 0 && rect.height > 0
                        && style.visibility !== "hidden"
                        && style.display !== "none";
                };
                const textOf = (el) => `${el.innerText || ""} ${el.textContent || ""} ${el.getAttribute("aria-label") || ""} ${el.getAttribute("title") || ""}`.toLowerCase();

                const aspect = Array.from(document.querySelectorAll("button,[role='button'],div"))
                    .filter(isVisible)
                    .map((el) => ({el, rect: el.getBoundingClientRect(), text: textOf(el)}))
                    .filter((item) => item.text.includes("landscape") || item.text.includes("portrait") || item.text.includes("9:16") || item.text.includes("16:9"))
                    .sort((a, b) => b.rect.top - a.rect.top)[0];
                if (aspect) {
                    const y = aspect.rect.top + aspect.rect.height / 2;
                    return [
                        {x: aspect.rect.left - 170, y, source: "aspect-left"},
                        {x: aspect.rect.left - 70, y, source: "aspect-left-near"}
                    ];
                }

                const selectors = [
                    'rich-textarea div[contenteditable="true"]',
                    'div[contenteditable="true"][role="textbox"]',
                    'div[contenteditable="true"][aria-label]',
                    '.ql-editor[contenteditable="true"]',
                    '.ProseMirror[contenteditable="true"]',
                    'div[contenteditable="true"]',
                    'textarea'
                ];
                const input = selectors
                    .flatMap((selector) => Array.from(document.querySelectorAll(selector)))
                    .filter(isVisible)
                    .sort((a, b) => a.getBoundingClientRect().top - b.getBoundingClientRect().top)
                    .pop();
                if (!input) return [];
                let container = input;
                for (let i = 0; i < 6 && container.parentElement; i++) {
                    const rect = container.getBoundingClientRect();
                    if (rect.width > 450 && rect.height > 90) break;
                    container = container.parentElement;
                }
                const rect = container.getBoundingClientRect();
                return [
                    {x: rect.left + rect.width * 0.25, y: rect.bottom - 28, source: "container-slot"},
                    {x: rect.left + rect.width * 0.20, y: rect.bottom - 28, source: "container-slot-left"}
                ];
            }"""
        )
        for point in points:
            page.mouse.click(point["x"], point["y"])
            logger.debug("  Clicked video composer upload slot via %s", point.get("source"))
            time.sleep(0.8)
            return True
        return False
    except Exception as exc:
        logger.debug("  Could not click video composer upload slot: %s", exc)
        return False


def _click_video_aspect_dropdown(page) -> bool:
    """Click the aspect-ratio dropdown in the video composer bottom row."""
    try:
        point = page.evaluate(
            """() => {
                const strip = (text) => (text || "")
                    .normalize("NFD")
                    .replace(/[\\u0300-\\u036f]/g, "")
                    .replace(/đ/g, "d")
                    .replace(/Đ/g, "D")
                    .toLowerCase();
                const isVisible = (el) => {
                    const rect = el.getBoundingClientRect();
                    const style = window.getComputedStyle(el);
                    return rect.width > 0 && rect.height > 0
                        && style.visibility !== "hidden"
                        && style.display !== "none";
                };
                const makeCandidates = (selector, priority) => Array.from(document.querySelectorAll(selector))
                    .filter(isVisible)
                    .map((el) => {
                        const rect = el.getBoundingClientRect();
                        const text = strip(`${el.innerText || ""} ${el.textContent || ""} ${el.getAttribute("aria-label") || ""} ${el.getAttribute("title") || ""}`);
                        return {el, rect, text, priority};
                    })
                    .filter((item) => item.rect.top > window.innerHeight * 0.55)
                    .filter((item) => item.rect.width >= 70 && item.rect.width <= 520)
                    .filter((item) => item.rect.height >= 24 && item.rect.height <= 90)
                    .filter((item) =>
                        item.text.includes("landscape") ||
                        item.text.includes("portrait") ||
                        item.text.includes("ngang") ||
                        item.text.includes("doc") ||
                        item.text.includes("16:9") ||
                        item.text.includes("9:16")
                    );
                const candidates = [
                    ...makeCandidates("button,[role='button'],[aria-haspopup]", 1000),
                    ...makeCandidates("div,span", 0),
                ].sort((a, b) => {
                    const score = (item) =>
                        item.priority +
                        (item.rect.left / Math.max(window.innerWidth, 1)) * 100 +
                        (item.rect.top / Math.max(window.innerHeight, 1)) * 50 -
                        Math.abs(item.text.length - 18);
                    return score(b) - score(a);
                });
                const chosen = candidates[0];
                if (!chosen) return null;
                return {
                    x: chosen.rect.left + chosen.rect.width / 2,
                    y: chosen.rect.top + chosen.rect.height / 2,
                    text: chosen.text
                };
            }"""
        )
        if not point:
            return False
        page.mouse.click(point["x"], point["y"])
        logger.debug("  Clicked aspect dropdown candidate: %s", point.get("text"))
        time.sleep(1)
        return True
    except Exception as exc:
        logger.debug("  Could not click video aspect dropdown: %s", exc)
        return False


def _click_video_aspect_option(page, labels: list[str]) -> bool:
    """Click a portrait/9:16 option in the open aspect-ratio menu."""
    try:
        point = page.evaluate(
            """({labels}) => {
                const strip = (text) => (text || "")
                    .normalize("NFD")
                    .replace(/[\\u0300-\\u036f]/g, "")
                    .replace(/đ/g, "d")
                    .replace(/Đ/g, "D")
                    .replace(/\\s+/g, " ")
                    .trim()
                    .toLowerCase();
                const wanted = labels.map(strip).filter(Boolean);
                const isVisible = (el) => {
                    const rect = el.getBoundingClientRect();
                    const style = window.getComputedStyle(el);
                    return rect.width > 0 && rect.height > 0
                        && style.visibility !== "hidden"
                        && style.display !== "none";
                };
                const optionSelectors = [
                    "[role='option']",
                    "[role='menuitem']",
                    ".cdk-overlay-pane button",
                    ".cdk-overlay-pane [role='button']",
                    ".cdk-overlay-pane *",
                    ".mat-mdc-menu-panel *",
                    "button",
                    "[role='button']"
                ];
                const seen = new Set();
                const candidates = [];
                for (const selector of optionSelectors) {
                    for (const el of document.querySelectorAll(selector)) {
                        if (seen.has(el) || !isVisible(el)) continue;
                        seen.add(el);
                        const rect = el.getBoundingClientRect();
                        if (rect.width < 20 || rect.height < 18) continue;
                        const text = strip(`${el.innerText || ""} ${el.textContent || ""} ${el.getAttribute("aria-label") || ""} ${el.getAttribute("title") || ""}`);
                        if (!text) continue;
                        const isPortrait =
                            text.includes("9:16") ||
                            text.includes("portrait") ||
                            text.includes("doc");
                        const labelMatch = wanted.some((needle) => text === needle || text.includes(needle));
                        if (!isPortrait && !labelMatch) continue;
                        const inOverlay = !!el.closest(".cdk-overlay-pane,.mat-mdc-menu-panel,[role='listbox'],[role='menu']");
                        candidates.push({el, rect, text, inOverlay});
                    }
                }
                candidates.sort((a, b) => {
                    const score = (item) =>
                        (item.inOverlay ? 1000 : 0) +
                        (item.text.includes("9:16") ? 200 : 0) +
                        (item.text.includes("portrait") || item.text.includes("doc") ? 100 : 0) -
                        Math.abs(item.text.length - 16);
                    return score(b) - score(a);
                });
                const chosen = candidates[0];
                if (!chosen) return null;
                const target = chosen.el.closest("button,[role='button'],[role='option'],[role='menuitem']") || chosen.el;
                const rect = target.getBoundingClientRect();
                return {
                    x: rect.left + rect.width / 2,
                    y: rect.top + rect.height / 2,
                    text: chosen.text
                };
            }""",
            {"labels": labels},
        )
        if not point:
            return False
        page.mouse.click(point["x"], point["y"])
        logger.debug("  Clicked vertical aspect option: %s", point.get("text"))
        time.sleep(1)
        return True
    except Exception as exc:
        logger.debug("  Could not click vertical aspect option: %s", exc)
        return False


def _find_visible_element_by_text(
    page,
    needles: list[str],
    *,
    selectors: str = "button,[role='button'],span,div",
):
    """Return first visible element matching text/aria-label, or None."""
    handle = page.evaluate_handle(
        """({selectors, needles}) => {
            const strip = (text) => (text || "")
                .normalize("NFD")
                .replace(/[\\u0300-\\u036f]/g, "")
                .replace(/đ/g, "d")
                .replace(/Đ/g, "D")
                .toLowerCase();
            const wanted = needles.map(strip).filter(Boolean);
            const isVisible = (el) => {
                const rect = el.getBoundingClientRect();
                const style = window.getComputedStyle(el);
                return rect.width > 0 && rect.height > 0
                    && style.visibility !== "hidden"
                    && style.display !== "none";
            };
            for (const el of document.querySelectorAll(selectors)) {
                if (!isVisible(el)) continue;
                const text = strip(`${el.innerText || ""} ${el.textContent || ""} ${el.getAttribute("aria-label") || ""} ${el.getAttribute("title") || ""}`);
                if (wanted.some((needle) => text.includes(needle))) return el;
            }
            return null;
        }""",
        {"selectors": selectors, "needles": needles},
    )
    return handle.as_element()


def _click_plus_near_prompt_box(page) -> bool:
    """Open the plus/attachment menu placed at the left of Gemini's prompt box."""
    try:
        target = page.evaluate(
            """() => {
                const selectors = [
                    'rich-textarea div[contenteditable="true"]',
                    'div[contenteditable="true"][role="textbox"]',
                    'div[contenteditable="true"][aria-label]',
                    '.ql-editor[contenteditable="true"]',
                    '.ProseMirror[contenteditable="true"]',
                    'div[contenteditable="true"]',
                    'textarea'
                ];
                const isVisible = (el) => {
                    const rect = el.getBoundingClientRect();
                    const style = window.getComputedStyle(el);
                    return rect.width > 0 && rect.height > 0
                        && style.visibility !== "hidden"
                        && style.display !== "none";
                };
                const input = selectors
                    .flatMap((selector) => Array.from(document.querySelectorAll(selector)))
                    .filter(isVisible)
                    .sort((a, b) => a.getBoundingClientRect().top - b.getBoundingClientRect().top)
                    .pop();
                if (!input) return null;

                const inputRect = input.getBoundingClientRect();
                const centerY = inputRect.top + inputRect.height / 2;
                const buttons = Array.from(document.querySelectorAll("button,[role='button']"))
                    .filter(isVisible)
                    .map((el) => {
                        const rect = el.getBoundingClientRect();
                        const text = `${el.innerText || ""} ${el.textContent || ""} ${el.getAttribute("aria-label") || ""} ${el.getAttribute("title") || ""}`.toLowerCase();
                        const cx = rect.left + rect.width / 2;
                        const cy = rect.top + rect.height / 2;
                        return {el, rect, text, cx, cy};
                    })
                    .filter((item) => Math.abs(item.cy - centerY) < 70)
                    .filter((item) => item.cx < inputRect.left + 120)
                    .sort((a, b) => Math.abs(a.cy - centerY) - Math.abs(b.cy - centerY));

                const labelMatch = buttons.find((item) =>
                    item.text.includes("add") ||
                    item.text.includes("plus") ||
                    item.text.includes("attach") ||
                    item.text.includes("upload") ||
                    item.text.includes("them") ||
                    item.text.includes("tai")
                );
                const points = [];
                const chosen = labelMatch || buttons[0];
                if (chosen) points.push({x: chosen.cx, y: chosen.cy, source: "button"});
                points.push({x: Math.max(10, inputRect.left - 24), y: centerY, source: "left-minus"});
                points.push({x: inputRect.left + 30, y: centerY, source: "left-plus"});
                points.push({x: inputRect.left + 45, y: centerY, source: "left-plus-wide"});
                return points;
            }"""
        )
        if not target:
            return False
        for point in target:
            page.mouse.click(point["x"], point["y"])
            logger.debug("  Clicked Gemini plus near prompt box via %s", point.get("source"))
            time.sleep(0.8)
            if _gemini_plus_menu_open(page):
                return True
        return _gemini_plus_menu_open(page)
    except Exception as exc:
        logger.debug("  Could not click plus near prompt box: %s", exc)
        return False


def _gemini_text_input_handle(page):
    """Find Gemini's prompt textbox, preferring the bottom-most visible editor."""
    selectors = [
        'rich-textarea div[contenteditable="true"]',
        'div[contenteditable="true"][role="textbox"]',
        'div[contenteditable="true"][aria-label]',
        '.ql-editor[contenteditable="true"]',
        '.ProseMirror[contenteditable="true"]',
        'div[contenteditable="true"]',
        'textarea',
    ]
    for selector in selectors:
        try:
            loc = page.locator(selector)
            count = loc.count()
            if count <= 0:
                continue
            candidates = []
            for idx in range(count):
                item = loc.nth(idx)
                try:
                    if item.is_visible(timeout=500):
                        box = item.bounding_box(timeout=500)
                        if box:
                            candidates.append((box["y"], item.element_handle(timeout=500)))
                except Exception:
                    continue
            if candidates:
                return sorted(candidates, key=lambda item: item[0])[-1][1]
        except Exception:
            continue

    handle = page.evaluate_handle(
        """() => {
            const selectors = [
                'rich-textarea div[contenteditable="true"]',
                'div[contenteditable="true"][role="textbox"]',
                'div[contenteditable="true"][aria-label]',
                '.ql-editor[contenteditable="true"]',
                '.ProseMirror[contenteditable="true"]',
                'div[contenteditable="true"]',
                'textarea'
            ];
            const isVisible = (el) => {
                const rect = el.getBoundingClientRect();
                const style = window.getComputedStyle(el);
                return rect.width > 0 && rect.height > 0
                    && style.visibility !== "hidden"
                    && style.display !== "none";
            };
            return selectors
                .flatMap((selector) => Array.from(document.querySelectorAll(selector)))
                .filter(isVisible)
                .sort((a, b) => a.getBoundingClientRect().top - b.getBoundingClientRect().top)
                .pop() || null;
        }"""
    )
    return handle.as_element()


def _wait_for_gemini_textbox(page, timeout: int = 30000):
    """Wait for the Gemini prompt textbox and return its element handle."""
    deadline = time.time() + timeout / 1000
    while time.time() < deadline:
        textbox = _gemini_text_input_handle(page)
        if textbox:
            return textbox
        time.sleep(0.5)
    return None


def _configure_download_behavior(context, download_dir: Path) -> None:
    """Best-effort download behavior for persistent or CDP Chrome contexts."""
    try:
        context.set_default_timeout(30000)
        context.set_default_navigation_timeout(60000)
    except Exception:
        pass

    try:
        page = context.pages[0] if context.pages else context.new_page()
        cdp = context.new_cdp_session(page)
        cdp.send(
            "Browser.setDownloadBehavior",
            {"behavior": "allow", "downloadPath": str(download_dir)},
        )
    except Exception as exc:
        logger.debug("Could not set Chrome download behavior: %s", exc)


def _connect_or_launch_chrome(p, config: WrapTestConfig):
    """Use an existing logged-in Chrome via CDP when configured, otherwise launch."""
    if config.chrome_cdp_url:
        logger.info("Connecting to existing Chrome via CDP: %s", config.chrome_cdp_url)
        browser = p.chromium.connect_over_cdp(config.chrome_cdp_url)
        context = browser.contexts[0] if browser.contexts else browser.new_context(
            accept_downloads=True,
            viewport={"width": 1920, "height": 1080},
            locale="vi-VN",
            timezone_id="Asia/Ho_Chi_Minh",
        )
        _configure_download_behavior(context, config.veo_download_dir)
        page = context.pages[0] if context.pages else context.new_page()
        return browser, context, page

    launch_args = [
        "--disable-blink-features=AutomationControlled",
        "--disable-features=IsolateOrigins,site-per-process",
        "--disable-infobars",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-component-extensions-with-background-pages",
        "--disable-default-apps",
        "--disable-popup-blocking",
        "--disable-background-timer-throttling",
        "--disable-backgrounding-occluded-windows",
        "--disable-renderer-backgrounding",
        "--disable-dev-shm-usage",
    ]

    user_data_dir = (
        config.chrome_user_data_dir
        if config.chrome_user_data_dir
        else str(PROJECT_ROOT / ".chrome_profile")
    )

    context = p.chromium.launch_persistent_context(
        user_data_dir=user_data_dir,
        headless=False,
        args=launch_args,
        channel="chrome" if not config.chrome_executable_path else None,
        executable_path=config.chrome_executable_path or None,
        accept_downloads=True,
        viewport={"width": 1920, "height": 1080},
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/130.0.0.0 Safari/537.36"
        ),
        locale="vi-VN",
        timezone_id="Asia/Ho_Chi_Minh",
    )
    _configure_download_behavior(context, config.veo_download_dir)
    page = context.pages[0] if context.pages else context.new_page()
    return None, context, page


def run_veo_browser_automation(config: WrapTestConfig) -> list[dict]:
    """Run Playwright to automate video generation on gemini.google.com.

    Gemini web app is a chat interface. Flow per scene:
      1. Open gemini.google.com (or start new chat)
      2. Click attachment button → upload model + product images
      3. Type VEO prompt into the chat rich-text editor
      4. Click Send
      5. Wait for Gemini response to complete (contains video)
      6. Download the generated video from the response
      7. Screenshot each step

    Returns list of {scene_id, video_path, status} dicts.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.error(
            "Playwright is not installed. Run:\n"
            "  pip install playwright\n"
            "  python -m playwright install chromium"
        )
        raise

    # Load prompt queue
    if not config.prompt_queue_path.exists():
        raise FileNotFoundError(
            f"Prompt queue not found: {config.prompt_queue_path}. "
            "Run --step build-prompts first."
        )

    queue = json.loads(config.prompt_queue_path.read_text(encoding="utf-8"))
    scenes = queue.get("scenes", [])
    if config.veo_scene_limit > 0:
        scenes = scenes[:config.veo_scene_limit]
        logger.info("VEO_SCENE_LIMIT active: processing first %d scene(s)", len(scenes))
    input_data = config.load_input()

    model_image = input_data.get("model_image_resolved", "")
    product_image = input_data.get("product_image_resolved", "")

    results = []

    if config.chrome_cdp_url:
        with sync_playwright() as p:
            browser, context, page = _connect_or_launch_chrome(p, config)
            context.on("page", lambda pg: pg.on("load", lambda: _inject_stealth(pg)))
            try:
                _run_veo_page_session(
                    page=page,
                    context=context,
                    config=config,
                    scenes=scenes,
                    model_image=model_image,
                    product_image=product_image,
                    results=results,
                )
            finally:
                # For CDP we are attached to the user's real Chrome; leave it open.
                pass
        return results

    with sync_playwright() as p:
        # ── Heavy stealth: bypass Gemini automation detection ──
        launch_args = [
            "--disable-blink-features=AutomationControlled",
            "--disable-features=IsolateOrigins,site-per-process",
            "--disable-infobars",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-component-extensions-with-background-pages",
            "--disable-default-apps",
            "--disable-extensions",
            "--disable-popup-blocking",
            "--disable-background-timer-throttling",
            "--disable-backgrounding-occluded-windows",
            "--disable-renderer-backgrounding",
            "--disable-dev-shm-usage",
        ]

        if config.chrome_user_data_dir:
            user_data_dir = config.chrome_user_data_dir
        else:
            user_data_dir = str(PROJECT_ROOT / ".chrome_profile")

        context = p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=False,
            args=launch_args,
            channel="chrome" if not config.chrome_executable_path else None,
            executable_path=config.chrome_executable_path or None,
            accept_downloads=True,
            viewport={"width": 1920, "height": 1080},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/130.0.0.0 Safari/537.36"
            ),
            locale="vi-VN",
            timezone_id="Asia/Ho_Chi_Minh",
        )

        # Inject stealth on every new page/navigation
        context.on("page", lambda pg: pg.on("load", lambda: _inject_stealth(pg)))

        page = context.pages[0] if context.pages else context.new_page()

        logger.info("Browser launched. Navigating to Gemini...")

        # ── Navigate to Gemini ──
        page.goto(config.gemini_veo_url, wait_until="domcontentloaded", timeout=60000)
        _inject_stealth(page)
        time.sleep(4)
        _take_screenshot(page, config, "01_initial_page")

        # ── Handle login ──
        current_url = page.url
        if "accounts.google.com" in current_url or "signin" in current_url.lower():
            logger.warning(
                "\n"
                "═══════════════════════════════════════════════════\n"
                "  ⚠  Google login required!\n"
                "  Please log in manually in the browser window.\n"
                "  The script will wait up to 180 seconds...\n"
                "═══════════════════════════════════════════════════"
            )
            try:
                page.wait_for_url(
                    lambda url: "gemini.google.com" in url,
                    timeout=180000,
                )
                logger.info("Login successful! Continuing...")
                time.sleep(5)
                _inject_stealth(page)
                _take_screenshot(page, config, "02_after_login")
            except Exception:
                logger.error("Login timeout. Please login and re-run.")
                context.close()
                return results

        # ── Wait for Gemini UI to fully load ──
        logger.info("Waiting for Gemini chat UI to load...")
        _wait_for_gemini_ready(page)
        try:
            _prepare_gemini_video_mode(page, config, "initial")
        except Exception as exc:
            logger.warning("Initial video-mode preparation failed, will retry per scene: %s", exc)
        _take_screenshot(page, config, "03_gemini_ready")
        logger.info("Gemini ready. Processing %d scenes...", len(scenes))

        # ── Process each scene ──
        for i, scene in enumerate(scenes):
            scene_id = scene["scene_id"]
            veo_prompt = scene["veo_prompt"]

            logger.info(
                "\n━━━ Scene %d/%d: %s (%s) ━━━",
                i + 1, len(scenes), scene_id, scene.get("scene_type", "?")
            )

            try:
                video_path = _process_gemini_scene(
                    page=page,
                    config=config,
                    scene_id=scene_id,
                    scene_index=i,
                    veo_prompt=veo_prompt,
                    model_image=model_image,
                    product_image=product_image,
                )
                results.append({
                    "scene_id": scene_id,
                    "video_path": video_path,
                    "status": "success",
                })
                logger.info("✓ Scene %s completed: %s", scene_id, video_path)

            except Exception as exc:
                logger.error("✗ Scene %s failed: %s", scene_id, exc)
                _take_screenshot(page, config, f"error_{scene_id}")
                results.append({
                    "scene_id": scene_id,
                    "video_path": None,
                    "status": f"error: {exc}",
                })

                # Save prompt as fallback
                prompt_fallback_path = config.output_dir / f"{scene_id}_prompt.txt"
                prompt_fallback_path.write_text(veo_prompt, encoding="utf-8")
                logger.info("Prompt saved to: %s", prompt_fallback_path)

                # Also try clipboard
                try:
                    import pyperclip
                    pyperclip.copy(veo_prompt)
                    logger.info("Prompt also copied to clipboard for manual paste.")
                except ImportError:
                    pass

        context.close()

    return results


def _run_veo_page_session(
    *,
    page,
    context,
    config: WrapTestConfig,
    scenes: list[dict],
    model_image: str,
    product_image: str,
    results: list[dict],
) -> None:
    """Run the Gemini flow on an already-open browser page/context."""
    logger.info("Navigating to Gemini...")
    page.goto(config.gemini_veo_url, wait_until="domcontentloaded", timeout=60000)
    _inject_stealth(page)
    time.sleep(4)
    _take_screenshot(page, config, "01_initial_page")

    current_url = page.url
    if "accounts.google.com" in current_url or "signin" in current_url.lower():
        logger.warning(
            "Google login required. Log in manually in the browser window; "
            "the script will wait up to 180 seconds."
        )
        try:
            page.wait_for_url(lambda url: "gemini.google.com" in url, timeout=180000)
            time.sleep(5)
            _inject_stealth(page)
            _take_screenshot(page, config, "02_after_login")
        except Exception:
            logger.error("Login timeout. Please login and re-run.")
            return

    logger.info("Waiting for Gemini chat UI to load...")
    _wait_for_gemini_ready(page)
    try:
        _prepare_gemini_video_mode(page, config, "initial")
    except Exception as exc:
        logger.warning("Initial video-mode preparation failed, will retry per scene: %s", exc)
    _take_screenshot(page, config, "03_gemini_ready")
    logger.info("Gemini ready. Processing %d scenes...", len(scenes))

    for i, scene in enumerate(scenes):
        scene_id = scene["scene_id"]
        veo_prompt = scene["veo_prompt"]

        logger.info(
            "\n--- Scene %d/%d: %s (%s) ---",
            i + 1, len(scenes), scene_id, scene.get("scene_type", "?")
        )

        try:
            video_path = _process_gemini_scene(
                page=page,
                config=config,
                scene_id=scene_id,
                scene_index=i,
                veo_prompt=veo_prompt,
                model_image=model_image,
                product_image=product_image,
            )
            results.append({
                "scene_id": scene_id,
                "video_path": video_path,
                "status": "success",
            })
            logger.info("Scene %s completed: %s", scene_id, video_path)
        except Exception as exc:
            logger.error("Scene %s failed: %s", scene_id, exc)
            _take_screenshot(page, config, f"error_{scene_id}")
            results.append({
                "scene_id": scene_id,
                "video_path": None,
                "status": f"error: {exc}",
            })
            prompt_fallback_path = config.output_dir / f"{scene_id}_prompt.txt"
            prompt_fallback_path.write_text(veo_prompt, encoding="utf-8")
            logger.info("Prompt saved to: %s", prompt_fallback_path)
            try:
                import pyperclip
                pyperclip.copy(veo_prompt)
                logger.info("Prompt also copied to clipboard for manual paste.")
            except ImportError:
                pass


def _wait_for_gemini_ready(page, timeout: int = 30000) -> None:
    """Wait until Gemini chat UI is interactable."""
    textbox = _wait_for_gemini_textbox(page, timeout=timeout)
    if textbox:
        logger.debug("Gemini ready: found prompt textbox")
        return

    logger.warning("Could not detect Gemini input area, waiting 10s...")
    time.sleep(10)


def _prepare_gemini_video_mode(page, config: WrapTestConfig, prefix: str) -> None:
    """Switch Gemini web to video mode and vertical 9:16 before submitting."""
    _wait_for_gemini_ready(page)
    _select_gemini_video_tool(page, config, prefix)
    _dismiss_gemini_video_onboarding(page, config, prefix)
    _select_gemini_vertical_aspect(page, config, prefix)


def _dismiss_gemini_video_onboarding(page, config: WrapTestConfig, prefix: str) -> None:
    """Dismiss Gemini video onboarding modal if it appears."""
    labels = [
        "Try it",
        "Get started",
        "Start",
        "Continue",
        "Got it",
        "OK",
        "Dùng thử",
        "Bắt đầu",
        "Tiếp tục",
        "Đã hiểu",
    ]
    try:
        if _click_exact_visible_text(
            page,
            labels,
            selectors="button,[role='button']",
            timeout=2000,
            label="video onboarding dismiss",
        ):
            time.sleep(2)
            _take_screenshot(page, config, f"{prefix}_video_onboarding_dismissed")
            logger.info("  Dismissed Gemini video onboarding modal")
    except Exception as exc:
        logger.debug("  No Gemini video onboarding modal dismissed: %s", exc)


def _gemini_video_mode_active(page) -> bool:
    """Return True when Gemini's video composer is active."""
    try:
        return bool(page.evaluate(
            """() => {
                const strip = (text) => (text || "")
                    .normalize("NFD")
                    .replace(/[\\u0300-\\u036f]/g, "")
                    .replace(/đ/g, "d")
                    .replace(/Đ/g, "D")
                    .toLowerCase();
                const body = strip(document.body.innerText || "");
                return body.includes("mo ta video cua ban")
                    || body.includes("describe your video")
                    || body.includes("tao bang omni")
                    || body.includes("create videos")
                    || Array.from(document.querySelectorAll("button,[role='button'],span"))
                        .some((el) => strip(el.innerText || el.textContent || "").trim() === "video");
            }"""
        ))
    except Exception:
        return False


def _select_gemini_video_tool(page, config: WrapTestConfig, prefix: str) -> None:
    """Open Gemini's plus/tool menu and choose the video generator."""
    if _gemini_video_mode_active(page):
        logger.info("  Gemini video mode is already active")
        return

    # On the current Gemini UI, the left nav has a dedicated "Videos" entry.
    # This is safer than scanning recents, where chat titles may contain
    # "Tạo video" and cause the script to open an old conversation.
    if _click_exact_visible_text(
        page,
        ["Videos", "Video"],
        selectors="a,[role='link'],button,[role='button']",
        timeout=2000,
        label="Gemini Videos nav",
    ):
        time.sleep(3)
        _dismiss_gemini_video_onboarding(page, config, prefix)
        if _gemini_video_mode_active(page):
            _take_screenshot(page, config, f"{prefix}_video_mode")
            logger.info("  Selected Gemini video tool via Videos nav")
            return

    tool_labels = [
        config.gemini_video_tool_label,
        "Tạo video",
        "Create video",
    ]

    if _click_exact_visible_text(page, tool_labels, selectors="[role='menuitem'],button,[role='button']", timeout=1500, label="video tool"):
        time.sleep(2)
        _dismiss_gemini_video_onboarding(page, config, prefix)
        if _gemini_video_mode_active(page):
            _take_screenshot(page, config, f"{prefix}_video_mode")
            logger.info("  Selected Gemini video tool")
            return

    trigger_selectors = [
        'button[aria-label*="Add" i]',
        'button[aria-label*="Attach" i]',
        'button[aria-label*="Upload" i]',
        'button[aria-label*="Thêm" i]',
        'button[aria-label*="Tải" i]',
        'button:has-text("+")',
        'button:has(mat-icon:has-text("add"))',
        'button:has(mat-icon:has-text("attach_file"))',
        'button:has(mat-icon:has-text("add_photo_alternate"))',
    ]

    opened_menu = False
    for selector in trigger_selectors:
        try:
            locator = page.locator(selector)
            count = locator.count()
            for idx in range(min(count, 8)):
                btn = locator.nth(idx)
                if not btn.is_visible(timeout=500):
                    continue
                try:
                    btn.click(timeout=2000)
                except Exception:
                    btn.click(force=True, timeout=2000)
                time.sleep(1)
                if _click_exact_visible_text(
                    page,
                    tool_labels,
                    selectors="[role='menuitem'],button,[role='button'],.cdk-overlay-pane *,.mat-mdc-menu-panel *",
                    timeout=3000,
                    label="video tool",
                ):
                    opened_menu = True
                    _dismiss_gemini_video_onboarding(page, config, prefix)
                    break
            if opened_menu:
                break
        except Exception:
            continue

    if not opened_menu and _click_plus_near_prompt_box(page):
        _take_screenshot(page, config, f"{prefix}_plus_menu_opened")
        if _click_exact_visible_text(
            page,
            tool_labels,
            selectors="[role='menuitem'],button,[role='button'],.cdk-overlay-pane *,.mat-mdc-menu-panel *",
            timeout=5000,
            label="video tool",
        ):
            opened_menu = True
            _dismiss_gemini_video_onboarding(page, config, prefix)

    time.sleep(2)
    if not _gemini_video_mode_active(page):
        _take_screenshot(page, config, f"{prefix}_video_mode_failed")
        raise RuntimeError(
            "Could not switch Gemini to video mode. "
            "Open the + menu and check that 'Tạo video' is available."
        )

    _take_screenshot(page, config, f"{prefix}_video_mode")
    logger.info("  Selected Gemini video tool")


def _gemini_vertical_aspect_active(page, config: WrapTestConfig) -> bool:
    try:
        return bool(page.evaluate(
            """({labels}) => {
                const strip = (text) => (text || "")
                    .normalize("NFD")
                    .replace(/[\\u0300-\\u036f]/g, "")
                    .replace(/đ/g, "d")
                    .replace(/Đ/g, "D")
                    .replace(/\\s+/g, " ")
                    .trim()
                    .toLowerCase();
                const wanted = labels.map(strip).filter(Boolean);
                const isVisible = (el) => {
                    const rect = el.getBoundingClientRect();
                    const style = window.getComputedStyle(el);
                    return rect.width > 0 && rect.height > 0
                        && style.visibility !== "hidden"
                        && style.display !== "none";
                };
                return Array.from(document.querySelectorAll("button,[role='button'],[aria-haspopup],div,span"))
                    .filter(isVisible)
                    .map((el) => {
                        const rect = el.getBoundingClientRect();
                        const text = strip(`${el.innerText || ""} ${el.textContent || ""} ${el.getAttribute("aria-label") || ""} ${el.getAttribute("title") || ""}`);
                        return {rect, text};
                    })
                    .filter((item) => item.rect.top > window.innerHeight * 0.55)
                    .filter((item) => item.rect.width >= 50 && item.rect.width <= 560)
                    .filter((item) => item.rect.height >= 18 && item.rect.height <= 100)
                    .some((item) => {
                        const portrait = item.text.includes("9:16")
                            || item.text.includes("portrait")
                            || item.text.includes("doc");
                        return portrait && (wanted.length === 0 || wanted.some((needle) => item.text.includes(needle)) || item.text.includes("9:16"));
                    });
            }""",
            {
                "labels": [
                    config.gemini_aspect_ratio,
                    config.gemini_aspect_label,
                    "Portrait (9:16)",
                    "Portrait",
                    "Dọc (9:16)",
                    "Dọc",
                ]
            },
        ))
    except Exception:
        return False


def _select_gemini_vertical_aspect(page, config: WrapTestConfig, prefix: str) -> None:
    """Set Gemini/Veo aspect ratio to vertical 9:16."""
    if _gemini_vertical_aspect_active(page, config):
        logger.info("  Gemini aspect ratio already looks vertical: %s", config.gemini_aspect_label)
        return

    if not _click_video_aspect_dropdown(page):
        _take_screenshot(page, config, f"{prefix}_aspect_selector_failed")
        raise RuntimeError("Could not open Gemini aspect-ratio selector")

    time.sleep(1)
    vertical_options = [
        config.gemini_aspect_label,
        f"Portrait ({config.gemini_aspect_ratio})",
        "Portrait (9:16)",
        "Dọc (9:16)",
        config.gemini_aspect_ratio,
        "Dọc",
        "Portrait",
        "9:16",
    ]
    if not (
        _click_exact_visible_text(
            page,
            vertical_options,
            selectors="[role='option'],[role='menuitem'],button,[role='button'],.cdk-overlay-pane *,.mat-mdc-menu-panel *",
            timeout=2000,
            label="vertical aspect",
        )
        or _click_video_aspect_option(page, vertical_options)
    ):
        _take_screenshot(page, config, f"{prefix}_aspect_vertical_failed")
        raise RuntimeError("Could not select vertical 9:16 aspect ratio")

    time.sleep(1)
    if not _gemini_vertical_aspect_active(page, config):
        _take_screenshot(page, config, f"{prefix}_aspect_vertical_failed")
        raise RuntimeError("Gemini aspect selector did not switch to 9:16")

    _take_screenshot(page, config, f"{prefix}_aspect_vertical")
    logger.info("  Selected vertical aspect ratio: %s", config.gemini_aspect_label)


def _process_gemini_scene(
    *,
    page,
    config: WrapTestConfig,
    scene_id: str,
    scene_index: int,
    veo_prompt: str,
    model_image: str,
    product_image: str,
) -> str:
    """Process one scene via Gemini chat UI.

    Flow:
      1. Start new chat (click "New chat" or navigate to gemini.google.com)
      2. Upload images via attachment button
      3. Type prompt into rich-text editor
      4. Send message
      5. Wait for Gemini to finish responding (look for video)
      6. Download video from response
    """
    prefix = f"scene_{scene_id}"

    # ─── Step 0: Start fresh chat for each scene ───
    _start_new_gemini_chat(page, config)
    time.sleep(2)
    _inject_stealth(page)
    _take_screenshot(page, config, f"{prefix}_01_new_chat")

    # ─── Step 1: Upload images ───
    _prepare_gemini_video_mode(page, config, prefix)
    _gemini_upload_images(page, config, scene_id, prefix, model_image, product_image)

    # ─── Step 2: Enter prompt ───
    _gemini_enter_prompt(page, config, scene_id, prefix, veo_prompt)

    # ─── Step 3: Send message ───
    _gemini_send_message(page, config, scene_id, prefix)

    # ─── Step 4: Wait for response with video ───
    _gemini_wait_for_video(page, config, scene_id, prefix)

    # ─── Step 5: Download video ───
    video_path = _gemini_download_video(page, config, scene_id, prefix)
    return video_path


def _start_new_gemini_chat(page, config: WrapTestConfig) -> None:
    """Navigate to a fresh Gemini chat to avoid context pollution."""
    # Method 1: Click "New chat" button
    new_chat_selectors = [
        'a[href="/app"]',                              # Gemini new chat link
        'button:has-text("New chat")',
        'button:has-text("Cuộc trò chuyện mới")',
        'button[aria-label*="New chat" i]',
        'button[aria-label*="new" i][aria-label*="chat" i]',
        '.new-chat-button',
        'a[aria-label*="New chat" i]',
        'mat-icon:text("add") >> xpath=..',            # Material icon "add"
    ]

    for selector in new_chat_selectors:
        try:
            btn = page.wait_for_selector(selector, timeout=3000, state="visible")
            if btn:
                btn.click()
                time.sleep(2)
                logger.debug("  Started new chat via: %s", selector)
                return
        except Exception:
            continue

    # Method 2: Navigate directly
    page.goto(config.gemini_veo_url, wait_until="domcontentloaded", timeout=30000)
    time.sleep(3)


def _gemini_upload_images(
    page, config: WrapTestConfig, scene_id: str, prefix: str,
    model_image: str, product_image: str,
) -> None:
    """Upload images to Gemini via the attachment/upload button."""

    images_to_upload = []
    if model_image and Path(model_image).exists():
        images_to_upload.append(model_image)
    if product_image and Path(product_image).exists():
        images_to_upload.append(product_image)

    if not images_to_upload:
        logger.warning("  No image files found. Skipping upload.")
        return

    # ─── Find and click the attachment/upload trigger button ───
    # Gemini has a "+" or attachment icon that opens a file picker
    upload_trigger_selectors = [
        'button:has-text("Tải tệp lên")',
        'div[role="menuitem"]:has-text("Tải tệp lên")',
        'button:has-text("Upload files")',
        'div[role="menuitem"]:has-text("Upload files")',
        'button:has-text("Upload")',
        'button[aria-label*="Upload" i]',
        'button[aria-label*="Tải lên" i]',
        'button[aria-label*="Add file" i]',
        'button[aria-label*="Thêm tệp" i]',
        'button[aria-label*="Attach" i]',
        'button[aria-label*="Đính kèm" i]',
        'button[aria-label*="image" i]',
        'button[aria-label*="Insert" i]',
        # Material icon buttons common in Gemini
        'button:has(mat-icon:text("add_photo_alternate"))',
        'button:has(mat-icon:text("attach_file"))',
        'button:has(mat-icon:text("add"))',
        'button:has(mat-icon:text("upload"))',
        # Generic icon selectors
        'button:has(span:text("add_photo_alternate"))',
        'button:has(span:text("upload_file"))',
        # Gemini-specific classes
        '.upload-button',
        '.attachment-button',
        'input-action-chip button',
    ]

    # First try: find a hidden file input directly (fastest, bypasses UI)
    file_input = _find_element(
        page,
        ['input[type="file"]', 'input[accept*="image"]'],
        timeout=3000, state="attached", label="file input",
    )

    if file_input:
        try:
            file_input.set_input_files(images_to_upload)
            time.sleep(3)
            _take_screenshot(page, config, f"{prefix}_02_images_uploaded")
            logger.info("  ✓ %d image(s) uploaded via file input", len(images_to_upload))
            return
        except Exception as e:
            logger.debug("  Direct file input failed: %s", e)

    # Second try: click upload trigger, then use the file chooser
    for selector in upload_trigger_selectors:
        try:
            btn = page.wait_for_selector(selector, timeout=2000, state="visible")
            if not btn:
                continue

            # Expect a file chooser dialog after clicking
            with page.expect_file_chooser(timeout=5000) as fc_info:
                btn.click()
            file_chooser = fc_info.value
            file_chooser.set_files(images_to_upload)
            time.sleep(3)
            _take_screenshot(page, config, f"{prefix}_02_images_uploaded")
            logger.info("  ✓ %d image(s) uploaded via %s", len(images_to_upload), selector)
            return
        except Exception:
            continue

    # Video mode has a large image-reference upload slot below the prompt.
    try:
        with page.expect_file_chooser(timeout=5000) as fc_info:
            if not _click_video_composer_upload_slot(page):
                raise RuntimeError("video composer upload slot not found")
        file_chooser = fc_info.value
        file_chooser.set_files(images_to_upload)
        time.sleep(3)
        _take_screenshot(page, config, f"{prefix}_02_images_uploaded")
        logger.info("  ✓ %d image(s) uploaded via video composer upload slot", len(images_to_upload))
        return
    except Exception as exc:
        logger.debug("  Video composer upload slot failed: %s", exc)

    # Gemini's video composer often hides upload behind the plus menu inside
    # the prompt box. Click that plus by geometry, then choose upload.
    if _click_plus_near_prompt_box(page):
        _take_screenshot(page, config, f"{prefix}_02_plus_menu_for_upload")
        upload_labels = ["Tải tệp lên", "Upload files", "Upload", "Upload image"]
        for _ in range(2):
            try:
                with page.expect_file_chooser(timeout=5000) as fc_info:
                    if not _click_visible_text(
                        page,
                        upload_labels,
                        selectors="button,[role='button'],[role='menuitem'],div,span",
                        timeout=3000,
                        label="upload menu item",
                    ):
                        break
                file_chooser = fc_info.value
                file_chooser.set_files(images_to_upload)
                time.sleep(3)
                _take_screenshot(page, config, f"{prefix}_02_images_uploaded")
                logger.info("  ✓ %d image(s) uploaded via plus menu", len(images_to_upload))
                return
            except Exception as exc:
                logger.debug("  Plus-menu upload failed: %s", exc)
                break

    # Third try: find file input that may have appeared after clicking something
    time.sleep(1)
    file_input = _find_element(
        page,
        ['input[type="file"]'],
        timeout=3000, state="attached", label="file input (retry)",
    )
    if file_input:
        try:
            file_input.set_input_files(images_to_upload)
            time.sleep(3)
            _take_screenshot(page, config, f"{prefix}_02_images_uploaded")
            logger.info("  ✓ %d image(s) uploaded via file input (retry)", len(images_to_upload))
            return
        except Exception as e:
            logger.warning("  File input retry failed: %s", e)

    logger.warning("  ⚠ Could not find upload mechanism. Continuing without images.")
    _take_screenshot(page, config, f"{prefix}_02_upload_failed")


def _gemini_enter_prompt(
    page, config: WrapTestConfig, scene_id: str, prefix: str,
    veo_prompt: str,
) -> None:
    """Type the VEO prompt into Gemini's rich text editor."""

    text_input = _wait_for_gemini_textbox(page, timeout=10000)

    if not text_input:
        _take_screenshot(page, config, f"{prefix}_03_no_input")
        raise RuntimeError(
            f"Could not find Gemini text input for {scene_id}. "
            "Check screenshot for current page state."
        )

    # Focus the input
    text_input.click()
    time.sleep(0.5)

    # Clear any existing text
    page.keyboard.press("Control+a")
    time.sleep(0.2)
    page.keyboard.press("Backspace")
    time.sleep(0.3)

    # ── Method 1: Use Clipboard paste (most reliable for contenteditable) ──
    try:
        page.evaluate(
            """(text) => {
                const input = document.activeElement;
                if (input) {
                    input.focus();
                    document.execCommand('insertText', false, text);
                    input.dispatchEvent(new InputEvent('input', {bubbles: true, inputType: 'insertText', data: text}));
                    input.dispatchEvent(new Event('change', {bubbles: true}));
                }
            }""",
            veo_prompt,
        )
        time.sleep(0.5)

        # Verify text was entered
        current_text = page.evaluate(
            """() => {
                const selectors = [
                    'rich-textarea div[contenteditable="true"]',
                    '.ql-editor[contenteditable="true"]',
                    'div[contenteditable="true"][role="textbox"]',
                    'div[contenteditable="true"]',
                    'textarea'
                ];
                const visible = (el) => {
                    const rect = el.getBoundingClientRect();
                    const style = window.getComputedStyle(el);
                    return rect.width > 0 && rect.height > 0
                        && style.visibility !== "hidden"
                        && style.display !== "none";
                };
                const el = selectors
                    .flatMap((selector) => Array.from(document.querySelectorAll(selector)))
                    .filter(visible)
                    .sort((a, b) => a.getBoundingClientRect().top - b.getBoundingClientRect().top)
                    .pop();
                return el ? (el.value || el.innerText || el.textContent || '') : '';
            }"""
        )
        if current_text and len(current_text.strip()) > 20:
            _take_screenshot(page, config, f"{prefix}_03_prompt_entered")
            logger.info("  ✓ Prompt entered via execCommand (%d chars)", len(veo_prompt))
            return
    except Exception as e:
        logger.debug("  execCommand method failed: %s", e)

    # ── Method 2: Clipboard paste via keyboard ──
    try:
        # Set clipboard content via JS
        page.evaluate(
            """async (text) => {
                await navigator.clipboard.writeText(text);
            }""",
            veo_prompt,
        )
        time.sleep(0.3)
        text_input.click()
        page.keyboard.press("Control+v")
        time.sleep(1)

        _take_screenshot(page, config, f"{prefix}_03_prompt_entered")
        logger.info("  ✓ Prompt entered via clipboard paste (%d chars)", len(veo_prompt))
        return
    except Exception as e:
        logger.debug("  Clipboard paste failed: %s", e)

    # ── Method 3: fill() for textarea elements ──
    try:
        tag = text_input.evaluate("el => el.tagName.toLowerCase()")
        if tag == "textarea":
            text_input.fill(veo_prompt)
        else:
            # For contenteditable, use type() as last resort
            text_input.type(veo_prompt, delay=2)
        time.sleep(1)
        _take_screenshot(page, config, f"{prefix}_03_prompt_entered")
        logger.info("  ✓ Prompt entered via fill/type (%d chars)", len(veo_prompt))
        return
    except Exception as e:
        logger.debug("  fill/type failed: %s", e)

    raise RuntimeError(f"All prompt entry methods failed for {scene_id}")


def _gemini_send_message(
    page, config: WrapTestConfig, scene_id: str, prefix: str,
) -> None:
    """Click the Send button in Gemini chat."""

    send_selectors = [
        'button[aria-label*="Send" i]',
        'button[aria-label*="Gửi" i]',
        'button[aria-label*="Submit" i]',
        'button:has(mat-icon:text("send"))',
        'button:has(mat-icon:text("arrow_upward"))',
        'button:has(span:text("send"))',
        '.send-button',
        'button.send-button',
        # Gemini's send is often the last enabled button in the input toolbar
        '.input-area-container button:last-of-type',
    ]

    send_btn = _find_send_button(page)
    if not send_btn:
        send_btn = _find_element(
            page, send_selectors, timeout=5000, state="visible", label="send button",
        )

    if send_btn:
        # Wait a moment for any image processing to complete
        time.sleep(1)
        try:
            send_btn.click()
        except Exception:
            # If click fails (e.g., overlay), try force click
            send_btn.click(force=True)
        time.sleep(2)
        _take_screenshot(page, config, f"{prefix}_04_sent")
        logger.info("  ✓ Message sent for %s", scene_id)
    else:
        # Fallback: press Enter
        logger.warning("  Send button not found, pressing Enter...")
        page.keyboard.press("Enter")
        time.sleep(2)
        _take_screenshot(page, config, f"{prefix}_04_enter_sent")


def _find_send_button(page):
    """Find Gemini's enabled send/submit button without hitting mic/model buttons."""
    try:
        handle = page.evaluate_handle(
            """() => {
                const strip = (text) => (text || "")
                    .normalize("NFD")
                    .replace(/[\\u0300-\\u036f]/g, "")
                    .replace(/đ/g, "d")
                    .replace(/Đ/g, "D")
                    .toLowerCase();
                const isVisible = (el) => {
                    const rect = el.getBoundingClientRect();
                    const style = window.getComputedStyle(el);
                    return rect.width > 0 && rect.height > 0
                        && style.visibility !== "hidden"
                        && style.display !== "none";
                };
                const bad = ["mic", "micro", "voice", "model", "flash", "upload", "attach", "them", "tai"];
                const good = ["send", "submit", "gui", "arrow_upward"];
                const buttons = Array.from(document.querySelectorAll("button,[role='button']"))
                    .filter((el) => isVisible(el) && !el.disabled && el.getAttribute("aria-disabled") !== "true");
                for (const el of buttons.reverse()) {
                    const text = strip(`${el.innerText || ""} ${el.textContent || ""} ${el.getAttribute("aria-label") || ""} ${el.getAttribute("title") || ""}`);
                    if (bad.some((needle) => text.includes(needle))) continue;
                    if (good.some((needle) => text.includes(needle))) return el;
                    const icon = strip(Array.from(el.querySelectorAll("mat-icon,span"))
                        .map((node) => node.textContent || "")
                        .join(" "));
                    if (icon.includes("send") || icon.includes("arrow_upward")) return el;
                }
                return null;
            }"""
        )
        return handle.as_element()
    except Exception:
        return None


def _gemini_wait_for_video(
    page, config: WrapTestConfig, scene_id: str, prefix: str,
) -> None:
    """Wait for Gemini to finish responding and produce a video."""
    logger.info("  Waiting for Gemini response + video (timeout: %ds)...", config.veo_timeout_sec)

    start_time = time.time()
    poll_interval = 8  # seconds
    last_screenshot_at = 0
    last_loading = False
    saw_limit_notice = False

    while time.time() - start_time < config.veo_timeout_sec:
        elapsed = int(time.time() - start_time)

        # ── Check if Gemini is still generating (loading indicator) ──
        is_loading = page.evaluate(
            """() => {
                // Check for loading/thinking indicators
                const loading = document.querySelector(
                    '.loading-indicator, .thinking-indicator, .response-loading, [aria-busy="true"], .model-response-loading, .generating'
                );
                // Also check if the stop button is visible (means still generating)
                const stopBtn = document.querySelector(
                    'button[aria-label*="Stop" i], button[aria-label*="Dừng" i]'
                );
                return !!(loading || (stopBtn && stopBtn.offsetParent !== null));
            }"""
        )
        last_loading = bool(is_loading)

        page_status = page.evaluate(
            """() => (document.body.innerText || "").slice(-2500)"""
        )
        normalized_status = _strip_accents(page_status)
        if "limit reached" in normalized_status and not saw_limit_notice:
            saw_limit_notice = True
            logger.warning(
                "  Gemini shows a limit notice; generation may be delayed or downgraded."
            )

        # ── Check for video element in the response ──
        has_video = page.evaluate(
            """() => {
                const videos = document.querySelectorAll('video');
                for (const v of videos) {
                    if (v.src || v.querySelector('source[src]')) return true;
                }
                // Also check for video preview/thumbnail images that indicate
                // a video was generated
                const videoCards = document.querySelectorAll(
                    '[data-video-id], .video-container, .video-preview'
                );
                if (videoCards.length > 0) return true;
                return false;
            }"""
        )

        if has_video:
            logger.info("  ✓ Video detected in response! (%ds)", elapsed)
            time.sleep(3)  # Let it fully render
            _take_screenshot(page, config, f"{prefix}_05_video_found")
            return

        # ── Check if response is complete but no video ──
        if not is_loading and elapsed > 30:
            # Response finished but no video found yet, check text response
            response_text = page.evaluate(
                """() => {
                    const responses = document.querySelectorAll(
                        '.model-response-text, .response-content, .message-content, [data-message-author-role="model"]'
                    );
                    const last = responses[responses.length - 1];
                    return last ? last.innerText.substring(0, 500) : '';
                }"""
            )
            if response_text:
                # Check if it mentions it can't generate video or has an error
                lower = response_text.lower()
                if any(w in lower for w in ["sorry", "can't", "unable", "không thể", "lỗi"]):
                    logger.warning("  Gemini declined: %s...", response_text[:200])
                    _take_screenshot(page, config, f"{prefix}_05_declined")
                    raise RuntimeError(f"Gemini declined video generation: {response_text[:200]}")

                # If there's a long response but no video, it might be text-only
                if elapsed > 60 and not has_video:
                    logger.warning("  Response complete but no video detected after %ds", elapsed)
                    _take_screenshot(page, config, f"{prefix}_05_no_video")
                    # Don't give up yet, keep waiting a bit more

        # ── Periodic screenshot ──
        if elapsed - last_screenshot_at >= 30:
            logger.info(
                "  Still waiting... %ds elapsed (loading=%s, limit_notice=%s)",
                elapsed,
                is_loading,
                saw_limit_notice,
            )
            _take_screenshot(page, config, f"{prefix}_waiting_{elapsed}s")
            last_screenshot_at = elapsed

        time.sleep(poll_interval)

    _take_screenshot(page, config, f"{prefix}_timeout")
    detail = ""
    if last_loading:
        detail = " Gemini was still generating when the timeout expired; increase VEO_TIMEOUT_SEC."
    if saw_limit_notice:
        detail += " Gemini also showed a limit notice for this account/session."
    raise TimeoutError(
        f"Video generation timed out after {config.veo_timeout_sec}s for {scene_id}.{detail}"
    )


def _gemini_download_video(
    page, config: WrapTestConfig, scene_id: str, prefix: str,
) -> str:
    """Download the generated video from Gemini's response."""

    target_path = config.veo_download_dir / f"{scene_id}_external.mp4"

    # ── Method 1: Find download/save button near the video ──
    download_selectors = [
        'button[aria-label*="Download" i]',
        'button[aria-label*="Tải xuống" i]',
        'button[aria-label*="Save" i]',
        'button[aria-label*="Lưu" i]',
        'button:has(mat-icon:text("download"))',
        'button:has(mat-icon:text("save_alt"))',
        'button:has(mat-icon:text("file_download"))',
        'button:has(span:text("download"))',
        'a[download]',
        '.download-button',
    ]

    for selector in download_selectors:
        try:
            btn = page.wait_for_selector(selector, timeout=3000, state="visible")
            if btn:
                with page.expect_download(timeout=60000) as dl_info:
                    btn.click()
                download = dl_info.value
                download.save_as(str(target_path))
                _take_screenshot(page, config, f"{prefix}_06_downloaded")
                logger.info("  ✓ Video downloaded via button: %s", target_path)
                return str(target_path)
        except Exception:
            continue

    # ── Method 2: Extract video src and download directly ──
    try:
        video_url = page.evaluate(
            """() => {
                const videos = document.querySelectorAll('video');
                for (const v of videos) {
                    if (v.src) return v.src;
                    const source = v.querySelector('source[src]');
                    if (source) return source.src;
                }
                return null;
            }"""
        )
        if video_url:
            logger.info("  Found video URL: %s...", video_url[:80])

            # If it's a blob URL, extract via fetch inside the page
            if video_url.startswith("blob:"):
                video_bytes = page.evaluate(
                    """async (url) => {
                        const resp = await fetch(url);
                        const blob = await resp.blob();
                        const buf = await blob.arrayBuffer();
                        return Array.from(new Uint8Array(buf));
                    }""",
                    video_url,
                )
                target_path.write_bytes(bytes(video_bytes))
                _take_screenshot(page, config, f"{prefix}_06_downloaded_blob")
                logger.info("  ✓ Video downloaded from blob: %s", target_path)
                return str(target_path)
            else:
                # Regular URL: download via API request
                response = page.request.get(video_url)
                if response.ok:
                    target_path.write_bytes(response.body())
                    _take_screenshot(page, config, f"{prefix}_06_downloaded_src")
                    logger.info("  ✓ Video downloaded from src: %s", target_path)
                    return str(target_path)
    except Exception as e:
        logger.warning("  Video src extraction failed: %s", e)

    # ── Method 3: Check system download dir for new files ──
    logger.info("  Checking download dir for new video files...")
    time.sleep(5)
    video_exts = {".mp4", ".mov", ".webm", ".mkv"}
    try:
        new_files = sorted(
            [f for f in config.veo_download_dir.iterdir()
             if f.is_file() and f.suffix.lower() in video_exts],
            key=lambda f: f.stat().st_mtime,
            reverse=True,
        )
        if new_files:
            newest = new_files[0]
            if newest != target_path:
                shutil.move(str(newest), str(target_path))
            logger.info("  ✓ Found downloaded video: %s", target_path)
            return str(target_path)
    except Exception:
        pass

    # ── Method 4: Try right-click save ──
    try:
        video_el = page.query_selector("video")
        if video_el:
            # Open video in new tab and download
            video_src = video_el.evaluate("el => el.src || (el.querySelector('source') || {}).src")
            if video_src and not video_src.startswith("blob:"):
                new_page = page.context.new_page()
                resp = new_page.goto(video_src)
                if resp and resp.ok:
                    target_path.write_bytes(resp.body())
                    new_page.close()
                    logger.info("  ✓ Video downloaded via new tab: %s", target_path)
                    return str(target_path)
                new_page.close()
    except Exception as e:
        logger.debug("  New tab download failed: %s", e)

    _take_screenshot(page, config, f"{prefix}_06_download_failed")
    raise RuntimeError(f"Could not download video for {scene_id}. Check screenshots.")


# =============================================================================
# 5. RESULT COLLECTOR
# =============================================================================

def collect_results(config: WrapTestConfig, veo_results: list[dict]) -> dict:
    """Collect and summarize all pipeline results."""

    summary = {
        "timestamp": datetime.now().isoformat(),
        "config": {
            "veo_url": config.gemini_veo_url,
            "llm_provider": config.llm_provider,
            "llm_model": config.llm_model_name,
        },
        "scenes_total": len(veo_results),
        "scenes_success": sum(1 for r in veo_results if r["status"] == "success"),
        "scenes_failed": sum(1 for r in veo_results if r["status"] != "success"),
        "results": veo_results,
        "output_dir": str(config.output_dir),
        "download_dir": str(config.veo_download_dir),
        "screenshot_dir": str(config.screenshot_dir),
    }

    # List screenshots
    screenshots = sorted(config.screenshot_dir.glob("*.png"))
    summary["screenshots"] = [str(s) for s in screenshots]

    # List downloaded videos
    videos = sorted(config.veo_download_dir.glob("*_external.*"))
    summary["videos"] = [str(v) for v in videos]

    # Save summary
    result_path = config.output_dir / "pipeline_result.json"
    result_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info("Pipeline result saved → %s", result_path)

    return summary


# =============================================================================
# 6. CLI INTERFACE
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Wrap Test - Gemini VEO Pipeline Test",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Steps:
  generate-script   Generate master_script.json from knowledge base via LLM
  build-prompts     Build VEO prompt queue from master script
  run-veo           Run browser automation to generate videos
  full              Run all steps (default)

Examples:
  python tests/wraptest.py                          # Full pipeline
  python tests/wraptest.py --step generate-script   # Only generate script
  python tests/wraptest.py --step run-veo           # Only run VEO automation
        """,
    )
    parser.add_argument(
        "--step",
        choices=["generate-script", "build-prompts", "run-veo", "full"],
        default="full",
        help="Which pipeline step to run (default: full)",
    )
    parser.add_argument(
        "--input",
        type=str,
        default=None,
        help="Override input.json path",
    )
    parser.add_argument(
        "--provider",
        choices=["gemini", "openai", "local"],
        default=None,
        help="Override LLM provider",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose/debug logging",
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Build config
    config = WrapTestConfig()

    # Apply CLI overrides
    if args.input:
        config.input_path = config._resolve(args.input)
    if args.provider:
        config.llm_provider = args.provider

    # Print config
    logger.info("\n%s", config.summary())

    step = args.step

    # ── Execute steps ──
    if step in ("generate-script", "full"):
        logger.info("═══ Step 1: Generate Master Script ═══")
        try:
            master_script = generate_master_script(config)
            logger.info(
                "Master script: %d scenes, %d playlists",
                len(master_script.get("scenes", [])),
                len(master_script.get("playlist", [])),
            )
        except Exception as exc:
            logger.error("Failed to generate master script: %s", exc)
            if step != "full":
                return 1

    if step in ("build-prompts", "full"):
        logger.info("═══ Step 2: Build Prompt Queue ═══")
        try:
            prompt_queue = build_prompt_queue(config)
            logger.info("Prompt queue: %d scenes ready", prompt_queue.get("total_scenes", 0))
        except Exception as exc:
            logger.error("Failed to build prompt queue: %s", exc)
            if step != "full":
                return 1

    if step in ("run-veo", "full"):
        logger.info("═══ Step 3: Run VEO Browser Automation ═══")
        try:
            veo_results = run_veo_browser_automation(config)
        except Exception as exc:
            logger.error("VEO automation failed: %s", exc)
            veo_results = []

        logger.info("═══ Step 4: Collect Results ═══")
        summary = collect_results(config, veo_results)

        # Print summary
        logger.info(
            "\n"
            "╔══════════════════════════════════════╗\n"
            "║       PIPELINE RESULT SUMMARY        ║\n"
            "╠══════════════════════════════════════╣\n"
            "║  Total scenes:    %3d                ║\n"
            "║  Success:         %3d                ║\n"
            "║  Failed:          %3d                ║\n"
            "║  Screenshots:     %3d                ║\n"
            "║  Videos:          %3d                ║\n"
            "╚══════════════════════════════════════╝",
            summary["scenes_total"],
            summary["scenes_success"],
            summary["scenes_failed"],
            len(summary["screenshots"]),
            len(summary["videos"]),
        )

    logger.info("Done! Output dir: %s", config.output_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
