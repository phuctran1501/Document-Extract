# Hướng Dẫn Tích Hợp ASP.NET Core Clean Architecture với DocuExtract

Tài liệu này cung cấp thiết kế kiến trúc chuẩn mực, đặc tả hợp đồng, và mã nguồn mẫu C# cho ứng dụng ASP.NET Core tiêu thụ dịch vụ DocuExtract theo các nguyên tắc Clean Architecture.

> [!NOTE] Trạng thái tích hợp trong dự án NewsHub (CMS Tòa soạn)
> - **Trạng thái:** `PROPOSED` (Đề xuất cho Phase 2+, tuyệt đối không nhồi vào MVP v2.0.0 của NewsHub).
> - **Ranh giới tiêu thụ (Consumer Contract):** Client ASP.NET Core chỉ tiêu thụ duy nhất endpoint trích xuất `POST /api/v1/documents/extract` phục vụ khởi tạo bản nháp bài viết (Draft Seed). Endpoint phụ `POST /api/v1/text/analyze` bị **loại bỏ hoàn toàn** khỏi consumer adapter vì .NET 10 tự đếm từ và tính thời gian đọc trực tiếp trong bộ nhớ C# (zero network latency).
> - **Điều kiện tiên quyết Production:** Bắt buộc phải triển khai xác thực Service-to-Service (S2S Header `X-Service-Api-Key` hoặc mạng nội bộ Private VPC) trước khi tích hợp vào môi trường production.

---

## 1. Ranh Giới Kiến Trúc (Architecture Boundaries)

Theo nguyên tắc phân tách trách nhiệm (Separation of Concerns):
- **Ứng dụng ASP.NET Core:** Sở hữu nghiệp vụ chính (Business Logic), Xác thực & Phân quyền (Authentication/Authorization), Quản lý người dùng, Quy trình xử lý hồ sơ/CV, và Lưu trữ dữ liệu lâu dài (SQL Database / Object Storage).
- **DocuExtract:** Dịch vụ xử lý tài liệu độc lập (Microservice), stateless, chỉ chịu trách nhiệm phân tích cú pháp PDF/DOCX, chuẩn hóa văn bản, và trả về JSON contract xác định.

```mermaid
flowchart TD
    subgraph ASPNET[ASP.NET Core Web API / Clean Architecture]
        subgraph AppCore[Application Layer (Core)]
            Handler[UploadDocumentCommandHandler / Service]
            IDoc[«interface» IDocumentExtractor]
            AppDTO[DocumentExtractionResult DTO]
            Handler -->|gọi| IDoc
            IDoc -->|trả về| AppDTO
        end

        subgraph Infra[Infrastructure Layer]
            Client[DocuExtractClient (Typed HttpClient Adapter)]
            Options[DocuExtractOptions]
            Client -.->|triển khai| IDoc
            Client -->|sử dụng| Options
        end
    end

    subgraph DocuExtractService[DocuExtract FastAPI Service]
        API[POST /api/v1/documents/extract]
    end

    Client -->|HTTP Multipart / X-Correlation-ID / Timeout / Cancellation| API
```

---

## 2. Tầng Application (Core/Application)

Tầng Application không được phụ thuộc vào `HttpClient`, `System.Net.Http`, hay các chi tiết mạng của FastAPI. Tầng này chỉ làm việc với abstraction và các model nghiệp vụ.

### 2.1. Abstraction: `IDocumentExtractor`

```csharp
namespace Application.Common.Interfaces;

/// <summary>
/// Abstraction trích xuất văn bản tài liệu cho tầng Application.
/// </summary>
public interface IDocumentExtractor
{
    /// <summary>
    /// Gửi stream tài liệu tới dịch vụ trích xuất.
    /// </summary>
    /// <param name="fileStream">Stream dữ liệu nhị phân của tài liệu.</param>
    /// <param name="fileName">Tên tệp tin (ví dụ: candidate.pdf).</param>
    /// <param name="contentType">MIME type (ví dụ: application/pdf).</param>
    /// <param name="cancellationToken">Token hủy thao tác.</param>
    /// <returns>Kết quả trích xuất văn bản và metadata.</returns>
    Task<DocumentExtractionResult> ExtractAsync(
        Stream fileStream,
        string fileName,
        string contentType,
        CancellationToken cancellationToken = default);
}
```

