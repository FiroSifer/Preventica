from datetime import datetime, timezone
from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String, Text, DateTime, Index
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

def now():
    return datetime.now(timezone.utc)

class Base(DeclarativeBase):
    pass

class Camera(Base):
    __tablename__ = 'cameras'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    location: Mapped[str] = mapped_column(String(200), default='')
    source_type: Mapped[str] = mapped_column(String(20))
    source: Mapped[str] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    zones: Mapped[list['Zone']] = relationship(cascade='all, delete-orphan')

class Zone(Base):
    __tablename__ = 'zones'
    id: Mapped[int] = mapped_column(primary_key=True)
    camera_id: Mapped[int] = mapped_column(ForeignKey('cameras.id', ondelete='CASCADE'), index=True)
    name: Mapped[str] = mapped_column(String(100))
    type: Mapped[str] = mapped_column(String(20))
    severity: Mapped[str] = mapped_column(String(20))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    polygon: Mapped[list] = mapped_column(JSON)
    required_ppe: Mapped[list] = mapped_column(JSON, default=list)
    description: Mapped[str] = mapped_column(Text, default='')

class Incident(Base):
    __tablename__ = 'incidents'
    id: Mapped[int] = mapped_column(primary_key=True)
    camera_id: Mapped[int | None] = mapped_column(ForeignKey('cameras.id', ondelete='SET NULL'), index=True)
    zone_id: Mapped[int | None] = mapped_column(ForeignKey('zones.id', ondelete='SET NULL'))
    track_id: Mapped[int | None] = mapped_column(Integer)
    key: Mapped[str] = mapped_column(String(200), index=True)
    category: Mapped[str] = mapped_column(String(40))
    severity: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default='open', index=True)
    explanation: Mapped[str] = mapped_column(Text)
    evidence: Mapped[dict] = mapped_column(JSON)
    simulated: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    history: Mapped[list] = mapped_column(JSON, default=list)
    __table_args__ = (Index('incident_camera_status', 'camera_id', 'status'),)
