import argparse
import json
import os
import sys
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.filter    import filter_comments
from src.retriever import KnowledgeRetriever
from src.batcher   import batch_comments
from src.generator import ScriptGenerator

from dotenv import load_dotenv
load_dotenv()


BASE_DIR   = Path(__file__).parent
KB_PATH    = BASE_DIR / "data" / "knowledge_base.json"
INPUT_PATH = BASE_DIR / "data" / "comments.json"
OUT_PATH   = BASE_DIR / "data" / "output.json"


def _print_banner(msg: str):
    print(f"\n{'─'*60}")
    print(f"  {msg}")
    print(f"{'─'*60}")


def _print_step(step: str, detail: str = ""):
    ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"[{ts}] {step}" + (f"  →  {detail}" if detail else ""))


def run_pipeline(
    input_path: Path,
    kb_path: Path,
    output_path: Path,
    dry_run: bool = False,
    model: str = "gpt-4o-mini",
    verbose: bool = True,
) -> list[dict]:
    """
    Full pipeline: JSON comments → list script output JSON

    Returns:
        List of script output dicts
    """
    t_total = time.time()

    # 1. Load input 
    _print_banner("BƯỚC 1 — Load comments")
    with open(input_path, encoding="utf-8") as f:
        raw_comments: list[dict] = json.load(f)
    _print_step(f"Đọc được {len(raw_comments)} comment từ {input_path.name}")

    if verbose:
        for c in raw_comments:
            print(f"  • [{c['timestamp']}] {c['comment']}")

    # 2. Filter & Classify 
    _print_banner("BƯỚC 2 — Filter & Classify")
    t0 = time.time()
    worthy = filter_comments(raw_comments)
    ms_filter = int((time.time() - t0) * 1000)

    noise_count = len(raw_comments) - len(worthy)
    _print_step(f"Loại bỏ {noise_count} comment nhiễu ({ms_filter}ms)")
    _print_step(f"Còn lại {len(worthy)} comment đáng trả lời:")

    if verbose:
        for c in worthy:
            print(f"  • [{c.intent.value:12s}] score={c.score:.2f}  \"{c.comment}\"")

    # 3. Load Knowledge Base
    _print_banner("BƯỚC 3 — Load Knowledge Base")
    retriever = KnowledgeRetriever(str(kb_path))
    _print_step(f"Loaded KB: {retriever.get_product_name()}")

    # 4. Batch comments
    _print_banner("BƯỚC 4 — Batch by Intent")
    batches = batch_comments(worthy)
    _print_step(f"Tạo {len(batches)} batch để xử lý")

    if verbose:
        for i, batch in enumerate(batches, 1):
            intent = batch[0].intent.value
            comments_preview = " | ".join(f'"{c.comment[:30]}…"' if len(c.comment) > 30 else f'"{c.comment}"' for c in batch)
            print(f"  Batch {i} [{intent}]: {comments_preview}")

    # 5. RAG + LLM cho từng batch
    _print_banner("BƯỚC 5 — RAG Retrieval + LLM Generation")

    if dry_run:
        print("  [DRY RUN] Bỏ qua bước gọi LLM")
        outputs = []
        for i, batch in enumerate(batches, 1):
            query = " ".join(c.comment for c in batch)
            docs  = retriever.retrieve(query, top_k=3)
            print(f"\n  Batch {i} — intent: {batch[0].intent.value}")
            print(f"    Query: {query[:80]}…")
            print(f"    Retrieved docs:")
            for d in docs:
                print(f"      [{d['tag']}] {d['text'][:80]}…  (score={d['score']})")
        return outputs

    generator = ScriptGenerator(model=model)
    outputs   = []

    for i, batch in enumerate(batches, 1):
        _print_step(f"Batch {i}/{len(batches)}", f"intent={batch[0].intent.value}, {len(batch)} comment(s)")

        # RAG
        query = " ".join(c.comment for c in batch)
        docs  = retriever.retrieve(query, top_k=3)
        if verbose:
            print(f"    Retrieved {len(docs)} doc(s): {[d['tag'] for d in docs]}")

        # LLM
        result = generator.generate(batch, docs)
        output_dict = {
            "batch_id":        i,
            "intent":          result.intent,
            "emotion":         result.emotion,
            "cta":             result.cta,
            "confidence":      result.confidence,
            "text":            result.text,
            "source_comments": result.source_comments,
            "retrieved_docs":  [d["tag"] for d in docs],
            "latency_ms":      result.latency_ms,
            "generated_at":    datetime.now(timezone.utc).isoformat(),
        }
        outputs.append(output_dict)


        print(f"\n  ✓ Script [{result.emotion} / {result.cta}]  ({result.latency_ms}ms)")
        print(f"    {result.text}")

    # 6. Save output
    _print_banner("BƯỚC 6 — Lưu output")
    final_output = {
        "pipeline_run": {
            "input_file":       str(input_path.name),
            "total_comments":   len(raw_comments),
            "filtered_out":     noise_count,
            "answered_batches": len(outputs),
            "total_latency_ms": int((time.time() - t_total) * 1000),
            "model":            model,
            "generated_at":     datetime.now(timezone.utc).isoformat(),
        },
        "scripts": outputs,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(final_output, f, ensure_ascii=False, indent=2)

    total_ms = int((time.time() - t_total) * 1000)
    _print_step(f"Đã lưu output → {output_path}")
    _print_step(f"Tổng thời gian xử lý: {total_ms}ms")

    return outputs


def main():
    parser = argparse.ArgumentParser(description="Livestream Comment → Script Pipeline")
    parser.add_argument("--input",   default=str(INPUT_PATH), help="Path tới file comments JSON")
    parser.add_argument("--output",  default=str(OUT_PATH),   help="Path lưu output JSON")
    parser.add_argument("--kb",      default=str(KB_PATH),    help="Path tới knowledge base JSON")
    parser.add_argument("--model",   default="gpt-4o-mini",   help="OpenAI model (default: gpt-4o-mini)")
    parser.add_argument("--dry-run", action="store_true",     help="Chạy không gọi LLM, chỉ xem filter+retrieval")
    parser.add_argument("--quiet",   action="store_true",     help="Ít log hơn")
    args = parser.parse_args()

    if not args.dry_run and not os.environ.get("OPENAI_API_KEY"):
        print("ERROR: Chưa set OPENAI_API_KEY")
        print("  export OPENAI_API_KEY=sk-...")
        sys.exit(1)

    run_pipeline(
        input_path  = Path(args.input),
        kb_path     = Path(args.kb),
        output_path = Path(args.output),
        dry_run     = args.dry_run,
        model       = args.model,
        verbose     = not args.quiet,
    )


if __name__ == "__main__":
    main()
