"""
Microsoft Azure AD (Entra ID) single sign-on.

Auth flow (OAuth2 authorization code, via MSAL):
1. GET /auth/login        -> redirects the browser to Microsoft's sign-in page
2. User signs in with their Microsoft account
3. GET /auth/callback     -> Microsoft redirects back with a code; we exchange
                             it for tokens and fetch the user's profile
4. We store {email, name, role} in a signed session cookie
5. GET /auth/me           -> frontend calls this to check who's logged in
6. GET /auth/logout       -> clears the session

Roles:
- "staff"  -> anyone whose email is in STAFF_EMAILS (see .env). Full access:
              create quotations, view/edit all of them.
- "client" -> everyone else who successfully signs in. Read-only access to
              quotations where quotation.client.email matches their own email.

STAFF_EMAILS is a simple allowlist, which is fine to start with. For a larger
team, switch to checking Azure AD App Roles or Group claims in the ID token
instead of hardcoding emails — see the README for how to set that up.
"""
import os
import uuid

import httpx
import msal
from fastapi import Depends, HTTPException, Request

CLIENT_ID = os.environ.get("AZURE_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("AZURE_CLIENT_SECRET", "")
TENANT_ID = os.environ.get("AZURE_TENANT_ID", "common")
REDIRECT_PATH = "/auth/callback"
SCOPE = ["User.Read"]
AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"

STAFF_EMAILS = {
    e.strip().lower()
    for e in os.environ.get("STAFF_EMAILS", "").split(",")
    if e.strip()
}


def sso_configured() -> bool:
    return bool(CLIENT_ID and CLIENT_SECRET)


def _msal_app():
    return msal.ConfidentialClientApplication(
        CLIENT_ID, authority=AUTHORITY, client_credential=CLIENT_SECRET
    )


def get_role(email: str) -> str:
    return "staff" if email.lower() in STAFF_EMAILS else "client"


def build_auth_url(request: Request, redirect_uri: str) -> str:
    state = str(uuid.uuid4())
    request.session["auth_state"] = state
    return _msal_app().get_authorization_request_url(
        SCOPE, state=state, redirect_uri=redirect_uri
    )


def fetch_profile(access_token: str) -> dict:
    """Fetch the signed-in user's profile from Microsoft Graph and resolve their role."""
    resp = httpx.get(
        "https://graph.microsoft.com/v1.0/me",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10,
    )
    resp.raise_for_status()
    profile = resp.json()

    email = (profile.get("mail") or profile.get("userPrincipalName") or "").lower()
    name = profile.get("displayName", email)
    return {"email": email, "name": name, "role": get_role(email)}


def handle_callback(request: Request, code: str, state: str, redirect_uri: str) -> dict:
    if state != request.session.get("auth_state"):
        raise HTTPException(status_code=400, detail="Invalid auth state")

    result = _msal_app().acquire_token_by_authorization_code(
        code, scopes=SCOPE, redirect_uri=redirect_uri
    )
    if "access_token" not in result:
        raise HTTPException(status_code=400, detail=result.get("error_description", "Sign-in failed"))

    user = fetch_profile(result["access_token"])
    request.session["user"] = user
    return user


def get_current_user(request: Request) -> dict:
    # Web: session cookie
    user = request.session.get("user")
    if user:
        return user

    # Mobile: Authorization: Bearer <token> issued by /api/mobile/token-exchange
    auth_header = request.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        from app import mobile_auth
        token = auth_header[7:].strip()
        user = mobile_auth.verify_token(token)
        if user:
            return user

    raise HTTPException(status_code=401, detail="Not signed in")


def require_staff(user: dict = Depends(get_current_user)) -> dict:
    if user["role"] != "staff":
        raise HTTPException(status_code=403, detail="Staff access only")
    return user
