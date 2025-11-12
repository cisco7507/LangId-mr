# Windows LangID API v1.0.0

This document provides an overview of the Windows LangID API, which allows you to submit audio files for language identification.

## API Endpoints

The following endpoints are available:

* `GET /jobs`: Retrieve a list of all jobs.
* `DELETE /jobs`: Delete one or more jobs.
* `POST /jobs`: Submit a job by uploading an audio file.
* `POST /jobs/by-url`: Submit a job by providing a URL to an audio file.
* `GET /jobs/{job_id}`: Get the status of a job.
* `GET /jobs/{job_id}/result`: Get the result of a job.
* `GET /healthz`: Health check endpoint.
* `GET /metrics`: Get API metrics.

## Authentication

The API does not currently require authentication.

## Rate Limiting

The API does not currently have rate limiting. This may be added in a future release.

## Command Reference

To preview the live Swagger and ReDoc pages, run the following command:

```bash
uvicorn app.main:app --reload
```

* **Swagger:** http://localhost:8080/docs
* **ReDoc:** http://localhost:8080/redoc
