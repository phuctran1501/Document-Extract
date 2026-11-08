# Kế hoạch triển khai: Phase 2 — Trích xuất PDF (PDF Extraction)

- **Trạng thái:** Đề xuất
- **Đặc tả liên quan:** `docs/product/requirements.md` (FR-02, FR-04, FR-05, FR-06, FR-07, FR-08, FR-09), `docs/architecture/architecture.md`, `docs/architecture/api-contract.md` (Mục 3 & 5)
- **Issue liên quan:** Phase 2 trong `docs/development/roadmap.md`

## 1. Kết quả khảo sát repository

- **Khảo sát bằng CodeGraph:**
  - `app/main.py`: Đã gắn `health_router` và `text_router` (`/api/v1/text`). Cần đăng ký `documents_router` dưới prefix `/api/v1`.
  - `app/core/config.py`: Đã có `max_upload_size_bytes = 10 * 1024 * 1024` (10 MiB) và `api_v1_prefix = "/api/v1"`.
  - `app/core/errors.py`: Đã có mã lỗi chuẩn: `INVALID_REQUEST` (400), `FILE_TOO_LARGE` (413), `UNSUPPORTED_FILE_TYPE` (415), `INVALID_DOCUMENT` (422), `ENCRYPTED_DOCUMENT` (422), `NO_EXTRACTABLE_TEXT` (422), `EXTRACTION_FAILED` (500).
  - `app/services/text_service.py`: Đã hoàn thiện ở Phase 1 (`normalize_text`, `compute_text_stats`), sẵn sàng tích hợp để chuẩn hóa văn bản trích xuất từ PDF.
  - `app/parsers/`: Hiện tại mới chỉ có `__init__.py`. Cần tạo `app/parsers/pdf_parser.py`.
  - `app/services/`: Hiện tại mới chỉ có `text_service.py`. Cần tạo `app/services/document_service.py`.
  - `app/schemas/`: Cần tạo `app/schemas/document.py`.
  - `pyproject.toml`: Chưa có `pypdf` và `python-multipart`. Cần thêm 2 dependencies này.
- **Ràng buộc:**
  - Coi file tải lên là dữ liệu không tin cậy (untrusted input, NFR-01, `security.md`).
  - Không tin tưởng MIME type hay extension do client gửi; phải kiểm tra magic bytes (`%PDF-`).
  - Không lưu file lâu dài, không ghi log nội dung tài liệu trích xuất (NFR-01).
  - Xử lý các tài liệu lỗi, mã hóa hoặc rỗng mà không làm crash tiến trình (NFR-02).
  - Parser phải độc lập với FastAPI/HTTP request (Mục 5 `AGENTS.md`).

## 2. Phạm vi (Scope)

### Trong phạm vi
1. **Dependencies:**
   - Thêm `pypdf` (runtime dependency để đọc cấu trúc và trích xuất text từ file PDF).
   - Thêm `python-multipart` (runtime dependency để FastAPI tiếp nhận `multipart/form-data`).
2. **PDF Parser Module (`app/parsers/pdf_parser.py`):**
   - Xác thực chữ ký file PDF (magic bytes `%PDF-`).
   - Kiểm tra mã hóa / mật khẩu (password-protected PDF).
   - Đọc số trang (`page_count`) và trích xuất nội dung văn bản từ tất cả các trang.
   - Bắt các lỗi phân tích cú pháp của PDF (`PdfReadError`, lỗi cấu trúc stream) và ánh xạ thành `AppException`.
   - Thiết kế dạng pure Python class/function độc lập với HTTP context.
3. **Document Service (`app/services/document_service.py`):**
   - Điều phối luồng xử lý: kiểm tra dung lượng file so với `max_upload_size_bytes`, kiểm tra file rỗng (0 bytes).
   - Xác định format tài liệu (`pdf`).
   - Gọi `PDFParser` để lấy `raw_text` và `page_count`.
   - Sử dụng `normalize_text()` và `compute_text_stats()` từ `text_service` của Phase 1 để chuẩn hóa text và tính số ký tự, số từ xác định.
   - Báo cáo lỗi `NO_EXTRACTABLE_TEXT` (HTTP 422) nếu tài liệu không có văn bản có thể trích xuất (ví dụ: PDF scan ảnh không OCR).
   - Tạo schema response hoàn chỉnh.
