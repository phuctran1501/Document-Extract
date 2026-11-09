# Document-Extract

> Một microservice xử lý tài liệu ưu tiên học tập, được xây dựng bằng Python và FastAPI, thiết kế để tích hợp với các ứng dụng ASP.NET Core.

## 1. Tổng quan dự án

DocuExtract nhận các tài liệu được hỗ trợ, trích xuất văn bản, thực hiện chuẩn hóa/phân tích nhẹ, và trả về phản hồi JSON ổn định. Dịch vụ này được thiết kế là một service chuyên biệt đứng sau ASP.NET Core API — không phải là sự thay thế cho backend nghiệp vụ chính.

**Định dạng được hỗ trợ ban đầu:** PDF và DOCX (sẽ mở rộng sau phase-4).

**Nguyên tắc MVP:** bắt đầu stateless và đồng bộ. Không thêm database, Redis, RabbitMQ, Celery, OCR, hay LLM cho đến khi có yêu cầu thực sự biện hộ cho điều đó.

## 2. Mục tiêu

- Học phát triển backend Python thông qua một service thực tế, có phạm vi rõ ràng.
- Xây dựng REST API với FastAPI và Pydantic.
- Xử lý file upload một cách an toàn.
- Tách biệt các HTTP route khỏi logic phân tích và xử lý.
- Tạo ra một API contract ổn định mà một typed client ASP.NET Core có thể sử dụng.
- Thực hành kiểm thử tự động, Docker, và xử lý lỗi giữa các service.

## 3. Nền tảng công nghệ ban đầu

| Công nghệ | Mục đích |
|---|---|
| Python 3.12+ | Runtime |
| FastAPI | REST API |
| Pydantic | Xác thực request/response |
| Uvicorn | ASGI server |
| pypdf | Trích xuất văn bản PDF |
| python-docx | Trích xuất văn bản DOCX |
| pytest + HTTPX | Kiểm thử tự động |
| Ruff | Linting và định dạng code |
| Docker | Đóng gói container ở milestone sau |

Cấu hình repository thực tế sẽ được ưu tiên hơn so với nền tảng đề xuất này khi quá trình triển khai bắt đầu.

## 4. Kiến trúc tổng quan

```text
ASP.NET Core API
      |
      | HTTP / multipart upload + JSON response
      v
DocuExtract (FastAPI)
  API routes
      |
  Processing services
      |
  Format parsers (PDF / DOCX)
      |
  Structured response
```

ASP.NET Core chịu trách nhiệm về identity, authorization, luồng nghiệp vụ, và lưu trữ dữ liệu nghiệp vụ. DocuExtract chịu trách nhiệm chỉ về trích xuất tài liệu và xử lý liên quan đến tài liệu.

## 5. Cấu trúc repository

```text
DocuExtract/
├── app/
│   ├── main.py
│   ├── api/routes/
│   ├── schemas/
│   ├── services/
│   ├── parsers/
│   └── core/
├── tests/
├── docs/
│   ├── product/
│   ├── architecture/decisions/
│   ├── development/
│   ├── operations/
│   └── ai/
├── .agents/
│   ├── rules/
│   └── skills/
├── .github/
├── AGENTS.md
├── GEMINI.md
└── README.md
```

Cây thư mục `app/` là bố cục MVP được đề xuất. Hãy kiểm tra và điều chỉnh theo dự án thực tế trước khi tạo hoặc di chuyển file.

## 6. Bản đồ tài liệu

| Tài liệu | Mục đích |
|---|---|
| `AGENTS.md` | Hướng dẫn thường trực cho AI agent |
| `docs/product/vision.md` | Mục đích sản phẩm và phạm vi |
| `docs/product/requirements.md` | Yêu cầu chức năng và phi chức năng |
| `docs/architecture/architecture.md` | Kiến trúc service và các phụ thuộc |
| `docs/architecture/api-contract.md` | Các HTTP endpoint và JSON contract |
| `docs/architecture/decisions/` | Các quyết định kiến trúc đã được chấp thuận |
| `docs/development/roadmap.md` | Các milestone triển khai theo từng bước |
| `docs/development/definition-of-done.md` | Danh sách kiểm tra chấp nhận và chất lượng |
| `docs/ai/prompt-playbook.md` | Các prompt thực tế dùng với Gemini in Antigravity |

## 7. Bắt đầu

Hướng dẫn cài đặt cục bộ chi tiết sẽ được duy trì tại [`docs/operations/development-setup.md`](docs/operations/development-setup.md). Dự án vẫn đang trong giai đoạn lên kế hoạch/dàn dựng; không giả định rằng các endpoint ứng dụng đã tồn tại cho đến khi chúng được triển khai và kiểm thử.

## 8. Phát triển với sự hỗ trợ của AI

Repository này sử dụng các workspace instructions, rules, và skills của Antigravity:

- `AGENTS.md` là hướng dẫn dự án luôn hoạt động và là nguồn tham chiếu chính.
- `.agents/rules/` chứa các ràng buộc có phạm vi cho Python, API contract, bảo mật, và kiểm thử.
- `.agents/skills/` chứa các quy trình có thể tái sử dụng cho việc lên kế hoạch, triển khai, review, và chuẩn bị tích hợp ASP.NET.

Yêu cầu agent kiểm tra và lên kế hoạch trước khi chỉnh sửa tính năng vừa/lớn. Review diff và bằng chứng kiểm thử trước khi chấp nhận kết quả.
