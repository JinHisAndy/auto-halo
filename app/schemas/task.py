from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator


class TaskCreate(BaseModel):
    urls: list[str]
    keep_citations: bool = False
    publish_type: str = "immediate"
    scheduled_at: Optional[datetime] = None
    trigger_source: str = "ui"
    model_provider: str
    model_name: str

    @field_validator("trigger_source", mode="before")
    @classmethod
    def normalize_trigger_source(cls, value: str | None) -> str:
        normalized = (value or "ui").strip().lower()
        if normalized not in {"ui", "api"}:
            raise ValueError("trigger_source must be 'ui' or 'api'")
        return normalized


class TaskResponse(BaseModel):
    id: str
    title: Optional[str]
    urls: list[str]
    status: str
    progress: int
    stage_detail: str
    error_msg: Optional[str]
    keep_citations: bool
    publish_type: str
    scheduled_at: Optional[datetime]
    minio_original_path: Optional[str]
    minio_rewritten_path: Optional[str]
    original_content: Optional[str]
    rewritten_content: Optional[str]
    rewritten_title: Optional[str] = None
    generated_tags: Optional[list[dict]] = None
    failed_stage: Optional[str] = None
    trigger_source: str = "ui"
    halo_post_id: Optional[str]
    model_provider: str
    model_name: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TaskListResponse(BaseModel):
    tasks: list[TaskResponse]