4. **Pydantic Schemas (`app/schemas/document.py`):**
   - `DocumentMetadata`: `filename`, `media_type`, `size_bytes`, `format`.
   - `ExtractionResult`: `text`, `page_count`, `character_count`, `word_count`.
   - `DocumentExtractResponse`: `document`, `extraction`, `warnings`.
5. **API Endpoint (`app/api/routes/documents.py`):**
   - `POST /api/v1/documents/extract` nhận multipart `file: UploadFile`.
   - Gắn router vào FastAPI app trong `app/main.py`.
6. **Kiểm thử tự động:**
   - Unit tests độc lập cho `PDFParser` (PDF chuẩn, PDF nhiều trang, PDF mã hóa, PDF hỏng, non-PDF bytes).
   - Integration tests cho endpoint `/api/v1/documents/extract`:
     - Upload PDF hợp lệ -> HTTP 200, đúng schema và counts.
     - Upload file rỗng (0 bytes) -> HTTP 400 `INVALID_REQUEST`.
     - Upload file quá giới hạn kích thước -> HTTP 413 `FILE_TOO_LARGE`.
     - Upload file giả dạng đuôi .pdf nhưng nội dung text/ảnh -> HTTP 415 `UNSUPPORTED_FILE_TYPE`.
     - Upload PDF bị hỏng/corrupted -> HTTP 422 `INVALID_DOCUMENT`.
     - Upload PDF có mật khẩu/encrypted -> HTTP 422 `ENCRYPTED_DOCUMENT`.
     - Upload PDF scan không có text -> HTTP 422 `NO_EXTRACTABLE_TEXT`.
     - Kiểm tra bảo toàn header `X-Correlation-ID`.

### Ngoài phạm vi (Explicit Non-Goals)
- Không triển khai parser DOCX (dành cho Phase 3).
- Không triển khai OCR cho PDF dạng scan (MVP không hỗ trợ OCR, báo lỗi rõ ràng theo FR-09).
- Không lưu trữ file lên ổ đĩa hay cloud storage lâu dài.

## 3. Thiết kế

### 3.1. Sơ đồ luồng dữ liệu

```text
HTTP Request: POST /api/v1/documents/extract (multipart/form-data)
      │
      ▼
app/api/routes/documents.py (Tiếp nhận UploadFile)
      │
      ▼
app/services/document_service.py
      │ 1. Kiểm tra kích thước (< max_upload_size_bytes)
      │ 2. Đọc bytes và kiểm tra magic bytes (%PDF-)
      │
      ▼
app/parsers/pdf_parser.py
      │ 1. Khởi tạo pypdf.PdfReader(stream)
      │ 2. Kiểm tra is_encrypted -> Raise ENCRYPTED_DOCUMENT nếu có mật khẩu
      │ 3. Đọc page_count và extract_text() từng trang
      │
      ▼
app/services/text_service.py (Phase 1)
      │ 1. normalize_text(raw_text) -> Unicode NFC, LF, clean whitespace
      │ 2. compute_text_stats(normalized_text) -> character_count, word_count
      │ 3. Kiểm tra character_count == 0 -> Raise NO_EXTRACTABLE_TEXT
      │
      ▼
app/schemas/document.py (Serialization thành DocumentExtractResponse)
      │
      ▼
HTTP Response: 200 OK (kèm Header X-Correlation-ID)
```

### 3.2. Chi tiết các module

1. **`app/parsers/pdf_parser.py`**:
   - `class PDFParser`:
     - `extract(stream: BinaryIO) -> tuple[int, str]`: Trả về `(page_count, raw_text)`.
     - Kiểm tra header: `stream.seek(0); header = stream.read(5)`. Nếu `header != b"%PDF-"`, raise `AppException(415, "UNSUPPORTED_FILE_TYPE", "File is not a valid PDF document.")`.
     - Bắt `pypdf.errors.PdfReadError` -> `AppException(422, "INVALID_DOCUMENT", ...)`.
     - Kiểm tra `reader.is_encrypted`: thử `reader.decrypt("")`. Nếu vẫn encrypted -> `AppException(422, "ENCRYPTED_DOCUMENT", ...)`.

