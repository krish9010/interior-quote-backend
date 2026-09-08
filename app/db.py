"""
Database connection via SQLAlchemy.

Supports two backends:
1. PostgreSQL (recommended) -- set DATABASE_URL, which Render provides
   automatically when you attach a free Postgres instance to this service.
   No special system drivers needed.
2. SQL Server -- set SQLSERVER_HOST / SQLSERVER_DB (see .env.example).
   Requires the ODBC driver + pyodbc installed, which needs a Docker-based
   deploy on Render (not the simple native Python environment). Kept here
   for a future migration if you move to a paid SQL Server plan.

If neither is configured, the app falls back to in-memory storage (fine for
local testing, but data is lost whenever the server restarts).
"""
import os
import urllib.parse

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# ---- PostgreSQL (primary path) ----
DATABASE_URL = os.environ.get("DATABASE_URL", "")

# ---- SQL Server (kept for a future paid-plan migration) ----
SQLSERVER_HOST = os.environ.get("SQLSERVER_HOST", "")
SQLSERVER_PORT = os.environ.get("SQLSERVER_PORT", "1433")
SQLSERVER_DB = os.environ.get("SQLSERVER_DB", "")
SQLSERVER_USER = os.environ.get("SQLSERVER_USER", "")
SQLSERVER_PASSWORD = os.environ.get("SQLSERVER_PASSWORD", "")
SQLSERVER_DRIVER = os.environ.get("SQLSERVER_DRIVER", "ODBC Driver 18 for SQL Server")
SQLSERVER_TRUSTED = os.environ.get("SQLSERVER_TRUSTED", "false").lower() == "true"
SQLSERVER_ENCRYPT = os.environ.get("SQLSERVER_ENCRYPT", "yes")
SQLSERVER_TRUST_CERT = os.environ.get("SQLSERVER_TRUST_SERVER_CERTIFICATE", "no")


def using_postgres() -> bool:
    return bool(DATABASE_URL)


def db_configured() -> bool:
    return using_postgres() or bool(SQLSERVER_HOST and SQLSERVER_DB)


def _build_url() -> str:
    if using_postgres():
        # Render (and some other hosts) hand out "postgres://", but
        # SQLAlchemy 2.x requires the "postgresql://" scheme.
        url = DATABASE_URL
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        return url

    if SQLSERVER_TRUSTED:
        odbc_str = (
            f"DRIVER={{{SQLSERVER_DRIVER}}};SERVER={SQLSERVER_HOST},{SQLSERVER_PORT};"
            f"DATABASE={SQLSERVER_DB};Trusted_Connection=yes;"
            f"Encrypt={SQLSERVER_ENCRYPT};TrustServerCertificate={SQLSERVER_TRUST_CERT}"
        )
    else:
        odbc_str = (
            f"DRIVER={{{SQLSERVER_DRIVER}}};SERVER={SQLSERVER_HOST},{SQLSERVER_PORT};"
            f"DATABASE={SQLSERVER_DB};UID={SQLSERVER_USER};PWD={SQLSERVER_PASSWORD};"
            f"Encrypt={SQLSERVER_ENCRYPT};TrustServerCertificate={SQLSERVER_TRUST_CERT}"
        )
    return "mssql+pyodbc:///?odbc_connect=" + urllib.parse.quote_plus(odbc_str)


Base = declarative_base()
engine = None
SessionLocal = None

if db_configured():
    _engine_kwargs = {"pool_pre_ping": True}
    if not using_postgres():
        _engine_kwargs["fast_executemany"] = True  # pyodbc-only option
    engine = create_engine(_build_url(), **_engine_kwargs)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db():
    """Create tables if they don't exist. For production, prefer proper migrations (e.g. Alembic)."""
    if not engine:
        return
    from app import models_db  # noqa: F401  (ensures models are registered on Base)
    Base.metadata.create_all(bind=engine)


def get_db():
    if not SessionLocal:
        raise RuntimeError("No database configured. Set DATABASE_URL (Postgres) or SQLSERVER_HOST/SQLSERVER_DB in .env")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
