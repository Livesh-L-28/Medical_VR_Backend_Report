from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.database.models.user import User
from app.database.models.session import TrainingSession
from app.services.test_report_service import generate_test_report
from app.utils.auth import get_current_user


router = APIRouter(
    prefix="/api/test-reports",
    tags=["Test Reports"]
)


@router.post("/{session_id}")
def create_test_report(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    # Check whether the session exists
    session = db.query(TrainingSession).filter(
        TrainingSession.id == session_id
    ).first()

    if not session:
        raise HTTPException(
            status_code=404,
            detail="Session not found"
        )

    # Make sure the session belongs to the logged-in user
    if session.user_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="You are not allowed to access this session"
        )

    # Only TEST sessions can generate test reports
    if session.session_type != "TEST":
        raise HTTPException(
            status_code=400,
            detail="Test report can only be generated for TEST sessions"
        )

    result = generate_test_report(
        session_id=session_id,
        db=db
    )

    return {
        "message": "Test report generated successfully",
        **result
    }