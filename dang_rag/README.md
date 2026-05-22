# Livestream Comment → Script Pipeline

Nhận comment JSON real-time từ livestream, lọc, truy xuất knowledge base,
sinh script trả lời hoàn chỉnh bằng OpenAI GPT.

## Cấu trúc project

```
livestream_bot/
├── main.py                  ← Orchestrator chính
├── requirements.txt
├── data/
│   ├── comments.json        ← Input: list comment + timestamp
│   ├── knowledge_base.json  ← Product knowledge base (tùy chỉnh theo sản phẩm)
│   └── output.json          ← Output scripts (tự sinh)
└── src/
    ├── filter.py            ← Rule-based filter + intent classifier
    ├── retriever.py         ← TF-IDF RAG retrieval
    ├── batcher.py           ← Gom comment cùng intent thành batch
    └── generator.py         ← OpenAI API + prompt builder
```

## Cài đặt

```bash
pip install -r requirements.txt
```

## Sử dụng

### 1. Chuẩn bị input

File `data/comments.json` — list comment với timestamp:
```json
[
  { "timestamp": "2024-01-15T10:00:01Z", "comment": "giá bao nhiêu vậy shop?" },
  { "timestamp": "2024-01-15T10:00:03Z", "comment": "có ship miền nam không?" }
]
```

### 2. Cập nhật knowledge base

Chỉnh `data/knowledge_base.json` theo sản phẩm thực tế của bạn.

### 3. Chạy pipeline

```bash
# Set API key
export OPENAI_API_KEY=sk-...

# Chạy full pipeline
python main.py

# Tùy chọn custom path
python main.py --input data/comments.json --output data/output.json

# Dry run (không tốn API key, chỉ xem filter + retrieval)
python main.py --dry-run

# Dùng model khác (mặc định: gpt-4o-mini)
python main.py --model gpt-4o
```

### 4. Output

File `data/output.json`:
```json
{
  "pipeline_run": {
    "total_comments": 14,
    "filtered_out": 5,
    "answered_batches": 7,
    "total_latency_ms": 3200,
    "model": "gpt-4o-mini"
  },
  "scripts": [
    {
      "batch_id": 1,
      "intent": "price",
      "emotion": "friendly",
      "cta": "buy_now",
      "confidence": 0.92,
      "text": "Dạ sản phẩm VitaGlow giá 85k/chai nha...",
      "source_comments": ["giá bao nhiêu vậy shop?"],
      "retrieved_docs": ["pricing", "promotion"],
      "latency_ms": 450
    }
  ]
}
```

## Flow xử lý

```
comments.json
      ↓
  [FILTER]  — loại spam, emoji, câu quá ngắn (<5ms)
      ↓
  [CLASSIFY] — gán intent: price / shipping / health / order... (<3ms)
      ↓
  [BATCH]   — gom comment cùng intent vào 1 batch (<1ms)
      ↓
  [RAG]     — TF-IDF search trên knowledge base (<10ms)
      ↓
  [LLM]     — gọi OpenAI GPT streaming (~300-500ms/batch)
      ↓
  output.json — JSON scripts hoàn chỉnh
```

## Tùy chỉnh

### Thêm intent mới (`src/filter.py`)
```python
INTENT_PATTERNS[Intent.WARRANTY] = [r"bảo hành", r"đổi trả"]
INTENT_PRIORITY[Intent.WARRANTY] = 0.8
```

### Thay đổi tone (`src/generator.py`)
Chỉnh `SYSTEM_PROMPT` để thay đổi phong cách trả lời.

### Tích hợp real-time
Thay vì đọc file JSON, gọi `run_pipeline()` từ code của bạn:
```python
from main import run_pipeline
scripts = run_pipeline(input_path, kb_path, output_path)
```

Hoặc gọi từng bước riêng lẻ để stream real-time:
```python
from src.filter    import filter_comments
from src.retriever import KnowledgeRetriever
from src.batcher   import batch_comments
from src.generator import ScriptGenerator

worthy  = filter_comments(raw_comments)
batches = batch_comments(worthy)
for batch in batches:
    docs   = retriever.retrieve(query)
    script = generator.generate(batch, docs)
    # → gửi script ra video model ngay lập tức
```
