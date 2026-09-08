"""
Pricing catalog for the interior design quotation tool.

Two kinds of line items:
- PER_SQFT: rate is multiplied by an area in square feet.
- FIXED: rate is multiplied by a unit count (e.g. one wardrobe, one door).

The catalog below is mutable at runtime (edited via the Modules screen /
/api/catalog/* endpoints) so staff can adjust rates without a redeploy.
Like quotations, these edits live in memory and reset on restart unless
SQL Server is configured -- same limitation documented in the README.

Unit conversion: room dimensions and any linear item measurement can be
entered in cm, m, or ft and are converted to feet before pricing.
"""

UNIT_TO_FT = {
    "mm": 0.003280839895,
    "cm": 0.03280839895,
    "in": 0.0833333333,
    "ft": 1.0,
    "m": 3.280839895,
}


def convert_to_ft(value: float, unit: str) -> float:
    factor = UNIT_TO_FT.get(unit, 1.0)
    return round(float(value) * factor, 4)


PER_SQFT_RATES = {
    "painting": {"label": "Painting", "rate": 18, "unit": "sq.ft", "description": ""},
    "false_ceiling": {"label": "False ceiling (POP/gypsum)", "rate": 85, "unit": "sq.ft", "description": ""},
    "flooring_tile": {"label": "Flooring - tile", "rate": 75, "unit": "sq.ft", "description": ""},
    "flooring_wood": {"label": "Flooring - engineered wood", "rate": 150, "unit": "sq.ft", "description": ""},
    "wall_tiling": {"label": "Wall tiling", "rate": 90, "unit": "sq.ft", "description": ""},
    "wallpaper": {"label": "Wallpaper", "rate": 60, "unit": "sq.ft", "description": ""},
    "pop_work": {"label": "POP / wall design work", "rate": 45, "unit": "sq.ft", "description": ""},
    "kitchen_base_cabinets": {"label": "Kitchen base cabinets", "rate": 1500, "unit": "sq.ft",
                               "description": "Handleless base cabinets with high-gloss/matt laminate finish"},
    "kitchen_wall_cabinets": {"label": "Kitchen wall cabinets", "rate": 1500, "unit": "sq.ft",
                               "description": "Wall-mounted storage units with glass/laminate shutters"},
    "kitchen_loft_unit": {"label": "Kitchen loft unit", "rate": 1200, "unit": "sq.ft",
                           "description": "U-shape top loft framework with openable shutters"},
}

FIXED_ITEM_RATES = {
    "modular_wardrobe": {"label": "Modular wardrobe", "rate": 42000, "unit": "unit", "description": ""},
    "modular_kitchen_rft": {"label": "Modular kitchen", "rate": 1600, "unit": "running ft", "description": ""},
    "door_installation": {"label": "Door installation", "rate": 6500, "unit": "door", "description": ""},
    "window_installation": {"label": "Window installation", "rate": 4500, "unit": "window", "description": ""},
    "tv_unit": {"label": "TV unit", "rate": 25000, "unit": "unit", "description": ""},
    "study_table": {"label": "Study table", "rate": 18000, "unit": "unit", "description": ""},
    "electrical_point": {"label": "Electrical point (wiring + fitting)", "rate": 450, "unit": "point", "description": ""},
    "curtain_track": {"label": "Curtain track / pelmet", "rate": 900, "unit": "running ft", "description": ""},
    "kitchen_accessories": {"label": "Kitchen accessories", "rate": 40000, "unit": "fixed",
                             "description": "Innotech drawers, 1 wicker basket, Gola profiles and handles"},
    "utility_storage": {"label": "Utility storage", "rate": 20000, "unit": "fixed",
                         "description": "Utility area storage boxes and washbasin cabinet framing"},
}

DEFAULT_TAX_PERCENT = 18.0

MODULE_PRESETS = {
    "kitchen": {"label": "Kitchen", "default_items": ["false_ceiling", "wall_tiling", "electrical_point", "painting"]},
    "modular_kitchen": {"label": "Modular kitchen", "default_items": [
        "kitchen_base_cabinets", "kitchen_wall_cabinets", "kitchen_loft_unit",
        "kitchen_accessories", "utility_storage",
    ]},
    "bedroom": {"label": "Bedroom", "default_items": ["modular_wardrobe", "false_ceiling", "painting", "flooring_wood", "electrical_point"]},
    "living_room": {"label": "Living room", "default_items": ["tv_unit", "false_ceiling", "painting", "flooring_tile", "curtain_track", "electrical_point"]},
    "bathroom": {"label": "Bathroom", "default_items": ["wall_tiling", "flooring_tile", "electrical_point"]},
    "dining_room": {"label": "Dining room", "default_items": ["false_ceiling", "painting", "flooring_tile", "electrical_point"]},
    "study_room": {"label": "Study room", "default_items": ["study_table", "painting", "electrical_point"]},
    "pooja_room": {"label": "Pooja room", "default_items": ["wall_tiling", "false_ceiling", "electrical_point"]},
    "balcony": {"label": "Balcony", "default_items": ["flooring_tile", "painting"]},
    "utility_room": {"label": "Utility room", "default_items": ["wall_tiling", "flooring_tile", "electrical_point"]},
    "reception": {"label": "Reception / entrance", "default_items": ["flooring_tile", "false_ceiling", "painting", "electrical_point"]},
    "dining_area": {"label": "Dining area (commercial)", "default_items": ["flooring_tile", "false_ceiling", "wall_tiling", "electrical_point", "painting"]},
    "display_area": {"label": "Display / retail floor", "default_items": ["flooring_tile", "false_ceiling", "electrical_point", "painting"]},
    "storage_room": {"label": "Storage / back room", "default_items": ["flooring_tile", "electrical_point", "painting"]},
    "billing_counter": {"label": "Billing counter", "default_items": ["flooring_tile", "electrical_point"]},
    "custom": {"label": "Custom / blank module", "default_items": []},
}

