
```text
input.json + knowledge_base.json
→ tạo full script trước
→ split thành nhiều scene ngắn
→ tạo prompt Veo cho từng scene
→ m gen video bằng Gemini/Veo theo từng prompt
→ upload/download video về folder
→ backend ghép audio + trim + lipsync + concat
→ final livestream loop
```

Quan trọng nhất: **không tạo video từ script dài ngay**. Phải tạo **master_script.json** trước, rồi từng scene mới đi qua Veo.

Google có đường chính thức để gọi Veo qua Gemini API, trong đó docs mô tả Veo 3.1 là model video generation có thể truy cập programmatically, nhưng bản pipeline tạm của m có thể dùng Gemini/Veo UI theo kiểu external/manual bridge để tiết kiệm trước. ([Google AI for Developers][1])

---

# 1. Input chuẩn cho pipeline

M nên chuẩn hóa input thành một file `input_job.json`.

```json
{
  "job_id": "cocoon_test_001",
  "mode": "external_veo_manual",
  "aspect_ratio": "9:16",
  "target_platform": "tiktok_live",
  "target_duration_sec": 40,

  "model": {
    "image_path": "assets/model/model_ref.png",
    "base_description": "Một phụ nữ Việt Nam 25 tuổi, tóc đen ngắn ngang cằm kiểu bob rẽ ngôi giữa, gương mặt thanh tú, trang điểm tự nhiên, tai đeo khuyên tròn nhỏ. Cô ấy mặc áo thun trắng tay ngắn có các đường sọc ngang nhỏ màu đen. Phía sau là bối cảnh khu vườn nhiệt đới với nhiều cây xanh và lá dương xỉ mờ nhẹ. Góc máy trung cận trực diện, camera cố định, ánh sáng tự nhiên ban ngày, chi tiết gương mặt sắc nét và đồng nhất."
  },

  "product": {
    "image_paths": [
      "assets/product/cocoon_body_scrub.png",
      "assets/product/cocoon_hair_tonic.png"
    ],
    "knowledge_base_path": "knowledge_base.json",
    "focus_product_ids": ["SP001", "SP002", "SP003", "SP004"]
  },

  "content_goal": {
    "goal": "Tạo video loop livestream giới thiệu bộ sản phẩm Cocoon, có host nói, cảnh cầm sản phẩm, cảnh đọc comment, cảnh CTA.",
    "tone": "chuyên nghiệp, tự nhiên, đáng tin, livestream bán hàng",
    "audience": "người xem livestream quan tâm chăm sóc da và tóc",
    "cta": "bấm vào giỏ hàng hoặc comment số điện thoại để được hỗ trợ lên đơn"
  }
}
```

File `knowledge_base.json` của m đang có đủ dữ liệu để sinh script: brand Cocoon, USP thuần chay/cruelty-free/CGMP, 4 sản phẩm chính, giá livestream, ưu đãi, FAQ, shipping, health notes và CTA mẫu. 

---

# 2. Output đầu tiên phải là `master_script.json`

Đừng gen video ngay. Bước đầu tiên của backend là tạo file này:

```json
{
  "job_id": "cocoon_test_001",
  "base_visual_lock": "...",
  "global_rules": {
    "aspect_ratio": "9:16",
    "camera": "medium close-up, fixed camera",
    "motion_level": "low",
    "scene_duration_sec": 5,
    "transition": "0.2s crossfade",
    "consistency_rule": "Every scene must use the same model reference, same outfit, same face, same hairstyle, same background, same camera framing."
  },
  "playlist": [
    {
      "clip_id": "A_MAIN_SALES_LOOP",
      "purpose": "main loop giới thiệu sản phẩm",
      "scenes": ["S001", "S002", "S003", "S004", "S005", "S006"]
    },
    {
      "clip_id": "B_COMMENT_READING_LOOP",
      "purpose": "loop nền khi đọc comment realtime",
      "scenes": ["S007"]
    },
    {
      "clip_id": "C_CTA_LOOP",
      "purpose": "loop chốt đơn",
      "scenes": ["S008"]
    }
  ],
  "scenes": []
}
```

Mỗi `scene` phải có đủ:

