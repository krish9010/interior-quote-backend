import os
import uuid
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()  # picks up backend/.env if present, before auth.py reads AZURE_* vars

from fastapi import Depends, FastAPI, HTTPException, Request, UploadFile, File, Response
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.models import (
    QuotationRequest, SuggestItemsRequest, ChatRequest, DesignConceptRequest,
    ClientUpsertRequest, CatalogItemUpsertRequest, ModulePresetUpsertRequest,
)
from app import pricing, auth, ai, store, clients as clients_module
from app import db as db_module

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
QUOTES_DIR = BASE_DIR / "quotes"
STATIC_DIR = BASE_DIR / "static"
UPLOAD_DIR.mkdir(exist_ok=True)
QUOTES_DIR.mkdir(exist_ok=True)

app = FastAPI(title="Interior Design Quotation API", version="1.0.0")

# Signs the session cookie that holds the logged-in user. MUST be overridden
# in production via the SESSION_SECRET env var -- see .env.example.
app.add_middleware(
    SessionMiddleware,
    secret_key=os.environ.get("SESSION_SECRET", "dev-secret-change-me"),
    same_site="lax",
)

# Allows the React Native app (a different origin) to call this API.
# Tighten allow_origins to your app's actual origin(s) in production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,  # mobile uses Bearer tokens, not cookies -- keep False with "*"
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory store of generated quotations, keyed by id -- used only as a
# fallback when SQL Server isn't configured; see app/store.py.
db_module.init_db()  # creates tables in SQL Server if configured; no-op otherwise


def _redirect_uri(request: Request) -> str:
    return str(request.base_url).rstrip("/") + auth.REDIRECT_PATH


# ---------- Auth ----------

@app.get("/auth/login", tags=["Auth"])
def login(request: Request):
    if not auth.sso_configured():
        raise HTTPException(status_code=500, detail="Azure AD is not configured. Set AZURE_CLIENT_ID / AZURE_CLIENT_SECRET / AZURE_TENANT_ID.")
    url = auth.build_auth_url(request, _redirect_uri(request))
    return RedirectResponse(url)


@app.get("/auth/callback", tags=["Auth"])
def callback(request: Request, code: str, state: str):
    auth.handle_callback(request, code, state, _redirect_uri(request))
    return RedirectResponse("/")


@app.get("/auth/logout", tags=["Auth"])
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(
        f"https://login.microsoftonline.com/{auth.TENANT_ID}/oauth2/v2.0/logout"
        f"?post_logout_redirect_uri={request.base_url}"
    )


@app.get("/auth/me", tags=["Auth"])
def me(request: Request):
    return {"user": request.session.get("user"), "sso_configured": auth.sso_configured()}


@app.post("/api/mobile/token-exchange", tags=["Auth"])
def mobile_token_exchange(body: dict):
    """
    Mobile app POSTs the Microsoft access token it obtained itself (via
    expo-auth-session's PKCE flow against Azure AD). We verify it against
    Graph and hand back our own signed app token for the app to use as a
    Bearer header from then on.
    Body: {"access_token": "<microsoft access token>"}
    """
    access_token = body.get("access_token")
    if not access_token:
        raise HTTPException(status_code=400, detail="access_token is required")
    try:
        user = auth.fetch_profile(access_token)
    except Exception:
        raise HTTPException(status_code=401, detail="Could not verify Microsoft access token")

    from app import mobile_auth
    app_token = mobile_auth.issue_token(user)
    return {"token": app_token, "user": user}


@app.post("/api/mobile/dev-login", tags=["Auth"])
def mobile_dev_login(body: dict):
    """
    TEMPORARY: issues a signed app token WITHOUT going through Microsoft at
    all. Only for testing the app while Azure AD setup is blocked.
    Only works when ALLOW_DEV_LOGIN=true is set in backend/.env -- remove
    that env var (or delete this endpoint) once real Microsoft sign-in is
    working, so nobody can log in without a real Microsoft account.
    Body: {"email": "...", "name": "..."}
    """
    if os.environ.get("ALLOW_DEV_LOGIN", "false").lower() != "true":
        raise HTTPException(status_code=404, detail="Not found")

    email = (body.get("email") or "").lower().strip()
    name = body.get("name") or email
    if not email:
        raise HTTPException(status_code=400, detail="email is required")

    user = {"email": email, "name": name, "role": auth.get_role(email)}
    from app import mobile_auth
    app_token = mobile_auth.issue_token(user)
    return {"token": app_token, "user": user}


