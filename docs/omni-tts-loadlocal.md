# OmniVoice local TTS

Script local:

```powershell
python tests/omni-wraptest.py --ref-audio data/voices/host_ref.wav
```

Input mặc định:

```text
data/cocoon_livecommerce_script_v2.json
```

Output mặc định:

```text
data/outputs/omni_tts/<job_id>/
  audio/S001.wav
  text/S001.txt
  tts_manifest.csv
  voice_profile.json
```

## Cài dependency

```powershell
pip install omnivoice soundfile torch tqdm
```

## Giữ một giọng duy nhất

Mặc định script dùng `--voice-mode clone`, tức là mọi scene đều gọi OmniVoice với cùng một `--ref-audio`. Đây là cách ổn nhất để giữ một người nói nhất quán.

Reference audio nên là một đoạn 3-10 giây, ít nhiễu, một người nói tiếng Việt, cùng chất giọng livestream mong muốn.

## Test nhanh không load model

```powershell
python tests/omni-wraptest.py --dry-run --max-scenes 3
```

## Chạy tiếp khi bị dừng

```powershell
python tests/omni-wraptest.py --ref-audio data/voices/host_ref.wav --resume
```

Hoặc chạy từ một scene cụ thể:

```powershell
python tests/omni-wraptest.py --ref-audio data/voices/host_ref.wav --start-scene S010
```

## Không có reference audio

Có thể dùng mode thiết kế giọng:

```powershell
python tests/omni-wraptest.py --voice-mode design --instruct "female, young adult, moderate pitch"
```

Mode này dùng cùng thuộc tính giọng cho toàn bộ scene, nhưng không chắc bằng clone mode.