```json
{
  "scene_id": "S001",
  "clip_id": "A_MAIN_SALES_LOOP",
  "order": 1,
  "scene_type": "HOST_TALK",
  "duration_target_sec": 5,
  "voiceover": "Dạ em xin chào cả nhà, hôm nay Cocoon có deal livestream rất hời.",
  "visual_goal": "Host mở đầu livestream, nhìn thẳng camera, cầm sản phẩm nhẹ nhàng.",
  "veo_prompt": "...",
  "start_anchor": "Host facing camera, product held at chest level.",
  "end_anchor": "Host still facing camera, product held steady at chest level.",
  "needs_lipsync": true,
  "needs_product_overlay": false,
  "expected_asset": "external_videos/S001_external.mp4"
}
```

---

# 3. Prompt tạo full script từ `input_job.json` + `knowledge_base.json`

Đây là prompt cho LLM planner. Dùng Gemini/GPT/local LLM đều được.

```text
You are an AI livestream video director and ecommerce script planner.

TASK:
Generate a complete livestream video script JSON from the provided model description, product knowledge base, and content goal.

The output will be used to generate short AI videos with Gemini/Veo, then stitched into a full livestream loop.

STRICT RULES:
1. Output valid JSON only.
2. Do not generate one long script. Split into micro-scenes.
3. Each scene must be 4–6 seconds.
4. Each voiceover line must be short enough for one video segment.
5. Every scene must have one clear visual purpose only.
6. Keep visual consistency across all scenes.
7. Use the exact same base model description in every video prompt.
8. Use low motion only: blink, small nod, small hand movement.
9. Avoid actions that start in one scene and end in another.
10. Product label and exact text should not be hallucinated by the video model. If exact price/name is needed, mark it as overlay_text.
11. Create enough scenes for:
   - opening
   - brand trust
   - product introduction
   - product benefit
   - pricing/promotion
   - comment reading loop
   - FAQ answer loop
   - CTA loop
12. For product facts, only use information from the knowledge base.

INPUT:
Model base description:
{model_base_description}

Product knowledge base:
{knowledge_base_json}

Content goal:
{content_goal_json}

OUTPUT JSON FORMAT:
{
  "job_id": "...",
  "base_visual_lock": "...",
  "global_rules": {
    "aspect_ratio": "9:16",
    "camera": "...",
    "motion_level": "low",
    "scene_duration_sec": 5,
    "transition": "0.2s crossfade",
    "consistency_rule": "..."
  },
  "playlist": [
    {
      "clip_id": "A_MAIN_SALES_LOOP",
      "purpose": "...",
      "scenes": ["S001"]
    }
  ],
  "scenes": [
    {
      "scene_id": "S001",
      "clip_id": "A_MAIN_SALES_LOOP",
      "order": 1,
      "scene_type": "HOST_TALK | PRODUCT_CLOSEUP | HOST_PHONE_READING | FAQ_ANSWER | CTA",
      "duration_target_sec": 5,
      "voiceover": "Vietnamese voiceover line",
      "visual_goal": "what viewer sees",
      "overlay_text": "optional text overlay",
      "start_anchor": "first frame state",
      "end_anchor": "last frame state",
      "needs_lipsync": true,
      "needs_product_overlay": false,
      "veo_prompt": "full English prompt for Veo"
    }
  ]
}
```

---

# 4. Ví dụ `master_script.json` được sinh từ file Cocoon

Dựa trên knowledge base của m, pipeline có thể sinh bản test như này. Nội dung sản phẩm lấy từ JSON: Cocoon thuần chay, không thử nghiệm trên động vật, có sản phẩm tẩy da chết cà phê Đắk Lắk, đường thốt nốt An Giang, nước dưỡng tóc tinh dầu bưởi, dầu gội bưởi không sulfate, cùng giá livestream và ưu đãi. 

