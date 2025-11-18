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
    filename: Optional[str] = None
    original_filename: Optional[str] = None
    language: Optional[str] = None
    probability: Optional[float] = None
    error: Optional[str] = None

class ResultResponse(BaseModel):
    job_id: str
    language: str
    probability: float
    detection_method: Optional[str] = None
    gate_decision: Optional[str] = None
    gate_meta: Optional[dict] = None
    music_only: bool = False
    transcript_snippet: Optional[str] = None
    processing_ms: int
    original_filename: Optional[str] = None
    raw: dict

class SubmitByUrl(BaseModel):
    url: str

class JobListResponse(BaseModel):
    jobs: list[JobStatusResponse]

class DeleteJobsRequest(BaseModel):
    job_ids: list[str]
