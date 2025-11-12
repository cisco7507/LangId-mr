from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime

class EnqueueResponse(BaseModel):
    job_id: str
    status: Literal["queued"]

class JobStatusResponse(BaseModel):
    job_id: str
    status: Literal["queued","running","succeeded","failed"]
    progress: int = 0
    created_at: datetime
    updated_at: datetime
    attempts: int
    error: Optional[str] = None

class ResultResponse(BaseModel):
    job_id: str
    language: str
    probability: float
    transcript_snippet: Optional[str] = None
    processing_ms: int
    raw: dict

class SubmitByUrl(BaseModel):
    url: str

class JobListResponse(BaseModel):
    jobs: list[JobStatusResponse]

class DeleteJobsRequest(BaseModel):
    job_ids: list[str]
