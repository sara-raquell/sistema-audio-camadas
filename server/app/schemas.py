"""
Schemas Pydantic usados nas respostas da API.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class AudioOut(BaseModel):
    id: UUID
    original_name: str
    original_ext: str
    mime_type: Optional[str] = None
    size_bytes: int
    duration_sec: Optional[float] = None
    sample_rate: Optional[int] = None
    channels: Optional[int] = None
    bitrate: Optional[int] = None
    processing_type: str
    created_at: datetime
    path_original: str
    path_processed: Optional[str] = None

    class Config:
        from_attributes = True


class ProcessingTypeOut(BaseModel):
    key: str
    label: str
