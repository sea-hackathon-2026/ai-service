Cơ chế chính cần sửa là: **không gen một screen dài**. Mỗi đoạn thoại phải được split thành nhiều micro-scene ngắn, mỗi micro-scene có audio riêng, ảnh riêng, video riêng, rồi cuối cùng ghép lại.

```text id="2xepgr"
1 câu thoại ngắn
→ 1 scene prompt
→ 1 keyframe image
→ 1 audio chunk
→ 1 base video ngắn
→ Wav2Lip lip-sync
→ scene_clip.mp4

Nhiều scene_clip.mp4
→ concat
→ final_video.mp4
```

---

# 1. Model stack nên dùng cho Colab

| Phần                      | Model/tool                                     | Vai trò                                                |
| ------------------------- | ---------------------------------------------- | ------------------------------------------------------ |
| Split script + tạo prompt | Gemini API hoặc rule-based local               | Tách thoại thành scene nhỏ, tạo prompt/keyframe/motion |
| TTS                       | Edge-TTS / Kokoro-82M                          | Tạo audio từng câu                                     |
| Gen ảnh                   | SDXL-Lightning / Gemini Image API nếu có quota | Tạo keyframe cho từng scene                            |
| Cử động nhẹ               | LivePortrait                                   | Cho mặt/host có blink, nod, head motion                |
| Lip-sync                  | Wav2Lip / Wav2Lip-SD-GAN                       | Ghép khẩu hình theo audio                              |
| Product motion            | FFmpeg zoom/pan hoặc SVD/AnimateDiff-Lightning | Tạo b-roll sản phẩm                                    |
| Ghép cuối                 | FFmpeg                                         | Concat, normalize fps, audio, overlay sản phẩm/text    |

Với Colab, **Wav2Lip + LivePortrait + FFmpeg** là combo nhẹ và thực tế hơn so với cố chạy video diffusion dài. LivePortrait tập trung vào portrait animation hiệu quả, kiểm soát tốt bằng source image + driving video, hợp để tạo cử động đầu/mắt nhẹ trước khi đưa qua lip-sync. ([GitHub][1])

Nếu cần text-to-video/product b-roll nhẹ, có thể thử AnimateDiff-Lightning vì model này được distill để chạy ít step hơn AnimateDiff gốc, có checkpoint 2-step/4-step/8-step. ([Hugging Face][2]) Nhưng với sản phẩm thật, cách ổn nhất vẫn là **dùng ảnh sản phẩm thật + FFmpeg motion/overlay**, vì diffusion rất dễ làm sai logo/chữ/bao bì.

Với image generation, SDXL-Lightning hợp Colab vì nó sinh ảnh 1024px trong ít bước, nhanh hơn SDXL thường. ([Hugging Face][3]) Còn nếu cần image-to-video từ ảnh, Stable Video Diffusion có thể tạo video ngắn 2–4 giây từ input image, nhưng sẽ nặng hơn FFmpeg và không chắc giữ đúng chi tiết sản phẩm. ([Hugging Face][4])

TTS: Kokoro-82M là open-weight 82M parameters, Apache-licensed weights, hợp nếu muốn local/offline hơn. ([Hugging Face][5]) Edge-TTS là option nhanh để demo vì package Python có thể gọi Microsoft Edge online TTS mà không cần tự host model. ([GitHub][6])

Về API free: Gemini API hiện có free tier cho một số model/text/TTS tùy model và tier, nhưng pricing/rate limit thay đổi theo model nên code cần có fallback rule-based/local. ([Google AI for Developers][7]) Hugging Face Inference Providers cũng có credits free nhỏ cho user free, nhưng không nên phụ thuộc làm core vì quota rất ít và có thể thay đổi. ([Hugging Face][8])

---

# 2. Rule quan trọng: split thoại để tăng consistency

M không nên để một scene dài 15–30 giây. Nên split như này:

```text id="ev3x66"
Một chunk thoại:
- 6–14 từ tiếng Việt
- audio khoảng 2–4 giây
- không quá 1 ý bán hàng
- có 1 cảm xúc/gesture duy nhất
- có 1 keyframe riêng
```

Ví dụ script gốc:

```text id="ghc21k"
Chào cả nhà, hôm nay shop giới thiệu mẫu serum dưỡng sáng đang sale mạnh, phù hợp cho da khô, da xỉn màu và những bạn hay ngồi máy lạnh.
```

Split thành:

```json id="g8u7q2"
[
  {
    "text": "Chào cả nhà, hôm nay shop giới thiệu mẫu serum dưỡng sáng.",
    "scene_type": "HOST_TALK",
    "emotion": "friendly_intro"
  },
  {
    "text": "Sản phẩm này phù hợp cho da khô và da xỉn màu.",
    "scene_type": "PRODUCT_CLOSEUP",
    "emotion": "explaining"
  },
  {
    "text": "Đặc biệt hôm nay đang có ưu đãi rất tốt.",
    "scene_type": "CTA",
    "emotion": "excited"
  }
]
```

Lợi ích:

```text id="jfwrl4"
Video ngắn hơn → ít drift mặt/sản phẩm hơn
Prompt cụ thể hơn → ảnh consistent hơn
Audio ngắn hơn → lip-sync ít lỗi hơn
Fail scene nào → regenerate scene đó, không cần gen lại toàn video
```

---

# 3. Data schema cho một scene

Nên ép mọi scene về JSON chuẩn:

```python id="k7qfze"
from pydantic import BaseModel
from typing import Literal, Optional, List

SceneType = Literal[
    "HOST_TALK",
    "HOST_PHONE_READING",
    "PRODUCT_CLOSEUP",
    "PRODUCT_BEAUTY",
    "CTA",
    "TRANSITION"
]

class SceneChunk(BaseModel):
    scene_id: str
    order: int
    scene_type: SceneType
    text: str
    visual_goal: str
    emotion: str
    camera: str
    host_action: str
    product_action: str
    duration_target_sec: float
    image_prompt: str
    negative_prompt: str
    motion_prompt: str
    overlay_text: Optional[str] = None
    use_lipsync: bool = True
    use_product_overlay: bool = False
```

---

# 4. Prompt split script thành micro-scene

Dùng prompt này cho Gemini/LLM. Nếu không có API key thì fallback bằng rule-based split dấu câu.

```python id="mr63h2"
SCENE_SPLIT_PROMPT = """
You are an AI livestream video director.

TASK:
Split the seller script into short micro-scenes for AI video generation.
The goal is consistency, so each scene must be short and visually simple.

RULES:
1. Each scene should contain only one spoken idea.
2. Each spoken text should be 6 to 14 Vietnamese words if possible.
3. Each scene duration should be around 2 to 4 seconds.
4. Avoid long scenes because long scenes reduce visual consistency.
5. Use HOST_TALK when the virtual host speaks to camera.
6. Use HOST_PHONE_READING when the host looks at a phone and reads comments.
7. Use PRODUCT_CLOSEUP when the product should be shown clearly.
8. Use CTA when the line asks users to buy, comment, click, or claim promotion.
9. Product text/logo must not be generated by AI if exact accuracy is required. Use overlay instead.
10. Output valid JSON only.

INPUT:
Product name: {product_name}
Product description: {product_description}
Brand style: {brand_style}
Script:
{script}

OUTPUT JSON ARRAY:
[
  {{
    "scene_id": "S001",
    "order": 1,
    "scene_type": "HOST_TALK",
    "text": "short Vietnamese sentence",
    "visual_goal": "what the viewer should see",
    "emotion": "friendly | excited | serious | helpful | reading_comment",
    "camera": "medium shot | close-up | product close-up",
    "host_action": "small nod, blink, natural expression",
    "product_action": "none | product on table | product near camera",
    "duration_target_sec": 3.0,
    "overlay_text": "optional short CTA text",
    "use_lipsync": true,
    "use_product_overlay": false
  }}
]
"""
```

---

