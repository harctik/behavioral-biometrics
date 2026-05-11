"""WSGI entrypoint shim.

Delegates to the canonical ``app/__init__.py`` which exposes the ``create_app``
factory and a lazy ``app`` singleton.  This file exists only for backwards
compatibility with deployment scripts that reference ``app.app:app``.
"""
from app import create_app, app  # noqa: F401

__all__ = ["create_app", "app"]
