# Kế hoạch triển khai: Phase 3 — Trích xuất DOCX (DOCX Extraction)

- **Trạng thái:** Đề xuất
- **Đặc tả liên quan:** `docs/product/requirements.md` (FR-03, FR-04, FR-05, FR-06, FR-07, FR-08, FR-09), `docs/architecture/architecture.md`, `docs/architecture/api-contract.md` (Mục 3 & 5)
- **Issue liên quan:** Phase 3 trong `docs/development/roadmap.md`

## 1. Kết quả khảo sát repository

- **Khảo sát bằng CodeGraph:**
  - `app/api/routes/documents.py`: Đã có endpoint `POST /api/v1/documents/extract` tiếp nhận `UploadFile`. Hiện tại mới chỉ hỗ trợ `pdf`, đang từ chối `docx` với thông báo chờ Phase 3.
  - `app/services/document_service.py`: Đang rẽ nhánh định dạng file. Cần cập nhật nhánh `.docx` để chuyển tới `DOCXParser` với `doc_format="docx"`, `media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"`.
  - `app/schemas/document.py`: Schema `ExtractionResult.page_count` đã hỗ trợ sẵn kiểu `int | None = None` (chuẩn bị cho DOCX không có số trang ổn định).
  - `app/parsers/`: Đã có `pdf_parser.py`. Cần thêm `docx_parser.py`.
  - `app/services/text_service.py`: Đã sẵn sàng chuẩn hóa văn bản Unicode NFC và đếm từ/ký tự cho văn bản trích xuất từ DOCX.
  - `pyproject.toml`: Chưa có thư viện `python-docx`. Cần bổ sung dependency `python-docx>=1.1.0`.
- **Ràng buộc:**
  - DOCX là file nén ZIP theo chuẩn Open Packaging Conventions (OPC) chứa các file XML.
  - Cần kiểm tra container/magic bytes: Phải bắt đầu bằng `PK\x03\x04` và chứa cấu trúc `word/document.xml`.
  - Xử lý file DOCX bị mã hóa mật khẩu (Office binary encryption container bắt đầu bằng `\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1`) $\rightarrow$ trả về `422 ENCRYPTED_DOCUMENT`.
  - Xử lý file ZIP hỏng/corrupted $\rightarrow$ trả về `422 INVALID_DOCUMENT`.
  - Với DOCX, `page_count` trong response phải là `null` theo đúng API Contract.
  - Thứ tự trích xuất phải tôn trọng thứ tự tự nhiên của văn bản (đoạn văn và bảng biểu xen kẽ).

## 2. Phạm vi (Scope)

### Trong phạm vi
1. **Dependencies:**
   - Bổ sung `python-docx>=1.1.0` vào `dependencies` trong `pyproject.toml`.
   - Cập nhật lockfile và môi trường ảo thông qua `uv sync`.
2. **DOCX Parser Module (`app/parsers/docx_parser.py`):**
   - Xác thực chữ ký magic bytes của container: `PK\x03\x04` cho DOCX chuẩn, phát hiện container OLE2 (`\xd0\xcf\x11\xe0...`) để báo lỗi mã hóa.
   - Kiểm tra tính hợp lệ của gói OPC: Kiểm tra sự tồn tại của `word/document.xml`.
   - Bắt các lỗi của `zipfile.BadZipFile` và `docx.opc.exceptions` $\rightarrow$ ánh xạ thành `AppException(422, "INVALID_DOCUMENT", ...)`.
   - Trích xuất nội dung văn bản theo thứ tự xuất hiện của phần tử trong `body` (`w:p` cho paragraph, `w:tbl` cho table).
   - Với bảng biểu (`table`), trích xuất từng hàng và các ô (ngăn cách bằng ` | `), giữ cấu trúc dữ liệu rõ ràng.
   - Trả về `page_count = None` và chuỗi `raw_text`.
3. **Document Service (`app/services/document_service.py`):**
   - Bổ sung nhánh xử lý file `.docx`: gán `media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"`, `format="docx"`.
   - Gọi `DOCXParser` trích xuất text.
   - Chuẩn hóa văn bản qua `text_service.normalize_text()` và tính thống kê ký tự/từ xác định.
   - Nếu `character_count == 0` $\rightarrow$ raise `AppException(422, "NO_EXTRACTABLE_TEXT", ...)`.
