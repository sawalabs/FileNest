from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from backend.app.core.config import settings
from backend.app.core.security import get_or_create_app_token

router = APIRouter()


class SessionResponse(BaseModel):
    token: str = Field(description="Runtime ephemeral session token for local desktop client authorization")
    status: str = Field(default="active", description="Session status")


@router.get("/session", response_model=SessionResponse, summary="Get ephemeral app session token")
async def get_session_token(request: Request, response: Response) -> SessionResponse:
    """Returns the current runtime ephemeral session token for local frontend authorization."""
    sec_fetch_site = (request.headers.get("Sec-Fetch-Site") or "").strip().lower()
    origin = request.headers.get("Origin")
    if origin is not None:
        normalized_origin = origin.strip().rstrip("/")
        allowed_origins = {o.strip().rstrip("/") for o in settings.CORS_ORIGINS}
        if normalized_origin not in allowed_origins:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Unauthorized Origin for session handshake.",
            )
    elif sec_fetch_site == "cross-site":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cross-site session handshake is forbidden.",
        )

    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    token = get_or_create_app_token()
    return SessionResponse(token=token, status="active")
