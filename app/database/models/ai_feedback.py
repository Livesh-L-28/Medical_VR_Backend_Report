from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.sql import func

from app.database.database import Base


class AIReportFeedback(Base):
    __tablename__ = "ai_report_feedback"

    id = Column(Integer, primary_key=True, index=True)

    session_id = Column(
        Integer,
        ForeignKey("sessions.id"),
        nullable=False,
        index=True
    )

    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True
    )

    model_name = Column(
        String,
        nullable=False,
        default="openbiollm"
    )

    feedback_json = Column(
        Text,
        nullable=False
    )

    status = Column(
        String,
        nullable=False,
        default="SUCCESS"
    )

    created_at = Column(
        DateTime,
        server_default=func.now()
    )

    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now()
    )
