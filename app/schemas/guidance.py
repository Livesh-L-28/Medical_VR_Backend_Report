from datetime import datetime
from pydantic import BaseModel


class GuidanceProfileCreate(BaseModel):
    user_id: int
    profile_version: int
    session_target: int


class GuidanceProfileResponse(BaseModel):
    id: int
    user_id: int
    profile_version: int
    session_target: int
    created_at: datetime

    class Config:
        from_attributes = True