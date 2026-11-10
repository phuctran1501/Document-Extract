# Cấu Hình Dịch Vụ và Vận Hành DocuExtract

Tài liệu này hướng dẫn chi tiết các biến môi trường cấu hình, cơ chế structured logging, health check probes, và hướng dẫn vận hành container cho DocuExtract.

---

## 1. Biến môi trường (Environment Variables)

Mọi cấu hình đều được nạp thông qua Pydantic Settings với tiền tố `DOCUEXTRACT_` từ file `.env` hoặc trực tiếp từ biến môi trường của hệ điều hành / container runtime.

| Biến môi trường | Kiểu dữ liệu | Giá trị mặc định | Mô tả |
| :--- | :--- | :--- | :--- |
| `DOCUEXTRACT_APP_NAME` | `str` | `"DocuExtract"` | Tên ứng dụng hiển thị trong Swagger UI / OpenAPI docs. |
| `DOCUEXTRACT_APP_VERSION` | `str` | `"0.1.0"` | Phiên bản ứng dụng hiện tại. |
| `DOCUEXTRACT_DEBUG` | `bool` | `false` | Bật/tắt chế độ debug (chỉ nên bật ở môi trường dev). |
| `DOCUEXTRACT_HOST` | `str` | `"127.0.0.1"` (`0.0.0.0` trong Docker) | Địa chỉ IP lắng nghe kết nối của Uvicorn. |
| `DOCUEXTRACT_PORT` | `int` | `8000` | Cổng HTTP lắng nghe. |
| `DOCUEXTRACT_MAX_UPLOAD_SIZE_BYTES` | `int` | `10485760` (10 MiB) | Dung lượng tối đa cho phép của tệp upload. |
| `DOCUEXTRACT_LOG_LEVEL` | `str` | `"INFO"` | Mức độ log (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`). |
| `DOCUEXTRACT_LOG_JSON_FORMAT` | `bool` | `true` | Xuất log dạng JSON 1 dòng (production) hoặc text dễ đọc (dev). |

### File cấu hình mẫu (`.env.example`):
```bash
# DocuExtract Environment Configuration Example
DOCUEXTRACT_DEBUG=false
DOCUEXTRACT_HOST=127.0.0.1
DOCUEXTRACT_PORT=8000
DOCUEXTRACT_MAX_UPLOAD_SIZE_BYTES=10485760
DOCUEXTRACT_LOG_LEVEL=INFO
DOCUEXTRACT_LOG_JSON_FORMAT=true
```

---

## 2. Structured Logging & An Toàn Dữ Liệu (NFR-01)

### 2.1. Định dạng Log
Khi `DOCUEXTRACT_LOG_JSON_FORMAT=true`, mọi dòng log được xuất ra `stdout` dưới dạng JSON tiêu chuẩn một dòng:
```json
{
  "timestamp": "2026-11-10T08:31:30.123456+00:00",
  "level": "INFO",
  "logger": "app.services.document_service",
  "message": "Document extracted successfully: filename=resume.pdf, format=pdf, size_bytes=104857, characters=1250, words=230",
  "correlation_id": "8f3b2c1a0e4d4e...",
  "doc_filename": "resume.pdf",
  "format": "pdf",
  "size_bytes": 104857,
  "character_count": 1250,
  "word_count": 230
}
```

### 2.2. Chính sách Zero Document Logging
Tuân thủ tuyệt đối yêu cầu phi chức năng **NFR-01**:
- Hệ thống chỉ ghi log các thông số kỹ thuật an toàn: `doc_filename`, `format`, `size_bytes`, `character_count`, `word_count`, `duration_ms`, `correlation_id`.
- **Tuyệt đối không bao giờ** ghi log nội dung văn bản trích xuất (`raw_text`, `normalized_text`), nội dung nhị phân (binary bytes), hay thông tin nhạy cảm của người dùng kể cả ở cấp độ log `DEBUG`.
- Hành vi này được kiểm chứng nghiêm ngặt bằng test tự động `tests/unit/test_logging.py` và `tests/integration/test_document_extract_api.py`.

---

## 3. Health Check (`/health`)

Endpoint `/health` được thiết kế siêu nhẹ (stateless), không phụ thuộc database hay dịch vụ bên ngoài, phục vụ cho Docker `HEALTHCHECK` và Kubernetes Liveness/Readiness Probes.

### 3.1. Request & Response
- **Method:** `GET`
- **Path:** `/health`
- **Status Code:** `200 OK`
- **Headers:** Luôn trả về `X-Correlation-ID: <hex-id>`
- **Response Body:**
```json
{
  "status": "ok",
  "app_name": "DocuExtract",
  "version": "0.1.0"
}
```

### 3.2. Cấu hình Orchestrator Probes
- **Docker Compose / Dockerfile:**
  ```dockerfile
  HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
      CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"
  ```
- **Kubernetes Pod Spec:**
  ```yaml
  livenessProbe:
    httpGet:
      path: /health
      port: 8000
    initialDelaySeconds: 5
    periodSeconds: 15
  readinessProbe:
    httpGet:
      path: /health
      port: 8000
    initialDelaySeconds: 3
    periodSeconds: 10
  ```

---

## 4. Vận Hành Container (Docker)

### 4.1. An ninh Non-Root Runtime
Dockerfile được làm cứng (security hardened) tuân thủ tiêu chuẩn production:
- Chạy trên base image `python:3.12-slim`.
- Ứng dụng chạy dưới quyền người dùng non-root: `appuser` (UID: `10001`, GID: `10001`).
- Tuyệt đối không chạy container dưới quyền `root`.

### 4.2. Build và Chạy Container

```bash
# 1. Build image
docker build -t docuextract:latest .

# 2. Chạy container ở cổng 8000
docker run -d \
  --name docuextract \
  -p 8000:8000 \
  -e DOCUEXTRACT_LOG_LEVEL=INFO \
  -e DOCUEXTRACT_MAX_UPLOAD_SIZE_BYTES=10485760 \
  docuextract:latest

# 3. Kiểm tra trạng thái và logs
docker ps
docker logs docuextract
```