2. **`app/services/document_service.py`**:
   - `class DocumentService`:
     - Kiểm tra giới hạn kích thước trước và trong khi đọc.
     - Xác định format dựa trên phần mở rộng và nội dung.
     - Gọi `PDFParser`.
     - Gọi `text_service.normalize_text` và `compute_text_stats`.
     - Kiểm tra tài liệu không có văn bản: Nếu `character_count == 0`, raise `AppException(422, "NO_EXTRACTABLE_TEXT", "The PDF document contains no extractable text. Scanned documents requiring OCR are not supported in MVP.")`.

3. **`app/schemas/document.py`**:
   - Khớp 100% với Mục 3 của `docs/architecture/api-contract.md`.
   ```python
   class DocumentMetadata(BaseModel):
       filename: str
       media_type: str
       size_bytes: int
       format: str

   class ExtractionResult(BaseModel):
       text: str
       page_count: int | None = None
       character_count: int
       word_count: int

   class DocumentExtractResponse(BaseModel):
       document: DocumentMetadata
       extraction: ExtractionResult
       warnings: list[str] = Field(default_factory=list)
   ```

4. **`app/api/routes/documents.py`**:
   - Router với prefix `/documents`, tag `Documents`.
   - `@router.post("/extract", response_model=DocumentExtractResponse)`

### 3.3. Ảnh hưởng API Contract
- Hiện thực hóa đầy đủ `POST /api/v1/documents/extract` cho định dạng PDF.
- Hoàn toàn tương thích ngược với API Contract v1.

## 4. Các bước triển khai tuần tự

1. **Bước 1 — Thêm Dependencies:**
   - Thêm `pypdf` và `python-multipart` vào `pyproject.toml`.
   - Chạy `uv sync` để cập nhật môi trường ảo và lockfile.
2. **Bước 2 — Xây dựng Parser PDF (`app/parsers/pdf_parser.py`):**
   - Triển khai kiểm tra chữ ký PDF (`%PDF-`).
   - Xử lý giải mã, đọc số trang, trích xuất text từng trang.
   - Bắt các lỗi của pypdf và ánh xạ sang `AppException`.
3. **Bước 3 — Xây dựng Schemas (`app/schemas/document.py`):**
   - Định nghĩa `DocumentMetadata`, `ExtractionResult`, `DocumentExtractResponse`.
4. **Bước 4 — Xây dựng Document Service (`app/services/document_service.py`):**
   - Điều phối upload: kiểm tra size, validate MIME, gọi parser, chuẩn hóa văn bản qua `text_service`.
5. **Bước 5 — Xây dựng Route & Đăng ký Router (`app/api/routes/documents.py` & `app/main.py`):**
   - Viết handler nhận `UploadFile`.
   - Đăng ký `documents_router` vào `app/main.py`.
6. **Bước 6 — Viết Unit Tests (`tests/unit/test_pdf_parser.py`):**
   - Tạo các helper in-memory PDF bằng `pypdf.PdfWriter`:
     - PDF có text chuẩn.
     - PDF nhiều trang.
     - PDF mã hóa mật khẩu (`writer.encrypt("secret")`).
     - PDF rỗng (trang trắng).
     - File bytes hỏng (`b"%PDF-corrupted..."`).
     - File không phải PDF (`b"random data"`).
   - Kiểm thử độc lập với FastAPI.
7. **Bước 7 — Viết Integration Tests (`tests/integration/test_document_extract_api.py`):**
   - Gọi endpoint `POST /api/v1/documents/extract` qua `TestClient`:
     - Happy path với file PDF chuẩn.
     - File rỗng 0 bytes -> HTTP 400 `INVALID_REQUEST`.
     - File quá cỡ > 10MB -> HTTP 413 `FILE_TOO_LARGE`.
     - File đuôi .pdf nhưng nội dung sai -> HTTP 415 `UNSUPPORTED_FILE_TYPE`.
     - File PDF hỏng -> HTTP 422 `INVALID_DOCUMENT`.
     - File PDF có mật khẩu -> HTTP 422 `ENCRYPTED_DOCUMENT`.
     - File PDF scan không có text -> HTTP 422 `NO_EXTRACTABLE_TEXT`.
     - Kiểm tra header `X-Correlation-ID`.
8. **Bước 8 — Xác minh chất lượng & CI:**
   - Chạy `uv run ruff check .`
   - Chạy `uv run ruff format --check .`
   - Chạy `uv run pytest`
9. **Bước 9 — Cập nhật tài liệu:**
   - Cập nhật `docs/development/roadmap.md` (Đánh dấu hoàn thành Phase 2).
   - Thêm `docs/development/dev-logs/dev-log-phase-2.md`.

## 5. Kế hoạch kiểm thử

| Kịch bản | Mức độ test | Phương thức | Kết quả mong đợi |
|---|---|---|---|
| Trích xuất PDF hợp lệ 1 trang | Unit & API | `test_extract_valid_pdf` | Status `200`, text được trích xuất, `page_count=1`, `format="pdf"` |
| Trích xuất PDF hợp lệ nhiều trang | Unit & API | `test_extract_multipage_pdf` | Status `200`, gộp text các trang, `page_count=3` |
| File không có magic bytes `%PDF-` | Unit & API | `test_extract_invalid_magic_bytes` | Status `415`, code `UNSUPPORTED_FILE_TYPE` |
| File rỗng 0 bytes | API | `test_extract_empty_file` | Status `400`, code `INVALID_REQUEST` |
| File vượt quá giới hạn 10 MiB | API | `test_extract_file_too_large` | Status `413`, code `FILE_TOO_LARGE` |
| File PDF bị hỏng (corrupted) | Unit & API | `test_extract_corrupted_pdf` | Status `422`, code `INVALID_DOCUMENT` |
| File PDF được bảo vệ bằng mật khẩu | Unit & API | `test_extract_encrypted_pdf` | Status `422`, code `ENCRYPTED_DOCUMENT` |
| File PDF scan không có chữ | Unit & API | `test_extract_scanned_pdf_no_text` | Status `422`, code `NO_EXTRACTABLE_TEXT` |
| Bảo toàn header `X-Correlation-ID` | API | `test_extract_preserves_correlation_id` | Header trả về khớp với request |

## 6. Rủi ro và biện pháp giảm thiểu

- **Rủi ro cạn kiệt bộ nhớ (OOM) khi upload file lớn:**
  - *Biện pháp:* Kiểm tra kích thước chunk khi đọc từ `UploadFile.file`, từ chối ngay lập tức khi số bytes vượt quá `max_upload_size_bytes` (10 MiB) mà không đọc toàn bộ file vào bộ nhớ.
- **Rủi ro PDF độc hại (PDF bomb/decompression bomb):**
  - *Biện pháp:* `pypdf` đọc theo stream; kết hợp giới hạn kích thước upload tối đa 10 MiB và giới hạn số trang tối đa hợp lý.
- **Rủi ro rò rỉ nội dung file trong log:**
  - *Biện pháp:* Tuân thủ `security.md`, tuyệt đối không ghi log nội dung file hay văn bản trích xuất; chỉ ghi log metadata kích thước, số trang và correlation ID.

## 7. Tài liệu cần cập nhật sau khi hoàn thành

- [ ] `docs/development/roadmap.md` (Đánh dấu hoàn thành các checkbox của Phase 2)
- [ ] `docs/development/dev-logs/dev-log-phase-2.md` (Ghi chép dev log theo template)

## 8. Lệnh xác minh

```powershell
$env:UV_PYTHON = "C:\Users\Admin\AppData\Roaming\uv\python\cpython-3.12.8-windows-x86_64-none\python.exe"
& "C:\Users\Admin\.local\bin\uv.exe" run ruff check .
& "C:\Users\Admin\.local\bin\uv.exe" run ruff format --check .
& "C:\Users\Admin\.local\bin\uv.exe" run pytest
```

