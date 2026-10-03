import hashlib
import secrets
from datetime import timedelta

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from app.auth import DISABLED, CurrentUser, is_admin
from app.config import get_settings
from app.database import SessionDep
from app.models import PasswordReset, User, normalise_email, utcnow
from app.security import create_access_token, hash_password, verify_password
from app.services import rate_limit
from app.services.google_auth import GoogleTokenError, verify_id_token
from app.services.mailer import MailError, send_email

router = APIRouter(prefix="/auth", tags=["auth"])

PASSWORD_MIN = 8
PASSWORD_MAX = 128  # argon2 would take more; the cap stops a megabyte "password"


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=PASSWORD_MIN, max_length=PASSWORD_MAX)
    name: str = Field(min_length=1, max_length=120)

    @field_validator("name")
    @classmethod
    def _strip_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Name can't be empty")
        return v


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(max_length=PASSWORD_MAX)


class UserOut(BaseModel):
    id: int
    email: str
    name: str
    # Shows the admin panel's link; the admin endpoints check for themselves.
    is_admin: bool = False


def _user_out(user: User) -> UserOut:
    return UserOut(id=user.id, email=user.email, name=user.name, is_admin=is_admin(user))


class TokenOut(BaseModel):
    token: str
    user: UserOut


def _token_response(user: User) -> TokenOut:
    if user.disabled_at is not None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, DISABLED)
    return TokenOut(token=create_access_token(user.id, user.token_version), user=_user_out(user))


EMAIL_TAKEN = "An account with this email already exists. Sign in instead."


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(body: RegisterIn, request: Request, session: SessionDep) -> TokenOut:
    ip = rate_limit.client_ip(request)
    rate_limit.check(
        session,
        "register:ip",
        ip,
        limit=10,
        within=timedelta(hours=1),
        message="Too many sign-ups from here. Please try again in an hour.",
    )
    rate_limit.record(session, "register:ip", ip)
    email = normalise_email(body.email)
    if session.exec(select(User).where(User.email == email)).first():
        raise HTTPException(status.HTTP_409_CONFLICT, EMAIL_TAKEN)

    user = User(email=email, name=body.name, password_hash=hash_password(body.password))
    session.add(user)
    try:
        session.commit()
    except IntegrityError:  # two sign-ups for the same email at once
        session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, EMAIL_TAKEN) from None
    session.refresh(user)
    return _token_response(user)


TOO_MANY_LOGINS = "Too many sign-in attempts. Please wait 15 minutes and try again."


@router.post("/login")
def login(body: LoginIn, request: Request, session: SessionDep) -> TokenOut:
    email = normalise_email(body.email)
    ip = rate_limit.client_ip(request)
    # Per account (someone guessing one person's password) and per IP (one source
    # trying many accounts). Only failures count, so a person signing in often is fine.
    window = timedelta(minutes=15)
    rate_limit.check(session, "login_failed:email", email, 10, window, TOO_MANY_LOGINS)
    rate_limit.check(session, "login_failed:ip", ip, 50, window, TOO_MANY_LOGINS)

    user = session.exec(select(User).where(User.email == email)).first()
    # Same message and same work whether the email or the password is wrong.
    if not verify_password(body.password, user.password_hash if user else None):
        rate_limit.record(session, "login_failed:email", email)
        rate_limit.record(session, "login_failed:ip", ip)
        if user and user.password_hash is None:
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED,
                "This account signs in with Google. Use “Continue with Google”, or set a "
                "password with “Forgot password”.",
            )
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Email or password is incorrect")
    return _token_response(user)


# --- Sign in with Google -----------------------------------------------------------------


class GoogleIn(BaseModel):
    # The ID token Google Identity Services gave the browser.
    credential: str = Field(min_length=20, max_length=8192)


GOOGLE_FAILED = "Signing in with Google didn't work. Please try again."


