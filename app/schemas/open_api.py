from datetime import datetime
from typing import Optional

from pydantic import BaseModel, model_validator


class OpenApiTaskCreateRequest(BaseModel):
    urls: list[str]
    publish_type: str = "immediate"
    scheduled_at: Optional[datetime] = None
    model_provider: Optional[str] = None
    model_name: Optional[str] = None
    keep_citations: bool = False

    @model_validator(mode="after")
    def validate_scheduled_publish(self):
        if self.publish_type == "scheduled" and self.scheduled_at is None:
            raise ValueError("scheduled_at is required when publish_type is scheduled")
        return self


class OpenApiTaskCreateResponse(BaseModel):
    task_id: str
    status: str
    trigger_source: str
    message: str
