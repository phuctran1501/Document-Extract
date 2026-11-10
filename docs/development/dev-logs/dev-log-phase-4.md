# Dev Log: Phase 4 — Tăng Cường Độ Bền Vững và Đóng Gói (Robustness and Packaging)

- **Ngày:** 2026-11-10
- **Issue/PR liên quan:** Phase 4 ([docs/development/roadmap.md](file:///d:/DocuExtract/docs/development/roadmap.md), [docs/development/plans/2026-11-10-phase-4-robustness-and-packaging.md](file:///d:/DocuExtract/docs/development/plans/2026-11-10-phase-4-robustness-and-packaging.md))
- **Files:** `app/core/config.py`, `app/core/correlation.py`, `app/core/logging.py`, `app/core/streaming.py`, `app/main.py`, `app/api/routes/documents.py`, `app/services/document_service.py`, `Dockerfile`, `.dockerignore`, `.env.example`, `.github/workflows/ci.yml`, `docs/operations/service-configuration.md`, `docs/architecture/decisions/ADR-002-structured-logging-and-robustness.md`, `tests/unit/test_streaming.py`, `tests/unit/test_logging.py`, `tests/integration/test_document_extract_api.py`

## Những gì đã xây dựng
- Triển khai tiện ích bounded chunked stream reading `read_upload_file_bounded` trong `app/core/streaming.py`: Đọc upload theo từng chunk 64 KiB, tích lũy dung lượng và ném ngay `AppException(413, "FILE_TOO_LARGE")` nếu vượt ngưỡng tối đa mà không đọc tiếp vào RAM.
- Cập nhật endpoint `POST /api/v1/documents/extract` trong `app/api/routes/documents.py`:
  - Kiểm tra sớm header `Content-Length`: Từ chối ngay lập tức với HTTP 413 nếu client khai báo file vượt `max_upload_size_bytes` trước khi nhận stream.
  - Sử dụng `read_upload_file_bounded` để bảo vệ server trước các payload độc hại hoặc truyền dạng chunked stream không giới hạn.
- Xây dựng hệ thống structured logging trong `app/core/logging.py`:
  - `StructuredJsonFormatter`: Xuất log dạng JSON 1 dòng với timestamp ISO 8601 UTC, log level, logger name, message, và tự động đính kèm `correlation_id` từ `ContextVar`.
  - `StructuredTextFormatter`: Hỗ trợ log text có cấu trúc dễ đọc khi debug cục bộ (`DOCUEXTRACT_LOG_JSON_FORMAT=false`).
  - Hàm `setup_logging()` cấu hình root logger và đồng bộ hóa các logger của Uvicorn (`uvicorn`, `uvicorn.access`, `uvicorn.error`).
- Tích hợp request lifecycle logging trong `CorrelationIdMiddleware`: Ghi log method, path, status code, duration_ms, và correlation_id mà không bao giờ log body.
- Thực thi nghiêm ngặt chính sách **Zero Document Logging (NFR-01)**: `DocumentService` chỉ log các trường metadata kỹ thuật an toàn (`doc_filename`, `format`, `size_bytes`, `character_count`, `word_count`), tuyệt đối không ghi log nội dung text hoặc binary.
- Đóng gói container production:
  - Tạo `Dockerfile` trên nền `python:3.12-slim` chạy với quyền **non-root user** (`appuser:10001`).
  - Tích hợp `HEALTHCHECK` kiểm tra liveness qua endpoint `/health`.
  - Tạo `.dockerignore` tinh gọn loại bỏ toàn bộ files thừa, test fixtures và secrets.
- Cập nhật CI workflow (`.github/workflows/ci.yml`) bổ sung bước `docker build -t docuextract:test .`.
- Bổ sung 13 tests mới (4 streaming unit tests, 7 logging & security unit tests, 2 integration tests), nâng tổng số test suite lên **61 tests pass**.
- Tài liệu hóa hoàn chỉnh cấu hình và quyết định kiến trúc: `docs/operations/service-configuration.md` và `docs/architecture/decisions/ADR-002-structured-logging-and-robustness.md`.

## Lý do chọn thiết kế này
- **Chống cạn kiệt bộ nhớ (Denial of Service / OOM Protection):** Phương thức mặc định `await file.read()` của Starlette/FastAPI sẽ nạp toàn bộ file vào bộ nhớ trước khi service có cơ hội kiểm tra dung lượng. Bằng cách kết hợp kiểm tra header `Content-Length` sớm và đọc stream theo chunks có chặn ngưỡng (bounded streaming), server được bảo vệ toàn diện kể cả khi client gửi stream chunked không khai báo độ dài.
- **Khả năng quan sát chuẩn cloud-native:** Xuất log JSON 1 dòng trực tiếp ra `stdout` cho phép các công cụ thu thập log như Fluentd, Logstash, Datadog hay AWS CloudWatch tự động parse mà không cần cấu hình regex phức tạp.
- **Bảo mật dữ liệu cá nhân & nhạy cảm (NFR-01):** Tài liệu gửi tới DocuExtract (hồ sơ, CV, hợp đồng) chứa dữ liệu bảo mật. Việc kiểm soát chặt chẽ các trường trong log và có test tự động kiểm chứng đảm bảo không có rò rỉ dữ liệu qua logging pipelines.
- **An ninh container (Least Privilege):** Chạy container dưới quyền `root` tiềm ẩn nguy cơ bảo mật nghiêm trọng (container escape). User `appuser` (UID 10001) được tạo riêng biệt với shell bị vô hiệu hóa (`/bin/false`).

## Cách hoạt động
1. Khi request đến, `CorrelationIdMiddleware` cấp phát hoặc nhận diện `X-Correlation-ID`, lưu vào `ContextVar`.
2. Khi request vào route `extract`:
   - Nếu có header `Content-Length > 10 MiB` $\rightarrow$ ném ngay 413 `FILE_TOO_LARGE`.
   - `read_upload_file_bounded` đọc từng chunk 64 KiB: nếu tổng bytes vượt 10 MiB $\rightarrow$ ngắt stream và ném 413.
3. `DocumentService` tiếp nhận bytes, log metadata an toàn kèm correlation ID, gọi parser tương ứng, và chuẩn hóa text.
4. Response trả về kèm header `X-Correlation-ID`. `CorrelationIdMiddleware` ghi log hoàn tất request kèm thời gian thực thi (duration ms).

## Những điều cần lưu ý (Gotchas)
- **Từ khóa bảo lưu trong Python LogRecord:** Khi truyền `extra={...}` vào logger của Python, các thuộc tính chuẩn như `filename`, `module`, `funcName` không được phép ghi đè (sẽ gây `KeyError: Attempt to overwrite 'filename' in LogRecord`). Vì vậy, metadata tên file tài liệu được đặt tên an toàn là `doc_filename`.
- **Cảnh báo Deprecation Starlette HTTP 413:** Trong Starlette/FastAPI phiên bản mới, `status.HTTP_413_REQUEST_ENTITY_TOO_LARGE` đã chuyển thành `status.HTTP_413_CONTENT_TOO_LARGE` theo chuẩn HTTP mới nhất (RFC 9110).

## Kiểm thử và bằng chứng
1. `uv run ruff check .` $\rightarrow$ `All checks passed!`
2. `uv run ruff format --check .` $\rightarrow$ `71 files already formatted!`
3. `uv run pytest` $\rightarrow$ `61 passed, 1 warning in 0.72s!`

## Điểm phỏng vấn / học tập
- **Khái niệm đã học:** Kỹ thuật bounded streaming chống tấn công DoS memory exhaustion, cấu trúc nội bộ của `logging.LogRecord` trong Python, kỹ thuật kiểm thử không rò rỉ dữ liệu (Canary String Testing) với `caplog`, và quy chuẩn xây dựng Dockerfile non-root an toàn.
- **Đánh đổi (Trade-off):** Đọc stream theo chunks 64 KiB có thể tăng thêm một lượng rất nhỏ overhead syscall so với đọc một lần cho các file nhỏ, nhưng đổi lại tính an toàn tuyệt đối trước các file quá cỡ hoặc stream vô tận.

