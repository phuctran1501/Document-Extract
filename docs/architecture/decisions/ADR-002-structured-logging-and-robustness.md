# ADR-002: Structured Logging, Bounded Upload Streaming và Đóng Gói Non-Root

- **Trạng thái:** Đã chấp thuận cho Phase 4
- **Ngày:** 2026-11-10
- **Người ra quyết định:** Chủ dự án & Antigravity

## Bối cảnh

Khi chuẩn bị đưa DocuExtract vào môi trường container hóa và tích hợp với ASP.NET Core, hệ thống cần đáp ứng các yêu cầu phi chức năng nghiêm ngặt về độ bền vững (NFR-02, NFR-03) và bảo mật dữ liệu người dùng (NFR-01, NFR-06):
1. Không đọc dữ liệu upload quá cỡ không giới hạn vào bộ nhớ RAM tránh nguy cơ tấn công từ chối dịch vụ (DoS / memory exhaustion).
2. Phát ra log có cấu trúc (structured JSON) kèm correlation ID để dễ dàng phân tích và truy vết lỗi trên container log aggregator (ELK, Datadog, CloudWatch).
3. Tuyệt đối không ghi log nội dung tài liệu trích xuất (Zero Document Logging) để đảm bảo quyền riêng tư và tuân thủ dữ liệu nhạy cảm.
4. Chạy container với đặc quyền tối thiểu (least privilege) thông qua non-root user.

## Quyết định

1. **Bounded Streaming & Early Check:**
   - Kiểm tra sớm header `Content-Length`: Nếu vượt ngưỡng `max_upload_size_bytes`, từ chối ngay với HTTP 413 `FILE_TOO_LARGE` trước khi đọc body.
   - Sử dụng `read_upload_file_bounded` đọc từng chunk 64 KiB, tích lũy dung lượng và ngắt kết nối ngay khi vượt ngưỡng mà không bao giờ nạp toàn bộ file lớn vào bộ nhớ.
2. **Structured JSON Logging & Correlation ID:**
   - Xây dựng `StructuredJsonFormatter` định dạng log chuẩn 1 dòng JSON chứa timestamp ISO 8601 UTC, log level, logger name, message, và tự động đính kèm `correlation_id` từ `ContextVar`.
   - Cho phép chuyển đổi linh hoạt sang dạng text (`DOCUEXTRACT_LOG_JSON_FORMAT=false`) khi phát triển ở local.
3. **Chính sách Zero Document Logging:**
   - Rà soát toàn bộ log: chỉ ghi nhận các trường metadata kỹ thuật an toàn (`doc_filename`, `format`, `size_bytes`, `character_count`, `word_count`, `duration_ms`, `correlation_id`).
   - Tuyệt đối cấm đưa `raw_text`, `normalized_text` hay nội dung binary vào log.
4. **Đóng gói Non-Root Container:**
   - Xây dựng Dockerfile trên nền `python:3.12-slim`, tạo user `appuser` (UID 10001) và chuyển `USER appuser` trước khi chạy ứng dụng.
   - Tích hợp chỉ thị `HEALTHCHECK` thăm dò `/health`.

## Hệ quả

**Tích cực**
- Ứng dụng an toàn trước các payload upload độc hại có kích thước lớn.
- Dễ dàng truy vết lỗi xuyên suốt giữa ASP.NET Core và DocuExtract thông qua `X-Correlation-ID`.
- Log thân thiện với máy đọc (machine-readable) cho hệ thống giám sát tập trung.
- Container an toàn, giảm thiểu rủi ro bảo mật thoát container (container escape) do chạy dưới quyền non-root.
- Bảo vệ dữ liệu nhạy cảm của tài liệu và CV người dùng.

**Tiêu cực / Đánh đổi**
- Khách hàng không cung cấp header `Content-Length` (chunked transfer) vẫn phải được đọc từng chunk cho đến khi chạm ngưỡng giới hạn.
- Định dạng JSON log có thể hơi khó đọc trực tiếp bằng mắt thường nếu không có công cụ format log hoặc tắt biến `DOCUEXTRACT_LOG_JSON_FORMAT`.

## Xem xét lại khi

- Khi chuyển đổi sang hệ thống phân tán phức tạp cần OpenTelemetry distributed tracing (OTel traces/spans) thay vì correlation ID đơn thuần.
- Khi dung lượng tài liệu hỗ trợ mở rộng vượt ngưỡng 100 MiB đòi hỏi cơ chế direct multipart upload lên Cloud Object Storage (S3/Azure Blob).