# 5. Prompt tạo ảnh/keyframe cho từng scene

Mỗi scene cần tạo prompt ảnh riêng, nhưng phải có phần lock cố định.

```python id="y97rao"
IMAGE_PROMPT_TEMPLATE = """
Create a vertical 9:16 ecommerce livestream keyframe.

CHARACTER LOCK:
- same person as the provided model reference image
- same face identity, same hairstyle, same outfit
- natural skin texture, realistic Vietnamese livestream host
- no face change, no age change, no hairstyle change

PRODUCT LOCK:
- use the provided product reference image as the accurate product source
- product package shape and main color must stay accurate
- do not invent new label text or logo
- if product text is unclear, leave space for overlay instead of generating fake text

SCENE:
{visual_goal}

HOST ACTION:
{host_action}

PRODUCT ACTION:
{product_action}

CAMERA:
{camera}, vertical livestream framing, stable tripod, clean ecommerce layout

LIGHTING:
soft studio lighting, bright but natural, product-focused, clean background

STYLE:
realistic ecommerce livestream, modern Vietnamese shop, clean and trustworthy

SAFE ZONE:
leave empty space at lower third for price/comment overlays

NEGATIVE PROMPT:
{negative_prompt}
"""
```

Negative prompt mặc định:

```python id="myoyur"
DEFAULT_NEGATIVE_PROMPT = """
distorted face, different person, changed hairstyle, changed outfit,
extra fingers, broken hands, warped product, wrong logo, fake text,
unreadable label, duplicated product, heavy motion blur, low quality,
overly cinematic, fantasy style, deformed mouth, bad teeth
"""
```

---

# 6. Prompt tạo motion cho video ngắn

```python id="khbaie"
MOTION_PROMPT_TEMPLATE = """
Create a very short seamless livestream motion clip.

SCENE TYPE:
{scene_type}

MOTION:
{motion_prompt}

STRICT MOTION RULES:
- subtle movement only
- natural blinking
- small head movement
- calm breathing
- stable camera
- no large body movement
- no fast hand gesture
- no scene change
- first and last frame should be visually similar for looping

DURATION:
{duration_sec} seconds

ASPECT RATIO:
9:16 vertical livestream video
"""
```

Motion prompt theo scene:

```python id="byae1v"
MOTION_RULES = {
    "HOST_TALK": "small head nod, natural blinking, slight mouth-ready expression",
    "HOST_PHONE_READING": "looking down at phone, small nod, natural blinking, calm breathing",
    "PRODUCT_CLOSEUP": "slow camera push-in, product remains centered and accurate",
    "PRODUCT_BEAUTY": "subtle light movement, product stays still, clean background",
    "CTA": "static product shot with animated text overlay, no AI product redraw",
    "TRANSITION": "short soft fade transition"
}
```

---

# 7. Cơ chế audio trước, video theo audio sau

Không nên set duration scene bằng cảm tính. Nên:

```text id="zzt322"
Text chunk
→ TTS audio
→ đo audio duration
→ tạo base video đúng duration
→ Wav2Lip
```

Code utility:

```python id="kkpnem"
import subprocess
import json
from pathlib import Path

def get_media_duration(path: str) -> float:
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "json", path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    data = json.loads(result.stdout)
    return float(data["format"]["duration"])
```

TTS bằng Edge-TTS:

```python id="wm5l0o"
import asyncio
import edge_tts

async def synthesize_edge_tts(text: str, output_path: str, voice: str = "vi-VN-HoaiMyNeural"):
    communicate = edge_tts.Communicate(
        text=text,
        voice=voice,
        rate="+0%",
        volume="+0%"
    )
    await communicate.save(output_path)

def generate_tts(text: str, output_path: str):
    asyncio.run(synthesize_edge_tts(text, output_path))
    return output_path
```

Fallback local bằng Kokoro có thể để sau. MVP dùng Edge-TTS nhanh hơn.

---

# 8. Tạo base video từ ảnh keyframe