```json
{
  "job_id": "cocoon_test_001",
  "base_visual_lock": "Một phụ nữ Việt Nam 25 tuổi, tóc đen ngắn ngang cằm kiểu bob rẽ ngôi giữa, gương mặt thanh tú, trang điểm tự nhiên, tai đeo khuyên tròn nhỏ. Cô ấy mặc áo thun trắng tay ngắn có các đường sọc ngang nhỏ màu đen. Phía sau là bối cảnh khu vườn nhiệt đới với nhiều cây xanh và lá dương xỉ mờ nhẹ. Góc máy trung cận trực diện, camera cố định, ánh sáng tự nhiên ban ngày, chi tiết gương mặt sắc nét và đồng nhất.",
  "global_rules": {
    "aspect_ratio": "9:16",
    "camera": "medium close-up, fixed camera, direct front view",
    "motion_level": "low",
    "scene_duration_sec": 5,
    "transition": "0.2s crossfade",
    "consistency_rule": "All scenes must use the same face, hairstyle, outfit, background, lighting, camera angle, and body framing."
  },
  "playlist": [
    {
      "clip_id": "A_MAIN_SALES_LOOP",
      "purpose": "Loop chính giới thiệu bộ sản phẩm Cocoon",
      "scenes": ["S001", "S002", "S003", "S004", "S005", "S006"]
    },
    {
      "clip_id": "B_COMMENT_READING_LOOP",
      "purpose": "Loop host nhìn điện thoại đọc comment",
      "scenes": ["S007"]
    },
    {
      "clip_id": "C_CTA_LOOP",
      "purpose": "Loop chốt đơn và nhắc ưu đãi",
      "scenes": ["S008"]
    }
  ],
  "scenes": [
    {
      "scene_id": "S001",
      "clip_id": "A_MAIN_SALES_LOOP",
      "order": 1,
      "scene_type": "HOST_TALK",
      "duration_target_sec": 5,
      "voiceover": "Dạ em xin chào cả nhà đang xem live Cocoon hôm nay nha.",
      "visual_goal": "Host mở đầu livestream, nhìn thẳng camera, mỉm cười nhẹ.",
      "overlay_text": null,
      "start_anchor": "Host facing camera, hands relaxed near product table.",
      "end_anchor": "Host facing camera, same pose, small smile.",
      "needs_lipsync": true,
      "needs_product_overlay": false
    },
    {
      "scene_id": "S002",
      "clip_id": "A_MAIN_SALES_LOOP",
      "order": 2,
      "scene_type": "HOST_TALK",
      "duration_target_sec": 5,
      "voiceover": "Cocoon là mỹ phẩm thuần chay Việt Nam, lành tính và không thử nghiệm trên động vật.",
      "visual_goal": "Host giới thiệu triết lý thương hiệu, giữ ánh mắt tự nhiên.",
      "overlay_text": "Thuần chay • Cruelty-Free • CGMP",
      "start_anchor": "Host facing camera, product visible on table.",
      "end_anchor": "Host facing camera, product still visible.",
      "needs_lipsync": true,
      "needs_product_overlay": true
    },
    {
      "scene_id": "S003",
      "clip_id": "A_MAIN_SALES_LOOP",
      "order": 3,
      "scene_type": "PRODUCT_CLOSEUP",
      "duration_target_sec": 5,
      "voiceover": "Tẩy da chết cà phê Đắk Lắk giúp da mịn hơn và đều màu hơn.",
      "visual_goal": "Cận cảnh hũ tẩy da chết cà phê Cocoon trên bàn livestream.",
      "overlay_text": "Tẩy da chết cà phê Đắk Lắk",
      "start_anchor": "Product centered on table, clean background.",
      "end_anchor": "Product centered, same angle, slight camera push-in.",
      "needs_lipsync": false,
      "needs_product_overlay": true
    },
    {
      "scene_id": "S004",
      "clip_id": "A_MAIN_SALES_LOOP",
      "order": 4,
      "scene_type": "PRODUCT_CLOSEUP",
      "duration_target_sec": 5,
      "voiceover": "Đường thốt nốt An Giang nhẹ nhàng hơn, hợp da nhạy cảm và da khô.",
      "visual_goal": "Cận cảnh sản phẩm đường thốt nốt, ánh sáng mềm, sản phẩm rõ.",
      "overlay_text": "Phù hợp da nhạy cảm",
      "start_anchor": "Product centered, no hands.",
      "end_anchor": "Product centered, no scene change.",
      "needs_lipsync": false,
      "needs_product_overlay": true
    },
    {
      "scene_id": "S005",
      "clip_id": "A_MAIN_SALES_LOOP",
      "order": 5,
      "scene_type": "PRODUCT_CLOSEUP",
      "duration_target_sec": 5,
      "voiceover": "Combo bưởi gồm dầu gội không sulfate và nước dưỡng tóc hỗ trợ giảm gãy rụng.",
      "visual_goal": "Cận cảnh combo dầu gội bưởi và nước dưỡng tóc tinh dầu bưởi.",
      "overlay_text": "Combo chăm sóc tóc bưởi",
      "start_anchor": "Two hair-care products centered on table.",
      "end_anchor": "Two products stay centered, slight zoom only.",
      "needs_lipsync": false,
      "needs_product_overlay": true
    },
    {
      "scene_id": "S006",
      "clip_id": "A_MAIN_SALES_LOOP",
      "order": 6,
      "scene_type": "CTA",
      "duration_target_sec": 5,
      "voiceover": "Hôm nay mua trên live có giá tốt, quà tặng kèm và ưu đãi riêng ạ.",
      "visual_goal": "Host mỉm cười, chỉ nhẹ xuống khu vực giỏ hàng.",
      "overlay_text": "Bấm giỏ hàng để nhận deal livestream",
      "start_anchor": "Host facing camera, right hand near lower screen area.",
      "end_anchor": "Host facing camera, hand returns near product table.",
      "needs_lipsync": true,
      "needs_product_overlay": true
    },
    {
      "scene_id": "S007",
      "clip_id": "B_COMMENT_READING_LOOP",
      "order": 7,
      "scene_type": "HOST_PHONE_READING",
      "duration_target_sec": 5,
      "voiceover": "Dạ câu hỏi này em trả lời ngay cho mình nha.",
      "visual_goal": "Host nhìn xuống điện thoại như đang đọc comment livestream.",
      "overlay_text": "Đang trả lời comment...",
      "start_anchor": "Host holding phone, looking slightly down.",
      "end_anchor": "Host still holding phone, looking slightly down.",
      "needs_lipsync": true,
      "needs_product_overlay": false
    },
    {
      "scene_id": "S008",
      "clip_id": "C_CTA_LOOP",
      "order": 8,
      "scene_type": "CTA",
      "duration_target_sec": 5,
      "voiceover": "Cả nhà bấm vào giỏ hàng góc dưới để em hỗ trợ chốt đơn nha.",
      "visual_goal": "Host nhìn camera, mỉm cười và chỉ nhẹ xuống góc dưới màn hình.",
      "overlay_text": "Chốt đơn tại giỏ hàng",
      "start_anchor": "Host facing camera, product visible on table.",
      "end_anchor": "Host facing camera, product visible on table.",
      "needs_lipsync": true,
      "needs_product_overlay": true
    }
  ]
}
```

