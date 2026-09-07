import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.database.models.user import User
from app.database.models.session import TrainingSession

from app.schemas.session import SessionCreate, SessionResponse
from app.utils.auth import get_current_user
from app.services.progress_service import save_progress_history


router = APIRouter(
    prefix="/api/sessions",
    tags=["Sessions"]
)


# =========================================================
# CREATE SESSION
# =========================================================

@router.post("/", response_model=SessionResponse)
def create_session(
    session_data: SessionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    # Security check:
    # The session must belong to the logged-in user.
    if session_data.user_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="You are not allowed to create a session for another user"
        )

    # Validate session type
    if session_data.session_type not in ["TRAINING", "TEST"]:
        raise HTTPException(
            status_code=400,
            detail="session_type must be TRAINING or TEST"
        )

    # Create unique session ID
    new_session_id = str(uuid.uuid4())

    new_session = TrainingSession(
        session_id=new_session_id,
        user_id=current_user.id,
        session_type=session_data.session_type,
        session_number=session_data.session_number,
        start_time=datetime.utcnow(),
        status="IN_PROGRESS"
    )

    db.add(new_session)
    db.commit()
    db.refresh(new_session)

    return new_session


# =========================================================
# COMPLETE SESSION
# =========================================================

@router.post("/{session_id}/complete", response_model=SessionResponse)
def complete_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    # ---------------------------------------------------------
    # 1. Find the session
    # ---------------------------------------------------------
    session = db.query(TrainingSession).filter(
        TrainingSession.id == session_id
    ).first()

    if not session:
        raise HTTPException(
            status_code=404,
            detail="Session not found"
        )

    # ---------------------------------------------------------
    # 2. Security check
    # ---------------------------------------------------------
    if session.user_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="You are not allowed to complete this session"
        )

    # ---------------------------------------------------------
    # 3. Prevent duplicate completion
    # ---------------------------------------------------------
    if session.status != "IN_PROGRESS":
        raise HTTPException(
            status_code=400,
            detail="Session is already completed"
        )

    # ---------------------------------------------------------
    # 4. Set completion time
    # ---------------------------------------------------------
    session.end_time = datetime.utcnow()

    # ---------------------------------------------------------
    # 5. Calculate total session duration
    # ---------------------------------------------------------
    duration = session.end_time - session.start_time

    session.total_time_seconds = duration.total_seconds()

    # ---------------------------------------------------------
    # 6. Update session status
    # ---------------------------------------------------------
    session.status = "COMPLETED"

    db.commit()
    db.refresh(session)

    # ---------------------------------------------------------
    # 7. Save progress history
    # ---------------------------------------------------------
    save_progress_history(
        session.id,
        db
    )

    # ---------------------------------------------------------
    # 8. Return completed session
    # ---------------------------------------------------------
    return session