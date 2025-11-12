# DELETE /jobs

Deletes one or more jobs.

## Request Body

The request body should be a `DeleteJobsRequest` object.

| Field | Type | Description |
|---|---|---|
| `job_ids` | `array[string]` | A list of job IDs to delete. |

**Example:**

```json
{
  "job_ids": [
    "a1b2c3d4-e5f6-7890-1234-567890abcdef"
  ]
}
```

## Responses

### 200 OK

Returns a JSON object indicating the number of deleted jobs.

**Example:**

```json
{
  "status": "ok",
  "deleted_count": 1
}
```
