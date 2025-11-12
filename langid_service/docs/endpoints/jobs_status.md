# GET /jobs/{job_id}

Get the status of a job.

## Request

### Path Parameters

| Name    | Type   | Description       |
| ------- | ------ | ----------------- |
| job_id  | string | The ID of the job. |

### Example

**cURL**

```bash
curl -X GET "http://localhost:8080/jobs/your_job_id"
```

**Python**

```python
import requests

job_id = "your_job_id"
url = f"http://localhost:8080/jobs/{job_id}"
response = requests.get(url)
print(response.json())
```

## Responses

### 200: Successful Response

**Body:** `JobStatusResponse`

```json
{
  "job_id": "string",
  "status": "queued",
  "progress": 0,
  "created_at": "2023-10-27T10:00:00Z",
  "updated_at": "2023-10-27T10:00:00Z",
  "attempts": 0,
  "error": null
}
```

### 422: Validation Error

**Body:** `HTTPValidationError`