---

# 5. Tạo prompt Veo từ từng scene

Sau khi có `master_script.json`, backend tạo `external_prompt_queue.json`.

## Template chung

```text
Vertical 9:16 ecommerce livestream video, target duration {duration_target_sec} seconds.

[VISUAL LOCK]
{base_visual_lock}

[CONSISTENCY RULES]
Use the same face identity, same hairstyle, same outfit, same background, same lighting, same camera angle, and same medium close-up framing across all scenes.
Do not change the model's facial structure, age, outfit, hairstyle, or background.
Camera is fixed. No zoom unless explicitly requested.
Motion level is low.

[SCENE GOAL]
{visual_goal}

[HOST ACTION]
{host_action}

[PRODUCT ACTION]
{product_action}

[START FRAME]
{start_anchor}

[END FRAME]
{end_anchor}

[MOTION]
Subtle movement only: natural blinking, small head nod, calm breathing, tiny hand movement.
No large gesture. No body turn. No scene transition.
The first and last frames should be visually similar so the clip can be looped or stitched.

[PRODUCT RULES]
Use the uploaded product reference image only as visual reference.
Do not invent new product label text.
Do not distort product packaging.
If exact price or product text is needed, leave space for later overlay.

[NEGATIVE]
distorted face, different person, changed hairstyle, changed outfit, warped product, fake logo, unreadable text, extra fingers, broken hands, heavy camera movement, cinematic cut, scene change
```

## Prompt S001 mẫu