# ---------- Catalog ----------

@app.get("/api/catalog", tags=["Catalog"])
def get_catalog(user: dict = Depends(auth.get_current_user)):
    """Return the pricing catalog (per-sq.ft rates, fixed item rates, module presets)."""
    return pricing.get_catalog()


# ---------- Floorplan ----------

@app.post("/api/floorplan/upload", tags=["Floorplan"])
async def upload_floorplan(file: UploadFile = File(...), user: dict = Depends(auth.require_staff)):
    """
    Upload a floor plan image or PDF as a reference attached to a quotation.
    Staff only. Note: this does NOT auto-extract room dimensions from the
    file -- measurements still need to be entered in the form.
    """
    allowed = {".png", ".jpg", ".jpeg", ".pdf", ".webp"}
    ext = Path(file.filename or "").suffix.lower()
    if ext not in allowed:
        raise HTTPException(status_code=400, detail=f"Unsupported file type '{ext}'. Allowed: {sorted(allowed)}")

    file_id = str(uuid.uuid4())
    dest = UPLOAD_DIR / f"{file_id}{ext}"
    content = await file.read()
    dest.write_bytes(content)

    return {"file_id": file_id, "filename": file.filename, "stored_as": dest.name}


# ---------- Quotation ----------

@app.post("/api/quotation", tags=["Quotation"])
def create_quotation(request: QuotationRequest, user: dict = Depends(auth.require_staff)):
    """Compute a quotation from client info + room measurements + selected work items. Staff only."""
    rooms = [r.model_dump() for r in request.rooms]
    result = pricing.compute_quotation(
        rooms=rooms,
        discount_percent=request.discount_percent,
        tax_percent=request.tax_percent,
    )

    client = request.client.model_dump()
    if client.get("email"):
        clients_module.upsert_client(client["email"], name=client.get("name"),
                                      phone=client.get("phone"), address=client.get("address"))

    return store.save_quotation(
        client=client,
        rooms_result=result["rooms"],
        notes=request.notes,
        floorplan_file_id=request.floorplan_file_id,
        discount_percent=result["discount_percent"],
        tax_percent=result["tax_percent"],
        subtotal=result["subtotal"],
        discount_amount=result["discount_amount"],
        tax_amount=result["tax_amount"],
        grand_total=result["grand_total"],
        created_by=user["email"],
    )


