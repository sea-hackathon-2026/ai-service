import re

from dataclasses import dataclass
from enum import Enum

class Intent(str, Enum):
    PRICE       = "price"           # hỏi giá
    FLAVOR      = "flavor"          # hỏi vị / loại
    SHIPPING    = "shipping"        # hỏi ship
    PROMOTION   = "promotion"       # hỏi khuyến mãi / giảm giá
    HEALTH      = "health"          # hỏi sức khỏe / thành phần
    SHELF_LIFE  = "shelf_life"      # hỏi hạn dùng
    ORDER       = "order"           # hỏi cách đặt hàng
    RESTOCK     = "restock"         # hỏi khi nào có hàng
    GENERAL     = "general"         # câu hỏi chung
    NOISE       = "noise"           # spam / emoji / không liên quan


@dataclass
class ClassifiedComment:
    timestamp: str
    comment: str
    intent: Intent
    score: float         # score cho việc ưu tiên trả lời
    should_answer: bool


# --- Rule-based patterns ---

NOISE_PATTERNS = [
    r"^[😀-🙏🌀-🗿🚀-🛿🇦-🇿✂-➰Ⓜ-🉑]+$",   # toàn emoji
    r"^[k]+$",                                        # kkkkk
    r"^\?+$",                                         # ???
    r"^[.]+$",                                        # ...
    r"^\w{1,3}$",                                     # quá ngắn (như ad ơi, ok)
]

INTENT_PATTERNS: dict[Intent, list[str]] = {
    Intent.PRICE:      [r"giá", r"bao nhiêu tiền", r"bao nhiêu", r"mấy tiền", r"mắc không", r"rẻ không"],
    Intent.FLAVOR:     [r"mấy vị", r"có vị", r"hương vị", r"loại nào", r"màu gì"],
    Intent.SHIPPING:   [r"ship", r"giao hàng", r"vận chuyển", r"miền", r"tỉnh", r"hà nội", r"hcm", r"sài gòn"],
    Intent.PROMOTION:  [r"giảm giá", r"khuyến mãi", r"sale", r"combo", r"mua \d+", r"tặng", r"discount"],
    Intent.HEALTH:     [r"tiểu đường", r"gluten", r"thành phần", r"bầu", r"mang thai", r"trẻ em", r"dị ứng",
                        r"an toàn", r"phù hợp", r"chứa", r"calo", r"hàm lượng đường", 
                        r"nhạy cảm", r"da dầu", r"da khô", r"da mụn", r"kích ứng", r"lành tính"],
    Intent.SHELF_LIFE: [r"hạn sử dụng", r"hạn dùng", r"date", r"bảo quản"],
    Intent.ORDER:      [r"order", r"đặt hàng", r"mua ở đâu", r"link", r"inbox"],
    Intent.RESTOCK:    [r"bao giờ có", r"hết hàng", r"khi nào có", r"còn hàng không"],
}

# Score ưu tiên theo intent (cao hơn = trả lời trước)
INTENT_PRIORITY: dict[Intent, float] = {
    Intent.ORDER:      1.0,
    Intent.PRICE:      0.9,
    Intent.PROMOTION:  0.85,
    Intent.HEALTH:     0.85,
    Intent.SHIPPING:   0.8,
    Intent.FLAVOR:     0.75,
    Intent.SHELF_LIFE: 0.7,
    Intent.RESTOCK:    0.65,
    Intent.GENERAL:    0.4,
    Intent.NOISE:      0.0,
}

ANSWER_THRESHOLD = 0.5   # score thấp hơn này thì bỏ qua


def _is_noise(text: str) -> bool:
    text = text.strip()
    for pattern in NOISE_PATTERNS:
        if re.fullmatch(pattern, text, re.UNICODE):
            return True
    if len(text) <= 3:
        return True

    emoji_count = sum(1 for c in text if ord(c) > 127)
    if len(text) > 0 and emoji_count / len(text) > 0.7:
        return True
    return False


def _classify_intent(text: str) -> Intent:
    text_lower = text.lower()
    for intent, patterns in INTENT_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text_lower):
                return intent
    return Intent.GENERAL


def classify_comment(timestamp: str, comment: str) -> ClassifiedComment:
    """Phân loại 1 comment, trả về ClassifiedComment."""
    if _is_noise(comment):
        return ClassifiedComment(
            timestamp=timestamp,
            comment=comment,
            intent=Intent.NOISE,
            score=0.0,
            should_answer=False,
        )

    intent = _classify_intent(comment)
    score  = INTENT_PRIORITY[intent]

    return ClassifiedComment(
        timestamp=timestamp,
        comment=comment,
        intent=intent,
        score=score,
        should_answer=score >= ANSWER_THRESHOLD,
    )


"""
Nhận list raw comment [{timestamp, comment}],
trả về list đã classify, chỉ giữ những cái should_answer=True,
sắp xếp theo score giảm dần.
"""
def filter_comments(raw: list[dict]) -> list[ClassifiedComment]:
    classified = [classify_comment(r["timestamp"], r["comment"]) for r in raw]
    worthy     = [c for c in classified if c.should_answer]
    worthy.sort(key=lambda c: c.score, reverse=True)
    return worthy
