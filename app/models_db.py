import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Float, Text, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class QuotationDB(Base):
    __tablename__ = "quotations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)

    client_name: Mapped[str] = mapped_column(String(200))
    client_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    client_email: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    client_address: Mapped[str | None] = mapped_column(String(500), nullable=True)

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    floorplan_file_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    discount_percent: Mapped[float] = mapped_column(Float, default=0.0)
    tax_percent: Mapped[float] = mapped_column(Float, default=18.0)
    subtotal: Mapped[float] = mapped_column(Float, default=0.0)
    discount_amount: Mapped[float] = mapped_column(Float, default=0.0)
    tax_amount: Mapped[float] = mapped_column(Float, default=0.0)
    grand_total: Mapped[float] = mapped_column(Float, default=0.0)

    created_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    rooms: Mapped[list["RoomDB"]] = relationship(
        back_populates="quotation", cascade="all, delete-orphan", order_by="RoomDB.id"
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "client": {
                "name": self.client_name,
                "phone": self.client_phone,
                "email": self.client_email,
                "address": self.client_address,
            },
            "notes": self.notes,
            "floorplan_file_id": self.floorplan_file_id,
            "discount_percent": self.discount_percent,
            "tax_percent": self.tax_percent,
            "subtotal": self.subtotal,
            "discount_amount": self.discount_amount,
            "tax_amount": self.tax_amount,
            "grand_total": self.grand_total,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "rooms": [r.to_dict() for r in self.rooms],
        }


class RoomDB(Base):
    __tablename__ = "rooms"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    quotation_id: Mapped[str] = mapped_column(String(36), ForeignKey("quotations.id"))

    name: Mapped[str] = mapped_column(String(200))
    length_ft: Mapped[float] = mapped_column(Float, default=0.0)
    width_ft: Mapped[float] = mapped_column(Float, default=0.0)
    area_sqft: Mapped[float] = mapped_column(Float, default=0.0)
    room_total: Mapped[float] = mapped_column(Float, default=0.0)

    quotation: Mapped["QuotationDB"] = relationship(back_populates="rooms")
    items: Mapped[list["RoomItemDB"]] = relationship(
        back_populates="room", cascade="all, delete-orphan", order_by="RoomItemDB.id"
    )

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "length_ft": self.length_ft,
            "width_ft": self.width_ft,
            "area_sqft": self.area_sqft,
            "room_total": self.room_total,
            "items": [i.to_dict() for i in self.items],
        }


class ClientDB(Base):
    __tablename__ = "clients"

    email: Mapped[str] = mapped_column(String(200), primary_key=True)  # stored lowercased
    name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    logo_data: Mapped[str | None] = mapped_column(Text, nullable=True)  # base64-encoded image bytes
    logo_mimetype: Mapped[str | None] = mapped_column(String(50), nullable=True)

    def to_dict(self) -> dict:
        return {
            "email": self.email,
            "name": self.name,
            "phone": self.phone,
            "address": self.address,
            "has_logo": bool(self.logo_data),
        }


class RoomItemDB(Base):
    __tablename__ = "room_items"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id"))

    category: Mapped[str] = mapped_column(String(100))
    label: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    length: Mapped[float | None] = mapped_column(Float, nullable=True)
    length_unit: Mapped[str] = mapped_column(String(10), default="ft")
    width: Mapped[float | None] = mapped_column(Float, nullable=True)
    width_unit: Mapped[str] = mapped_column(String(10), default="ft")
    quantity: Mapped[float] = mapped_column(Float, default=0.0)
    unit: Mapped[str] = mapped_column(String(50))
    rate: Mapped[float] = mapped_column(Float, default=0.0)
    amount: Mapped[float] = mapped_column(Float, default=0.0)

    room: Mapped["RoomDB"] = relationship(back_populates="items")

    def to_dict(self) -> dict:
        return {
            "category": self.category,
            "label": self.label,
            "description": self.description,
            "length": self.length,
            "length_unit": self.length_unit,
            "width": self.width,
            "width_unit": self.width_unit,
            "quantity": self.quantity,
            "unit": self.unit,
            "rate": self.rate,
            "amount": self.amount,
        }
