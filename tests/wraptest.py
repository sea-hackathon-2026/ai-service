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
        )
        self.chrome_user_data_dir: str = os.getenv("CHROME_USER_DATA_DIR", "")
        self.chrome_executable_path: str = os.getenv("CHROME_EXECUTABLE_PATH", "")
        self.veo_download_dir: Path = self._resolve(
            os.getenv("VEO_DOWNLOAD_DIR", "./data/outputs/veo_downloads")
        )
        self.veo_timeout_sec: int = int(os.getenv("VEO_TIMEOUT_SEC", "600"))
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
            f"  LLM Provider:   {self.llm_provider}\n"
            f"  LLM Model:      {self.llm_model_name}\n"
            f"  Input:          {self.input_path}\n"
            f"  Output:         {self.output_dir}\n"
            f"  Downloads:      {self.veo_download_dir}\n"
            f"  Screenshots:    {self.screenshot_dir}\n"
            f"  VEO Timeout:    {self.veo_timeout_sec}s\n"
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
    input_data = config.load_input()

    model_image = input_data.get("model_image_resolved", "")
    product_image = input_data.get("product_image_resolved", "")

    results = []

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


def _wait_for_gemini_ready(page, timeout: int = 30000) -> None:
    """Wait until Gemini chat UI is interactable."""
    # Gemini's input area selectors (try multiple patterns)
    input_selectors = [
        '.ql-editor',                                  # Quill editor
        'div[contenteditable="true"]',                 # Generic contenteditable
        'rich-textarea div[contenteditable="true"]',   # Gemini rich textarea
        '.input-area-container [contenteditable]',     # Input area
        'div[role="textbox"]',                         # ARIA textbox
        '.ProseMirror',                                # ProseMirror editor
        'textarea[aria-label]',                        # Fallback textarea
    ]

    for selector in input_selectors:
        try:
            page.wait_for_selector(selector, timeout=timeout, state="visible")
            logger.debug("Gemini ready: found input via %s", selector)
            return
        except Exception:
            continue

    # Last resort: just wait and hope
    logger.warning("Could not detect Gemini input area, waiting 10s...")
    time.sleep(10)


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

    # Gemini uses various rich text editor implementations
    input_selectors = [
        'rich-textarea div[contenteditable="true"]',   # Gemini-specific
        '.ql-editor[contenteditable="true"]',          # Quill editor
        'div[contenteditable="true"][role="textbox"]',  # ARIA textbox
        'div[contenteditable="true"][aria-label]',     # Labeled contenteditable
        '.ProseMirror[contenteditable="true"]',        # ProseMirror
        'div[contenteditable="true"]',                 # Generic contenteditable
        'textarea',                                     # Fallback textarea
    ]

    text_input = _find_element(
        page, input_selectors, timeout=10000, state="visible", label="text input",
    )

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
                // Use execCommand insertText for contenteditable
                const input = document.querySelector(
                    'rich-textarea div[contenteditable="true"],'
                    '.ql-editor[contenteditable="true"],'
                    'div[contenteditable="true"][role="textbox"],'
                    'div[contenteditable="true"]'
                );
                if (input) {
                    input.focus();
                    // Try insertText first (triggers input events properly)
                    document.execCommand('insertText', false, text);
                }
            }""",
            veo_prompt,
        )
        time.sleep(0.5)

        # Verify text was entered
        current_text = page.evaluate(
            """() => {
                const el = document.querySelector(
                    'rich-textarea div[contenteditable="true"],'
                    '.ql-editor[contenteditable="true"],'
                    'div[contenteditable="true"][role="textbox"],'
                    'div[contenteditable="true"]'
                );
                return el ? el.innerText : '';
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


def _gemini_wait_for_video(
    page, config: WrapTestConfig, scene_id: str, prefix: str,
) -> None:
    """Wait for Gemini to finish responding and produce a video."""
    logger.info("  Waiting for Gemini response + video (timeout: %ds)...", config.veo_timeout_sec)

    start_time = time.time()
    poll_interval = 8  # seconds
    last_screenshot_at = 0

    while time.time() - start_time < config.veo_timeout_sec:
        elapsed = int(time.time() - start_time)

        # ── Check if Gemini is still generating (loading indicator) ──
        is_loading = page.evaluate(
            """() => {
                // Check for loading/thinking indicators
                const loading = document.querySelector(
                    '.loading-indicator, .thinking-indicator, '
                    '.response-loading, [aria-busy="true"], '
                    '.model-response-loading, .generating'
                );
                // Also check if the stop button is visible (means still generating)
                const stopBtn = document.querySelector(
                    'button[aria-label*="Stop" i], '
                    'button[aria-label*="Dừng" i]'
                );
                return !!(loading || (stopBtn && stopBtn.offsetParent !== null));
            }"""
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
                        '.model-response-text, .response-content, '
                        '.message-content, [data-message-author-role="model"]'
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
            logger.info("  Still waiting... %ds elapsed (loading=%s)", elapsed, is_loading)
            _take_screenshot(page, config, f"{prefix}_waiting_{elapsed}s")
            last_screenshot_at = elapsed

        time.sleep(poll_interval)

    _take_screenshot(page, config, f"{prefix}_timeout")
    raise TimeoutError(f"Video generation timed out after {config.veo_timeout_sec}s for {scene_id}")


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