```text
Vertical 9:16 ecommerce livestream video, target duration 5 seconds.

[VISUAL LOCK]
Một phụ nữ Việt Nam 25 tuổi, tóc đen ngắn ngang cằm kiểu bob rẽ ngôi giữa, gương mặt thanh tú, trang điểm tự nhiên, tai đeo khuyên tròn nhỏ. Cô ấy mặc áo thun trắng tay ngắn có các đường sọc ngang nhỏ màu đen. Phía sau là bối cảnh khu vườn nhiệt đới với nhiều cây xanh và lá dương xỉ mờ nhẹ. Góc máy trung cận trực diện, camera cố định, ánh sáng tự nhiên ban ngày, chi tiết gương mặt sắc nét và đồng nhất.

[CONSISTENCY RULES]
Use the same face identity, same hairstyle, same outfit, same background, same lighting, same camera angle, and same medium close-up framing across all scenes.
Do not change the model's facial structure, age, outfit, hairstyle, or background.
Camera is fixed. Motion level is low.

[SCENE GOAL]
The host opens a Cocoon livestream, looks directly at the camera, and smiles gently.

[HOST ACTION]
She faces the camera, smiles naturally, and appears to speak in a friendly livestream style.

[PRODUCT ACTION]
Products are visible on the table but not moved.

[START FRAME]
Host facing camera, hands relaxed near product table.

[END FRAME]
Host facing camera, same pose, small smile.

[MOTION]
Subtle movement only: natural blinking, small head nod, calm breathing, tiny mouth movement.
No large gesture. No body turn. No scene transition.
The first and last frames should be visually similar.

[PRODUCT RULES]
Do not invent readable product text.
Leave lower third space for livestream overlay.

[NEGATIVE]
distorted face, different person, changed hairstyle, changed outfit, warped product, fake logo, unreadable text, extra fingers, broken hands, heavy camera movement, cinematic cut, scene change
```

---

# 6. Cơ chế Gemini/Veo manual bridge

Vì m đang test workflow, bridge chỉ cần làm 4 việc:

```text
1. Đọc external_prompt_queue.json
2. Copy prompt scene hiện tại vào clipboard
3. M paste vào Gemini/Veo, generate, download video
4. Script watch folder download và map video về đúng scene_id
```

Không cần auto click Gemini. Việc này giữ pipeline sạch hơn, vì Playwright cũng khuyến nghị không automate default Chrome profile; nếu có browser automation thì nên dùng profile riêng thay vì profile duyệt web chính. ([Playwright][2])

## Output queue

```json
{
  "job_id": "cocoon_test_001",
  "current_scene_index": 0,
  "download_dir": "watched_downloads",
  "external_video_dir": "external_videos",
  "scenes": [
    {
      "scene_id": "S001",
      "scene_type": "HOST_TALK",
      "voiceover": "Dạ em xin chào cả nhà đang xem live Cocoon hôm nay nha.",
      "veo_prompt": "Vertical 9:16 ecommerce livestream video..."
    }
  ]
}
```

## Helper copy prompt

```python
import json
import pyperclip
from pathlib import Path

QUEUE_PATH = Path("external_prompt_queue.json")
STATE_PATH = Path("external_state.json")

def read_json(path, default=None):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return default

def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def copy_next_prompt():
    queue = read_json(QUEUE_PATH)
    state = read_json(STATE_PATH, {"current_index": 0, "completed": []})

    scenes = queue["scenes"]
    idx = state["current_index"]

    if idx >= len(scenes):
        print("Done. No more prompts.")
        return

    scene = scenes[idx]
    pyperclip.copy(scene["veo_prompt"])

    print("=" * 80)
    print(f"Copied: {scene['scene_id']} - {scene['scene_type']}")
    print("Voiceover:", scene["voiceover"])
    print("=" * 80)
    print(scene["veo_prompt"])
    print("=" * 80)
    print("Paste into Gemini/Veo, generate, download video, then run watcher.")

    state["last_copied_scene_id"] = scene["scene_id"]
    write_json(STATE_PATH, state)

if __name__ == "__main__":
    copy_next_prompt()
```

---

# 7. Watch downloaded video và map vào scene

