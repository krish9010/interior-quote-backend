"""
Quotation storage. Uses SQL Server (via SQLAlchemy) when SQLSERVER_* env vars
are set; otherwise falls back to the original in-memory dict so the app still
runs out of the box for local testing without a database.
"""
import uuid
from datetime import datetime, timezone

from app import db as db_module

_memory_store: dict[str, dict] = {}


def using_sql_server() -> bool:
    return db_module.db_configured()


def save_quotation(client: dict, rooms_result: list[dict], notes, floorplan_file_id,
                    discount_percent, tax_percent, subtotal, discount_amount,
                    tax_amount, grand_total, created_by: str) -> dict:
    quotation_id = str(uuid.uuid4())

    if using_sql_server():
        from app.models_db import QuotationDB, RoomDB, RoomItemDB
        session = db_module.SessionLocal()
        try:
            q = QuotationDB(
                id=quotation_id,
                client_name=client.get("name"),
                client_phone=client.get("phone"),
                client_email=client.get("email"),
                client_address=client.get("address"),
                notes=notes,
                floorplan_file_id=floorplan_file_id,
                discount_percent=discount_percent,
                tax_percent=tax_percent,
                subtotal=subtotal,
                discount_amount=discount_amount,
                tax_amount=tax_amount,
                grand_total=grand_total,
                created_by=created_by,
            )
            for room in rooms_result:
                r = RoomDB(
                    name=room["name"], length_ft=room["length_ft"], width_ft=room["width_ft"],
                    area_sqft=room["area_sqft"], room_total=room["room_total"],
                )
                for item in room["items"]:
                    r.items.append(RoomItemDB(**item))
                q.rooms.append(r)
            session.add(q)
            session.commit()
            session.refresh(q)
            return q.to_dict()
        finally:
            session.close()

    record = {
        "id": quotation_id,
        "client": client,
        "notes": notes,
        "floorplan_file_id": floorplan_file_id,
        "discount_percent": discount_percent,
        "tax_percent": tax_percent,
        "subtotal": subtotal,
        "discount_amount": discount_amount,
        "tax_amount": tax_amount,
        "grand_total": grand_total,
        "created_by": created_by,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "rooms": rooms_result,
    }
    _memory_store[quotation_id] = record
    return record


def update_quotation(quotation_id: str, client: dict, rooms_result: list[dict], notes, floorplan_file_id,
                      discount_percent, tax_percent, subtotal, discount_amount,
                      tax_amount, grand_total) -> dict | None:
    if using_sql_server():
        from app.models_db import QuotationDB, RoomDB, RoomItemDB
        session = db_module.SessionLocal()
        try:
            q = session.get(QuotationDB, quotation_id)
            if not q:
                return None
            q.client_name = client.get("name")
            q.client_phone = client.get("phone")
            q.client_email = client.get("email")
            q.client_address = client.get("address")
            q.notes = notes
            q.floorplan_file_id = floorplan_file_id
            q.discount_percent = discount_percent
            q.tax_percent = tax_percent
            q.subtotal = subtotal
            q.discount_amount = discount_amount
            q.tax_amount = tax_amount
            q.grand_total = grand_total
            q.rooms.clear()
            for room in rooms_result:
                r = RoomDB(
                    name=room["name"], length_ft=room["length_ft"], width_ft=room["width_ft"],
                    area_sqft=room["area_sqft"], room_total=room["room_total"],
                )
                for item in room["items"]:
                    r.items.append(RoomItemDB(**item))
                q.rooms.append(r)
            session.commit()
            session.refresh(q)
            return q.to_dict()
        finally:
            session.close()

    record = _memory_store.get(quotation_id)
    if not record:
        return None
    record.update({
        "client": client, "notes": notes, "floorplan_file_id": floorplan_file_id,
        "discount_percent": discount_percent, "tax_percent": tax_percent,
        "subtotal": subtotal, "discount_amount": discount_amount,
        "tax_amount": tax_amount, "grand_total": grand_total, "rooms": rooms_result,
    })
    return record


def delete_quotation(quotation_id: str) -> bool:
    if using_sql_server():
        from app.models_db import QuotationDB
        session = db_module.SessionLocal()
        try:
            q = session.get(QuotationDB, quotation_id)
            if not q:
                return False
            session.delete(q)
            session.commit()
            return True
        finally:
            session.close()
    return _memory_store.pop(quotation_id, None) is not None


def get_quotation(quotation_id: str) -> dict | None:
    if using_sql_server():
        from app.models_db import QuotationDB
        session = db_module.SessionLocal()
        try:
            q = session.get(QuotationDB, quotation_id)
            return q.to_dict() if q else None
        finally:
            session.close()
    return _memory_store.get(quotation_id)


def list_all() -> list[dict]:
    if using_sql_server():
        from app.models_db import QuotationDB
        session = db_module.SessionLocal()
        try:
            return [q.to_dict() for q in session.query(QuotationDB).order_by(QuotationDB.created_at.desc()).all()]
        finally:
            session.close()
    return list(_memory_store.values())


def list_by_client_email(email: str) -> list[dict]:
    email = (email or "").lower()
    if using_sql_server():
        from app.models_db import QuotationDB
        session = db_module.SessionLocal()
        try:
            rows = session.query(QuotationDB).filter(QuotationDB.client_email.ilike(email)).all()
            return [q.to_dict() for q in rows]
        finally:
            session.close()
    return [q for q in _memory_store.values() if (q.get("client") or {}).get("email", "").lower() == email]


def list_grouped_by_client() -> list[dict]:
    """Returns [{email, name, has_logo, quotations: [...]}] sorted by client name."""
    from app import clients as clients_module
    all_quotes = list_all()
    groups: dict[str, dict] = {}
    for q in all_quotes:
        email = (q.get("client") or {}).get("email") or "no-email"
        key = email.lower()
        if key not in groups:
            client_record = clients_module.get_client(email) or {}
            groups[key] = {
                "email": email,
                "name": client_record.get("name") or (q.get("client") or {}).get("name") or "Unknown",
                "has_logo": client_record.get("has_logo", False),
                "quotations": [],
            }
        groups[key]["quotations"].append(q)
    return sorted(groups.values(), key=lambda g: g["name"].lower())
