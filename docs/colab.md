
---

# 14. Colab setup cell

Đây là cell cần có trước khi chạy server:

```bash id="kyvbqv"
!apt-get update -y
!apt-get install -y ffmpeg

!pip install fastapi uvicorn python-multipart pyngrok edge-tts pydantic
!pip install librosa==0.9.2
```

Wav2Lip setup:

```bash id="ctm9if"
%cd /content
!git clone https://github.com/Rudrabha/Wav2Lip.git

%cd /content/Wav2Lip
!pip install -r requirements.txt

!mkdir -p checkpoints
!mkdir -p face_detection/detection/sfd

!wget "https://www.adrianbulat.com/downloads/python-fan/s3fd-619a316812.pth" \
  -O "face_detection/detection/sfd/s3fd.pth"
```

Copy checkpoint từ Drive:

```python id="lmlo7m"
from google.colab import drive
drive.mount("/content/gdrive")

!cp -f "/content/gdrive/MyDrive/[SEAHACKATHON]/Wav2Lip-SD-GAN.pt" \
  "/content/Wav2Lip/checkpoints/Wav2Lip-SD-GAN.pt"
```

Run server + ngrok:

```python id="qmubvd"
from pyngrok import ngrok
import uvicorn
import threading

public_url = ngrok.connect(8000)
print("Public URL:", public_url)

def run():
    uvicorn.run("main:app", host="0.0.0.0", port=8000)

threading.Thread(target=run).start()
```

---

# 15. Flow cuối cùng khi web gọi vào Colab

```text id="fr4ydn"
Web upload:
- model_image
- product_image
- product_name
- product_description
- script

Colab AI Server:
1. split script thành micro-scenes
2. generate audio từng scene
3. tạo/copy keyframe từng scene
4. tạo base video đúng duration
5. scene host → Wav2Lip
6. scene product → FFmpeg zoom/overlay
7. concat tất cả scene
8. return final_video_url
```

MVP này đủ đúng cơ chế trước. Sau đó nâng cấp từng block:

```text id="s84xxd"
copy keyframe → SDXL-Lightning keyframe generation
FFmpeg product zoom → SVD/AnimateDiff/Wan product motion
rule-based split → Gemini scene planner
static host image → LivePortrait motion trước Wav2Lip
```