### 2.2. Application DTOs

```csharp
namespace Application.Common.Models;

public sealed record DocumentExtractionResult(
    DocumentMetadataDto Document,
    ExtractionDataDto Extraction,
    IReadOnlyList<string> Warnings);

public sealed record DocumentMetadataDto(
    string FileName,
    string MediaType,
    long SizeBytes,
    string Format);

public sealed record ExtractionDataDto(
    string Text,
    int? PageCount,
    int CharacterCount,
    int WordCount);
```

### 2.3. Phân Cấp Ngoại Lệ (Exception Hierarchy)

```csharp
namespace Application.Common.Exceptions;

using System.Net;

/// <summary>Ngoại lệ cơ sở cho các lỗi liên quan tới dịch vụ DocuExtract.</summary>
public abstract class DocuExtractException : Exception
{
    protected DocuExtractException(string message, Exception? innerException = null)
        : base(message, innerException) { }
}

/// <summary>Lỗi nghiệp vụ từ DocuExtract (400, 413, 415, 422, 500).</summary>
public sealed class DocuExtractClientException : DocuExtractException
{
    public string ErrorCode { get; }
    public string? CorrelationId { get; }
    public HttpStatusCode StatusCode { get; }

    public DocuExtractClientException(
        string errorCode,
        string message,
        string? correlationId,
        HttpStatusCode statusCode)
        : base($"DocuExtract returned {statusCode} ({errorCode}): {message}")
    {
        ErrorCode = errorCode;
        CorrelationId = correlationId;
        StatusCode = statusCode;
    }
}

/// <summary>Lỗi vượt quá thời gian chờ (Timeout) khi gọi DocuExtract.</summary>
public sealed class DocuExtractTimeoutException : DocuExtractException
{
    public DocuExtractTimeoutException(string message, Exception? inner = null)
        : base(message, inner) { }
}

/// <summary>Lỗi mất kết nối mạng hoặc DocuExtract không thể truy cập.</summary>
public sealed class DocuExtractConnectionException : DocuExtractException
{
    public DocuExtractConnectionException(string message, Exception? inner = null)
        : base(message, inner) { }
}

/// <summary>Lỗi phản hồi rỗng hoặc sai cấu trúc payload từ DocuExtract.</summary>
public sealed class DocuExtractInvalidResponseException : DocuExtractException
{
    public DocuExtractInvalidResponseException(string message, Exception? inner = null)
        : base(message, inner) { }
}
```

---

## 3. Tầng Infrastructure (Infrastructure/ExternalServices/DocuExtract)

Tầng Infrastructure chịu trách nhiệm giao tiếp HTTP, đóng gói multipart, phân tích cú pháp JSON, quản lý Correlation ID, và Zero Document Logging.

### 3.1. Data Contract Models (Khớp API DocuExtract)

```csharp
namespace Infrastructure.ExternalServices.DocuExtract.Contracts;

using System.Text.Json.Serialization;

internal sealed record DocuExtractResponse(
    [property: JsonPropertyName("document")] DocuExtractMetadata Document,
    [property: JsonPropertyName("extraction")] DocuExtractData Extraction,
    [property: JsonPropertyName("warnings")] List<string> Warnings);

internal sealed record DocuExtractMetadata(
    [property: JsonPropertyName("filename")] string Filename,
    [property: JsonPropertyName("media_type")] string MediaType,
    [property: JsonPropertyName("size_bytes")] long SizeBytes,
    [property: JsonPropertyName("format")] string Format);

internal sealed record DocuExtractData(
    [property: JsonPropertyName("text")] string Text,
    [property: JsonPropertyName("page_count")] int? PageCount,
    [property: JsonPropertyName("character_count")] int CharacterCount,
    [property: JsonPropertyName("word_count")] int WordCount);

internal sealed record DocuExtractErrorEnvelope(
    [property: JsonPropertyName("error")] DocuExtractErrorDetail Error);

internal sealed record DocuExtractErrorDetail(
    [property: JsonPropertyName("code")] string Code,
    [property: JsonPropertyName("message")] string Message,
    [property: JsonPropertyName("correlation_id")] string? CorrelationId);
```

