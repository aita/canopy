"""Utility functions and decorators for Canopy core."""

import functools
import logging
from typing import Any, Callable, TypeVar

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


def safe_slot(func: F) -> F:
    """Decorator to safely handle exceptions in Qt signal slots.

    This decorator wraps a slot function to catch any exceptions that occur
    during its execution. Instead of allowing the exception to propagate
    (which can cause crashes or undefined behavior in Qt's event loop),
    the exception is logged and the slot returns gracefully.

    Usage:
        @safe_slot
        def _on_some_signal(self, arg: str) -> None:
            # This code is now protected from crashing the app
            ...

    Args:
        func: The slot function to wrap.

    Returns:
        The wrapped function that catches exceptions.
    """
    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except Exception:
            logger.exception(f"Exception in slot {func.__qualname__}")
            return None
    return wrapper  # type: ignore[return-value]
