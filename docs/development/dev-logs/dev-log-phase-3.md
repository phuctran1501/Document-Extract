# Dev Log: Phase 3 — Trích Xuất DOCX (DOCX Extraction)

- **Ngày:** 2026-11-09
- **Issue/PR liên quan:** Phase 3 ([docs/development/roadmap.md](file:///d:/DocuExtract/docs/development/roadmap.md)), [docs/development/plans/2026-11-09-phase-3-docx-extraction.md](file:///d:/DocuExtract/docs/development/plans/2026-11-09-phase-3-docx-extraction.md)
- **Files:** `pyproject.toml`, `app/parsers/docx_parser.py`, `app/services/document_service.py`, `tests/docx_helpers.py`, `tests/unit/test_docx_parser.py`, `tests/integration/test_document_extract_api.py`

## Những gì đã xây dựng
- Thêm `python-docx>=1.1.0` vào runtime dependencies trong `pyproject.toml`.
- Triển khai `DOCXParser` trong `app/parsers/docx_parser.py`:
  - Kiểm tra magic bytes ZIP (`PK\x03\x04`).
  - Phát hiện OLE2 compound document container (`\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1`) đặc trưng của DOCX mã hóa bằng mật khẩu và bắn lỗi `EncryptedDocumentError`.
  - Kiểm tra tính hợp lệ của cấu trúc file DOCX (chứa `word/document.xml`).
  - Duyệt tuần tự qua các phần tử cấp cao nhất trong `doc.element.body` (`w:p` và `w:tbl`) để giữ nguyên thứ tự luồng văn bản tự nhiên giữa các đoạn và bảng biểu.
  - Định dạng các dòng bảng dạng text trực quan (`cell_1 | cell_2 | ...`).
- Cập nhật `DocumentService` trong `app/services/document_service.py`:
  - Hỗ trợ định dạng mở rộng `.docx` song song với `.pdf`.
  - Phân luồng parser: `.docx` $\rightarrow$ `DOCXParser`, `.pdf` $\rightarrow$ `PDFParser`.
  - Thiết lập metadata chuẩn contract: `doc_format="docx"`, `media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"`, và `page_count=None` (DOCX là flow layout không có khái niệm trang cố định nếu không render).
  - Tích hợp kiểm tra trích xuất text: trả về lỗi `NO_EXTRACTABLE_TEXT` (422) nếu file rỗng nội dung chữ.
- Xây dựng module sinh DOCX in-memory (`tests/docx_helpers.py`) với đầy đủ trường hợp: văn bản thông thường, bảng biểu, thứ tự xen kẽ đoạn văn và bảng biểu, tài liệu rỗng, file hỏng, và file giả lập mã hóa OLE2.
- Bổ sung 13 test cases mới (8 unit tests, 5 integration tests DOCX), nâng toàn bộ test suite lên 48 tests pass.

## Lý do chọn thiết kế này
- **Giữ nguyên thứ tự luồng tài liệu tự nhiên (Natural Flow Preservation):** Thay vì đọc tách biệt `doc.paragraphs` rồi mới đến `doc.tables` (làm đảo lộn cấu trúc của CV hoặc báo cáo), parser duyệt trực tiếp `doc.element.body` để trích xuất xen kẽ các đoạn văn và bảng đúng vị trí xuất hiện trong tài liệu.
- **Xử lý tài liệu mã hóa chuẩn xác:** Microsoft Word mã hóa file `.docx` bằng cách đóng gói bên trong một container OLE2 (Compound File Binary Format). Bằng cách kiểm tra magic bytes OLE2, DocuExtract phân biệt chính xác giữa file bị mã hóa mật khẩu (`ENCRYPTED_DOCUMENT` - 422) và file bị hỏng (`INVALID_DOCUMENT` - 422).
- **Tuân thủ API Contract:** DOCX là định dạng bố cục động (flowable document). Việc đặt `page_count = None` phản ánh đúng bản chất kỹ thuật và hoàn toàn tương thích với schema API (`page_count: Optional[int]`).

## Cách hoạt động
1. Client gửi request upload file DOCX tới `POST /api/v1/documents/extract`.
2. `DocumentService` kiểm tra kích thước và extension `.docx`.
3. `DOCXParser` đọc stream binary trong bộ nhớ:
   - Kiểm tra magic bytes: nếu là OLE2 $\rightarrow$ raise `EncryptedDocumentError`. Nếu không phải `PK\x03\x04` $\rightarrow$ raise `InvalidDocumentError`.
   - Mở qua `zipfile.ZipFile`: kiểm tra sự tồn tại của `word/document.xml`.
   - Nạp vào `docx.Document(file_stream)`.
   - Duyệt `doc.element.body`: chuyển `w:p` thành `Paragraph` và `w:tbl` thành `Table` rồi trích xuất nội dung văn bản.
4. `DocumentService` gọi `text_service.analyze_text()` để chuẩn hóa Unicode NFC và tính toán thống kê (characters, words).
5. Trả về `DocumentExtractResponse` với metadata định dạng DOCX và `page_count: null`.

## Những điều cần lưu ý (Gotchas)
- **Tập tin DOCX rỗng (Blank Document):** Một file Word mới tạo dù trắng hoàn toàn vẫn chứa các đoạn văn rỗng (`\n`). Text service sau khi strip sẽ trả về 0 ký tự, kích hoạt lỗi `NO_EXTRACTABLE_TEXT` (422) như đúng thiết kế bảo mật và chất lượng đầu ra.
- **Tương thích lxml & python-docx trên Python 3.12:** Thư viện `python-docx` nạp `lxml` để phân tích XML; tất cả đều chạy an toàn trên memory stream mà không tạo file tạm trên disk.

## Kiểm thử và bằng chứng
1. `uv run ruff check .` $\rightarrow$ `All checks passed!`
2. `uv run ruff format --check .` $\rightarrow$ `68 files already formatted!`
3. `uv run pytest` $\rightarrow$ `48 passed, 1 warning in 0.68s!`

## Điểm phỏng vấn / học tập
- **Khái niệm đã học:** Bản chất của OpenXML DOCX (thực chất là một file ZIP nén chứa các phần XML), sự khác biệt giữa flow-based document (Word) và fixed-layout document (PDF), cách duyệt cây XML tầng thấp `doc.element.body` trong `python-docx`.
- **Đánh đổi (Trade-off):** `page_count: None` tránh việc phải phụ thuộc vào các công cụ render cồng kềnh như LibreOffice hay MS Word Interop chỉ để đếm số trang. Phù hợp tuyệt đối với tiêu chí MVP nhẹ, nhanh và stateless.

