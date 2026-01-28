"""
Reusable decorators for error handling and other cross-cutting concerns.
"""

import traceback
from functools import wraps
from typing import Callable, ParamSpec, TypeVar

from backend.utlils.utils import error, notify

P = ParamSpec("P")
T = TypeVar("T")


def async_error_handler(
    function_name: str | None = None,
    critical: bool = False,
    username_param: str | None = "username",
):
    """
    Decorator for async functions to catch and log exceptions.

    Args:
        function_name: Name to use in error logs (defaults to actual function name)
        critical: Whether errors should be treated as critical
        username_param: Name of the parameter containing username (for error logging)

    Usage:
        @async_error_handler(critical=False)
        async def some_job(username: str):
            # ... logic

        # Instead of:
        asyncio.create_task(_run_job_with_error_handling(
            some_job(username), "some_job", username
        ))

        # You can now do:
        asyncio.create_task(some_job(username))
    """

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            # Extract username from kwargs or args
            username = kwargs.get(username_param) if username_param else None

            # Get function name
            fname = function_name or func.__name__

            try:
                return await func(*args, **kwargs)
            except Exception as e:
                error_msg = f"{fname} crashed: {e}\n{traceback.format_exc()}"
                notify(f"❌ [Error] {error_msg}")
                error(
                    error_msg,
                    status_code=500,
                    function_name=fname,
                    username=username,
                    critical=critical,
                )
                if critical:
                    raise
                return None

        return wrapper

    return decorator


async def run_job_with_error_handling(coro, job_name: str, username: str):
    """
    Legacy wrapper for asyncio.create_task - prefer using @async_error_handler decorator.

    This function is kept for backward compatibility. New code should use the decorator instead.

    Args:
        coro: Coroutine to run
        job_name: Name of the job for error logging
        username: Username for error logging

    Example:
        # Old way (still works):
        asyncio.create_task(_run_job_with_error_handling(
            some_job(username), "some_job", username
        ))

        # New way (preferred):
        @async_error_handler(critical=False)
        async def some_job(username: str):
            ...
        asyncio.create_task(some_job(username))
    """
    try:
        return await coro
    except Exception as e:
        error_msg = f"{job_name} crashed: {e}\n{traceback.format_exc()}"
        notify(f"❌ [Background] {error_msg}")
        error(
            error_msg,
            status_code=500,
            function_name=job_name,
            username=username,
            critical=False,
        )
