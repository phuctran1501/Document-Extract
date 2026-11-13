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

- [x] Thêm module parser DOCX.
- [x] Xác định thứ tự trích xuất đoạn văn/bảng.
- [x] Kiểm tra container/nội dung DOCX.
- [x] Thêm test cho đoạn văn, bảng, file rỗng và nội dung ZIP bị lỗi.

**Tiêu chí thoát:** các file DOCX hợp lệ trả về văn bản và metadata mang tính xác định.

## Phase 4 — Tăng cường độ bền vững và đóng gói

- [x] Thực thi và test giới hạn kích thước upload có thể cấu hình.
- [x] Thêm correlation ID và structured logging.
- [x] Xác minh không có nội dung tài liệu nào bị ghi log.
- [x] Thêm Dockerfile và runtime chạy với quyền non-root.
- [x] Thêm CI cho lint, kiểm tra format và chạy test.
- [x] Tài liệu hóa health check và cấu hình service.

**Tiêu chí thoát:** build/test local và khởi động container thành công; các trường hợp lỗi mong đợi được bao phủ.

## Phase 5 — Bằng chứng tích hợp ASP.NET Core

- [x] Hoàn thiện API contract.
- [x] Chuẩn bị abstraction `IDocumentExtractor` cho .NET và adapter typed `HttpClient` trong Infrastructure của ứng dụng ASP.NET Core tiêu thụ.
- [x] Truyền cancellation và correlation ID.
- [x] Xử lý timeout, lỗi kết nối và các response lỗi từ downstream.
- [x] Thêm integration test chạy với một instance DocuExtract thực hoặc HTTP stub có kiểm soát.

**Tiêu chí thoát:** tầng Application của ASP.NET Core phụ thuộc vào một abstraction, trong khi adapter Infrastructure sở hữu các chi tiết transport HTTP.

## Ý tưởng cho tương lai — chỉ sau khi có bằng chứng

- **Xác thực giữa các service (S2S Authentication Middleware):** Triển khai middleware kiểm tra header `X-Service-Api-Key` hoặc cấu hình mạng nội bộ Private VPC, chuẩn bị cho việc tích hợp production với các dịch vụ tiêu thụ bên ngoài (bao gồm dự án **NewsHub** ở giai đoạn `PROPOSED` Phase 2+).
- OCR cho các PDF dạng scan (Tesseract/PaddleOCR).
- Xử lý job bất đồng bộ / queue / worker (Celery/Redis hoặc RabbitMQ).
- Object storage (S3/MinIO cho lưu trữ tạm thời có mã hóa).
- Hiểu và phân tích cấu trúc tài liệu/CV nâng cao dựa trên LLM.
- Rate limiting phân tán theo API Key/Client IP.

Hãy tạo một ADR và cập nhật requirements trước khi thêm bất kỳ tính năng nào trong số này.
