"""
CLI Runner — Interactive terminal chat with the Sales Closing Agent.

Chạy trực tiếp từ trong folder agent-sales/:
    cd agent-sales
    python run_cli.py

Hoặc từ folder cha:
    python agent-sales/run_cli.py

Yêu cầu:
    pip install google-adk python-dotenv
    GOOGLE_API_KEY phải được set trong file .env
"""

from __future__ import annotations

import sys
import uuid
import asyncio
import os
from pathlib import Path
from google.adk.runners import Runner
from google.adk.models import registry
from google.adk.models.lite_llm import LiteLlm

# Đăng ký LiteLLM để fallback không bị lỗi Model Not Found
registry.LLMRegistry._register(r"^groq/.*", LiteLlm)
registry.LLMRegistry._register(r"^openrouter/.*", LiteLlm)
registry.LLMRegistry._register(r"^huggingface/.*", LiteLlm)

# ── Resolve paths ─────────────────────────────────────────────────────
_THIS_DIR = Path(__file__).resolve().parent
_PARENT_DIR = _THIS_DIR.parent

# Add parent to sys.path so "agent-sales" is findable by ADK
if str(_PARENT_DIR) not in sys.path:
    sys.path.insert(0, str(_PARENT_DIR))

# ── Load .env ─────────────────────────────────────────────────────────
from dotenv import load_dotenv

# Try loading from agent-sales/.env first, then parent .env
load_dotenv(_THIS_DIR / ".env")
load_dotenv(_PARENT_DIR / ".env", override=False)

# Verify API key
api_key = os.environ.get("GOOGLE_API_KEY", "")
if not api_key:
    # Fallback: try GEMINI_API_KEY from parent project
    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    if gemini_key:
        os.environ["GOOGLE_API_KEY"] = gemini_key
        api_key = gemini_key

if not api_key:
    print("❌ ERROR: GOOGLE_API_KEY chưa được set!")
    print("   Tạo file .env trong folder agent-sales/ với nội dung:")
    print("   GOOGLE_API_KEY=your-api-key-here")
    print()
    print("   Hoặc lấy key tại: https://aistudio.google.com/apikey")
    sys.exit(1)

# ── Import ADK components ────────────────────────────────────────────
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

# ── Import agent (handle hyphenated folder name) ─────────────────────
# ADK uses the folder as a Python package. Since "agent-sales" has a
# hyphen we must manually load it.
import importlib.util


def _load_agent():
    """Load the agent module from the current directory."""
    # 1. Load tools module
    tools_spec = importlib.util.spec_from_file_location(
        "agent_sales.tools",
        _THIS_DIR / "tools.py",
    )
    tools_mod = importlib.util.module_from_spec(tools_spec)
    sys.modules["agent_sales.tools"] = tools_mod
    tools_spec.loader.exec_module(tools_mod)

    # 2. Create package
    pkg_spec = importlib.util.spec_from_file_location(
        "agent_sales",
        _THIS_DIR / "__init__.py",
        submodule_search_locations=[str(_THIS_DIR)],
    )
    pkg_mod = importlib.util.module_from_spec(pkg_spec)
    pkg_mod.tools = tools_mod
    sys.modules["agent_sales"] = pkg_mod

    # 3. Load agent module
    agent_spec = importlib.util.spec_from_file_location(
        "agent_sales.agent",
        _THIS_DIR / "agent.py",
    )
    agent_mod = importlib.util.module_from_spec(agent_spec)
    sys.modules["agent_sales.agent"] = agent_mod
    agent_spec.loader.exec_module(agent_mod)
    pkg_mod.agent = agent_mod

    return agent_mod.root_agent