### 3.2. Cấu Hình Options

```csharp
namespace Infrastructure.ExternalServices.DocuExtract;

public sealed class DocuExtractOptions
{
    public const string SectionName = "DocuExtract";

    public string BaseUrl { get; set; } = "http://localhost:8000";

    /// <summary>
    /// API Key xác thực Service-to-Service (Header X-Service-Api-Key). Bắt buộc ở Production khi gọi cross-service.
    /// </summary>
    public string? ApiKey { get; set; }

    public int TimeoutSeconds { get; set; } = 30;
    public long MaxFileSizeBytes { get; set; } = 10 * 1024 * 1024; // 10 MiB
}
```

### 3.3. Typed HttpClient Adapter: `DocuExtractClient`

```csharp
namespace Infrastructure.ExternalServices.DocuExtract;

using System.Diagnostics;
using System.Net.Http.Headers;
using System.Text.Json;
using Application.Common.Exceptions;
using Application.Common.Interfaces;
using Application.Common.Models;
using Infrastructure.ExternalServices.DocuExtract.Contracts;
using Microsoft.AspNetCore.Http;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;

public sealed class DocuExtractClient : IDocumentExtractor
{
    private const string CorrelationHeader = "X-Correlation-ID";
    private const string ApiKeyHeader = "X-Service-Api-Key";
    private readonly HttpClient _httpClient;
    private readonly DocuExtractOptions _options;
    private readonly IHttpContextAccessor _httpContextAccessor;
    private readonly ILogger<DocuExtractClient> _logger;

    public DocuExtractClient(
        HttpClient httpClient,
        IOptions<DocuExtractOptions> options,
        IHttpContextAccessor httpContextAccessor,
        ILogger<DocuExtractClient> logger)
    {
        _httpClient = httpClient;
        _options = options.Value;
        _httpContextAccessor = httpContextAccessor;
        _logger = logger;
    }

    public async Task<DocumentExtractionResult> ExtractAsync(
        Stream fileStream,
        string fileName,
        string contentType,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(fileStream);
        ArgumentException.ThrowIfNullOrWhiteSpace(fileName);

        // 1. Kiểm tra giới hạn kích thước sớm phía client
        if (fileStream.CanSeek && fileStream.Length > _options.MaxFileSizeBytes)
        {
            throw new DocuExtractClientException(
                "FILE_TOO_LARGE",
                $"File size ({fileStream.Length} bytes) exceeds the configured limit of {_options.MaxFileSizeBytes} bytes.",
                GetOrCreateCorrelationId(),
                System.Net.HttpStatusCode.RequestEntityTooLarge);
        }

        var correlationId = GetOrCreateCorrelationId();
        using var content = new MultipartFormDataContent();
        using var streamContent = new StreamContent(fileStream);
        streamContent.Headers.ContentType = new MediaTypeHeaderValue(contentType);
        content.Add(streamContent, "file", fileName);

        using var request = new HttpRequestMessage(HttpMethod.Post, "/api/v1/documents/extract")
        {
            Content = content
        };
        request.Headers.Add(CorrelationHeader, correlationId);
        if (!string.IsNullOrWhiteSpace(_options.ApiKey))
        {
            request.Headers.Add(ApiKeyHeader, _options.ApiKey);
        }

        var stopwatch = Stopwatch.StartNew();
        HttpResponseMessage response;

        try
        {
            _logger.LogInformation(
                "Dispatching document extraction to DocuExtract [CorrelationId: {CorrelationId}, FileName: {FileName}]",
                correlationId, fileName);

            response = await _httpClient.SendAsync(
                request,
                HttpCompletionOption.ResponseHeadersRead,
                cancellationToken);
        }
        catch (OperationCanceledException ex) when (!cancellationToken.IsCancellationRequested)
        {
            // Timeout xảy ra do HttpClient.Timeout chứ không phải caller chủ động cancel
            _logger.LogError(ex, "Timeout contacting DocuExtract after {Duration}ms [CorrelationId: {CorrelationId}]",
                stopwatch.ElapsedMilliseconds, correlationId);
            throw new DocuExtractTimeoutException("DocuExtract request timed out.", ex);
        }
        catch (HttpRequestException ex)
        {
            _logger.LogError(ex, "Network connection error contacting DocuExtract [CorrelationId: {CorrelationId}]", correlationId);
            throw new DocuExtractConnectionException("Failed to connect to DocuExtract service.", ex);
        }

        stopwatch.Stop();

        // 2. Xử lý phản hồi thành công (200 OK)
        if (response.IsSuccessStatusCode)
        {
            await using var responseStream = await response.Content.ReadAsStreamAsync(cancellationToken);
            var payload = await JsonSerializer.DeserializeAsync<DocuExtractResponse>(
                responseStream,
                cancellationToken: cancellationToken);

            if (payload is null)
            {
                throw new DocuExtractInvalidResponseException("Received empty response payload from DocuExtract.");
            }

            // Zero Document Logging: chỉ log metadata, không log text
            _logger.LogInformation(
                "Document extraction succeeded in {Duration}ms [CorrelationId: {CorrelationId}, Format: {Format}, Words: {Words}]",
                stopwatch.ElapsedMilliseconds, correlationId, payload.Document.Format, payload.Extraction.WordCount);

            return new DocumentExtractionResult(
                new DocumentMetadataDto(
                    payload.Document.Filename,
                    payload.Document.MediaType,
                    payload.Document.SizeBytes,
                    payload.Document.Format),
                new ExtractionDataDto(
                    payload.Extraction.Text,
                    payload.Extraction.PageCount,
                    payload.Extraction.CharacterCount,
                    payload.Extraction.WordCount),
                payload.Warnings.AsReadOnly());
        }

        // 3. Xử lý lỗi downstream có cấu trúc (400, 413, 415, 422, 500)
        await using var errorStream = await response.Content.ReadAsStreamAsync(cancellationToken);
        DocuExtractErrorEnvelope? errorEnvelope = null;
        try
        {
            errorEnvelope = await JsonSerializer.DeserializeAsync<DocuExtractErrorEnvelope>(
                errorStream,
                cancellationToken: cancellationToken);
        }
        catch (JsonException)
        {
            // Downstream trả về non-JSON (ví dụ: Nginx 502/504 gateway error)
        }

        var errorCode = errorEnvelope?.Error.Code ?? $"HTTP_{(int)response.StatusCode}";
        var errorMessage = errorEnvelope?.Error.Message ?? "An error occurred while extracting the document.";
        var returnedCorrelationId = errorEnvelope?.Error.CorrelationId ?? correlationId;

        _logger.LogWarning(
            "DocuExtract returned error {StatusCode} ({ErrorCode}): {Message} [CorrelationId: {CorrelationId}]",
            response.StatusCode, errorCode, errorMessage, returnedCorrelationId);

        throw new DocuExtractClientException(errorCode, errorMessage, returnedCorrelationId, response.StatusCode);
    }

    private string GetOrCreateCorrelationId()
    {
        var httpContext = _httpContextAccessor.HttpContext;
        if (httpContext?.Request.Headers.TryGetValue(CorrelationHeader, out var id) == true &&
            !string.IsNullOrWhiteSpace(id))
        {
            return id.ToString();
        }

        return Activity.Current?.Id ?? Guid.NewGuid().ToString("N");
    }
}
```

