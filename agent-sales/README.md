# 🛍️ Sales Closing Agent — Google ADK + Gemini

Agent chốt đơn hàng livestream sử dụng **Google Agent Development Kit (ADK)** kết nối **Gemini 2.0 Flash**.

## ✨ Tính năng

- 🎯 **Phát hiện ý định mua hàng** — Nhận diện khi khách nói "em muốn mua", "đặt hàng", "lấy cho em"...
- 📋 **Thu thập thông tin tự động** — Hỏi lần lượt 5 thông tin cần thiết:
  - Sản phẩm
  - Số lượng
  - Giá
  - Địa chỉ giao hàng
  - Số điện thoại
- ✅ **Xác nhận đơn hàng** — Tổng hợp và xác nhận khi đủ thông tin
- 💬 **Chat tự nhiên** — Nói chuyện thân thiện, tự nhiên như livestream thật

## 📁 Cấu trúc thư mục

```
agent-sales/
├── .env              # API key config
├── __init__.py       # Package init (ADK auto-discovery)
├── agent.py          # Định nghĩa agent + instruction tiếng Việt
├── tools.py          # 3 tools: save_order_info, get_order_status, confirm_order
├── run_cli.py        # CLI runner (chạy chat trong terminal)
└── README.md         # File này
```

## 🚀 Cài đặt

### 1. Môi trường Local

```bash
cd agent-sales
pip install -r requirements.txt
```

### 2. Cấu hình API Keys

Sửa file `.env` trong folder `agent-sales`:

```env
GOOGLE_API_KEY=your-gemini-api-key
GROQ_API_KEY=your-groq-api-key
```

> 💡 **Cơ chế Fallback**: Hệ thống sử dụng **Gemini** làm ưu tiên. Nếu Gemini hết quota (lỗi 429), agent sẽ **tự động chuyển sang Groq** (`llama-3.3-70b-versatile`) thông qua LiteLLM để tiếp tục chat mà không bị gián đoạn.

---

## 🏃 Cách chạy

### Cách 1: Docker (Khuyên dùng - Độc lập hoàn toàn)

Chạy agent như một microservice riêng biệt với FastAPI qua Docker:

```bash
cd agent-sales
docker build -t sales-agent .
docker run -d -p 8000:8000 --env-file .env sales-agent
```

API sẽ có sẵn tại: `http://localhost:8000/chat` (Xem `main.py`).

### Cách 2: Chạy trực tiếp FastAPI Local

```bash
cd agent-sales
uvicorn main:app --reload --port 8000
```

### Cách 3: CLI Runner (Chạy test trên Terminal)

```bash
cd agent-sales
python run_cli.py
```

---

## 💬 Demo kịch bản chat

```
👤 Bạn: Chào shop, cho mình hỏi về kem dưỡng da
🤖 Agent: Dạ chào bạn! Bên mình đang có nhiều dòng kem dưỡng da lắm nha...

👤 Bạn: Em muốn mua
🤖 Agent: Dạ, bạn muốn mua sản phẩm nào ạ? Bên mình đang có nhiều mẫu lắm nè!

...
```

## 🛠️ Kiến trúc hệ thống

```
Khách hàng
    │
    ▼
┌────────────────────────────────────────────────────────┐
│  Agent Sales Microservice (FastAPI / Docker)           │
│                                                        │
│  ┌────────────────────────┐       ┌─────────────────┐  │
│  │ Primary: Gemini 2.0    │──────▶│ Fallback: Groq  │  │
│  │ (Google GenAI)         │ (429) │ (LiteLLM)       │  │
│  └────────────────────────┘       └─────────────────┘  │
│              │                             │           │
│              ▼                             ▼           │
│  ┌──────────────────────────────────────────────────┐  │
│  │ Tools: save_order_info, confirm_order            │  │
│  └──────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────┘
    │
    ▼
  Đơn hàng confirmed ✅
```

## ❓ Troubleshooting

| Vấn đề | Giải pháp |
|---------|-----------|
| `429 RESOURCE_EXHAUSTED` | Gemini đã hết quota. Hệ thống sẽ tự động gọi sang Groq nếu bạn đã cấu hình `GROQ_API_KEY`. |
| `Không thể khởi tạo Fallback Groq` | Kiểm tra xem đã set `GROQ_API_KEY` trong `.env` chưa và đảm bảo thư viện `litellm` đã được cài. |
| Chatbot không trả lời | Kiểm tra logs API. Có thể cả 2 key đều lỗi. |

## 📖 Tài liệu tham khảo

- [Google ADK Documentation](https://adk.dev)
- [LiteLLM for Groq](https://docs.litellm.ai/docs/providers/groq)
