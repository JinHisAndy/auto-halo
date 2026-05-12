import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Integer, Text, Boolean, DateTime, Enum, JSON

from app.db import Base


class TaskStatus(str, enum.Enum):
    fetching = "fetching"
    parsing = "parsing"
    rewriting = "rewriting"
    publishing = "publishing"
    scheduled = "scheduled"
    completed = "completed"
    failed = "failed"


class PublishType(str, enum.Enum):
    immediate = "immediate"
    scheduled = "scheduled"


class Task(Base):
    __tablename__ = "tasks"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String(500), nullable=True)
    urls = Column(JSON, nullable=False, default=list)
    status = Column(Enum(TaskStatus), nullable=False, default=TaskStatus.fetching)
    progress = Column(Integer, nullable=False, default=0)
    stage_detail = Column(String(500), nullable=False, default="等待开始...")
    error_msg = Column(Text, nullable=True)
    keep_citations = Column(Boolean, nullable=False, default=False)
    publish_type = Column(Enum(PublishType), nullable=False, default=PublishType.immediate)
    scheduled_at = Column(DateTime, nullable=True)
    minio_original_path = Column(String(500), nullable=True)
    minio_rewritten_path = Column(String(500), nullable=True)
    original_content = Column(Text, nullable=True)
    rewritten_content = Column(Text, nullable=True)
    halo_post_id = Column(Integer, nullable=True)
    model_provider = Column(String(50), nullable=False)
    model_name = Column(String(100), nullable=False)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))