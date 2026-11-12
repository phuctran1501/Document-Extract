# DocuExtract — API Contract (v1)

**Trạng thái:** Đã hoàn thiện (Finalized v1). Đã kiểm chứng tương thích 100% với OpenAPI schema và ASP.NET Core client.

## 1. Quy ước chung

- Base path: `/api/v1`
- Content negotiation: JSON responses (`application/json`).
- Upload: `multipart/form-data`.
- File field: `file`.
- Định dạng file được phép: PDF (`application/pdf`) và DOCX (`application/vnd.openxmlformats-officedocument.wordprocessingml.document`).
- Giới hạn upload mặc định: 10 MiB (10,485,760 bytes), có thể cấu hình.
- Bounded streaming: đọc stream theo chunks 64 KiB và kiểm tra sớm header `Content-Length`.
- Correlation ID: truyền và nhận qua header `X-Correlation-ID`. Nếu client cung cấp, service sẽ bảo toàn; nếu client không cung cấp, service sẽ tự sinh mới dạng hex UUID.
- Mã hóa văn bản: UTF-8, chuẩn hóa Unicode NFC trong JSON responses.

## 2. Health

### `GET /health`

Trả về HTTP `200` khi process đang hoạt động và có thể phục vụ request.

```json
{
  "status": "ok",
  "service": "docuextract"
}
```

Không báo cáo các downstream dependency chưa tồn tại. Chỉ thêm readiness check khi service có các dependency thực sự có thể trở nên không khả dụng.

## 3. Trích xuất tài liệu

### `POST /api/v1/documents/extract`

**Request:** `multipart/form-data`

| Field | Type | Required | Description |
|---|---|---|---|
| `file` | binary file | Yes | Một tài liệu PDF hoặc DOCX |

**Thành công:** HTTP `200 OK`

```json
{
  "document": {
    "filename": "candidate-cv.pdf",
    "media_type": "application/pdf",
    "size_bytes": 48321,
    "format": "pdf"
  },
  "extraction": {
    "text": "Extracted document text...",
    "page_count": 2,
    "character_count": 1450,
    "word_count": 218
  },
  "warnings": []
}
```

Với DOCX, `page_count` là `null` vì DOCX không cung cấp số trang ổn định độc lập với rendering engine. Thứ tự paragraph/table và chuẩn hóa khoảng trắng phải được ghi lại trong parser tests.

Một tài liệu không có văn bản có thể trích xuất không được im lặng trông như một lần trích xuất thành công hữu ích. Trả về một warning được ghi lại hoặc một lỗi `NO_EXTRACTABLE_TEXT` ổn định theo quyết định implementation cuối cùng. Không tuyên bố hỗ trợ OCR.

## 4. Phân tích văn bản (endpoint MVP tùy chọn)

### `POST /api/v1/text/analyze`

**Request:** `application/json`

```json
{
  "text": "Text to analyze"
}
```

**Thành công:** HTTP `200 OK`

```json
{
  "character_count": 16,
  "word_count": 3,
  "line_count": 1
}
```

Endpoint này là tùy chọn và không được làm chậm luồng trích xuất tài liệu cốt lõi.

## 5. Error contract

Tất cả các lỗi API được kỳ vọng đều dùng cùng một envelope:

```json
{
  "error": {
    "code": "UNSUPPORTED_FILE_TYPE",
    "message": "Only PDF and DOCX files are supported.",
    "correlation_id": "01J..."
  }
}
```

`correlation_id` chỉ có thể bị bỏ qua khi một request chưa được gán một ID. Không bao giờ đưa stack trace hoặc nội dung lỗi parser nội bộ vào message công khai.

| HTTP status | Error code | Ý nghĩa |
|---:|---|---|
| 400 | `INVALID_REQUEST` | Thiếu hoặc request input sai định dạng |
| 413 | `FILE_TOO_LARGE` | Upload vượt quá giới hạn đã cấu hình |
| 415 | `UNSUPPORTED_FILE_TYPE` | Định dạng file không được hỗ trợ hoặc nội dung không hợp lệ |
| 422 | `INVALID_DOCUMENT` | File bị lỗi, không đọc được, hoặc cấu trúc không hợp lệ |
| 422 | `ENCRYPTED_DOCUMENT` | Tài liệu được mã hóa/bảo vệ bằng mật khẩu, không thể đọc |
| 422 | `NO_EXTRACTABLE_TEXT` | Không thể trích xuất văn bản và OCR không khả dụng |
| 500 | `EXTRACTION_FAILED` | Lỗi trích xuất không mong đợi; chi tiết được lưu trong server logs |
| 503 | `SERVICE_UNAVAILABLE` | Service hiện không thể xử lý request |

Implementation có thể tinh chỉnh bảng này, nhưng các thay đổi phải được phản ánh trong tests và tài liệu này.

## 6. Kỳ vọng từ phía ASP.NET Core client

Caller nên:
- Gửi file dưới dạng multipart field `file`.
- Đặt timeout rõ ràng phù hợp với kích thước tài liệu tối đa (khuyến nghị 30 giây).
- Truyền `CancellationToken` xuyên suốt chuỗi gọi hàm của application.
- Xử lý riêng biệt: `200`, `4xx`, `5xx`, timeout, connection failure, và JSON response không hợp lệ.
- Giữ lại correlation ID để phục vụ chẩn đoán.
- Tránh retry các upload non-idempotent một cách mù quáng. Retry policy phải tính đến kích thước file, timeout, và liệu việc xử lý có side effect hay không (MVP không có side effect).
- Xem chi tiết kiến trúc Clean Architecture, C# Interface, Typed HttpClient Adapter, và bộ test mẫu tại [`docs/architecture/aspnet-integration.md`](./aspnet-integration.md).

## 7. Chính sách thay đổi contract

Coi việc xóa/đổi tên response field, thay đổi kiểu dữ liệu field, thay đổi ngữ nghĩa lỗi, và thay đổi multipart field bắt buộc là các breaking change tiềm năng. Cập nhật tài liệu này và thêm tests trước khi implementation. Ưu tiên các optional field bổ sung để phát triển tương thích ngược.
