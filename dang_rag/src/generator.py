import json
import os
import time

from dataclasses import dataclass
from openai import OpenAI
from .filter import ClassifiedComment, Intent


EMOTION_MAP: dict[Intent, str] = {
    Intent.PRICE:      "friendly",
    Intent.FLAVOR:     "enthusiastic",
    Intent.SHIPPING:   "helpful",
    Intent.PROMOTION:  "excited",
    Intent.HEALTH:     "caring",
    Intent.SHELF_LIFE: "informative",
    Intent.ORDER:      "encouraging",
    Intent.RESTOCK:    "empathetic",
    Intent.GENERAL:    "friendly",
    Intent.NOISE:      "neutral",
}

CTA_MAP: dict[Intent, str] = {
    Intent.PRICE:      "mention_order",
    Intent.FLAVOR:     "suggest_try",
    Intent.SHIPPING:   "confirm_order",
    Intent.PROMOTION:  "buy_now",
    Intent.HEALTH:     "reassure_buy",
    Intent.SHELF_LIFE: "mention_order",
    Intent.ORDER:      "direct_order",
    Intent.RESTOCK:    "notify_me",
    Intent.GENERAL:    "engage",
    Intent.NOISE:      "none",
}

SYSTEM_PROMPT = """Bạn là MC livestream bán hàng chuyên nghiệp, nhiệt tình và thân thiện.
Nhiệm vụ: trả lời các câu hỏi của khách hàng trong buổi livestream bán mỹ phẩm và sản phẩm chăm sóc da, tóc của Cocoon

Quy tắc:
- Giọng nói tự nhiên, gần gũi như đang nói chuyện trực tiếp
- Ngắn gọn, súc tích (tối đa 3-4 câu)
- Dùng ngôn ngữ tiếng Việt bình dân, có thể thêm "dạ", "ạ", "nha"
- Luôn kết thúc bằng 1 câu khuyến khích hành động (mua hàng, inbox, comment SĐT)
- KHÔNG bịa thông tin, chỉ dùng thông tin được cung cấp
- KHÔNG dùng emoji trong script (để TTS đọc được)

Trả về JSON theo đúng format sau, không thêm gì khác:
{
  "text": "<script trả lời>",
  "emotion": "<friendly|enthusiastic|helpful|excited|caring|informative|encouraging|empathetic>",
  "cta": "<buy_now|mention_order|suggest_try|confirm_order|reassure_buy|direct_order|notify_me|engage|none>",
  "confidence": <0.0-1.0>
}"""


@dataclass
class ScriptOutput:
    text:            str
    emotion:         str
    cta:             str
    intent:          str
    confidence:      float
    source_comments: list[str]
    latency_ms:      int


class ScriptGenerator:
    def __init__(self, api_key: str | None = None, model: str = "gpt-4o-mini"):
        self.client = OpenAI(api_key=api_key or os.environ["OPENAI_API_KEY"])
        self.model  = model

    def _build_user_prompt(
        self,
        comments: list[ClassifiedComment],
        docs: list[dict],
    ) -> str:
        comment_block = "\n".join(
            f"- [{c.intent.value}] {c.comment}" for c in comments
        )
        doc_block = "\n".join(f"[{d['tag']}] {d['text']}" for d in docs)

        return f"""=== CÂU HỎI TỪ KHÁN GIẢ ===
{comment_block}

=== THÔNG TIN SẢN PHẨM ===
{doc_block}

Hãy tạo script trả lời tổng hợp cho các câu hỏi trên."""

    def generate(self, comments: list[ClassifiedComment], docs: list[dict],) -> ScriptOutput:
        # Gọi OpenAI, trả về ScriptOutput đầy đủ.
        t0 = time.time()

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": self._build_user_prompt(comments, docs)},
            ],
            temperature=0.7,
            max_tokens=400,
            response_format={"type": "json_object"},
        )

        latency_ms = int((time.time() - t0) * 1000)
        raw        = response.choices[0].message.content
        parsed     = json.loads(raw)

        # Fallback nếu LLM trả thiếu field
        dominant_intent = comments[0].intent if comments else Intent.GENERAL
        emotion  = parsed.get("emotion",    EMOTION_MAP.get(dominant_intent, "friendly"))
        cta      = parsed.get("cta",        CTA_MAP.get(dominant_intent, "engage"))
        confidence = float(parsed.get("confidence", 0.8))

        return ScriptOutput(
            text=parsed.get("text", ""),
            emotion=emotion,
            cta=cta,
            intent=dominant_intent.value,
            confidence=confidence,
            source_comments=[c.comment for c in comments],
            latency_ms=latency_ms,
        )
