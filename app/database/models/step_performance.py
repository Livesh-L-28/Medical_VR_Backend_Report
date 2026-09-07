from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Boolean,
    ForeignKey
)

from app.database.database import Base


class StepPerformance(Base):
    __tablename__ = "step_performance"

    id = Column(Integer, primary_key=True, index=True)

    session_id = Column(
        Integer,
        ForeignKey("sessions.id"),
        nullable=False
    )

    step_id = Column(
        Integer,
        nullable=False
    )

    step_name = Column(
        String,
        nullable=False
    )

    attempts = Column(
        Integer,
        default=0,
        nullable=False
    )

    mistakes = Column(
        Integer,
        default=0,
        nullable=False
    )

    first_attempt_correct = Column(
        Boolean,
        default=False,
        nullable=False
    )

    step_time_seconds = Column(
        Float,
        default=0,
        nullable=False
    )

    completed = Column(
        Boolean,
        default=False,
        nullable=False
    )