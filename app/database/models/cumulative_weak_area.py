from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.sql import func

from app.database.database import Base


class CumulativeWeakArea(Base):
    __tablename__ = "cumulative_weak_areas"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False
    )

    step_id = Column(Integer, nullable=False)

    step_name = Column(String, nullable=False)

    total_attempts = Column(Integer, nullable=False, default=0)

    total_mistakes = Column(Integer, nullable=False, default=0)

    mistake_ratio = Column(Float, nullable=False, default=0)

    severity = Column(String, nullable=False)

    rank = Column(Integer, nullable=False)

    last_session_id = Column(
        Integer,
        ForeignKey("sessions.id"),
        nullable=True
    )

    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now()
    )