from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.sql import func

from app.database.database import Base


class GuidanceProfile(Base):
    __tablename__ = "guidance_profiles"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False
    )

    profile_version = Column(
        Integer,
        nullable=False,
        default=1
    )

    session_target = Column(
        Integer,
        nullable=False
    )

    created_at = Column(
        DateTime,
        server_default=func.now()
    )