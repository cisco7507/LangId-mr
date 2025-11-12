# POST /jobs

Submit a job by uploading an audio file.

## Request

### Body

| Name | Type   | Description           |
| ---- | ------ | --------------------- |
| file | binary | The audio file to analyze. |

### Example

**cURL**

```bash
curl -X POST "http://localhost:8080/jobs" \
-H "Content-Type: multipart/form-data" \
-F "file=@/path/to/your/audio.wav"
```

**Python**

```python
import requests

url = "http://localhost:8080/jobs"
files = {"file": open("/path/to/your/audio.wav", "rb")}
response = requests.post(url, files=files)
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
