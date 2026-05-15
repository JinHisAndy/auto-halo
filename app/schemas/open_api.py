from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class OpenApiTaskCreateRequest(BaseModel):
    urls: list[str]
    publish_type: str = "immediate"
    scheduled_at: Optional[datetime] = None
    model_provider: Optional[str] = None
    model_name: Optional[str] = None
    keep_citations: bool = False


class OpenApiTaskCreateResponse(BaseModel):
    task_id: str
    status: str
    trigger_source: str
    message: str
