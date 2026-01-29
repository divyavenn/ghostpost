"""Desktop app integration module"""

from backend.desktop.desktop_jobs import router, create_desktop_job, cleanup_old_jobs

__all__ = ["router", "create_desktop_job", "cleanup_old_jobs"]
