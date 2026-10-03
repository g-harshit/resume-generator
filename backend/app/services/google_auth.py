"""Checking a "Sign in with Google" ID token.

The browser gets the token from Google (Google Identity Services) and hands it to us.
It's a JWT signed by Google; we check the signature against Google's published keys,
that it was issued for our client ID, by Google, and hasn't expired, and that Google
has verified the email address. Only then do we trust who it says the person is.
"""

from dataclasses import dataclass
from functools import cache

import jwt

GOOGLE_CERTS = "https://www.googleapis.com/oauth2/v3/certs"
GOOGLE_ISSUERS = ("accounts.google.com", "https://accounts.google.com")


class GoogleTokenError(Exception):
    """The token can't be trusted. Shown to the user only as a generic failure."""


@dataclass
class GoogleIdentity:
    sub: str
    email: str
    name: str


@cache
def _keys() -> jwt.PyJWKClient:
    # Fetched once, then cached by key id (Google rotates keys every few weeks; an
    # unknown kid makes the client fetch again).
    return jwt.PyJWKClient(GOOGLE_CERTS, cache_keys=True, lifespan=6 * 3600)


def _signing_key(token: str):
    return _keys().get_signing_key_from_jwt(token).key


def verify_id_token(token: str, client_id: str) -> GoogleIdentity:
    if not client_id:
        raise GoogleTokenError("Google sign-in isn't set up")
    try:
        claims = jwt.decode(
            token,
            _signing_key(token),
            algorithms=["RS256"],
            audience=client_id,
            options={"require": ["exp", "iat", "iss", "aud", "sub"]},
            leeway=30,
        )
    except (jwt.PyJWTError, ValueError) as exc:
        raise GoogleTokenError(f"invalid token: {exc}") from None
    if claims.get("iss") not in GOOGLE_ISSUERS:
        raise GoogleTokenError("not issued by Google")
    email = (claims.get("email") or "").strip()
    if not email or claims.get("email_verified") is not True:
        raise GoogleTokenError("Google hasn't verified this email address")
    name = (claims.get("name") or claims.get("given_name") or email.split("@")[0]).strip()
    return GoogleIdentity(sub=str(claims["sub"]), email=email, name=name[:120])
