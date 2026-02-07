"""OASIS Apps - MCP Apps with interactive UIs.

This package provides MCP Apps that render interactive UI alongside text results.
Apps are registered with the ToolRegistry like regular tools, but also declare
a UI resource that the host can render in an iframe.
"""

import threading

from oasis.core.tools import ToolRegistry

# Track initialization state with thread safety
_apps_lock = threading.Lock()
_apps_initialized = False


def init_apps() -> None:
    """Initialize and register all available MCP Apps.

    This function registers all app tool classes with the ToolRegistry.
    It is idempotent and thread-safe - calling it multiple times or
    from multiple threads has no additional effect.

    This should be called during application startup, after init_tools().
    """
    global _apps_initialized

    with _apps_lock:
        if _apps_initialized:
            return
        # No apps registered yet — add custom apps here
        _apps_initialized = True


def reset_apps() -> None:
    """Reset the app initialization state."""
    global _apps_initialized

    with _apps_lock:
        _apps_initialized = False


__all__ = [
    "init_apps",
    "reset_apps",
]