# ── Main ─────────────────────────────────────────────────────────────
async def main() -> None:
    """Run an interactive CLI chat session with the sales agent."""

    print("⏳ Đang khởi tạo Sales Agent...")
    agent = _load_agent()
    print(f"✅ Agent '{agent.name}' loaded with tools: "
          f"{[t.__name__ for t in agent.tools]}")

    session_service = InMemorySessionService()
    runner = Runner(
        agent=agent,
        app_name="sales_closing_agent",
        session_service=session_service,
    )
    
    fallback_runner = None
    try:
        from google.adk.agents import Agent
        from agent_sales import tools
        
        # Ưu tiên HuggingFace -> OpenRouter -> Groq
        hf_key = os.environ.get("HUGGINGFACE_API_KEY") or os.environ.get("HUGGING_FACE_API_KEY") or os.environ.get("HF_TOKEN")
        if hf_key:
            os.environ["HUGGINGFACE_API_KEY"] = hf_key
            fallback_model = "huggingface/deepseek-ai/DeepSeek-V4-Pro:together"
        elif os.environ.get("OPENROUTER_API_KEY"):
            fallback_model = "openrouter/deepseek/deepseek-v4-flash:free"
        else:
            fallback_model = "groq/llama-3.3-70b-versatile"
        
        fallback_agent = Agent(
            name="sales_closing_agent_fallback",
            model=fallback_model,
            description=agent.description,
            instruction=agent.instruction,
            tools=[tools.save_order_info, tools.get_order_status, tools.confirm_order],
        )
        fallback_runner = Runner(
            agent=fallback_agent,
            app_name="sales_closing_agent",
            session_service=session_service,
        )
        
        # Bỏ qua Gemini, ưu tiên dùng luôn fallback
        runner = fallback_runner
        fallback_runner = None
        print(f"✅ Bỏ qua Gemini, ưu tiên dùng model: {fallback_model}")
    except Exception as e:
        print(f"⚠️ Không thể khởi tạo Fallback: {e}")

    user_id = "cli_user"

    # Create initial session
    session = await session_service.create_session(
        app_name="sales_closing_agent",
        user_id=user_id,
    )
    session_id = session.id

    print()
    print("=" * 60)
    print("🛍️  SALES CLOSING AGENT — Trợ lý chốt đơn hàng")
    print("=" * 60)
    print("💬 Nhập tin nhắn để chat với agent.")
    print("📝 Thử nói: 'em muốn mua' để bắt đầu flow chốt đơn.")
    print("🔄 Gõ 'reset' để bắt đầu phiên mới.")
    print("🚪 Gõ 'quit' hoặc Ctrl+C để thoát.")
    print("-" * 60)

    while True:
        try:
            user_input = input("\n👤 Bạn: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\n👋 Tạm biệt!")
            break

        if not user_input:
            continue

        if user_input.lower() in ("quit", "exit", "q"):
            print("\n👋 Tạm biệt! Cảm ơn bạn đã ghé thăm!")
            break

        if user_input.lower() == "reset":
            session = await session_service.create_session(
                app_name="sales_closing_agent",
                user_id=user_id,
            )
            session_id = session.id
            print("🔄 Đã reset phiên chat. Bắt đầu cuộc hội thoại mới!")
            continue

        # Package user message
        content = types.Content(
            role="user",
            parts=[types.Part(text=user_input)],
        )

        # Run the agent and collect response
        print("\n🤖 Agent: ", end="", flush=True)

        response_text = ""
        try:
            async for event in runner.run_async(
                user_id=user_id,
                session_id=session_id,
                new_message=content,
            ):
                # Only print final response text (skip tool calls)
                if event.content and event.content.parts:
                    if event.is_final_response():
                        for part in event.content.parts:
                            if part.text:
                                response_text += part.text
                                print(part.text, end="", flush=True)

        except Exception as e:
            error_msg = str(e)
            if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
                print(f"\n⚠️  Gemini API đã hết quota (429).")
                hf_keys_exist = os.environ.get("HUGGINGFACE_API_KEY") or os.environ.get("HUGGING_FACE_API_KEY") or os.environ.get("HF_TOKEN")
                has_fallback_keys = bool(hf_keys_exist or os.environ.get("OPENROUTER_API_KEY") or os.environ.get("GROQ_API_KEY"))
                if fallback_runner and has_fallback_keys:
                    print("🔄 Tự động chuyển đổi sang Fallback Agent...")
                    try:
                        print("\n🤖 Agent (Fallback): ", end="", flush=True)
                        async for event in fallback_runner.run_async(
                            user_id=user_id,
                            session_id=session_id,
                            new_message=content,
                        ):
                            if event.content and event.content.parts and event.is_final_response():
                                for part in event.content.parts:
                                    if part.text:
                                        response_text += part.text
                                        print(part.text, end="", flush=True)
                    except Exception as fallback_e:
                        print(f"\n❌ Lỗi Fallback: {fallback_e}")
                else:
                    print("   Không tìm thấy HUGGINGFACE_API_KEY, OPENROUTER_API_KEY hoặc GROQ_API_KEY. Vui lòng thiết lập để sử dụng fallback.")
            elif "403" in error_msg or "PERMISSION_DENIED" in error_msg:
                print(f"\n❌ API key không hợp lệ! Kiểm tra lại GOOGLE_API_KEY trong .env")
            else:
                print(f"\n❌ Lỗi: {e}")

        if not response_text and not any(
            x in str(locals().get("e", "")) for x in ["429", "403"]
        ):
            print("(Không có phản hồi)")

        print()  # newline after response


if __name__ == "__main__":
    asyncio.run(main())