@app.put("/api/quotation/{quotation_id}", tags=["Quotation"])
def edit_quotation(quotation_id: str, request: QuotationRequest, user: dict = Depends(auth.require_staff)):
    """Edit and recompute an existing quotation. Staff only."""
    existing = store.get_quotation(quotation_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Quotation not found")

    rooms = [r.model_dump() for r in request.rooms]
    result = pricing.compute_quotation(
        rooms=rooms, discount_percent=request.discount_percent, tax_percent=request.tax_percent,
    )
    client = request.client.model_dump()
    if client.get("email"):
        clients_module.upsert_client(client["email"], name=client.get("name"),
                                      phone=client.get("phone"), address=client.get("address"))

    updated = store.update_quotation(
        quotation_id, client=client, rooms_result=result["rooms"],
        notes=request.notes, floorplan_file_id=request.floorplan_file_id,
        discount_percent=result["discount_percent"], tax_percent=result["tax_percent"],
        subtotal=result["subtotal"], discount_amount=result["discount_amount"],
        tax_amount=result["tax_amount"], grand_total=result["grand_total"],
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Quotation not found")
    return updated


def _authorize_view(quotation: dict, user: dict):
    if user["role"] == "staff":
        return
    client_email = (quotation.get("client") or {}).get("email") or ""
    if client_email.lower() != user["email"].lower():
        raise HTTPException(status_code=403, detail="You can only view your own quotation")


@app.get("/api/quotations", tags=["Quotation"])
def list_quotations(user: dict = Depends(auth.require_staff)):
    """List every quotation. Staff only."""
    return store.list_all()


@app.get("/api/quotations/by-client", tags=["Quotation"])
def list_quotations_by_client(user: dict = Depends(auth.require_staff)):
    """List all quotations grouped by client. Staff only."""
    return store.list_grouped_by_client()


@app.get("/api/my-quotations", tags=["Quotation"])
def my_quotations(user: dict = Depends(auth.get_current_user)):
    """List quotations belonging to the signed-in client (matched by email)."""
    if user["role"] == "staff":
        return store.list_all()
    return store.list_by_client_email(user["email"])


@app.get("/api/quotation/{quotation_id}", tags=["Quotation"])
def get_quotation(quotation_id: str, user: dict = Depends(auth.get_current_user)):
    q = store.get_quotation(quotation_id)
    if not q:
        raise HTTPException(status_code=404, detail="Quotation not found")
    _authorize_view(q, user)
    return q


@app.get("/api/quotation/{quotation_id}/pdf", tags=["Quotation"])
def quotation_pdf(quotation_id: str, user: dict = Depends(auth.get_current_user)):
    q = store.get_quotation(quotation_id)
    if not q:
        raise HTTPException(status_code=404, detail="Quotation not found")
    _authorize_view(q, user)

    from app.pdf_export import build_quotation_pdf
    pdf_path = QUOTES_DIR / f"{quotation_id}.pdf"
    build_quotation_pdf(q, pdf_path)

    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=f"quotation-{quotation_id[:8]}.pdf",
    )


@app.delete("/api/quotation/{quotation_id}", tags=["Quotation"])
def delete_quotation(quotation_id: str, user: dict = Depends(auth.require_staff)):
    """Delete a quotation. Staff only."""
    deleted = store.delete_quotation(quotation_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Quotation not found")
    return {"deleted": quotation_id}


# ---------- AI features (Claude) ----------

@app.get("/api/ai/status", tags=["AI"])
def ai_status(user: dict = Depends(auth.get_current_user)):
    return {"ai_configured": ai.ai_configured()}


@app.post("/api/ai/suggest-items", tags=["AI"])
def ai_suggest_items(request: SuggestItemsRequest, user: dict = Depends(auth.require_staff)):
    """Suggest catalog item categories for a free-text room description. Staff only."""
    try:
        return ai.suggest_items(request.description, pricing.get_catalog())
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception:
        raise HTTPException(status_code=502, detail="AI suggestion failed. Try again or add items manually.")


@app.post("/api/ai/design-concept", tags=["AI"])
def ai_design_concept(request: DesignConceptRequest, user: dict = Depends(auth.require_staff)):
    """Written design-concept description (palette/materials/mood) for a room. Staff only."""
    try:
        text = ai.design_concept(request.description, request.budget_hint or "")
        return {"concept": text}
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception:
        raise HTTPException(status_code=502, detail="AI generation failed. Try again.")


@app.post("/api/floorplan/extract", tags=["Floorplan"])
async def ai_extract_floorplan(file: UploadFile = File(...), user: dict = Depends(auth.require_staff)):
    """Best-effort read of room names/dimensions off an uploaded floor plan image. Staff only."""
    media_types = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}
    ext = Path(file.filename or "").suffix.lower()
    if ext not in media_types:
        raise HTTPException(status_code=400, detail="Extraction supports image files (png/jpg/webp) only, not PDF.")

    content = await file.read()
    try:
        return ai.extract_floorplan(content, media_types[ext], pricing.get_catalog())
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception:
        raise HTTPException(status_code=502, detail="Couldn't read the floor plan. Enter measurements manually.")


@app.get("/api/quotation/{quotation_id}/proposal", tags=["AI"])
def ai_proposal(quotation_id: str, user: dict = Depends(auth.get_current_user)):
    """AI-written client-friendly cover note for a quotation."""
    q = store.get_quotation(quotation_id)
    if not q:
        raise HTTPException(status_code=404, detail="Quotation not found")
    _authorize_view(q, user)
    try:
        return {"proposal": ai.write_proposal(q)}
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception:
        raise HTTPException(status_code=502, detail="AI generation failed. Try again.")


@app.post("/api/quotation/{quotation_id}/chat", tags=["AI"])
def ai_chat(quotation_id: str, request: ChatRequest, user: dict = Depends(auth.get_current_user)):
    """Client (or staff) asks a question about a specific quotation, answered grounded in its data."""
    q = store.get_quotation(quotation_id)
    if not q:
        raise HTTPException(status_code=404, detail="Quotation not found")
    _authorize_view(q, user)
    try:
        return {"answer": ai.chat_about_quotation(q, request.question)}
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception:
        raise HTTPException(status_code=502, detail="AI chat failed. Try again.")


# ---------- Clients ----------

@app.get("/api/clients", tags=["Clients"])
def list_clients_endpoint(user: dict = Depends(auth.require_staff)):
    """List all known clients. Staff only."""
    return clients_module.list_clients()


@app.get("/api/clients/{email}", tags=["Clients"])
def get_client_endpoint(email: str, user: dict = Depends(auth.get_current_user)):
    """Get one client's details (used to show their logo on a quotation). Any signed-in user."""
    client = clients_module.get_client(email)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return client


@app.post("/api/clients", tags=["Clients"])
def upsert_client_endpoint(request: ClientUpsertRequest, user: dict = Depends(auth.require_staff)):
    """Create or update a client's details. Staff only."""
    return clients_module.upsert_client(
        request.email, name=request.name, phone=request.phone, address=request.address,
    )


@app.delete("/api/clients/{email}", tags=["Clients"])
def delete_client_endpoint(email: str, user: dict = Depends(auth.require_staff)):
    """Delete a client record. Staff only. Does not delete their past quotations."""
    deleted = clients_module.delete_client(email)
    if not deleted:
        raise HTTPException(status_code=404, detail="Client not found")
    return {"deleted": email}


@app.post("/api/clients/{email}/logo", tags=["Clients"])
async def upload_client_logo(email: str, file: UploadFile = File(...), user: dict = Depends(auth.require_staff)):
    """Upload a logo image for a client. Staff only. Stored in the database (not local
    disk) so it survives restarts/redeploys."""
    allowed = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}
    ext = Path(file.filename or "").suffix.lower()
    if ext not in allowed:
        raise HTTPException(status_code=400, detail=f"Unsupported file type '{ext}'. Allowed: {sorted(allowed)}")

    content = await file.read()
    max_size = 2 * 1024 * 1024  # 2MB -- generous for a logo, keeps DB rows small
    if len(content) > max_size:
        raise HTTPException(status_code=400, detail="Logo too large. Please use an image under 2MB.")

    client = clients_module.upsert_client(email, logo_bytes=content, logo_mimetype=allowed[ext])
    return {"client": client}


