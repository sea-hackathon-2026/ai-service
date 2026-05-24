import os
import subprocess
import threading
import time
from pathlib import Path

def run_cmd(cmd: str):
    print(f"🔄 Executing: {cmd}")
    subprocess.run(cmd, shell=True, check=True)

def setup_colab_environment():
    print("🚀 Bắt đầu quá trình cài đặt môi trường trên Colab...")
    
    # 1. Cài đặt FFmpeg
    print("📦 Cài đặt FFmpeg...")
    run_cmd("apt-get update -y && apt-get install -y ffmpeg")
    
    # 2. Setup Wav2Lip
    wav2lip_dir = Path("/content/Wav2Lip")
    if not wav2lip_dir.exists():
        print("📦 Clone thư viện Wav2Lip...")
        run_cmd("cd /content && git clone https://github.com/Rudrabha/Wav2Lip.git")
        run_cmd("cd /content/Wav2Lip && pip install -r requirements.txt")
        
        print("📁 Tạo thư mục checkpoints...")
        run_cmd("mkdir -p /content/Wav2Lip/checkpoints")
        run_cmd("mkdir -p /content/Wav2Lip/face_detection/detection/sfd")
        
        print("⬇️ Tải Face Detection model...")
        run_cmd("wget 'https://www.adrianbulat.com/downloads/python-fan/s3fd-619a316812.pth' -O '/content/Wav2Lip/face_detection/detection/sfd/s3fd.pth'")
    
    # 3. Mount Google Drive và copy checkpoint
    print("🔗 Kết nối Google Drive để lấy checkpoint Wav2Lip-SD-GAN.pt...")
    try:
        from google.colab import drive
        drive.mount('/content/drive')
        
        # NOTE: Người dùng cần tùy chỉnh đường dẫn này
        drive_ckpt = "/content/drive/MyDrive/[SEAHACKATHON]/Wav2Lip-SD-GAN.pt"
        colab_ckpt = "/content/Wav2Lip/checkpoints/Wav2Lip-SD-GAN.pt"
        
        if Path(drive_ckpt).exists():
            print(f"⬇️ Copy checkpoint từ Drive sang Colab...")
            run_cmd(f"cp -f '{drive_ckpt}' '{colab_ckpt}'")
            print("✅ Đã lấy checkpoint thành công!")
        else:
            print(f"⚠️ Không tìm thấy checkpoint tại: {drive_ckpt}. Hãy đảm bảo bạn đã upload model lên Drive.")
    except Exception as e:
        print(f"⚠️ Lỗi kết nối Google Drive: {e}")

def run_server():
    """Khởi chạy FastAPI Server bằng uvicorn với Ngrok"""
    import uvicorn
    import nest_asyncio
    from pyngrok import ngrok
    
    # Thiết lập biến môi trường
    os.environ["LIVESTREAM_ENABLE_WAV2LIP"] = "true"
    os.environ["WAV2LIP_PATH"] = "/content/Wav2Lip"
    os.environ["CHECKPOINT_PATH"] = "/content/Wav2Lip/checkpoints/Wav2Lip-SD-GAN.pt"
    
    # Bạn có thể điền Gemini API Key ở đây
    if "GEMINI_API_KEY" not in os.environ:
        os.environ["GEMINI_API_KEY"] = "" # TODO: Điền key vào đây
    
    # Thiết lập Ngrok Auth Token (Tùy chọn)
    NGROK_AUTH_TOKEN = os.getenv("NGROK_AUTH_TOKEN", "")
    if NGROK_AUTH_TOKEN:
        ngrok.set_auth_token(NGROK_AUTH_TOKEN)
        
    nest_asyncio.apply()
    
    public_url = ngrok.connect(8000)
    print("===========================================================")
    print("🚀 PUBLIC URL (Dùng cho Frontend kết nối):", public_url)
    print("📚 SWAGGER UI (Để test API):", f"{public_url}/docs")
    print("===========================================================")
    
    # Chạy uvicorn trực tiếp trên thread này vì colab support block
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000)

if __name__ == "__main__":
    print("⚠️ CẢNH BÁO: Script này được thiết kế để chạy trực tiếp trên môi trường Google Colab.")
    setup_colab_environment()
    
    print("📦 Cài đặt thư viện của AI Service...")
    run_cmd("pip install -r requirements.txt")
    run_cmd("pip install fastapi uvicorn python-multipart pyngrok edge-tts pydantic librosa==0.9.2 nest_asyncio")
    
    print("🚀 Khởi chạy server...")
    run_server()
