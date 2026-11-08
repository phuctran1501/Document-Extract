# DocuExtract — Lộ Trình Phát Triển

Lộ trình được sắp xếp để tạo ra một vertical slice hoạt động được sớm nhất có thể. Một giai đoạn sau không có nghĩa là được phép xây dựng cơ sở hạ tầng của nó ngay bây giờ.

## Phase 0 — Nền tảng repository

- [x] Khởi tạo Python project và package manager.
- [x] Tạo điểm vào ứng dụng FastAPI.
- [x] Thêm cài đặt/cấu hình và endpoint `/health`.
- [x] Thêm cấu hình Ruff và pytest.
- [x] Thêm hướng dẫn cài đặt cục bộ và các CI check ban đầu.

**Tiêu chí thoát:** ứng dụng khởi động được ở local; health endpoint và test của nó pass; cài đặt có thể tái tạo được.

## Phase 1 — Nền tảng xử lý văn bản

- [x] Xác định chính sách chuẩn hóa văn bản.
- [x] Triển khai thống kê ký tự/từ/dòng mang tính xác định.
- [x] Thêm unit test cho Unicode, whitespace, input rỗng và các ký tự xuống dòng.
- [x] Thêm endpoint tùy chọn `POST /api/v1/text/analyze`.

**Tiêu chí thoát:** hành vi của service được bao phủ bởi unit test và API test.

## Phase 2 — Trích xuất PDF

- [x] Thêm module parser PDF sử dụng một thư viện phù hợp.
- [x] Kiểm tra chữ ký PDF và các file bị lỗi/mã hóa.
- [x] Trích xuất văn bản và số trang.
- [x] Chuẩn hóa văn bản và tạo metadata cho response.
- [x] Test các PDF rỗng/dạng scan và các trường hợp lỗi parser.

**Tiêu chí thoát:** các PDF có văn bản hợp lệ hoạt động được; giới hạn được nêu rõ ràng; các file lỗi không làm crash ứng dụng.

## Phase 3 — Trích xuất DOCX

- [ ] Thêm module parser DOCX.
- [ ] Xác định thứ tự trích xuất đoạn văn/bảng.
- [ ] Kiểm tra container/nội dung DOCX.
- [ ] Thêm test cho đoạn văn, bảng, file rỗng và nội dung ZIP bị lỗi.

**Tiêu chí thoát:** các file DOCX hợp lệ trả về văn bản và metadata mang tính xác định.

## Phase 4 — Tăng cường độ bền vững và đóng gói

- [ ] Thực thi và test giới hạn kích thước upload có thể cấu hình.
- [ ] Thêm correlation ID và structured logging.
- [ ] Xác minh không có nội dung tài liệu nào bị ghi log.
- [ ] Thêm Dockerfile và runtime chạy với quyền non-root.
- [ ] Thêm CI cho lint, kiểm tra format và chạy test.
- [ ] Tài liệu hóa health check và cấu hình service.

**Tiêu chí thoát:** build/test local và khởi động container thành công; các trường hợp lỗi mong đợi được bao phủ.

## Phase 5 — Bằng chứng tích hợp ASP.NET Core

- [ ] Hoàn thiện API contract.
- [ ] Chuẩn bị abstraction `IDocumentExtractor` cho .NET và adapter typed `HttpClient` trong Infrastructure của ứng dụng ASP.NET Core tiêu thụ.
- [ ] Truyền cancellation và correlation ID.
- [ ] Xử lý timeout, lỗi kết nối và các response lỗi từ downstream.
- [ ] Thêm integration test chạy với một instance DocuExtract thực hoặc HTTP stub có kiểm soát.

**Tiêu chí thoát:** tầng Application của ASP.NET Core phụ thuộc vào một abstraction, trong khi adapter Infrastructure sở hữu các chi tiết transport HTTP.

## Ý tưởng cho tương lai — chỉ sau khi có bằng chứng

- OCR cho các PDF dạng scan.
- Xử lý job bất đồng bộ / queue / worker.
- Object storage.
- Hiểu CV dựa trên LLM.
- Xác thực giữa các service, rate limit và chính sách mạng cho production.

Hãy tạo một ADR và cập nhật requirements trước khi thêm bất kỳ tính năng nào trong số này.
