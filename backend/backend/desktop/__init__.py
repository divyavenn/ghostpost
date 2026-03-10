"""Desktop app integration module"""

from backend.desktop.desktop_jobs import router, create_desktop_job, cleanup_old_jobs
from backend.desktop.task_types import DesktopTaskType, normalize_task_type, supported_task_catalog

__all__ = [
    "router",
    "create_desktop_job",
    "cleanup_old_jobs",
    "DesktopTaskType",
    "normalize_task_type",
    "supported_task_catalog",
]
