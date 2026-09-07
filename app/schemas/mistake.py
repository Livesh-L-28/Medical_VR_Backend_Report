from datetime import datetime
from pydantic import BaseModel


class MistakeCreate(BaseModel):
    session_id: int
    step_id: int
    mistake_type: str
    attempt_number: int


class MistakeResponse(BaseModel):
    id: int
    session_id: int
    step_id: int
    mistake_type: str
    attempt_number: int
    timestamp: datetime

    class Config:
        from_attributes = True