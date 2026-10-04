from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.database.models.user import User
from app.services.dashboard_service import get_dashboard
from app.services.pdf_report_service import generate_dashboard_pdf
from app.schemas.dashboard import DashboardResponse
from app.utils.auth import get_current_user


router = APIRouter(
    prefix="/api/users",
    tags=["Personalized Dashboard"]
)


@router.get(
    "/{user_id}/dashboard",
    response_model=DashboardResponse
)
def get_user_dashboard(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Security check:
    # A user can access only their own dashboard.
    if user_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="You are not allowed to access this user's data"
        )

    dashboard = get_dashboard(user_id, db)

    if dashboard is None:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    return dashboard


@router.get(
    "/{user_id}/dashboard/pdf"
)
def download_user_dashboard_pdf(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Generate and stream a formal 5-page Longitudinal Trainee Clinical Portfolio PDF.
    
    Security:
    - User authentication enforced via JWT bearer token.
    - Strict user ownership validation: user_id == current_user.id (403 Forbidden otherwise).
    """
    if user_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="You are not allowed to access this user's data"
        )

    dashboard = get_dashboard(user_id, db)

    if dashboard is None:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    pdf_buffer = generate_dashboard_pdf(dashboard)

    filename = f"trainee_portfolio_{user_id}.pdf"
    return Response(
        content=pdf_buffer.getvalue(),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )