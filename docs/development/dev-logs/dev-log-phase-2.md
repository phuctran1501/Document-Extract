# Dev Log: Phase 2 — Trích Xuất PDF (PDF Extraction)

- **Ngày:** 2026-11-08
- **Issue/PR liên quan:** Phase 2 ([docs/development/roadmap.md](file:///d:/DocuExtract/docs/development/roadmap.md))
- **Files:** `pyproject.toml`, `app/parsers/pdf_parser.py`, `app/schemas/document.py`, `app/services/document_service.py`, `app/api/routes/documents.py`, `app/main.py`, `tests/pdf_helpers.py`, `tests/unit/test_pdf_parser.py`, `tests/integration/test_document_extract_api.py`

## Những gì đã xây dựng
- Thêm `pypdf` và `python-multipart` vào runtime dependencies trong `pyproject.toml`.
- Triển khai `PDFParser` trong `app/parsers/pdf_parser.py`: Kiểm tra magic bytes `%PDF-`, xử lý PDF mã hóa mật khẩu, bắt lỗi cú pháp pypdf, đọc số trang và trích xuất text từng trang.
- Định nghĩa Pydantic schemas trong `app/schemas/document.py`: `DocumentMetadata`, `ExtractionResult`, `DocumentExtractResponse`.
- Triển khai `DocumentService` trong `app/services/document_service.py`: Kiểm tra dung lượng (giới hạn 10 MiB), kiểm tra file rỗng (0 bytes), vệ sinh tên file chống path traversal, kết hợp `text_service` chuẩn hóa Unicode NFC và thống kê từ/ký tự xác định. Báo lỗi `NO_EXTRACTABLE_TEXT` (422) khi văn bản rỗng (không hỗ trợ OCR).
- Triển khai endpoint `POST /api/v1/documents/extract` (`multipart/form-data`) trong `app/api/routes/documents.py` và đăng ký route tại `app/main.py`.
- Xây dựng module sinh PDF in-memory (`tests/pdf_helpers.py`) và bổ sung 16 test cases mới (6 unit tests, 10 integration tests), nâng tổng số test suite lên 35 tests pass.

## Lý do chọn thiết kế này
- **Ranh giới kiến trúc (Architecture Boundaries):** `PDFParser` là pure Python logic, độc lập hoàn toàn với FastAPI / Starlette request objects. `DocumentService` đóng vai trò điều phối giữa parser và text normalizer.
- **Bảo mật file upload (Security First):** Không tin tưởng client MIME type hay extension; kiểm tra magic bytes `%PDF-` trực tiếp trên binary stream. Vệ sinh tên file tránh path traversal. Không log nội dung nhạy cảm của tài liệu (NFR-01).
- **Phản hồi lỗi xác định:** Mọi ca lỗi (file rỗng, quá cỡ, file hỏng, mã hóa, không có text) đều trả về error envelope chuẩn với mã lỗi ổn định máy đọc được (`INVALID_REQUEST`, `FILE_TOO_LARGE`, `UNSUPPORTED_FILE_TYPE`, `INVALID_DOCUMENT`, `ENCRYPTED_DOCUMENT`, `NO_EXTRACTABLE_TEXT`).

## Cách hoạt động
1. Request multipart upload file tới `POST /api/v1/documents/extract`.
2. FastAPI tiếp nhận `UploadFile`, đọc nội dung binary vào bộ nhớ stream.
3. `DocumentService` kiểm tra kích thước file và tên file.
4. `PDFParser` kiểm tra 5 bytes đầu (`%PDF-`), mở cấu trúc tài liệu, kiểm tra mật khẩu `reader.is_encrypted`, và duyệt qua các trang để trích xuất text thô.
5. `text_service.analyze_text()` chuẩn hóa Unicode sang `NFC`, chuẩn hóa khoảng trắng/dòng trống, tính số ký tự và từ.
6. Nếu số ký tự = 0 $\rightarrow$ bắn exception `NO_EXTRACTABLE_TEXT` (422).
7. Đóng gói kết quả vào `DocumentExtractResponse` (HTTP 200) kèm `X-Correlation-ID`.
8. Tự động đóng stream `UploadFile` trong khối `finally` để giải phóng tài nguyên.

## Những điều cần lưu ý (Gotchas)
- **PDF Scanned/Ảnh:** Các PDF chỉ chứa ảnh quét không chứa text stream sẽ trả về chuỗi rỗng. DocuExtract từ chối giả vờ thực hiện OCR và trả về lỗi 422 `NO_EXTRACTABLE_TEXT` rõ ràng cho client.
- **FastAPI B008 & Annotated:** Sử dụng `Annotated[UploadFile, File(...)]` thay vì gán giá trị mặc định trực tiếp để tuân thủ quy tắc linter của Ruff và chuẩn code hiện đại của FastAPI.

## Kiểm thử và bằng chứng
1. `uv run ruff check .` $\rightarrow$ `All checks passed!`
2. `uv run ruff format --check .` $\rightarrow$ `63 files already formatted!`
3. `uv run pytest` $\rightarrow$ `35 passed, 1 warning in 0.31s!`

## Điểm phỏng vấn / học tập
- **Khái niệm đã học:** Xử lý file binary stream an toàn trong FastAPI, phân tích cấu trúc file PDF với `pypdf`, kỹ thuật tạo in-memory PDF cho unit test tự động mà không cần lưu file fixture trên đĩa.
- **Đánh đổi (Trade-off):** Đọc file vào bộ nhớ stream (`BytesIO`) cho các tài liệu nhỏ $\le$ 10 MiB (phù hợp MVP stateless) giúp xử lý nhanh và đơn giản, không cần quản lý file tạm trên ổ đĩa.

