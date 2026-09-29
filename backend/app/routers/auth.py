from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from app.auth import CurrentUser
from app.database import SessionDep
from app.models import User, normalise_email
from app.security import create_access_token, hash_password, verify_password

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


class TokenOut(BaseModel):
    token: str
    user: UserOut


def _token_response(user: User) -> TokenOut:
    return TokenOut(
        token=create_access_token(user.id),
        user=UserOut(id=user.id, email=user.email, name=user.name),
    )


EMAIL_TAKEN = "An account with this email already exists. Sign in instead."


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(body: RegisterIn, session: SessionDep) -> TokenOut:
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


@router.post("/login")
def login(body: LoginIn, session: SessionDep) -> TokenOut:
    user = session.exec(select(User).where(User.email == normalise_email(body.email))).first()
    # Same message and same work whether the email or the password is wrong.
    if not verify_password(body.password, user.password_hash if user else None):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Email or password is incorrect")
    return _token_response(user)


@router.get("/me")
def me(user: CurrentUser) -> UserOut:
    return UserOut(id=user.id, email=user.email, name=user.name)
