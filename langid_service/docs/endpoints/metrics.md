# GET /metrics

Get API metrics.

## Request

### Example

**cURL**

```bash
curl -X GET "http://localhost:8080/metrics"
```

**Python**

```python
import requests

url = "http://localhost:8080/metrics"
response = requests.get(url)
print(response.json())
```

## Responses

### 200: Successful Response

**Body:**

```json
{
  "time_utc": "2025-11-07T00:22:10.334928+00:00",
  "workers_configured": 2,
  "model": {
    "size": "base",
    "device": "cpu",
    "compute": "int8"
  },
  "queue": {
    "queued": 0,
    "running": 1,
    "succeeded_24h": 37,
    "failed_24h": 2
  }
}
```
