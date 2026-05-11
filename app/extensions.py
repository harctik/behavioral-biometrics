from flask import current_app
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)


def get_db():
    """Get the active database engine for the current app context."""
    return current_app.extensions["db"]


def get_redis():
    """Get the active redis client for the current app context."""
    return current_app.extensions.get("redis_client")