---

## 4. Đăng Ký Dependency Injection

```csharp
namespace Infrastructure.DependencyInjection;

using Application.Common.Interfaces;
using Infrastructure.ExternalServices.DocuExtract;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;

public static class DocuExtractServiceCollectionExtensions
{
    public static IServiceCollection AddDocuExtractClient(
        this IServiceCollection services,
        IConfiguration configuration)
    {
        services.Configure<DocuExtractOptions>(
            configuration.GetSection(DocuExtractOptions.SectionName));

        var options = configuration
            .GetSection(DocuExtractOptions.SectionName)
            .Get<DocuExtractOptions>() ?? new DocuExtractOptions();

        services.AddHttpClient<IDocumentExtractor, DocuExtractClient>(client =>
        {
            client.BaseAddress = new Uri(options.BaseUrl);
            client.Timeout = TimeSpan.FromSeconds(options.TimeoutSeconds);
        });

        return services;
    }
}
```

### Cấu hình `appsettings.json`:
```json
{
  "DocuExtract": {
    "BaseUrl": "http://localhost:8000",
    "ApiKey": "change-this-in-production-s2s-secret",
    "TimeoutSeconds": 30,
    "MaxFileSizeBytes": 10485760
  }
}
```

---

## 5. Kiểm Thử Tích Hợp (Testing Recipes với xUnit)

