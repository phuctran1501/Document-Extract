# Dev Log: Phase 5 — Bằng Chứng Tích Hợp ASP.NET Core (ASP.NET Core Integration Proof)

- **Ngày:** 2026-11-12
- **Issue/PR liên quan:** Phase 5 ([docs/development/roadmap.md](file:///d:/DocuExtract/docs/development/roadmap.md), [docs/development/plans/2026-11-12-phase-5-aspnet-integration.md](file:///d:/DocuExtract/docs/development/plans/2026-11-12-phase-5-aspnet-integration.md))
- **Files:** `docs/architecture/api-contract.md`, `docs/architecture/aspnet-integration.md`, `docs/architecture/decisions/ADR-003-aspnet-core-integration.md`, `docs/operations/service-configuration.md`, `docs/development/roadmap.md`, `tests/integration/test_contract_conformance.py`

## Những gì đã xây dựng
- Hoàn thiện đặc tả API Contract v1 trong `docs/architecture/api-contract.md`: Kiểm chứng và đồng bộ 100% với schema OpenAPI thực tế, hoàn thiện quy định về Correlation ID header (`X-Correlation-ID`), bounded streaming, và danh mục mã lỗi máy đọc được.
- Đồng bộ hóa tài liệu vận hành `docs/operations/service-configuration.md` khớp với schema thực tế của `HealthResponse`.
- Xây dựng tài liệu thiết kế và mã nguồn C# mẫu chuẩn mực Clean Architecture trong `docs/architecture/aspnet-integration.md`:
  - **Tầng Application:** Định nghĩa interface `IDocumentExtractor`, các Application DTOs (`DocumentExtractionResult`, `DocumentMetadataDto`, `ExtractionDataDto`), và hệ thống ngoại lệ đặc thù (`DocuExtractClientException`, `DocuExtractTimeoutException`, `DocuExtractConnectionException`).
  - **Tầng Infrastructure:** Cài đặt adapter typed `HttpClient` (`DocuExtractClient`), xử lý stream multipart an toàn, truyền `CancellationToken`, tự động gắn `X-Correlation-ID` từ `IHttpContextAccessor` hoặc `Activity.Current?.Id`, phân loại mã lỗi có cấu trúc, và thực thi Zero Document Logging ở phía client.
  - **Dependency Injection:** Cung cấp extension method `AddDocuExtractClient` liên kết cấu hình `DocuExtractOptions`.
  - **Kiểm thử tích hợp phía .NET:** Cung cấp các công thức test mẫu xUnit với `MockHttpMessageHandler` cho các ca thành công, lỗi nghiệp vụ (415, 422, 413), timeout, cancellation và lỗi mạng.
- Ghi nhận bản ghi quyết định kiến trúc `docs/architecture/decisions/ADR-003-aspnet-core-integration.md`.
- Bổ sung 6 integration tests mới trong `tests/integration/test_contract_conformance.py` kiểm chứng tính tương thích của OpenAPI schema, round-trip correlation ID, cấu trúc error envelope, và tính đúng đắn của toàn bộ các mã lỗi trong hợp đồng. Toàn bộ test suite đạt **67 tests pass 100%**.

## Lý do chọn thiết kế này
- **Tuân thủ Clean Architecture (Dependency Inversion Principle):** Tầng Application của ASP.NET Core chỉ phụ thuộc vào abstraction `IDocumentExtractor` và model nghiệp vụ, hoàn toàn không biết đến `HttpClient` hay FastAPI transport. Điều này cho phép team .NET unit test dễ dàng với mock mà không cần bật service DocuExtract thật.
- **Ranh giới công nghệ độc lập:** Không đưa mã nguồn C# .NET vào repository Python DocuExtract giúp giữ repository tinh gọn, không xung đột toolchain, và đảm bảo hai service có thể được deploy, scale và cập nhật độc lập.
- **Phân loại lỗi xác định:** Thay vì coi mọi lỗi HTTP là exception chung chung, adapter .NET phân tách rõ rệt: lỗi timeout (`DocuExtractTimeoutException`), lỗi kết nối (`DocuExtractConnectionException`), và lỗi nghiệp vụ từ DocuExtract (`DocuExtractClientException` chứa `ErrorCode` ổn định như `ENCRYPTED_DOCUMENT`, `UNSUPPORTED_FILE_TYPE`), giúp backend ASP.NET Core phản hồi chính xác mã HTTP tương ứng (400, 415, 422, 502, 504) cho người dùng cuối.

## Cách hoạt động
1. Khi có request tải lên tài liệu trong ứng dụng .NET, `UploadDocumentCommandHandler` gọi `_documentExtractor.ExtractAsync(...)`.
2. `DocuExtractClient` (Infrastructure) đóng gói file stream vào `MultipartFormDataContent`, trích xuất Correlation ID hiện tại truyền vào header `X-Correlation-ID`.
3. Yêu cầu được gửi qua HTTP tới DocuExtract FastAPI kèm `CancellationToken`.
4. DocuExtract xác thực stream, trích xuất text, chuẩn hóa NFC và trả về response JSON.
5. `DocuExtractClient` giải nén response, ánh xạ sang `DocumentExtractionResult` và trả về cho tầng Application mà không bao giờ ghi log nội dung tài liệu.

## Những điều cần lưu ý (Gotchas)
- **Đặt tên trường JSON giữa C# và Python:** Python sử dụng `snake_case` (ví dụ `size_bytes`, `media_type`, `page_count`), trong khi C# sử dụng `PascalCase`. Adapter C# sử dụng thuộc tính `[JsonPropertyName("...")]` trên các contract record để ánh xạ chính xác 100% mà không bị phụ thuộc vào naming policy toàn cục.
- **Phân biệt giữa Timeout và Client Cancellation:** Trong .NET `HttpClient`, khi hết thời gian `Timeout`, runtime ném ra `OperationCanceledException`. Cần kiểm tra `!cancellationToken.IsCancellationRequested` để nhận diện chính xác sự cố timeout và ném `DocuExtractTimeoutException` thay vì nhầm lẫn với việc caller chủ động hủy thao tác.

## Kiểm thử và bằng chứng
1. `uv run ruff check .` $\rightarrow$ `All checks passed!`
2. `uv run ruff format --check .` $\rightarrow$ `78 files already formatted!`
3. `uv run pytest` $\rightarrow$ `67 passed, 1 warning in 0.81s!`

## Điểm phỏng vấn / học tập
- **Khái niệm đã học:** Cách thiết kế ranh giới adapter Typed HttpClient trong Clean Architecture, kỹ thuật lan truyền `CancellationToken` và Correlation ID qua ranh giới tiến trình (IPC / HTTP), và kỹ thuật kiểm thử hợp đồng tự động (Contract Conformance Testing).
- **Đánh đổi (Trade-off):** Duy trì tài liệu C# mẫu thay vì tạo một thư viện NuGet dùng chung (shared library) giữa 2 repo giúp giảm thiểu tight-coupling và version-lock giữa Python và .NET trong giai đoạn MVP.

