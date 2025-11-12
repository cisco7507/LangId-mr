# GET /jobs/{job_id}/result

Get the result of a job.

## Request

### Path Parameters

| Name    | Type   | Description       |
| ------- | ------ | ----------------- |
| job_id  | string | The ID of the job. |

### Example

**cURL**

```bash
curl -X GET "http://localhost:8080/jobs/your_job_id/result"
```

**Python**

```python
import requests

job_id = "your_job_id"
url = f"http://localhost:8080/jobs/{job_id}/result"
response = requests.get(url)
print(response.json())
```

## Responses

### 200: Successful Response

**Body:** `ResultResponse`

```json
{
  "job_id": "string",
  "language": "en",
  "probability": 0.9,
  "transcript_snippet": "string",
  "processing_ms": 0,
  "raw": {}
}
```

### 422: Validation Error

**Body:** `HTTPValidationError`
