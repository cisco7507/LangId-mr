# GET /jobs

Retrieves a list of all jobs.

## Responses

### 200 OK

Returns a `JobListResponse` object containing a list of all jobs.

**Example:**

```json
{
  "jobs": [
    {
      "job_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
      "status": "succeeded",
      "progress": 100,
      "created_at": "2023-10-27T10:00:00Z",
      "updated_at": "2023-10-27T10:01:00Z",
      "attempts": 1,
      "error": null
    }
  ]
}
```