Với scene host, tạo video nền từ ảnh trước rồi đưa vào Wav2Lip.

```python id="sjz4kr"
import subprocess
from pathlib import Path

def make_base_video_from_image(
    image_path: str,
    audio_path: str,
    output_path: str,
    width: int = 720,
    height: int = 1280,
    fps: int = 25
):
    duration = get_media_duration(audio_path) + 0.15

    vf = (
        f"scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},"
        f"fps={fps}"
    )

    cmd = [
        "ffmpeg", "-y",
        "-loop", "1",
        "-i", image_path,
        "-t", str(duration),
        "-vf", vf,
        "-pix_fmt", "yuv420p",
        "-r", str(fps),
        output_path
    ]
    subprocess.run(cmd, check=True)
    return output_path
```

Với sản phẩm, dùng zoom nhẹ để nhìn như có motion nhưng vẫn giữ đúng sản phẩm:

```python id="wjnb69"
def make_product_zoom_video(
    image_path: str,
    audio_path: str,
    output_path: str,
    width: int = 720,
    height: int = 1280,
    fps: int = 25
):
    duration = get_media_duration(audio_path) + 0.15
    frames = int(duration * fps)

    vf = (
        f"scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},"
        f"zoompan=z='min(zoom+0.0008,1.06)':"
        f"d={frames}:"
        f"x='iw/2-(iw/zoom/2)':"
        f"y='ih/2-(ih/zoom/2)':"
        f"s={width}x{height}:fps={fps},"
        f"format=yuv420p"
    )

    cmd = [
        "ffmpeg", "-y",
        "-loop", "1",
        "-i", image_path,
        "-t", str(duration),
        "-vf", vf,
        "-pix_fmt", "yuv420p",
        output_path
    ]
    subprocess.run(cmd, check=True)
    return output_path
```

---

# 9. Wav2Lip worker

Bọc code hiện tại thành function. Không chạy notebook command rời rạc nữa.

```python id="kr1cih"
import subprocess
from pathlib import Path

def run_wav2lip(
    wav2lip_dir: str,
    checkpoint_path: str,
    face_video_or_image: str,
    audio_path: str,
    output_path: str,
    pads=(0, 20, 0, 0),
    resize_factor: int = 2
):
    result_path = Path(wav2lip_dir) / "results" / "result_voice.mp4"

    cmd = [
        "python", "inference.py",
        "--checkpoint_path", checkpoint_path,
        "--face", face_video_or_image,
        "--audio", audio_path,
        "--pads", str(pads[0]), str(pads[1]), str(pads[2]), str(pads[3]),
        "--resize_factor", str(resize_factor)
    ]

    subprocess.run(cmd, cwd=wav2lip_dir, check=True)

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["cp", str(result_path), output_path], check=True)

    return output_path
```

Với scene không cần lip-sync, không chạy Wav2Lip:

```python id="pxcmdw"
def should_lipsync(scene_type: str) -> bool:
    return scene_type in ["HOST_TALK", "HOST_PHONE_READING"]
```

---

# 10. Scene generation pipeline

Đây là cơ chế chính.

