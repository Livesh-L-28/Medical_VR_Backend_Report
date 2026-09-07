from sqlalchemy import Column, Integer, String, Float, ForeignKey
from app.database.database import Base


class GuidanceStep(Base):
    __tablename__ = "guidance_steps"

    id = Column(Integer, primary_key=True, index=True)

    guidance_profile_id = Column(
        Integer,
        ForeignKey("guidance_profiles.id"),
        nullable=False
    )

    step_id = Column(Integer, nullable=False)

    step_name = Column(String, nullable=False)

    guidance_level = Column(
        String,
        nullable=False
    )

    mistake_count = Column(
        Integer,
        nullable=False,
        default=0
    )

    mistake_ratio = Column(
        Float,
        nullable=False,
        default=0
    )

    guidance_message = Column(
        String,
        nullable=False
    )