# Property-type presets: a full property expands into several rooms at once.
# Each entry references a MODULE_PRESETS key for its default items, and gives
# a distinct name so multiple bedrooms/bathrooms are numbered sensibly.
PROPERTY_TYPE_PRESETS = {
    "1bhk": {"label": "1 BHK", "rooms": [
        {"module_key": "bedroom", "name": "Bedroom"},
        {"module_key": "modular_kitchen", "name": "Kitchen"},
        {"module_key": "living_room", "name": "Living Room"},
        {"module_key": "bathroom", "name": "Bathroom"},
    ]},
    "2bhk": {"label": "2 BHK", "rooms": [
        {"module_key": "bedroom", "name": "Bedroom 1"},
        {"module_key": "bedroom", "name": "Bedroom 2"},
        {"module_key": "modular_kitchen", "name": "Kitchen"},
        {"module_key": "living_room", "name": "Living Room"},
        {"module_key": "dining_room", "name": "Dining Room"},
        {"module_key": "bathroom", "name": "Bathroom 1"},
        {"module_key": "bathroom", "name": "Bathroom 2"},
    ]},
    "3bhk": {"label": "3 BHK", "rooms": [
        {"module_key": "bedroom", "name": "Bedroom 1"},
        {"module_key": "bedroom", "name": "Bedroom 2"},
        {"module_key": "bedroom", "name": "Bedroom 3"},
        {"module_key": "modular_kitchen", "name": "Kitchen"},
        {"module_key": "living_room", "name": "Living Room"},
        {"module_key": "dining_room", "name": "Dining Room"},
        {"module_key": "bathroom", "name": "Bathroom 1"},
        {"module_key": "bathroom", "name": "Bathroom 2"},
        {"module_key": "bathroom", "name": "Bathroom 3"},
        {"module_key": "utility_room", "name": "Utility"},
    ]},
    "4bhk": {"label": "4 BHK", "rooms": [
        {"module_key": "bedroom", "name": "Bedroom 1"},
        {"module_key": "bedroom", "name": "Bedroom 2"},
        {"module_key": "bedroom", "name": "Bedroom 3"},
        {"module_key": "bedroom", "name": "Bedroom 4"},
        {"module_key": "modular_kitchen", "name": "Kitchen"},
        {"module_key": "living_room", "name": "Living Room"},
        {"module_key": "dining_room", "name": "Dining Room"},
        {"module_key": "bathroom", "name": "Bathroom 1"},
        {"module_key": "bathroom", "name": "Bathroom 2"},
        {"module_key": "bathroom", "name": "Bathroom 3"},
        {"module_key": "bathroom", "name": "Bathroom 4"},
        {"module_key": "utility_room", "name": "Utility"},
    ]},
    "villa": {"label": "Villa", "rooms": [
        {"module_key": "bedroom", "name": "Master Bedroom"},
        {"module_key": "bedroom", "name": "Bedroom 2"},
        {"module_key": "bedroom", "name": "Bedroom 3"},
        {"module_key": "bedroom", "name": "Bedroom 4"},
        {"module_key": "modular_kitchen", "name": "Kitchen"},
        {"module_key": "living_room", "name": "Living Room"},
        {"module_key": "dining_room", "name": "Dining Room"},
        {"module_key": "bathroom", "name": "Bathroom 1"},
        {"module_key": "bathroom", "name": "Bathroom 2"},
        {"module_key": "bathroom", "name": "Bathroom 3"},
        {"module_key": "bathroom", "name": "Bathroom 4"},
        {"module_key": "balcony", "name": "Balcony"},
        {"module_key": "pooja_room", "name": "Pooja Room"},
        {"module_key": "utility_room", "name": "Utility"},
    ]},
    "restaurant": {"label": "Restaurant", "rooms": [
        {"module_key": "reception", "name": "Entrance / Reception"},
        {"module_key": "dining_area", "name": "Dining Area"},
        {"module_key": "kitchen", "name": "Kitchen"},
        {"module_key": "bathroom", "name": "Restroom"},
        {"module_key": "billing_counter", "name": "Billing Counter"},
    ]},
    "shop": {"label": "Shop / Retail", "rooms": [
        {"module_key": "reception", "name": "Entrance"},
        {"module_key": "display_area", "name": "Display Floor"},
        {"module_key": "billing_counter", "name": "Billing Counter"},
        {"module_key": "storage_room", "name": "Storage Room"},
    ]},
}


