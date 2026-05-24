# Hướng dẫn đưa AI Service Backend lên Google Colab

Tài liệu này hướng dẫn bạn cách đóng gói toàn bộ codebase của AI Service, tải lên Google Colab, cài đặt các dependencies (như FFmpeg, Wav2Lip, ngrok) và khởi chạy server FastAPI để public API ra ngoài thông qua `pyngrok`.

## 1. Cấu trúc Codebase (Codebase Overview)

Project được xây dựng theo kiến trúc Clean Architecture, giúp tách biệt các logic:

```text
ai-service/
├── app/                   # Chứa logic chính của ứng dụng
│   ├── api/               # Router, endpoint RESTful & WebSocket
│   ├── application/       # Use cases (ví dụ: video_usecase.py quản lý logic pipeline)
│   ├── domain/            # Entities, Enums, Interfaces
│   ├── infrastructure/    # Các kết nối với AI (Wav2Lip, FFmpeg, LLM), DB, Storage
│   └── main.py            # Entrypoint của FastAPI
├── data/                  # Thư mục lưu inputs, outputs, và DB tạm (SQLite)
├── docs/                  # Tài liệu dự án
├── dang_rag/              # Code tích hợp RAG, xử lý kịch bản
├── tests/                 # Scripts test (VD: wraptest.py dùng Playwright để test pipeline Gemini)
├── .env.example           # File cấu hình mẫu
├── requirements.txt       # Danh sách thư viện Python
└── colab.py               # (Tùy chọn) File chứa script khởi chạy ngrok
```

**Workflow hoạt động trên Colab:**
- Nhận request (ảnh, text) từ Web thông qua endpoint POST.
- Gọi LLM để sinh kịch bản micro-scenes (nếu có).
- Gọi các AI Generator (Gemini/Playwright pipeline) để tạo video nền.
- Sử dụng **Wav2Lip** để ghép môi host khớp với âm thanh (TTS).
- Sử dụng **FFmpeg** để thêm text, overlay product và concat các video lại.
- Trả về đường dẫn public của file video cuối cùng.

---

## 2. Chuẩn bị Codebase

1. Ở máy tính của bạn, **tạo file `.env`** bằng cách copy từ `.env.example`. Điền các key cần thiết như `GEMINI_API_KEY`, API key TTS (nếu có) và cấu hình NGROK nếu cần.
2. Xóa các thư mục không cần thiết để file nén nhẹ hơn: `.venv`, `__pycache__`, `data/outputs` (giữ cấu trúc thư mục rỗng).
3. Nén toàn bộ thư mục `ai-service` thành file `ai-service.zip`.

---

## 3. Upload lên Google Drive / Colab

1. Mở [Google Colab](https://colab.research.google.com/) và tạo một Notebook mới.
2. **Bật GPU:** Vào `Runtime` > `Change runtime type` > chọn **T4 GPU** (hoặc GPU mạnh hơn nếu có).
3. Mount Google Drive vào Colab:

```python
from google.colab import drive
drive.mount('/content/drive')
```

4. Upload file `ai-service.zip` của bạn lên Google Drive (ví dụ lưu ở `MyDrive/[SEAHACKATHON]/ai-service.zip`).
5. Giải nén vào môi trường Colab:

```bash
!cp "/content/drive/MyDrive/[SEAHACKATHON]/ai-service.zip" "/content/ai-service.zip"
!unzip -q /content/ai-service.zip -d /content/ai-service
```

---

## 4. Cài đặt Môi trường & Dependencies

Chạy cell dưới đây để cài đặt FFmpeg và các thư viện Python:

```bash
# Cập nhật và cài đặt FFmpeg
!apt-get update -y
!apt-get install -y ffmpeg

# Di chuyển vào thư mục code
%cd /content/ai-service

# Cài đặt thư viện của dự án
!pip install -r requirements.txt

# Cài thêm các package cần thiết cho Colab & Ngrok
!pip install fastapi uvicorn python-multipart pyngrok edge-tts pydantic librosa==0.9.2
```

---

## 5. Cài đặt Wav2Lip (AI Lipsync)

AI Service sử dụng thư viện Wav2Lip. Bạn cần clone repo và chép model pre-train.

```bash
%cd /content
!git clone https://github.com/Rudrabha/Wav2Lip.git

%cd /content/Wav2Lip
!pip install -r requirements.txt

# Tạo thư mục chứa checkpoint
!mkdir -p checkpoints
!mkdir -p face_detection/detection/sfd

# Tải model detect khuôn mặt
!wget "https://www.adrianbulat.com/downloads/python-fan/s3fd-619a316812.pth" -O "face_detection/detection/sfd/s3fd.pth"
```

**Copy model Wav2Lip checkpoint từ Drive của bạn:**
*(Đảm bảo bạn đã upload file `Wav2Lip-SD-GAN.pt` hoặc `wav2lip_gan.pth` lên Drive)*

```bash
!cp -f "/content/drive/MyDrive/[SEAHACKATHON]/Wav2Lip-SD-GAN.pt" "/content/Wav2Lip/checkpoints/Wav2Lip-SD-GAN.pt"
```

---

## 6. Chạy Server FastAPI với Ngrok

FastAPI chạy ở port 8000 trên Colab không thể truy cập trực tiếp từ Internet. Bạn sẽ dùng `pyngrok` để tạo một Public URL.

> Lưu ý: Hãy chắc chắn bạn đã vào thư mục dự án bằng `%cd /content/ai-service`.

Chạy đoạn code Python sau trong một Cell của Colab:

```python
import os
import threading
import uvicorn
from pyngrok import ngrok

# (Tùy chọn) Đặt token Ngrok của bạn nếu cần tạo đường dẫn cố định/ổn định hơn
# ngrok.set_auth_token("YOUR_NGROK_AUTH_TOKEN")

# Mở port 8000
public_url = ngrok.connect(8000)
print("🚀 Public URL cho Frontend kết nối:", public_url)

# Cấu hình biến môi trường nếu cần ghi đè
os.environ["LIVESTREAM_ENABLE_WAV2LIP"] = "true"
os.environ["WAV2LIP_PATH"] = "/content/Wav2Lip"
os.environ["CHECKPOINT_PATH"] = "/content/Wav2Lip/checkpoints/Wav2Lip-SD-GAN.pt"

# Hàm khởi chạy server
def run_server():
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000)

# Chạy server trên một thread riêng biệt để không block Colab cell
thread = threading.Thread(target=run_server)
thread.start()
```

Khi chạy thành công, console sẽ in ra một đường dẫn dạng `https://xxxx-xx-xx-xx-xx.ngrok-free.app`.
Bạn copy URL này và dùng nó làm `BASE_URL` dưới Web/Frontend (CORS đã được bật sẵn trong codebase).

---

## 7. Flow Test Cơ Bản (Cuối Cùng)

1. Mở Postman hoặc Swagger UI: `[PUBLIC_URL]/docs`
2. Gọi endpoint POST `/api/v1/video/livestream/jobs`.
3. Server sẽ:
   - Chạy logic `micro_scene_pipeline` 
   - Chia kịch bản.
   - Sync voice.
   - Run Wav2Lip qua `subprocess`.
   - FFmpeg ghép file.
   - Trả về đường link video hoàn thiện.

🎉 Chúc bạn thành công!
