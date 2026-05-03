# Hướng dẫn code — AI Service

Tài liệu này bổ sung [README.md](../README.md): mô tả từng thư mục và quy ước code để thêm tính năng, đổi adapter AI, chạy test.

---

## Cấu trúc gốc repo

| Đường dẫn | Mục đích |
|-----------|----------|
| `app/` | Toàn bộ mã nguồn ứng dụng FastAPI (Clean Architecture). |
| `tests/` | Pytest: `unit/` (use case, mock port), `integration/` (HTTP/endpoint). |
| `docs/` | Tài liệu bổ sung (file này). |
| `requirements.txt` | Dependencies Python. |
| `.env.example` | Mẫu biến môi trường; copy thành `.env`. |
| `Dockerfile` | Build image chạy service. |
| `docker-compose.yml` | Orchestration (app + dependency phụ trợ nếu có). |
| `data/` | Tạo khi chạy app: SQLite (`ai_service.db`), thư mục output (theo `STORAGE_LOCAL_PATH`). |

---

## `app/` — Tổng quan lớp

Luồng phụ thuộc **chỉ hướng vào trong**: `api` → `application` → `domain` ← `infrastructure` (implement interface).

- **domain**: Không import FastAPI/SQLAlchemy. Entity, enum, exception, **interface (ABC)**.
- **application**: Use case + DTO; chỉ nói chuyện qua interface domain.
- **infrastructure**: Implement interface (DB, storage, mock/real AI).
- **api**: HTTP/WebSocket, Pydantic schema, middleware, wiring qua `deps.py`.
- **core**: Logging, security, WebSocket manager, events — dùng chéo nhiều lớp.

---

## `app/api/` — Presentation

| Thư mục / file | Mô tả |
|----------------|--------|
| `deps.py` | **Trung tâm DI**: `SettingsDep`, `SessionDep`, repository, `IVideoService` / `ITTSService` / `IStorageService`, factory use case (`get_generate_video_use_case`, …). Thay mock → real model **ở đây** (singleton `get_video_service`, `get_tts_service`). |
| `schemas/` | Pydantic: body/query response REST (`video`, `tts`, `job`, `common`, `ws_messages`). Không chứa logic nghiệp vụ. |
| `middlewares/` | `cors`, `rate_limit`, `auth` — thứ tự stack xem `main.py`. |
| `v1/router.py` | Gom router: `api_v1_router` prefix `/api/v1`, `health_router_global` (không prefix), `ws_router` (WebSocket). |
| `v1/endpoints/` | REST: `health.py`, `video.py`, `tts.py`, `jobs.py`. |
| `v1/endpoints/websockets/` | `video_ws.py`, `tts_ws.py` — auth message → gọi use case stream. |

**Quy ước**: Endpoint chỉ parse request → gọi use case → map sang schema response / WebSocket message. Không gọi trực tiếp SQLAlchemy hoặc file storage từ endpoint (trừ khi refactor sau này có lý do rõ).

---

## `app/application/` — Use cases & DTO

| Thư mục | Mô tả |
|---------|--------|
| `dto/` | `VideoRequest`, `TTSRequest` — input đã “sạch” cho use case (map từ API schema). |
| `use_cases/` | `generate_video.py`, `text_to_speech.py`, `get_job_status.py`: tạo/cập nhật `Job`, gọi `IVideoService` / `ITTSService`, lưu output qua `IStorageService`. |

**Luồng điển hình (video REST hoặc WS)**: `execute` / `execute_stream` → tạo `Job` → `job_repository` → stream hoặc batch từ service → cập nhật tiến độ → lưu file → trạng thái job.

---

## `app/domain/` — Nghiệp vụ thuần & “cổng”

| Thư mục | Mô tả |
|---------|--------|
| `entities/` | `Job`, `VideoResult`, `VideoChunk`, `AudioChunk` — đối tượng miền. |
| `enums/` | `JobStatus`, `ModelType`. |
| `exceptions/` | `DomainException` và con (`video`, `tts`) — được `main.py` map sang HTTP. |
| `interfaces/` | **Ports**: `IVideoService`, `ITTSService`, `IJobRepository`, `IStorageService` — ABC cho infrastructure. |

Thêm adapter mới: **implement đúng ABC** trong `interfaces/`, không sửa entity trừ khi contract thật sự đổi.

---

## `app/infrastructure/` — Adapter

| Thư mục | Mô tả |
|---------|--------|
| `ai_models/` | `video_generator.py` (`MockVideoGenerator`), `tts_engine.py` (`MockTTSEngine`) — thay bằng model thật, giữ signature `IVideoService` / `ITTSService`. |
| `persistence/` | `database.py` (async engine/session), `models/job_model.py`, `repositories/job_repository.py` — implement `IJobRepository`. |
| `storage/` | `local_storage.py` — implement `IStorageService`; có thể thêm S3 sau (cùng interface). |
| `cache/redis_cache.py` | Redis (chuẩn bị/hạn chế tùy phiên bản code). |
| `queue/task_manager.py` | Task/queue (mở rộng job nền). |

