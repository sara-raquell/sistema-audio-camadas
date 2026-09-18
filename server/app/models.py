"""
Modelo ORM da tabela `audios`, conforme especificação da Atividade 3.
"""
import uuid
from datetime import datetime

from sqlalchemy import Column, String, Integer, Float, DateTime
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from .database import Base


class Audio(Base):
    __tablename__ = "audios"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    original_name = Column(String, nullable=False)
    original_ext = Column(String, nullable=False)
    mime_type = Column(String, nullable=True)
    size_bytes = Column(Integer, nullable=False)

    duration_sec = Column(Float, nullable=True)
    sample_rate = Column(Integer, nullable=True)
    channels = Column(Integer, nullable=True)
    bitrate = Column(Integer, nullable=True)

    processing_type = Column(String, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    path_original = Column(String, nullable=False)
    path_processed = Column(String, nullable=True)

    def to_dict(self):
        return {
            "id": str(self.id),
            "original_name": self.original_name,
            "original_ext": self.original_ext,
            "mime_type": self.mime_type,
            "size_bytes": self.size_bytes,
            "duration_sec": self.duration_sec,
            "sample_rate": self.sample_rate,
            "channels": self.channels,
            "bitrate": self.bitrate,
            "processing_type": self.processing_type,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "path_original": self.path_original,
            "path_processed": self.path_processed,
        }
