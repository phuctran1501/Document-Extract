# ADR-003: Ranh Giới Tích Hợp ASP.NET Core Clean Architecture

- **Trạng thái:** Đã chấp thuận cho Phase 5
- **Ngày:** 2026-11-12
- **Người ra quyết định:** Chủ dự án & Antigravity

## Bối cảnh

DocuExtract được thiết kế như một service chuyên biệt phục vụ trích xuất và chuẩn hóa văn bản từ tài liệu PDF/DOCX cho các ứng dụng backend ASP.NET Core. Để đảm bảo tính bền vững và khả năng mở rộng:
1. ASP.NET Core là bộ điều phối chính, sở hữu cơ sở dữ liệu nghiệp vụ, tài khoản người dùng, xác thực và phân quyền.
2. DocuExtract là microservice độc lập, stateless, không sở hữu dữ liệu người dùng hay cơ sở dữ liệu dùng chung.
3. Cần xác lập một ranh giới tích hợp rõ ràng giữa hai hệ thống để tránh việc tầng nghiệp vụ của .NET bị gắn chặt (tight coupling) với các chi tiết transport HTTP của FastAPI.

## Quyết định

1. **Abstraction ở tầng Application:**
   - Tầng Application của ứng dụng ASP.NET Core phụ thuộc duy nhất vào interface `IDocumentExtractor` và các Application DTOs.
   - Tuyệt đối không để tầng Application tham chiếu trực tiếp đến `HttpClient`, `System.Net.Http`, hay các schema nội bộ của FastAPI.
2. **Typed HttpClient Adapter ở tầng Infrastructure:**
   - Tầng Infrastructure triển khai adapter `DocuExtractClient : IDocumentExtractor` sử dụng typed `HttpClient`.
   - Adapter chịu trách nhiệm: cấu hình base URL, timeout, đóng gói multipart stream, phân tích cú pháp JSON, và lan truyền `CancellationToken`.
3. **Phân loại lỗi xác định (Deterministic Error Mapping):**
   - Lỗi mạng / không thể kết nối $\rightarrow$ ném `DocuExtractConnectionException`.
   - Quá thời gian chờ $\rightarrow$ ném `DocuExtractTimeoutException`.
   - Lỗi trả về từ DocuExtract (400, 413, 415, 422, 500) $\rightarrow$ giải nén error envelope và ném `DocuExtractClientException` chứa đầy đủ mã lỗi máy đọc được (`ErrorCode`), HTTP status code, và `CorrelationId`.
4. **Lan truyền Correlation ID:**
   - Adapter .NET tự động trích xuất Correlation ID từ request hiện tại (hoặc sinh mới nếu chưa có) và truyền qua header `X-Correlation-ID`. DocuExtract bảo toàn ID này trong logs và response header.
5. **Chính sách Zero Document Logging:**
   - Cả hai phía (DocuExtract và .NET adapter) chỉ được phép ghi log các metadata kỹ thuật an toàn (tên file, dung lượng, định dạng, thời gian thực thi, mã lỗi, correlation ID). Tuyệt đối cấm ghi log nội dung văn bản trích xuất hay luồng dữ liệu nhị phân.
6. **Không đưa mã nguồn .NET vào repository DocuExtract:**
   - DocuExtract là một repository thuần Python. Tài liệu kiến trúc và mã nguồn C# mẫu được cung cấp đầy đủ trong `docs/architecture/aspnet-integration.md` để team .NET tham chiếu và triển khai độc lập.

## Hệ quả

**Tích cực**
- Ranh giới kiến trúc cực kỳ trong sáng: Tầng Application của .NET có thể dễ dàng unit test use case bằng mock/stub mà không cần bật service Python.
- Adapter hạ tầng có thể thay thế hoặc nâng cấp (ví dụ: chuyển từ HTTP sang gRPC trong tương lai) mà không làm thay đổi bất kỳ dòng code nào trong tầng Application của .NET.
- Hai service hoàn toàn độc lập về vòng đời phát triển, công nghệ (Python vs .NET C#), triển khai (Docker/K8s), và scaling.

**Tiêu cực / Đánh đổi**
- Cần duy trì tính đồng bộ giữa schema Pydantic trong DocuExtract và các DTO contract trong C#. Thay đổi contract phải tuân thủ nghiêm ngặt chính sách versioning `/api/v1`.

## Xem xét lại khi

- Khi khối lượng tài liệu tải lên vượt quá giới hạn xử lý đồng bộ và cần chuyển sang mô hình xử lý background job qua Message Broker (RabbitMQ/Azure Service Bus).
- Khi yêu cầu thông lượng cực cao đòi hỏi giao thức nhị phân gRPC thay cho HTTP/JSON REST.

