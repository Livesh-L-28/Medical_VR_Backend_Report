from sqlalchemy import Column, Integer, Float, DateTime, ForeignKey
from sqlalchemy.sql import func

from app.database.database import Base


class ProgressHistory(Base):
    __tablename__ = "progress_history"

    id = Column(Integer, primary_key=True, index=True)

    session_id = Column(
        Integer,
        ForeignKey("sessions.id"),
        nullable=False
    )

    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False
    )

    session_number = Column(
        Integer,
        nullable=False
    )

    accuracy = Column(
        Float,
        nullable=False,
        default=0
    )

    total_mistakes = Column(
        Integer,
        nullable=False,
        default=0
    )

    total_attempts = Column(
        Integer,
        nullable=False,
        default=0
    )

    total_time_seconds = Column(
        Float,
        nullable=False,
        default=0
    )

    completed_steps = Column(
        Integer,
        nullable=False,
        default=0
    )

    created_at = Column(
        DateTime,
        server_default=func.now()
    )