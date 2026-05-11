"""Application package exports.

Exposes both:
- ``create_app`` for factory-based initialization (tests/dev).
- ``app`` for WSGI servers expecting ``app:app`` entrypoint.

Uses lazy initialization to prevent route collisions during imports.
"""

from .app_impl import create_app

# Lazy app initialization — created on first access, not at import time.
# This prevents route collisions when sub-modules trigger re-imports.
_app_instance = None


def get_app():
    """Get or create the singleton Flask application."""
    global _app_instance
    if _app_instance is None:
        _app_instance = create_app()
    return _app_instance


class _LazyApp:
    """Proxy that creates the Flask app on first attribute access."""

    def __getattr__(self, name):
        return getattr(get_app(), name)

    def __call__(self, *args, **kwargs):
        return get_app()(*args, **kwargs)


# WSGI-compatible default application object for `app:app`.
# Uses lazy proxy so importing `from app import app` doesn't
# immediately trigger create_app().
app = _LazyApp()

__all__ = ["create_app", "get_app", "app"]
