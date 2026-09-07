from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.sql import func

from app.database.database import Base


class Mistake(Base):
    __tablename__ = "mistakes"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    session_id = Column(
        Integer,
        ForeignKey("sessions.id"),
        nullable=False
    )

    step_id = Column(
        Integer,
        nullable=False
    )

    mistake_type = Column(
        String,
        nullable=False
    )

    attempt_number = Column(
        Integer,
        nullable=False
    )

    timestamp = Column(
        DateTime,
        server_default=func.now(),
        nullable=False
    )