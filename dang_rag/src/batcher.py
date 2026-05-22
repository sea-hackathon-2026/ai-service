"""
batcher.py — Đăng gom các comment có intent giống nhau vào 1 batch
để trả lời 1 script cho nhiều câu hỏi tương tự, tiết kiệm LLM call
"""

from collections import defaultdict
from .filter import ClassifiedComment, Intent

# Intent nào được gộp cùng nhau
BATCHABLE = {
    Intent.PRICE,
    Intent.FLAVOR,
    Intent.SHIPPING,
    Intent.PROMOTION,
    Intent.HEALTH,
    Intent.SHELF_LIFE,
    Intent.ORDER,
    Intent.RESTOCK,
    Intent.GENERAL,
}


"""
Gom comments theo intent, mỗi batch tối đa max_per_batch comment.
Trả về list các batch, mỗi batch là list ClassifiedComment.
Batch nào có score cao hơn sẽ được xử lý trước.
"""
def batch_comments(comments: list[ClassifiedComment], max_per_batch: int = 4,) -> list[list[ClassifiedComment]]:
    groups: dict[Intent, list[ClassifiedComment]] = defaultdict(list)

    for c in comments:
        if c.intent in BATCHABLE:
            groups[c.intent].append(c)

    # Chia group lớn thành nhiều batch nhỏ
    batches: list[list[ClassifiedComment]] = []
    for intent_group in groups.values():
        for i in range(0, len(intent_group), max_per_batch):
            batches.append(intent_group[i : i + max_per_batch])

    # Sắp xếp batch theo score cao nhất trong batch (priority queue)
    batches.sort(key=lambda b: max(c.score for c in b), reverse=True)

    return batches