```python id="87llml"
from pathlib import Path

def generate_scene_clip(
    scene: dict,
    paths: dict,
    config: dict
):
    scene_id = scene["scene_id"]
    scene_dir = Path(paths["job_dir"]) / "scenes" / scene_id
    scene_dir.mkdir(parents=True, exist_ok=True)

    audio_path = str(scene_dir / "audio.wav")
    keyframe_path = str(scene_dir / "keyframe.png")
    base_video_path = str(scene_dir / "base.mp4")
    lipsync_video_path = str(scene_dir / "lipsync.mp4")
    final_scene_path = str(scene_dir / "scene_final.mp4")

    # 1. Generate audio first
    generate_tts(scene["text"], audio_path)
    audio_duration = get_media_duration(audio_path)

    # 2. Generate/select keyframe
    # MVP: copy model image or product image.
    # Later: replace this with SDXL-Lightning/Gemini image generation.
    if scene["scene_type"] in ["PRODUCT_CLOSEUP", "PRODUCT_BEAUTY", "CTA"]:
        source_image = paths["product_image"]
    else:
        source_image = paths["model_image"]

    subprocess.run(["cp", source_image, keyframe_path], check=True)

    # 3. Create base video
    if scene["scene_type"] in ["PRODUCT_CLOSEUP", "PRODUCT_BEAUTY"]:
        make_product_zoom_video(keyframe_path, audio_path, base_video_path)
    else:
        make_base_video_from_image(keyframe_path, audio_path, base_video_path)

    # 4. Lip-sync if needed
    if scene.get("use_lipsync", True) and should_lipsync(scene["scene_type"]):
        run_wav2lip(
            wav2lip_dir=config["wav2lip_dir"],
            checkpoint_path=config["wav2lip_checkpoint"],
            face_video_or_image=base_video_path,
            audio_path=audio_path,
            output_path=lipsync_video_path,
            pads=config.get("wav2lip_pads", (0, 20, 0, 0)),
            resize_factor=config.get("resize_factor", 2)
        )
        current_video = lipsync_video_path
    else:
        current_video = base_video_path

    # 5. Add overlay text if any
    if scene.get("overlay_text"):
        add_text_overlay(
            input_video=current_video,
            output_video=final_scene_path,
            text=scene["overlay_text"]
        )
    else:
        subprocess.run(["cp", current_video, final_scene_path], check=True)

    return final_scene_path
```

Overlay đơn giản:

```python id="ry8ywe"
def add_text_overlay(input_video: str, output_video: str, text: str):
    safe_text = text.replace(":", "\\:").replace("'", "\\'")
    vf = (
        "drawbox=x=40:y=h-260:w=w-80:h=170:color=black@0.45:t=fill,"
        f"drawtext=text='{safe_text}':"
        "fontcolor=white:fontsize=42:"
        "x=(w-text_w)/2:y=h-210:"
        "box=0"
    )

    cmd = [
        "ffmpeg", "-y",
        "-i", input_video,
        "-vf", vf,
        "-c:a", "copy",
        output_video
    ]
    subprocess.run(cmd, check=True)
    return output_video
```

---

# 11. Ghép nhiều scene clip thành final video

```python id="aixh3h"
def concat_scene_clips(scene_video_paths: list[str], output_path: str):
    list_path = Path(output_path).parent / "concat_list.txt"

    with open(list_path, "w", encoding="utf-8") as f:
        for path in scene_video_paths:
            f.write(f"file '{Path(path).resolve()}'\n")

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(list_path),
        "-c", "copy",
        output_path
    ]

    subprocess.run(cmd, check=True)
    return output_path
```

Nếu concat lỗi do codec mismatch, dùng normalize:

```python id="6v8kw5"
def normalize_video(input_path: str, output_path: str, width=720, height=1280, fps=25):
    vf = (
        f"scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},fps={fps},format=yuv420p"
    )

    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-vf", vf,
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "23",
        "-c:a", "aac",
        "-ar", "44100",
        "-ac", "2",
        output_path
    ]
    subprocess.run(cmd, check=True)
    return output_path
```

---

# 12. FastAPI server tối thiểu

MVP server chỉ cần 3 endpoint:

```text id="cumhtr"
POST /jobs
GET /jobs/{job_id}
GET /jobs/{job_id}/outputs
```

Code skeleton:

