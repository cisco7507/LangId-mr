# POST /jobs/by-url

Submit a job by providing a URL to an audio file.

## Request

### Body

| Name | Type   | Description           |
| ---- | ------ | --------------------- |
| url  | string | The URL of the audio file to analyze. |

### Example

**cURL**

```bash
curl -X POST "http://localhost:8080/jobs/by-url" \
-H "Content-Type: application/json" \
-d '{"url": "http://example.com/audio.wav"}'
```

**Python**

```python
import requests

url = "http://localhost:8080/jobs/by-url"
payload = {"url": "http://example.com/audio.wav"}
response = requests.post(url, json=payload)
print(response.json())
```

## Responses

### 200: Successful Response

**Body:** `EnqueueResponse`

```json
{
  "job_id": "string",
  "status": "queued"
}
```

### 422: Validation Error

**Body:** `HTTPValidationError`