def get_catalog():
    return {
        "per_sqft": PER_SQFT_RATES,
        "fixed": FIXED_ITEM_RATES,
        "default_tax_percent": DEFAULT_TAX_PERCENT,
        "module_presets": MODULE_PRESETS,
        "property_type_presets": PROPERTY_TYPE_PRESETS,
        "units": list(UNIT_TO_FT.keys()),
    }


# ---- Catalog mutation (used by the Modules admin screen) ----

def upsert_item(kind: str, key: str, label: str, rate: float, unit: str, description: str = ""):
    table = PER_SQFT_RATES if kind == "per_sqft" else FIXED_ITEM_RATES
    table[key] = {"label": label, "rate": float(rate), "unit": unit, "description": description or ""}
    return table[key]


def delete_item(kind: str, key: str):
    table = PER_SQFT_RATES if kind == "per_sqft" else FIXED_ITEM_RATES
    table.pop(key, None)


def upsert_module_preset(key: str, label: str, default_items: list):
    MODULE_PRESETS[key] = {"label": label, "default_items": default_items}
    return MODULE_PRESETS[key]


def delete_module_preset(key: str):
    MODULE_PRESETS.pop(key, None)


def _rate_for(category: str):
    if category in PER_SQFT_RATES:
        return PER_SQFT_RATES[category], "per_sqft"
    if category in FIXED_ITEM_RATES:
        return FIXED_ITEM_RATES[category], "fixed"
    return None, None


def compute_quotation(rooms, discount_percent: float = 0.0, tax_percent: float = DEFAULT_TAX_PERCENT):
    """
    rooms: list of dicts, each:
      { "name": str, "length_ft": float, "width_ft": float,
        "length_unit": "ft"|"m"|"cm" (optional, default ft),
        "width_unit": "ft"|"m"|"cm" (optional, default ft),
        "items": [
          { "category": str, "quantity": float | None,
            "quantity_unit": "ft"|"m"|"cm" (optional, only meaningful for
            "running ft" categories -- converted to running ft before pricing) }
        ]}
    """
    room_results = []
    subtotal = 0.0

    for room in rooms:
        length_ft = convert_to_ft(room.get("length_ft", 0), room.get("length_unit", "ft"))
        width_ft = convert_to_ft(room.get("width_ft", 0), room.get("width_unit", "ft"))
        area = round(length_ft * width_ft, 2)
        line_items = []
        room_total = 0.0

        for item in room.get("items", []):
            category = item.get("category")
            catalog_entry, kind = _rate_for(category)
            if not catalog_entry:
                continue

            length = item.get("length")
            width = item.get("width")
            effective_rate = item.get("rate")
            effective_rate = float(effective_rate) if effective_rate not in (None, "") else catalog_entry["rate"]

            if length is not None and width is not None:
                # New model: every item carries its own L x W (width defaults
                # to 1 for plain count items, so area == length in that case).
                length_ft = convert_to_ft(length, item.get("length_unit", "ft"))
                width_ft = convert_to_ft(width, item.get("width_unit", "ft"))
                measure = round(length_ft * width_ft, 4)
            else:
                # Legacy fallback for older clients sending a bare quantity.
                quantity = item.get("quantity")
                if quantity is not None and catalog_entry["unit"] == "running ft":
                    quantity = convert_to_ft(quantity, item.get("quantity_unit", "ft"))
                if kind == "per_sqft" and (quantity is None or quantity == 0):
                    quantity = area
                measure = float(quantity or 0)

            amount = round(measure * effective_rate, 2)
            room_total += amount

            line_items.append({
                "category": category,
                "label": catalog_entry["label"],
                "description": catalog_entry.get("description", ""),
                "length": length,
                "length_unit": item.get("length_unit", "ft"),
                "width": width,
                "width_unit": item.get("width_unit", "ft"),
                "quantity": measure,
                "unit": catalog_entry["unit"],
                "rate": effective_rate,
                "amount": amount,
            })

        subtotal += room_total
        room_results.append({
            "name": room.get("name", "Room"),
            "length_ft": length_ft,
            "width_ft": width_ft,
            "area_sqft": area,
            "items": line_items,
            "room_total": round(room_total, 2),
        })

    discount_amount = round(subtotal * (discount_percent / 100.0), 2)
    taxable_amount = round(subtotal - discount_amount, 2)
    tax_amount = round(taxable_amount * (tax_percent / 100.0), 2)
    grand_total = round(taxable_amount + tax_amount, 2)

    return {
        "rooms": room_results,
        "subtotal": round(subtotal, 2),
        "discount_percent": discount_percent,
        "discount_amount": discount_amount,
        "tax_percent": tax_percent,
        "tax_amount": tax_amount,
        "grand_total": grand_total,
    }
