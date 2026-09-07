from sqlalchemy import Column, Integer, String, DateTime, Float, ForeignKey
from sqlalchemy.sql import func
from app.database.database import Base


class TrainingSession(Base):
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, index=True)

    session_id = Column(String, unique=True, nullable=False, index=True)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    session_type = Column(String, nullable=False)
    session_number = Column(Integer, nullable=False)

    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=True)

    total_time_seconds = Column(Float, nullable=True)

    status = Column(String, nullable=False, default="IN_PROGRESS")

    created_at = Column(DateTime, server_default=func.now())