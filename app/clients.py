"""
Client registry, keyed by email. Uses the database (Postgres) when
configured -- see db.py -- otherwise falls back to in-memory storage, same
pattern as store.py.

Logos are stored as base64 text directly in the database (not on local
disk), so they survive Render restarts/redeploys just like everything else.
Kept out of the normal client dict (to_dict) to avoid bloating every list/get
response with image bytes -- fetch them via get_client_logo_bytes() instead.
"""
import base64
import uuid

from app import db as db_module

_clients: dict[str, dict] = {}  # in-memory fallback, keyed by lowercased email


def _using_db() -> bool:
    return db_module.db_configured()


def upsert_client(email: str, name: str = None, phone: str = None,
                   address: str = None, logo_bytes: bytes = None, logo_mimetype: str = None) -> dict:
    key = email.lower()
    logo_data = base64.b64encode(logo_bytes).decode("ascii") if logo_bytes is not None else None

    if _using_db():
        from app.models_db import ClientDB
        session = db_module.SessionLocal()
        try:
            record = session.get(ClientDB, key)
            if not record:
                record = ClientDB(email=key)
            if name is not None:
                record.name = name
            if phone is not None:
                record.phone = phone
            if address is not None:
                record.address = address
            if logo_data is not None:
                record.logo_data = logo_data
                record.logo_mimetype = logo_mimetype
            session.add(record)
            session.commit()
            session.refresh(record)
            return record.to_dict()
        finally:
            session.close()

    existing = _clients.get(key, {})
    record = {
        "email": key,
        "name": name if name is not None else existing.get("name", ""),
        "phone": phone if phone is not None else existing.get("phone"),
        "address": address if address is not None else existing.get("address"),
        "_logo_data": logo_data if logo_data is not None else existing.get("_logo_data"),
        "_logo_mimetype": logo_mimetype if logo_data is not None else existing.get("_logo_mimetype"),
    }
    _clients[key] = record
    return {k: v for k, v in record.items() if not k.startswith("_")} | {"has_logo": bool(record.get("_logo_data"))}


def get_client(email: str) -> dict | None:
    key = (email or "").lower()
    if _using_db():
        from app.models_db import ClientDB
        session = db_module.SessionLocal()
        try:
            record = session.get(ClientDB, key)
            return record.to_dict() if record else None
        finally:
            session.close()
    record = _clients.get(key)
    if not record:
        return None
    return {"email": record["email"], "name": record.get("name"), "phone": record.get("phone"),
            "address": record.get("address"), "has_logo": bool(record.get("_logo_data"))}


def get_client_logo_bytes(email: str) -> tuple[bytes, str] | None:
    """Returns (raw_bytes, mimetype) for a client's logo, or None if they have none."""
    key = (email or "").lower()
    if _using_db():
        from app.models_db import ClientDB
        session = db_module.SessionLocal()
        try:
            record = session.get(ClientDB, key)
            if not record or not record.logo_data:
                return None
            return base64.b64decode(record.logo_data), record.logo_mimetype or "image/jpeg"
        finally:
            session.close()
    record = _clients.get(key)
    if not record or not record.get("_logo_data"):
        return None
    return base64.b64decode(record["_logo_data"]), record.get("_logo_mimetype") or "image/jpeg"


def delete_client(email: str) -> bool:
    key = (email or "").lower()
    if _using_db():
        from app.models_db import ClientDB
        session = db_module.SessionLocal()
        try:
            record = session.get(ClientDB, key)
            if not record:
                return False
            session.delete(record)
            session.commit()
            return True
        finally:
            session.close()
    return _clients.pop(key, None) is not None


def list_clients() -> list[dict]:
    if _using_db():
        from app.models_db import ClientDB
        session = db_module.SessionLocal()
        try:
            return [c.to_dict() for c in session.query(ClientDB).order_by(ClientDB.name).all()]
        finally:
            session.close()
    return [
        {"email": r["email"], "name": r.get("name"), "phone": r.get("phone"),
         "address": r.get("address"), "has_logo": bool(r.get("_logo_data"))}
        for r in _clients.values()
    ]


def new_upload_id() -> str:
    return str(uuid.uuid4())
