from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from agentreview_api.deps import get_session as get_session
from agentreview_api.routers import analysis, api_keys, audit, auth, metrics, policies, repositories, retention, users
from agentreview_api.schemas.auth import HealthResponse

__all__ = ["app", "get_session"]

app = FastAPI(
    title="AgentReviewOps API",
    version="0.1.0",
    summary="Analyze pull request diffs and generate review reports.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:8080",
        "http://localhost:8080",
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://127.0.0.1:4173",
        "http://localhost:4173",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(repositories.router)
app.include_router(users.router)
app.include_router(api_keys.router)
app.include_router(audit.router)
app.include_router(retention.router)
app.include_router(policies.router)
app.include_router(analysis.router)
app.include_router(metrics.router)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", service="agentreview-api")