4. **Kiểm thử tự động:**
   - Xây dựng helper in-memory DOCX generator (`tests/docx_helpers.py`):
     - DOCX có văn bản đoạn văn và bảng biểu.
     - DOCX rỗng (không có chữ).
     - File ZIP hỏng cấu trúc (corrupted).
     - File ZIP hợp lệ nhưng không phải DOCX (thiếu `word/document.xml`).
     - File DOCX có mật khẩu (encrypted OLE2 header).
     - File non-DOCX.
   - Unit tests cho `DOCXParser` (`tests/unit/test_docx_parser.py`).
   - Integration tests cho `POST /api/v1/documents/extract` với file DOCX (`tests/integration/test_document_extract_api.py`).

### Ngoài phạm vi (Explicit Non-Goals)
- Không giả lập rendering engine để tính số trang DOCX (giữ `page_count = null` theo API Contract).
- Không trích xuất hình ảnh, biểu đồ nhúng, hay macro VBA trong DOCX.
- Không hỗ trợ định dạng `.doc` cũ (binary Word 97-2003).

## 3. Thiết kế

### 3.1. Luồng xử lý DOCX

```text
HTTP Request: POST /api/v1/documents/extract (multipart/form-data)
      │
      ▼
app/api/routes/documents.py (Nhận UploadFile)
      │
      ▼
app/services/document_service.py
      │ 1. Validate file size (< max_upload_size_bytes)
      │ 2. Nhận diện định dạng: đuôi .docx
      │
      ▼
app/parsers/docx_parser.py
      │ 1. Kiểm tra magic bytes:
      │    - Nếu là OLE2 (\xd0\xcf\x11\xe0...) -> Raise ENCRYPTED_DOCUMENT (422)
      │    - Nếu không phải ZIP (PK\x03\x04) -> Raise UNSUPPORTED_FILE_TYPE (415)
      │ 2. Mở zipfile.ZipFile:
      │    - Nếu thiếu word/document.xml -> Raise UNSUPPORTED_FILE_TYPE (415)
      │    - Nếu BadZipFile -> Raise INVALID_DOCUMENT (422)
      │ 3. Khởi tạo docx.Document(stream)
      │ 4. Duyệt doc.element.body theo thứ tự:
      │    - Paragraph: lấy text
      │    - Table: duyệt rows/cells, nối ô bằng " | "
      │ 5. Trả về (None, raw_text)
      │
      ▼
app/services/text_service.py
      │ 1. normalize_text(raw_text) -> Unicode NFC, LF, clean whitespace
      │ 2. compute_text_stats(normalized_text) -> character_count, word_count
      │ 3. Nếu character_count == 0 -> Raise NO_EXTRACTABLE_TEXT (422)
      │
      ▼
app/schemas/document.py (Tạo DocumentExtractResponse với page_count=None)
      │
      ▼
HTTP Response: 200 OK
```

### 3.2. Thuật toán trích xuất bảng và đoạn văn theo thứ tự

Trong `app/parsers/docx_parser.py`:
```python
elements: list[str] = []
for child in doc.element.body:
    tag = child.tag
    if tag.endswith("p"):
        p = Paragraph(child, doc)
        text = p.text.strip()
        if text:
            elements.append(text)
    elif tag.endswith("tbl"):
        table = Table(child, doc)
        for row in table.rows:
            row_cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if row_cells:
                elements.append(" | ".join(row_cells))

raw_text = "\n\n".join(elements)
```

## 4. Các bước triển khai tuần tự

1. **Bước 1 — Thêm Dependency:**
   - Thêm `python-docx>=1.1.0` vào `pyproject.toml`.
   - Chạy `uv sync` cập nhật môi trường ảo và lockfile.
2. **Bước 2 — Xây dựng DOCX Parser (`app/parsers/docx_parser.py`):**
   - Triển khai `DOCXParser` với kiểm tra magic bytes `PK\x03\x04` và OLE2 header.
   - Kiểm tra `word/document.xml`.
   - Trích xuất paragraphs và tables theo thứ tự văn bản.
3. **Bước 3 — Cập nhật Document Service (`app/services/document_service.py`):**
   - Thêm instance `self.docx_parser = DOCXParser()`.
   - Xử lý nhánh `.docx`: gán `media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"`, `format="docx"`.
   - Gọi `docx_parser.extract()`, chuẩn hóa text và trả về `DocumentExtractResponse`.
4. **Bước 4 — Xây dựng Helper In-Memory DOCX (`tests/docx_helpers.py`):**
   - Viết các hàm tạo DOCX có text, có bảng, DOCX rỗng, file zip hỏng, file mã hóa OLE2.
