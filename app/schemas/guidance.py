from datetime import datetime
from pydantic import BaseModel, ConfigDict


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

    model_config = ConfigDict(from_attributes=True)