```python id="6utdzl"
from fastapi import FastAPI, UploadFile, Form, File, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import uuid
import shutil
import json

app = FastAPI(title="AI Video Generation Server")

BASE_DIR = Path("/content/ai_video_server")
OUTPUT_DIR = BASE_DIR / "outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

JOBS = {}

app.mount("/files", StaticFiles(directory=str(OUTPUT_DIR)), name="files")

CONFIG = {
    "wav2lip_dir": "/content/Wav2Lip",
    "wav2lip_checkpoint": "/content/Wav2Lip/checkpoints/Wav2Lip-SD-GAN.pt",
    "wav2lip_pads": (0, 20, 0, 0),
    "resize_factor": 2
}

@app.post("/jobs")
async def create_job(
    background_tasks: BackgroundTasks,
    product_name: str = Form(...),
    product_description: str = Form(""),
    script: str = Form(...),
    brand_style: str = Form("clean ecommerce livestream"),
    model_image: UploadFile = File(...),
    product_image: UploadFile = File(...)
):
    job_id = f"job_{uuid.uuid4().hex[:10]}"
    job_dir = OUTPUT_DIR / job_id
    input_dir = job_dir / "input"
    input_dir.mkdir(parents=True, exist_ok=True)

    model_path = input_dir / "model.png"
    product_path = input_dir / "product.png"
    script_path = input_dir / "script.txt"

    with open(model_path, "wb") as f:
        shutil.copyfileobj(model_image.file, f)

    with open(product_path, "wb") as f:
        shutil.copyfileobj(product_image.file, f)

    script_path.write_text(script, encoding="utf-8")

    JOBS[job_id] = {
        "job_id": job_id,
        "status": "queued",
        "progress": 0,
        "current_step": "Job created",
        "outputs": []
    }

    background_tasks.add_task(
        run_generation_job,
        job_id=job_id,
        product_name=product_name,
        product_description=product_description,
        script=script,
        brand_style=brand_style,
        model_path=str(model_path),
        product_path=str(product_path),
        job_dir=str(job_dir)
    )

    return {"job_id": job_id, "status": "queued"}

@app.get("/jobs/{job_id}")
def get_job(job_id: str):
    return JOBS.get(job_id, {"error": "job not found"})

@app.get("/jobs/{job_id}/outputs")
def get_outputs(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        return {"error": "job not found"}

    return {
        "job_id": job_id,
        "status": job["status"],
        "videos": job.get("outputs", []),
        "final_video_url": job.get("final_video_url")
    }
```

Job runner:

```python id="vq7h7s"
def update_job(job_id: str, status: str, progress: int, current_step: str):
    JOBS[job_id]["status"] = status
    JOBS[job_id]["progress"] = progress
    JOBS[job_id]["current_step"] = current_step

def run_generation_job(
    job_id: str,
    product_name: str,
    product_description: str,
    script: str,
    brand_style: str,
    model_path: str,
    product_path: str,
    job_dir: str
):
    try:
        update_job(job_id, "planning_scenes", 10, "Splitting script into micro-scenes")

        scenes = split_script_to_scenes(
            product_name=product_name,
            product_description=product_description,
            brand_style=brand_style,
            script=script
        )

        plan_dir = Path(job_dir) / "plan"
        plan_dir.mkdir(parents=True, exist_ok=True)
        (plan_dir / "scene_plan.json").write_text(
            json.dumps(scenes, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

        scene_outputs = []
        total = len(scenes)

        for idx, scene in enumerate(scenes):
            progress = 20 + int((idx / total) * 65)
            update_job(job_id, "generating_scenes", progress, f"Generating {scene['scene_id']}")

            scene_video = generate_scene_clip(
                scene=scene,
                paths={
                    "job_dir": job_dir,
                    "model_image": model_path,
                    "product_image": product_path
                },
                config=CONFIG
            )

            public_url = f"/files/{job_id}/scenes/{scene['scene_id']}/scene_final.mp4"

            scene_outputs.append({
                "scene_id": scene["scene_id"],
                "scene_type": scene["scene_type"],
                "text": scene["text"],
                "url": public_url
            })

        update_job(job_id, "post_processing", 90, "Concatenating final video")

        final_dir = Path(job_dir) / "final"
        final_dir.mkdir(parents=True, exist_ok=True)

        final_path = str(final_dir / "final_video.mp4")
        concat_scene_clips(
            [str(Path(job_dir) / "scenes" / s["scene_id"] / "scene_final.mp4") for s in scenes],
            final_path
        )

        JOBS[job_id]["outputs"] = scene_outputs
        JOBS[job_id]["final_video_url"] = f"/files/{job_id}/final/final_video.mp4"

        update_job(job_id, "done", 100, "Done")

    except Exception as e:
        JOBS[job_id]["status"] = "failed"
        JOBS[job_id]["error"] = str(e)
        JOBS[job_id]["current_step"] = "Generation failed"
```

