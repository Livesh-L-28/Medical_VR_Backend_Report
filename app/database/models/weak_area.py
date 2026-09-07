from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.sql import func

from app.database.database import Base


class WeakArea(Base):
    __tablename__ = "weak_areas"

    id = Column(Integer, primary_key=True, index=True)

    session_id = Column(
        Integer,
        ForeignKey("sessions.id"),
        nullable=False
    )

    step_id = Column(Integer, nullable=False)

    step_name = Column(String, nullable=False)

    attempts = Column(Integer, nullable=False, default=0)

    mistakes = Column(Integer, nullable=False, default=0)

    mistake_ratio = Column(Float, nullable=False, default=0)

    severity = Column(String, nullable=False)

    rank = Column(Integer, nullable=False)

    created_at = Column(
        DateTime,
        server_default=func.now()
    )