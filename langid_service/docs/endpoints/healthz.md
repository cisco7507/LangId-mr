# GET /healthz

Health check endpoint.

## Request

### Example

**cURL**

```bash
curl -X GET "http://localhost:8080/healthz"
```

**Python**

```python
import requests

url = "http://localhost:8080/healthz"
response = requests.get(url)
print(response.json())
```

## Responses

### 200: Successful Response

**Body:**

```json
{
  "status": "ok"
}
```
