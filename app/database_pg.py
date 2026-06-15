"""PostgreSQL-specific database manager.

This module provides a PostgreSQL-aware ``DatabaseManager`` subclass
(aliased as ``PostgresDatabaseManager``) for production deployments.

In the current architecture the main ``app.database.DatabaseManager``
already handles PostgreSQL via SQLAlchemy when the connection string
starts with ``postgresql://``.  This module re-exports that class so
that legacy ``from app.database_pg import ...`` imports continue to
work without error.
"""

from app.database import DatabaseManager

# Alias so both import styles resolve:
#   from app.database_pg import DatabaseManager as PostgresDatabaseManager
#   from app.database_pg import PostgresDatabaseManager
PostgresDatabaseManager = DatabaseManager

__all__ = ["DatabaseManager", "PostgresDatabaseManager"]
