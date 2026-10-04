import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse

from app.database.database import Base, engine
from app.database.models import (
    User,
    TrainingSession,
    StepPerformance,
    Mistake,
    WeakArea,
    ProgressHistory,
    GuidanceProfile, TrainingReport, CumulativeWeakArea, TestReport, GuidanceStep
)

from app.api.users import router as users_router
from app.api.sessions import router as sessions_router
from app.api.step_performance import router as step_performance_router
from app.api.mistakes import router as mistakes_router
from app.api.performance import router as performance_router
from app.api.weak_areas import router as weak_area_router
from app.api.progress import router as progress_router
from app.api.comparison import router as comparison_router
from app.api.guidance import router as guidance_router
from app.api.training_report import router as training_report_router
from app.api.test_assessment import router as test_assessment_router
from app.api.cumulative_weak_area import router as cumulative_weak_area_router
from app.api.test_report import router as test_report_router
from app.api.dashboard import router as dashboard_router
from app.api.auth import router as auth_router
from app.api.reports import router as reports_router

try:
    Base.metadata.create_all(bind=engine)
except Exception as e:
    print(f"[!] Warning: Could not connect to database on module load: {e}")


app = FastAPI(
    title="Medical VR Training & Assessment Backend",
    version="1.0.0"
)

# Enable CORS for Unity clients (Editor, WebGL, Standalone) and web dashboards
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from fastapi.routing import APIRoute

all_routers = [
    users_router,
    sessions_router,
    step_performance_router,
    mistakes_router,
    performance_router,
    weak_area_router,
    progress_router,
    comparison_router,
    guidance_router,
    training_report_router,
    test_assessment_router,
    cumulative_weak_area_router,
    test_report_router,
    dashboard_router,
    auth_router,
    reports_router,
]

for router in all_routers:
    app.include_router(router)
    # Mirror routes under /api/v1/... for API versioning compatibility
    for route in router.routes:
        if isinstance(route, APIRoute) and route.path.startswith("/api/"):
            v1_path = route.path.replace("/api/", "/api/v1/", 1)
            app.add_api_route(
                v1_path,
                route.endpoint,
                methods=route.methods,
                response_model=route.response_model,
                status_code=route.status_code,
                dependencies=route.dependencies,
                summary=route.summary,
                description=route.description,
                include_in_schema=False
            )

# Mount static files and serve the Testing UI
static_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/ui", include_in_schema=False)
def serve_ui():
    index_file = os.path.join(static_dir, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"message": "Testing UI is under construction. index.html not found."}


@app.get("/")
def root():
    return {
        "message": "Medical VR Assessment & Report Generation Backend is running",
        "testing_ui": "/ui",
        "api_docs": "/docs",
        "health": "/health"
    }


@app.get("/health")
def health():
    return {
        "status": "healthy"
    }