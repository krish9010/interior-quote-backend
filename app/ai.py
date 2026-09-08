"""
Claude (Anthropic API) integration.

Requires ANTHROPIC_API_KEY to be set (see .env.example). Get a key at
https://console.anthropic.com/settings/keys

Five features, four backed directly by Claude:
1. suggest_items()          -> text description -> suggested catalog items
2. write_proposal()         -> quotation data -> client-friendly cover note
3. chat_about_quotation()   -> client question + quotation data -> answer
4. extract_floorplan()      -> floor plan image -> suggested room list/dimensions
5. design_concept()         -> NOT image generation (see note below) -> a
   written design-concept description usable as an image-gen prompt elsewhere

Note on #5: the Claude API does not generate images. "Design mood board /
concept image" is implemented here as a detailed written concept (materials,
palette, layout mood) that a designer can act on directly, or feed into a
separate image-generation tool (e.g. Midjourney, DALL-E, Stable Diffusion) if
you want an actual rendered image. Wiring up one of those is a separate,
small integration if you want it — happy to add it.
"""
import base64
import json
import os

import anthropic

MODEL = "claude-sonnet-5"

_client = None


def _get_client():
    global _client
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    if _client is None:
        _client = anthropic.Anthropic(api_key=api_key)
    return _client


def ai_configured() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def _require_client():
    client = _get_client()
    if not client:
        raise RuntimeError("ANTHROPIC_API_KEY is not set. Add it to backend/.env")
    return client


def suggest_items(description: str, catalog: dict) -> dict:
    """Given a free-text room description, suggest catalog item categories."""
    client = _require_client()
    valid_categories = list(catalog["per_sqft"].keys()) + list(catalog["fixed"].keys())

    prompt = f"""A client described a room like this: "{description}"

Available item categories (choose only from this exact list): {valid_categories}

Return ONLY a JSON object, no other text, in this shape:
{{"suggested_categories": ["category_key", ...], "reasoning": "one short sentence"}}"""

    resp = client.messages.create(
        model=MODEL,
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}],
    )
    return _parse_json(resp.content[0].text)


def write_proposal(quotation: dict) -> str:
    """Generate a short, client-friendly cover note / proposal summary for a quotation."""
    client = _require_client()
    summary = {
        "client_name": quotation.get("client", {}).get("name"),
        "rooms": [{"name": r["name"], "area_sqft": r["area_sqft"],
                   "items": [i["label"] for i in r["items"]]} for r in quotation["rooms"]],
        "grand_total": quotation["grand_total"],
    }
    prompt = f"""Write a short, warm, professional cover note (120-180 words) for an
interior design quotation, based on this data:

{json.dumps(summary, indent=2)}

Address the client by name. Mention the rooms/modules covered at a high level
(don't list every line item). End with a brief note that the detailed
breakdown follows below. Return plain text only, no markdown headers."""

    resp = client.messages.create(
        model=MODEL,
        max_tokens=400,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.content[0].text.strip()


def chat_about_quotation(quotation: dict, question: str) -> str:
    """Answer a client's question about their own quotation, grounded in its actual data."""
    client = _require_client()
    prompt = f"""You are answering a client's question about their interior design
quotation. Use ONLY the data below — don't invent prices or items that
aren't listed. If the question can't be answered from this data, say so.

Quotation data:
{json.dumps(quotation, indent=2)}

Client question: {question}

Answer in 2-4 sentences, plain text, friendly and direct."""

    resp = client.messages.create(
        model=MODEL,
        max_tokens=400,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.content[0].text.strip()


def extract_floorplan(image_bytes: bytes, media_type: str, catalog: dict) -> dict:
    """
    Look at a floor plan image and suggest a room list with dimensions.
    This is a best-effort read of labeled dimensions/scale on the plan, not a
    guarantee — always shown to the user to review/correct before submitting.
    """
    client = _require_client()
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    module_keys = list(catalog.get("module_presets", {}).keys())

    prompt = f"""This is a floor plan image. Identify each labeled room and its
dimensions if they're written on the plan (e.g. "12' x 10'", or a scale bar
you can use to estimate). If a room's dimensions aren't legible or given,
omit that room rather than guessing.

Match each room to the closest module key from this list where possible:
{module_keys}. If none fit well, use "custom".

Return ONLY a JSON object, no other text:
{{"rooms": [{{"name": "...", "length_ft": 0.0, "width_ft": 0.0, "module_key": "..."}}],
 "notes": "one short sentence on anything you couldn't read confidently"}}"""

    resp = client.messages.create(
        model=MODEL,
        max_tokens=1000,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": b64}},
                {"type": "text", "text": prompt},
            ],
        }],
    )
    return _parse_json(resp.content[0].text)


def design_concept(description: str, budget_hint: str = "") -> str:
    """
    Written design-concept description (palette, materials, mood, layout ideas)
    for a room. This is text, not an image — see module docstring.
    """
    client = _require_client()
    prompt = f"""A client wants design ideas for: "{description}"
{f"Budget context: {budget_hint}" if budget_hint else ""}

Write a short design concept (150-200 words): suggested color palette,
materials/finishes, furniture style, and lighting mood. Plain text, no
markdown headers. This will be read directly by the client or used as a
prompt for a separate image-generation tool."""

    resp = client.messages.create(
        model=MODEL,
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.content[0].text.strip()


def _parse_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text.strip())