@router.post("/google")
def google_sign_in(body: GoogleIn, request: Request, session: SessionDep) -> TokenOut:
    """Sign in, link, or sign up with a Google ID token.

    - An account already linked to this Google account (by Google's stable `sub`): in.
    - Else an account with the same email: linked, and in. If that address had never
      been verified, whoever set its password may not own the inbox (anyone can sign
      up with any address), so the password is removed and other sessions are signed
      out; the owner can set a new one with "Forgot password".
    - Else a new account, with no password.
    """
    ip = rate_limit.client_ip(request)
    window = timedelta(minutes=15)
    rate_limit.check(session, "google_failed:ip", ip, 30, window, TOO_MANY_LOGINS)
    try:
        identity = verify_id_token(body.credential, get_settings().google_client_id)
    except GoogleTokenError:
        rate_limit.record(session, "google_failed:ip", ip)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, GOOGLE_FAILED) from None

    user = session.exec(select(User).where(User.google_sub == identity.sub)).first()
    if user is None:
        email = normalise_email(identity.email)
        user = session.exec(select(User).where(User.email == email)).first()
        now = utcnow()
        if user is None:
            user = User(
                email=email,
                name=identity.name or email.split("@")[0],
                password_hash=None,
                google_sub=identity.sub,
                email_verified_at=now,
            )
        else:
            if user.google_sub is not None:  # linked to a different Google account
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    "This email is already linked to a different Google account.",
                )
            if user.email_verified_at is None and user.password_hash is not None:
                user.password_hash = None
                user.token_version += 1
            user.google_sub = identity.sub
            user.email_verified_at = now
        session.add(user)
        try:
            session.commit()
        except IntegrityError:  # the same person, twice at once
            session.rollback()
            user = session.exec(select(User).where(User.google_sub == identity.sub)).first()
            if user is None:
                raise HTTPException(status.HTTP_409_CONFLICT, GOOGLE_FAILED) from None
        session.refresh(user)
    return _token_response(user)


@router.get("/me")
def me(user: CurrentUser) -> UserOut:
    return _user_out(user)


# --- password reset --------------------------------------------------------------------

RESET_VALID_FOR = timedelta(hours=1)


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class ResetRequestIn(BaseModel):
    email: EmailStr


class ResetConfirmIn(BaseModel):
    token: str = Field(min_length=20, max_length=200)
    password: str = Field(min_length=PASSWORD_MIN, max_length=PASSWORD_MAX)


@router.post("/password-reset", status_code=status.HTTP_202_ACCEPTED)
def request_reset(body: ResetRequestIn, request: Request, session: SessionDep) -> dict:
    """Email a reset link. Answers the same whether or not the account exists, so this
    can't be used to find out who has one."""
    email = normalise_email(body.email)
    ip = rate_limit.client_ip(request)
    rate_limit.check(
        session,
        "reset:email",
        email,
        3,
        timedelta(hours=1),
        "We've already sent a few reset emails. Check your inbox, or try again in an hour.",
    )
    rate_limit.check(
        session,
        "reset:ip",
        ip,
        20,
        timedelta(hours=1),
        "Too many reset requests from here. Please try again in an hour.",
    )
    rate_limit.record(session, "reset:email", email)
    rate_limit.record(session, "reset:ip", ip)

    user = session.exec(select(User).where(User.email == email)).first()
    if user is not None:
        token = secrets.token_urlsafe(32)
        session.add(
            PasswordReset(
                user_id=user.id, token_hash=_hash(token), expires_at=utcnow() + RESET_VALID_FOR
            )
        )
        session.commit()
        settings = get_settings()
        link = f"{settings.web_url.rstrip('/')}/reset-password?token={token}"
        try:
            send_email(
                user.email,
                f"Reset your {settings.app_name} password",
                f"Hi {user.name},\n\n"
                f"Someone (hopefully you) asked to reset your {settings.app_name} password.\n"
                f"Choose a new one here — the link works for an hour, once:\n\n{link}\n\n"
                "If it wasn't you, ignore this email; your password hasn't changed.\n",
            )
        except MailError as exc:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from None
    return {"detail": "If that email has an account, a reset link is on its way."}


@router.post("/password-reset/confirm")
def confirm_reset(body: ResetConfirmIn, session: SessionDep) -> TokenOut:
    reset = session.exec(
        select(PasswordReset).where(PasswordReset.token_hash == _hash(body.token))
    ).first()
    if reset is None or reset.used_at is not None or reset.expires_at < utcnow():
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "This reset link has expired or was already used. Ask for a new one.",
        )
    user = session.get(User, reset.user_id)
    now = utcnow()
    user.password_hash = hash_password(body.password)
    # Using the emailed link shows the inbox is theirs.
    user.email_verified_at = user.email_verified_at or now
    # Sign out every existing session: whoever had the old password shouldn't keep in.
    user.token_version += 1
    reset.used_at = now
    # Any other outstanding links for this account stop working too.
    for other in session.exec(
        select(PasswordReset).where(
            PasswordReset.user_id == user.id, PasswordReset.used_at.is_(None)
        )
    ).all():
        other.used_at = now
        session.add(other)
    session.add(user)
    session.add(reset)
    session.commit()
    session.refresh(user)
    return _token_response(user)