@app.get("/api/clients/{email}/logo", tags=["Clients"])
def get_client_logo(email: str):
    """Public: serves a client's logo image by email."""
    result = clients_module.get_client_logo_bytes(email)
    if not result:
        raise HTTPException(status_code=404, detail="No logo for this client")
    content, mimetype = result
    return Response(content=content, media_type=mimetype)


@app.get("/api/logo/{filename}", tags=["Clients"])
def get_logo_legacy(filename: str):
    """Deprecated: old disk-based logo serving, kept only so any already-shared
    links don't hard-crash. New uploads use GET /api/clients/{email}/logo instead."""
    path = UPLOAD_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="Logo not found")
    return FileResponse(path)


# ---------- Catalog management (Modules screen) ----------

@app.post("/api/catalog/item", tags=["Catalog"])
def upsert_catalog_item(request: CatalogItemUpsertRequest, user: dict = Depends(auth.require_staff)):
    """Add or update a per-sq.ft or fixed catalog item. Staff only."""
    if request.kind not in ("per_sqft", "fixed"):
        raise HTTPException(status_code=400, detail="kind must be 'per_sqft' or 'fixed'")
    return pricing.upsert_item(request.kind, request.key, request.label, request.rate, request.unit, request.description)


@app.delete("/api/catalog/item/{kind}/{key}", tags=["Catalog"])
def delete_catalog_item(kind: str, key: str, user: dict = Depends(auth.require_staff)):
    """Remove a catalog item. Staff only."""
    pricing.delete_item(kind, key)
    return {"deleted": key}


@app.post("/api/catalog/module-preset", tags=["Catalog"])
def upsert_module_preset(request: ModulePresetUpsertRequest, user: dict = Depends(auth.require_staff)):
    """Add or update a module preset (e.g. Kitchen, Bedroom) and its default items. Staff only."""
    return pricing.upsert_module_preset(request.key, request.label, request.default_items)


@app.delete("/api/catalog/module-preset/{key}", tags=["Catalog"])
def delete_module_preset(key: str, user: dict = Depends(auth.require_staff)):
    """Remove a module preset. Staff only."""
    pricing.delete_module_preset(key)
    return {"deleted": key}


# Serve the frontend (index.html + assets) at the root
if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