5. **Bước 5 — Viết Unit Tests (`tests/unit/test_docx_parser.py`):**
   - Kiểm thử trích xuất đoạn văn, trích xuất bảng, xen kẽ đoạn văn và bảng.
   - Kiểm thử file không phải zip (415), file zip không có document.xml (415), file hỏng (422), file mã hóa (422), file rỗng.
6. **Bước 6 — Viết Integration Tests cho DOCX (`tests/integration/test_document_extract_api.py`):**
   - Upload DOCX hợp lệ -> HTTP 200, `format="docx"`, `page_count=None`, text và counts chính xác.
   - Upload DOCX có bảng biểu -> HTTP 200, nội dung bảng xuất hiện đầy đủ.
   - Upload DOCX rỗng không chữ -> HTTP 422 `NO_EXTRACTABLE_TEXT`.
   - Upload DOCX hỏng/mã hóa -> HTTP 422.
   - Upload file zip đổi đuôi .docx -> HTTP 415.
7. **Bước 7 — Xác minh chất lượng & CI:**
   - Chạy `uv run ruff check .`
   - Chạy `uv run ruff format --check .`
   - Chạy `uv run pytest`
8. **Bước 8 — Cập nhật tài liệu & Dev log:**
   - Cập nhật `docs/development/roadmap.md` (Đánh dấu hoàn thành Phase 3).
   - Thêm `docs/development/dev-logs/dev-log-phase-3.md`.

## 5. Kế hoạch kiểm thử

| Kịch bản | Mức độ test | Phương thức | Kết quả mong đợi |
|---|---|---|---|
| Trích xuất DOCX có đoạn văn | Unit & API | `test_extract_valid_docx_paragraphs` | Status `200`, `format="docx"`, `page_count=None`, text chính xác |
| Trích xuất DOCX có bảng biểu | Unit & API | `test_extract_docx_with_tables` | Status `200`, nội dung hàng/cột được ngăn cách bằng ` \| ` |
| Trích xuất xen kẽ đoạn văn & bảng | Unit | `test_extract_docx_mixed_order` | Văn bản trích xuất theo đúng thứ tự xuất hiện |
| File không có chữ ký ZIP `PK\x03\x04` | Unit & API | `test_extract_docx_invalid_magic_bytes` | Status `415`, code `UNSUPPORTED_FILE_TYPE` |
| File ZIP không có `word/document.xml` | Unit & API | `test_extract_docx_missing_document_xml` | Status `415`, code `UNSUPPORTED_FILE_TYPE` |
| File DOCX bị hỏng (corrupted ZIP) | Unit & API | `test_extract_corrupted_docx` | Status `422`, code `INVALID_DOCUMENT` |
| File DOCX có mật khẩu (OLE2 Encrypted) | Unit & API | `test_extract_encrypted_docx` | Status `422`, code `ENCRYPTED_DOCUMENT` |
| File DOCX rỗng không có chữ | Unit & API | `test_extract_blank_docx_no_text` | Status `422`, code `NO_EXTRACTABLE_TEXT` |
| Bảo toàn header `X-Correlation-ID` cho DOCX | API | `test_extract_docx_preserves_correlation_id` | Header trả về khớp với request |

## 6. Rủi ro và biện pháp giảm thiểu

- **Rủi ro ZIP Bomb / Decompression Bomb:** File nén DOCX dung lượng nhỏ khi giải nén bung ra gigabytes XML.
  - *Biện pháp:* `python-docx` phân tích cấu trúc theo đối tượng; kết hợp giới hạn kích thước upload tối đa 10 MiB đã có từ Phase 0 và Phase 2.
- **Rủi ro ô bảng rỗng / ô gộp (Merged Cells):** Bảng biểu phức tạp có thể gây duplicate text khi đọc merged cells.
  - *Biện pháp:* Xử lý cell text an toàn, loại bỏ các chuỗi rỗng và kiểm tra tính hợp lệ trước khi format.

## 7. Tài liệu cần cập nhật sau khi hoàn thành

- [ ] `docs/development/roadmap.md` (Đánh dấu hoàn thành các checkbox của Phase 3)
- [ ] `docs/development/dev-logs/dev-log-phase-3.md` (Ghi chép dev log theo template)

## 8. Lệnh xác minh

```powershell
$env:UV_PYTHON = "C:\Users\Admin\AppData\Roaming\uv\python\cpython-3.12.8-windows-x86_64-none\python.exe"
& "C:\Users\Admin\.local\bin\uv.exe" run ruff check .
& "C:\Users\Admin\.local\bin\uv.exe" run ruff format --check .
& "C:\Users\Admin\.local\bin\uv.exe" run pytest
```

