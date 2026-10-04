from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class SessionCreate(BaseModel):
    user_id: int
    session_type: str
    session_number: int


class SessionResponse(BaseModel):
    id: int
    session_id: str
    user_id: int
    session_type: str
    session_number: int
    start_time: datetime
    end_time: Optional[datetime] = None
    total_time_seconds: Optional[float] = None
    status: str

    model_config = ConfigDict(from_attributes=True)