```python
import json
import shutil
import time
from pathlib import Path

QUEUE_PATH = Path("external_prompt_queue.json")
STATE_PATH = Path("external_state.json")
DOWNLOAD_DIR = Path("watched_downloads")
OUTPUT_DIR = Path("external_videos")
VIDEO_EXTS = {".mp4", ".mov", ".webm", ".mkv"}

DOWNLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

def read_json(path, default=None):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return default

def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def get_newest_video():
    files = [
        p for p in DOWNLOAD_DIR.iterdir()
        if p.is_file() and p.suffix.lower() in VIDEO_EXTS
    ]
    if not files:
        return None
    return max(files, key=lambda p: p.stat().st_mtime)

def wait_until_download_stable(path, stable_wait=2):
    size_1 = path.stat().st_size
    time.sleep(stable_wait)
    size_2 = path.stat().st_size
    return size_1 == size_2 and size_2 > 0

def map_download_to_scene(timeout_sec=600):
    state = read_json(STATE_PATH, {"current_index": 0, "completed": []})
    scene_id = state.get("last_copied_scene_id")

    if not scene_id:
        raise RuntimeError("No last_copied_scene_id found. Copy a prompt first.")

    print(f"Waiting for downloaded video for {scene_id}...")

    start = time.time()

    while time.time() - start < timeout_sec:
        video = get_newest_video()

        if video and wait_until_download_stable(video):
            target = OUTPUT_DIR / f"{scene_id}_external.mp4"
            shutil.move(str(video), str(target))

            state["completed"].append({
                "scene_id": scene_id,
                "video_path": str(target)
            })
            state["current_index"] += 1
            state["last_copied_scene_id"] = None

            write_json(STATE_PATH, state)

            print(f"Saved: {target}")
            return str(target)

        time.sleep(2)

    raise TimeoutError("No downloaded video found.")

if __name__ == "__main__":
    map_download_to_scene()
```

---

# 8. Audio generation cho từng scene

Với test nhanh, dùng `edge-tts`. Package này cho phép tạo speech từ text bằng Microsoft Edge online TTS thông qua Python/CLI, hợp làm MVP nhanh. ([GitHub][3])

```python
import asyncio
import edge_tts
from pathlib import Path

async def _edge_tts(text, output_path, voice="vi-VN-HoaiMyNeural"):
    communicate = edge_tts.Communicate(
        text=text,
        voice=voice,
        rate="+0%",
        volume="+0%"
    )
    await communicate.save(output_path)

def generate_audio(text, output_path):
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    asyncio.run(_edge_tts(text, output_path))
    return output_path
```

---

# 9. Sync external video với audio

Vì Gemini/Veo có thể trả video dài hơn hoặc ngắn hơn mong muốn, backend phải chuẩn hóa:

```text
external video
→ normalize 720x1280
→ trim hoặc loop theo audio duration
→ add audio
→ nếu host scene thì đưa qua Wav2Lip
→ scene_final.mp4
```

FFmpeg có concat demuxer để ghép danh sách file video theo thứ tự, nhưng các file nên được normalize cùng codec/resolution/fps trước để tránh lỗi mismatch. ([FFmpeg][4])

```python
import subprocess
import json
from pathlib import Path

def media_duration(path):
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "json",
        path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return float(json.loads(result.stdout)["format"]["duration"])

def normalize_video(input_video, output_video, width=720, height=1280, fps=25):
    vf = (
        f"scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},fps={fps},format=yuv420p"
    )

    cmd = [
        "ffmpeg", "-y",
        "-i", input_video,
        "-vf", vf,
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "23",
        "-an",
        output_video
    ]
    subprocess.run(cmd, check=True)
    return output_video

def fit_video_to_audio(input_video, audio_path, output_video):
    audio_len = media_duration(audio_path)
    video_len = media_duration(input_video)

    if video_len >= audio_len:
        cmd = [
            "ffmpeg", "-y",
            "-i", input_video,
            "-i", audio_path,
            "-t", str(audio_len),
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-c:v", "copy",
            "-c:a", "aac",
            "-shortest",
            output_video
        ]
    else:
        loop_count = int(audio_len // video_len) + 1
        cmd = [
            "ffmpeg", "-y",
            "-stream_loop", str(loop_count),
            "-i", input_video,
            "-i", audio_path,
            "-t", str(audio_len),
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "23",
            "-c:a", "aac",
            "-shortest",
            output_video
        ]

    subprocess.run(cmd, check=True)
    return output_video
```

---

# 10. Rule lipsync

Scene nào có host nói thì lipsync. Scene sản phẩm thì voiceover thôi.

```python
def needs_lipsync(scene):
    return scene["scene_type"] in [
        "HOST_TALK",
        "HOST_PHONE_READING",
        "FAQ_ANSWER",
        "CTA"
    ] and scene.get("needs_lipsync", True)
```