---

## `app/core/`

| File | Vai trò |
|------|---------|
| `logging.py` | Khởi tạo logging (lifespan gọi `setup_logging`). |
| `security.py` | `verify_api_key` — so khớp với `API_KEY_SECRET` / header. |
| `ws_manager.py` | Quản lý kết nối WebSocket nếu có dùng chung. |
| `events.py` | Sự kiện app-level (mở rộng). |

---

## `app/config.py` & `app/main.py`

- **`Settings`**: đọc env qua Pydantic; `get_settings()` có `@lru_cache`.
- **`lifespan`**: `init_db()`, tạo thư mục `storage_local_path` + `videos`/`audio`, `./data`.
- **`create_app`**: Rate limit → CORS → handler `DomainException` → mount router → static `/static/outputs` trỏ tới thư mục output.
- **Swagger**: `debug=True` mới bật `/docs`, `/redoc`.

---

## Thêm endpoint REST mới (checklist)

1. **Schema** (`app/api/schemas/`): model request/response.
2. **DTO** (nếu cần) (`app/application/dto/`): tách input phức tạp khỏi API.
3. **Use case** (`app/application/use_cases/`): nhận port qua constructor; không import infrastructure cụ thể.
4. **Interface** (nếu cần service mới): thêm ABC trong `app/domain/interfaces/`.
5. **Adapter**: implement trong `app/infrastructure/...`.
6. **`deps.py`**: factory service + `get_*_use_case` + `Annotated[..., Depends(...)]`.
7. **Endpoint** (`app/api/v1/endpoints/`): inject use case, trả schema.
8. **`router.py`**: `include_router` cho module mới.
9. **Test**: `tests/unit/` mock interface; `tests/integration/` gọi `TestClient`.

---

## WebSocket — code path

1. Client kết nối URL trong README (`/ws/video/generate`, `/ws/tts/stream`).
2. Handler trong `websockets/*.py`: nhận JSON (`authenticate` → `generate` / `synthesize`).
3. Sau auth, gọi `execute_stream` trên use case tương ứng; forward chunk ra message (`progress`, `frame_chunk`, `audio_chunk`, `complete`, `error`).
4. Protocol chi tiết: xem `app/api/schemas/ws_messages.py` và handler thực tế để đồng bộ `type` field.

---

## Plug-in model AI (thay mock)

1. Tạo class mới (vd. `CogVideoAdapter`) trong `app/infrastructure/ai_models/`, implement đủ method của `IVideoService` hoặc `ITTSService`.
2. Trong `get_video_service()` / `get_tts_service()` (`deps.py`), khởi tạo adapter mới thay `MockVideoGenerator` / `MockTTSEngine`.
3. Dùng `Settings` (`video_model_id`, `tts_model_id`, device…) để cấu hình; tránh hard-code trong use case.
4. `readiness`: endpoint readiness gọi `is_ready()` — implement đúng để probe chính xác.

---

## Testing

| Thư mục | Nội dung |
|---------|----------|
| `tests/conftest.py` | Fixtures chung (app, client, override dependency nếu có). |
| `tests/unit/` | `test_*_usecase.py` — mock `IJobRepository`, `IVideoService`, … |
| `tests/integration/test_endpoints.py` | Gọi API thật (có thể cần DB/test env). |

Chạy: `pytest tests/unit/ -v`, `pytest tests/integration/ -v`, hoặc `pytest -v`.

---

## Biến môi trường quan trọng

- **`API_KEY_SECRET`**: phải khớp giá trị gửi header `X-API-Key` (REST); WebSocket thường gửi `api_key` trong message đầu — xem handler WS.
- **`DATABASE_URL`**: dev SQLite; prod nên PostgreSQL + `asyncpg`.
- **`STORAGE_LOCAL_PATH`**: trùng với static mount `./data/outputs` mặc định; URL file public qua `/static/outputs/...`.
- **`CORS_ORIGINS`**: danh sách origin frontend (comma-separated trong `.env.example`).

---

## Ghi nhớ nhanh

- **Đổi hành vi AI**: infrastructure + `deps.py`.
- **Đổi rule nghiệp vụ / job lifecycle**: use case + domain entity/exception.
- **Đổi contract HTTP/WS**: schemas + endpoint + (tuỳ chọn) ws_messages.

Nếu refactor lớn (thêm S3, queue Celery), giữ **interface** ổn định để API và use case ít động vào nhất có thể.