---

# 13. Rule-based splitter fallback

Dùng tạm trước khi nối Gemini.

```python id="vahcc3"
import re

def split_sentence_to_chunks(text: str, max_words: int = 12):
    parts = re.split(r"(?<=[.!?。！？])\s+|[,;，]\s*", text.strip())
    chunks = []

    for part in parts:
        words = part.strip().split()
        if not words:
            continue

        current = []
        for word in words:
            current.append(word)
            if len(current) >= max_words:
                chunks.append(" ".join(current))
                current = []

        if current:
            chunks.append(" ".join(current))

    return chunks

def classify_scene_type(text: str, order: int):
    lower = text.lower()

    if any(k in lower for k in ["comment", "bình luận", "hỏi", "inbox"]):
        return "HOST_PHONE_READING"

    if any(k in lower for k in ["giá", "sale", "ưu đãi", "chốt", "mua", "đặt hàng"]):
        return "CTA"

    if any(k in lower for k in ["sản phẩm", "thiết kế", "chất liệu", "thành phần", "công dụng"]):
        return "PRODUCT_CLOSEUP"

    return "HOST_TALK"

def split_script_to_scenes(product_name, product_description, brand_style, script):
    chunks = split_sentence_to_chunks(script, max_words=12)

    scenes = []
    for i, chunk in enumerate(chunks, start=1):
        scene_type = classify_scene_type(chunk, i)

        scene = {
            "scene_id": f"S{i:03d}",
            "order": i,
            "scene_type": scene_type,
            "text": chunk,
            "visual_goal": f"Livestream scene introducing {product_name}",
            "emotion": "friendly" if scene_type == "HOST_TALK" else "helpful",
            "camera": "medium shot" if scene_type.startswith("HOST") else "product close-up",
            "host_action": MOTION_RULES.get(scene_type, "natural subtle movement"),
            "product_action": "show product clearly" if "PRODUCT" in scene_type else "none",
            "duration_target_sec": 3.0,
            "image_prompt": "",
            "negative_prompt": DEFAULT_NEGATIVE_PROMPT,
            "motion_prompt": MOTION_RULES.get(scene_type, "subtle motion"),
            "overlay_text": chunk if scene_type == "CTA" else None,
            "use_lipsync": scene_type in ["HOST_TALK", "HOST_PHONE_READING"],
            "use_product_overlay": scene_type in ["PRODUCT_CLOSEUP", "CTA"]
        }
        scenes.append(scene)

    return scenes
```


[1]: https://github.com/KlingAIResearch/LivePortrait?utm_source=chatgpt.com "KlingAIResearch/LivePortrait: Bring portraits to life!"
[2]: https://huggingface.co/ByteDance/AnimateDiff-Lightning?utm_source=chatgpt.com "ByteDance/AnimateDiff-Lightning"
[3]: https://huggingface.co/ByteDance/SDXL-Lightning?utm_source=chatgpt.com "ByteDance/SDXL-Lightning"
[4]: https://huggingface.co/docs/diffusers/using-diffusers/svd?utm_source=chatgpt.com "Stable Video Diffusion"
[5]: https://huggingface.co/hexgrad/Kokoro-82M?utm_source=chatgpt.com "hexgrad/Kokoro-82M"
[6]: https://github.com/rany2/edge-tts?utm_source=chatgpt.com "rany2/edge-tts: Use Microsoft Edge's online text-to-speech ..."
[7]: https://ai.google.dev/gemini-api/docs/pricing?utm_source=chatgpt.com "Gemini Developer API pricing"
[8]: https://huggingface.co/docs/inference-providers/en/index?utm_source=chatgpt.com "Inference Providers"