Flow cho từng scene:

```python
def process_scene(scene, external_video_path, job_dir):
    scene_id = scene["scene_id"]
    scene_dir = Path(job_dir) / "scenes" / scene_id
    scene_dir.mkdir(parents=True, exist_ok=True)

    audio_path = scene_dir / "voice.wav"
    normalized_video = scene_dir / "normalized.mp4"
    synced_video = scene_dir / "synced.mp4"
    final_video = scene_dir / "scene_final.mp4"

    generate_audio(scene["voiceover"], str(audio_path))
    normalize_video(external_video_path, str(normalized_video))
    fit_video_to_audio(str(normalized_video), str(audio_path), str(synced_video))

    if needs_lipsync(scene):
        run_wav2lip(
            face_video_or_image=str(synced_video),
            audio_path=str(audio_path),
            output_path=str(final_video)
        )
    else:
        final_video.write_bytes(synced_video.read_bytes())

    return str(final_video)
```

`run_wav2lip` dùng lại worker m đã có trước đó.

---

# 11. Ghép final livestream loop

Sau khi có `scene_final.mp4` cho từng scene:

```python
def concat_videos(video_paths, output_path):
    list_path = Path(output_path).parent / "concat_list.txt"

    with open(list_path, "w", encoding="utf-8") as f:
        for path in video_paths:
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

Nếu lỗi codec mismatch thì normalize lại toàn bộ scene trước khi concat.

Output cuối:

```text
outputs/cocoon_test_001/
  master_script.json
  external_prompt_queue.json
  external_videos/
    S001_external.mp4
    S002_external.mp4
  scenes/
    S001/scene_final.mp4
    S002/scene_final.mp4
  final/
    A_MAIN_SALES_LOOP.mp4
    B_COMMENT_READING_LOOP.mp4
    C_CTA_LOOP.mp4
    final_livestream_loop.mp4
```

---

# 12. Cách đảm bảo video 1 giống video 2

M không nên cố tạo cảm giác “một cú quay liên tục”. Với Veo/Gemini UI, cách ổn hơn là **giả lập livestream bằng nhiều cut ngắn có cùng khung hình**.

Rule bắt buộc:

```text
1. Mỗi scene dùng cùng base_visual_lock.
2. Mỗi prompt lặp lại cùng camera, outfit, background, lighting.
3. Scene dài tối đa 4–6 giây.
4. Không có hành động kéo dài qua 2 scene.
5. Start_anchor và end_anchor phải gần giống nhau.
6. Chuyển giữa scene bằng cut hoặc crossfade 0.2s.
7. Product text/giá dùng overlay hậu kỳ, không bắt Veo vẽ chữ.
8. Không yêu cầu host xoay người, đưa tay quá xa, hoặc thay đổi góc mặt.
```

Mấu chốt là: **giống về format, không cần nối hành động liên tục**. Livestream thật cũng thường có cut/loop/replay, nên cách này chấp nhận được.

---

# 13. Pipeline tạm hoàn chỉnh

```text
Bước 1:
input_job.json + knowledge_base.json

Bước 2:
planner sinh master_script.json

Bước 3:
prompt_builder sinh external_prompt_queue.json

Bước 4:
copy_prompt_helper copy prompt S001

Bước 5:
m paste vào Gemini/Veo, generate, download video

Bước 6:
download_watcher map file download thành S001_external.mp4

Bước 7:
lặp lại đến hết scene

Bước 8:
backend tạo audio từng scene bằng TTS

Bước 9:
backend sync video với audio

Bước 10:
host scene chạy Wav2Lip

Bước 11:
product scene giữ voiceover + overlay

Bước 12:
concat theo playlist

Bước 13:
xuất final_livestream_loop.mp4
```


[1]: https://ai.google.dev/gemini-api/docs/video?utm_source=chatgpt.com "Generate videos with Veo 3.1 in Gemini API"
[2]: https://playwright.dev/docs/api/class-browsertype?utm_source=chatgpt.com "BrowserType"
[3]: https://github.com/rany2/edge-tts?utm_source=chatgpt.com "rany2/edge-tts: Use Microsoft Edge's online text-to-speech ..."
[4]: https://ffmpeg.org/ffmpeg-formats.html?utm_source=chatgpt.com "FFmpeg Formats Documentation"