Ví dụ mock HTTP responses để kiểm thử adapter `DocuExtractClient`:

```csharp
public class DocuExtractClientTests
{
    [Fact]
    public async Task ExtractAsync_ValidPdf_ReturnsStructuredResult()
    {
        var mockHandler = new MockHttpMessageHandler(
            HttpStatusCode.OK,
            """
            {
              "document": { "filename": "sample.pdf", "media_type": "application/pdf", "size_bytes": 1024, "format": "pdf" },
              "extraction": { "text": "Extracted text content", "page_count": 1, "character_count": 22, "word_count": 3 },
              "warnings": []
            }
            """);

        var httpClient = new HttpClient(mockHandler) { BaseAddress = new Uri("http://test:8000") };
        var client = new DocuExtractClient(httpClient, Options.Create(new DocuExtractOptions()), new HttpContextAccessor(), NullLogger<DocuExtractClient>.Instance);

        using var ms = new MemoryStream(new byte[] { 1, 2, 3 });
        var result = await client.ExtractAsync(ms, "sample.pdf", "application/pdf");

        Assert.Equal("sample.pdf", result.Document.FileName);
        Assert.Equal("Extracted text content", result.Extraction.Text);
        Assert.Equal(1, result.Extraction.PageCount);
    }

    [Fact]
    public async Task ExtractAsync_EncryptedFile_ThrowsDocuExtractClientException()
    {
        var mockHandler = new MockHttpMessageHandler(
            HttpStatusCode.UnprocessableEntity,
            """
            {
              "error": { "code": "ENCRYPTED_DOCUMENT", "message": "File is password protected.", "correlation_id": "test-id" }
            }
            """);

        var httpClient = new HttpClient(mockHandler) { BaseAddress = new Uri("http://test:8000") };
        var client = new DocuExtractClient(httpClient, Options.Create(new DocuExtractOptions()), new HttpContextAccessor(), NullLogger<DocuExtractClient>.Instance);

        using var ms = new MemoryStream(new byte[] { 1, 2, 3 });
        var ex = await Assert.ThrowsAsync<DocuExtractClientException>(
            () => client.ExtractAsync(ms, "locked.pdf", "application/pdf"));

        Assert.Equal("ENCRYPTED_DOCUMENT", ex.ErrorCode);
        Assert.Equal(HttpStatusCode.UnprocessableEntity, ex.StatusCode);
    }
}
```

