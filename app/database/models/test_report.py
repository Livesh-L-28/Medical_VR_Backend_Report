from sqlalchemy import Column, Integer, Float, String, DateTime, ForeignKey
from sqlalchemy.sql import func

from app.database.database import Base


class TestReport(Base):
    __test__ = False
    __tablename__ = "test_reports"

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

    session_number = Column(Integer, nullable=False)

    total_steps = Column(Integer, nullable=False, default=16)

    completed_steps = Column(Integer, nullable=False, default=0)

    correct_steps = Column(Integer, nullable=False, default=0)

    accuracy = Column(Float, nullable=False, default=0)

    total_attempts = Column(Integer, nullable=False, default=0)

    total_mistakes = Column(Integer, nullable=False, default=0)

    first_attempt_correct_count = Column(
        Integer,
        nullable=False,
        default=0
    )

    first_attempt_accuracy = Column(
        Float,
        nullable=False,
        default=0
    )

    total_time_seconds = Column(
        Float,
        nullable=False,
        default=0
    )

    average_step_time_seconds = Column(
        Float,
        nullable=False,
        default=0
    )

    result = Column(
        String,
        nullable=False
    )

    created_at = Column(
        DateTime,
        server_default=func.now()
    )