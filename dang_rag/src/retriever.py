"""
retriever.py — RAG retrieval từ product knowledge base
Dùng keyword matching + TF-IDF đơn giản, không cần vector DB
→ latency <10ms, phù hợp real-time livestream
"""

import json
import math
import re

from pathlib import Path
from typing import Any


def _load_kb(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _kb_to_chunks(kb: dict) -> list[dict[str, str]]:
    """Chuyển knowledge base JSON thành list các text chunk có nhãn."""
    chunks = []

    def add(tag: str, text: str):
        chunks.append({"tag": tag, "text": text.strip()})

    # Thông tin cơ bản
    add("product_info",
        f"Sản phẩm: {kb['product_name']}. {kb['description']}")

    # Vị 
    products = kb.get("products", [])
    product_names = ", ".join(p["name"] for p in products)
    add(
        "flavor",
        f"Các sản phẩm hiện có gồm: {product_names}."
    )

    # Giá
    pricing = kb.get("pricing", {})
    price_lines = []
    for pid, item in pricing.items():
        line = (
            f"{item['name']}: "
            f"giá livestream {item.get('livestream_price', item.get('single', 0)):,}đ"
        )
        if item.get("promotion"):
            line += f". {item['promotion']}"
        price_lines.append(line)
    add("pricing", " | ".join(price_lines))

    # Giao hàng
    s = kb["shipping"]
    add(
        "shipping",
        f"{s['coverage']}. "
        f"TP.HCM: {s['fee_hcm']}, giao {s['estimated_days_hcm']}. "
        f"Hà Nội: {s['fee_hanoi']}, giao {s['estimated_days_hanoi']}. "
        f"Tỉnh khác: {s['fee_other']}, giao {s['estimated_days_other']}."
    )

    # Sức khỏe
    h = kb["health_notes"]
    add(
        "health",
        f"{h['general']} "
        f"Phụ nữ mang thai: {h['pregnant']} "
        f"Trẻ em: {h['children']} "
        f"{h['sensitive_skin']} "
        f"{h['gluten_free']}"
        f"{h['preservatives']}"
    )
    
    # Hạn sử dụng
    sl = kb["shelf_life"]
    add(
        "shelf_life",
        f"Thời hạn sử dụng sản phẩm: "
        f"{sl.get('SP001', '')} "
        f"{sl.get('storage', '')}"
    )

    # Đặt hàng
    add("order", f"Cách đặt hàng: {kb['how_to_order']}.")

    # Hàng tồn / chứng nhận
    certs = ", ".join(kb.get("certifications", []))
    add("certifications", f"Chứng nhận: {certs}.")

    # FAQ
    for item in kb.get("faq", []):
        add("faq", f"Hỏi: {item['q']} — Trả lời: {item['a']}")

    return chunks


class KnowledgeRetriever:
    def __init__(self, kb_path: str):
        kb          = _load_kb(kb_path)
        self.chunks = _kb_to_chunks(kb)
        self.kb_raw = kb
        self._build_index()

    # --- TF-IDF đơn giản ---

    def _tokenize(self, text: str) -> list[str]:
        text = text.lower()
        text = re.sub(r"[^\w\s]", " ", text)
        return text.split()

    def _build_index(self):
        N = len(self.chunks)
        # df: document frequency của mỗi token
        df: dict[str, int] = {}
        self._doc_tokens: list[list[str]] = []
        for chunk in self.chunks:
            tokens = set(self._tokenize(chunk["text"]))
            self._doc_tokens.append(list(tokens))
            for t in tokens:
                df[t] = df.get(t, 0) + 1
        # idf
        self._idf = {t: math.log((N + 1) / (v + 1)) for t, v in df.items()}

    def _score(self, query_tokens: list[str], doc_idx: int) -> float:
        doc_set = set(self._doc_tokens[doc_idx])
        return sum(self._idf.get(t, 0) for t in query_tokens if t in doc_set)

    def retrieve(self, query: str, top_k: int = 3) -> list[dict[str, str]]:
        """Trả về top_k chunk liên quan nhất với query."""
        q_tokens = self._tokenize(query)
        if not q_tokens:
            return []
        scores = [(i, self._score(q_tokens, i)) for i in range(len(self.chunks))]
        scores.sort(key=lambda x: x[1], reverse=True)
        results = []
        for idx, score in scores[:top_k]:
            if score > 0:
                results.append({
                    "tag":   self.chunks[idx]["tag"],
                    "text":  self.chunks[idx]["text"],
                    "score": round(score, 3),
                })
        return results

    def get_product_name(self) -> str:
        return self.kb_raw.get("product_name", "sản phẩm")
