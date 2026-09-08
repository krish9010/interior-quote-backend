from pydantic import BaseModel, Field
from typing import Optional


class ClientInfo(BaseModel):
    name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None


class RoomItemIn(BaseModel):
    category: str
    length: Optional[float] = None
    length_unit: Optional[str] = "ft"
    width: Optional[float] = None
    width_unit: Optional[str] = "ft"
    rate: Optional[float] = None  # per-line rate override; falls back to the catalog rate if omitted
    quantity: Optional[float] = None  # legacy fallback, used only if length/width aren't given
    quantity_unit: Optional[str] = "ft"


class RoomIn(BaseModel):
    name: str
    length_ft: Optional[float] = 0  # no longer required -- items now carry their own dimensions
    width_ft: Optional[float] = 0
    length_unit: Optional[str] = "ft"  # "ft" | "m" | "cm"
    width_unit: Optional[str] = "ft"
    items: list[RoomItemIn] = []


class QuotationRequest(BaseModel):
    client: ClientInfo
    rooms: list[RoomIn]
    discount_percent: float = 0.0
    tax_percent: float = 18.0
    floorplan_file_id: Optional[str] = None
    notes: Optional[str] = None


class SuggestItemsRequest(BaseModel):
    description: str


class ChatRequest(BaseModel):
    question: str


class DesignConceptRequest(BaseModel):
    description: str
    budget_hint: Optional[str] = None


class ClientUpsertRequest(BaseModel):
    email: str
    name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None


class CatalogItemUpsertRequest(BaseModel):
    kind: str  # "per_sqft" | "fixed"
    key: str
    label: str
    rate: float
    unit: str
    description: Optional[str] = ""


class ModulePresetUpsertRequest(BaseModel):
    key: str
    label: str
    default_items: list[str] = []
