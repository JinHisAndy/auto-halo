from datetime import datetime, timezone

from sqlalchemy import Column, String, Text, DateTime

from app.db import Base


class SystemConfig(Base):
    __tablename__ = "system_config"

    key = Column(String(200), primary_key=True)
    value = Column(Text, nullable=False, default="{}")
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))