"""
API routes for browser-based OAuth authentication.
Users login through a backend browser that saves state.
"""
import io

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.browser_session import cleanup_expired_sessions, close_session, create_browser_session, get_session_screenshot, get_session_status, save_and_close_session
from backend.utils import error

router = APIRouter(prefix="/auth/browser", tags=["browser-auth"])


class BrowserSessionRequest(BaseModel):
    username: str


class SaveSessionRequest(BaseModel):
    session_id: str


@router.post("/start")
async def start_browser_session(request: BrowserSessionRequest):
    """
    Start a new browser session for OAuth login.
    Returns session ID for tracking.
    """
    try:
        # Cleanup expired sessions first
        await cleanup_expired_sessions()

        session_info = await create_browser_session(request.username)
        return session_info
    except Exception as e:
        error("Failed to start browser session", status_code=500, exception_text=str(e), function_name="start_browser_session", username=request.username)
        raise HTTPException(status_code=500, detail=f"Failed to start browser session: {str(e)}")


@router.get("/status/{session_id}")
async def check_session_status(session_id: str):
    """
    Check if user has completed login in the browser.
    Frontend should poll this endpoint.
    """
    try:
        status = await get_session_status(session_id)
        return status
    except Exception as e:
        error("Failed to check session status", status_code=500, exception_text=str(e), function_name="check_session_status")
        raise HTTPException(status_code=500, detail=f"Failed to check session status: {str(e)}")


@router.post("/save")
async def save_browser_session(request: SaveSessionRequest):
    """
    Save browser state and close session after successful login.
    """
    try:
        result = await save_and_close_session(request.session_id)
        return result
    except ValueError as e:
        error("Session not found", status_code=404, exception_text=str(e), function_name="save_browser_session")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        error("Failed to save session", status_code=500, exception_text=str(e), function_name="save_browser_session")
        raise HTTPException(status_code=500, detail=f"Failed to save session: {str(e)}")


@router.delete("/cancel/{session_id}")
async def cancel_browser_session(session_id: str):
    """
    Cancel and close a browser session without saving.
    """
    try:
        await close_session(session_id)
        return {"status": "cancelled"}
    except Exception as e:
        error("Failed to cancel session", status_code=500, exception_text=str(e), function_name="cancel_browser_session")
        raise HTTPException(status_code=500, detail=f"Failed to cancel session: {str(e)}")


@router.get("/screenshot/{session_id}")
async def get_browser_screenshot(session_id: str):
    """
    Get a screenshot of the current browser state.
    Useful for showing user what the browser looks like.
    """
    try:
        screenshot_bytes = await get_session_screenshot(session_id)
        if not screenshot_bytes:
            error("Session not found", status_code=404, function_name="get_browser_screenshot")
            raise HTTPException(status_code=404, detail="Session not found")

        return StreamingResponse(io.BytesIO(screenshot_bytes), media_type="image/png")
    except HTTPException:
        raise
    except Exception as e:
        error("Failed to get screenshot", status_code=500, exception_text=str(e), function_name="get_browser_screenshot")
        raise HTTPException(status_code=500, detail=f"Failed to get screenshot: {str(e)}")
