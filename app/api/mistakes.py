from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.database.models.user import User
from app.database.models.session import TrainingSession
from app.database.models.mistake import Mistake
from app.schemas.mistake import MistakeCreate, MistakeResponse
from app.config.constants import STEPS
from app.utils.auth import get_current_user

router = APIRouter(
    prefix="/api/mistakes",
    tags=["Mistakes"]
)


@router.post("/", response_model=MistakeResponse)
def create_mistake(
    mistake_data: MistakeCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # 1. Check whether the session exists
    session = db.query(TrainingSession).filter(
        TrainingSession.id == mistake_data.session_id
    ).first()

    if not session:
        raise HTTPException(
            status_code=404,
            detail="Session not found"
        )

    # 2. Check session ownership
    if session.user_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="You are not allowed to access this session"
        )

    # 3. Validate step ID
    if mistake_data.step_id not in STEPS:
        raise HTTPException(
            status_code=400,
            detail="Invalid step_id. Must be between 0 and 15."
        )

    # 4. Validate mistake type
    allowed_mistake_types = [
        "WRONG_OBJECT",
        "WRONG_ZONE",
        "INCORRECT_PLACEMENT"
    ]

    if mistake_data.mistake_type not in allowed_mistake_types:
        raise HTTPException(
            status_code=400,
            detail="Invalid mistake_type"
        )

    # 5. Create mistake
    mistake = Mistake(
        session_id=mistake_data.session_id,
        step_id=mistake_data.step_id,
        mistake_type=mistake_data.mistake_type,
        attempt_number=mistake_data.attempt_number
    )

    db.add(mistake)
    db.commit()
    db.refresh(mistake)

    return mistake