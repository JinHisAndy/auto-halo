from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ProviderConfig(BaseModel):
    name: str
    api_key: str
    base_url: str
    models: list[str] = []


class OpenApiKeyItem(BaseModel):
    id: str
    key: str
    label: str = ""
    created_at: str = ""


class MinioConfig(BaseModel):
    endpoint: str
    access_key: str
    secret_key: str
    bucket: str
    secure: bool = False


class HaloConfig(BaseModel):
    site_url: str
    api_token: str


class ConfigResponse(BaseModel):
    providers: list[ProviderConfig]
    minio: Optional[MinioConfig]
    halo: Optional[HaloConfig]
    fetch_mode: str = "http"
    open_api_keys: list[OpenApiKeyItem] = []
    default_model_provider: Optional[str] = None
    default_model_name: Optional[str] = None

    class Config:
        from_attributes = True


class ConfigSaveRequest(BaseModel):
    providers: list[ProviderConfig] = []
    minio: Optional[MinioConfig] = None
    halo: Optional[HaloConfig] = None
    fetch_mode: str = "http"
    open_api_key: Optional[str] = None
    default_model_provider: Optional[str] = None
    default_model_name: Optional[str] = None


class TestConnectionResponse(BaseModel):
    success: bool
    message: str
