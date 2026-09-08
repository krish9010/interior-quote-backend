"""
Mobile auth: issues a signed, expiring token the React Native app stores and
sends as `Authorization: Bearer <token>`, as an alternative to the browser
session cookie used by the web app.

Flow:
1. The mobile app runs the Azure AD PKCE flow itself (via expo-auth-session),
   talking directly to Microsoft -- no client secret needed on-device.
2. It POSTs the resulting Microsoft access token to /api/mobile/token-exchange.
3. The backend verifies that token against Microsoft Graph (same check used
   for the web flow), then issues its OWN signed token via issue_token()
   below. The app stores this token and sends it as a Bearer header on every
   request after that.

This keeps a single source of truth for "who is this user / what's their
role" (STAFF_EMAILS, same as the web flow) while giving mobile a stateless,
cookie-free credential.
"""
import json
import os
import time

from itsdangerous import BadSignature, SignatureExpired, TimestampSigner

TOKEN_MAX_AGE_SECONDS = 60 * 60 * 24 * 14  # 14 days


def _signer() -> TimestampSigner:
    secret = os.environ.get("SESSION_SECRET", "dev-secret-change-me")
    return TimestampSigner(secret, salt="mobile-token")


def issue_token(user: dict) -> str:
    payload = json.dumps(user, separators=(",", ":"))
    return _signer().sign(payload.encode("utf-8")).decode("utf-8")


def verify_token(token: str) -> dict | None:
    try:
        payload = _signer().unsign(token, max_age=TOKEN_MAX_AGE_SECONDS)
        return json.loads(payload)
    except (BadSignature, SignatureExpired, ValueError):
        return None
