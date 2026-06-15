from pydantic import (
    BaseModel,
    EmailStr,
    field_validator,
    model_validator,
    StringConstraints,
)
from typing import Annotated, Optional
import re

class RegisterSchema(BaseModel):
    username: Annotated[str, StringConstraints(min_length=3, max_length=50)]
    email: EmailStr
    password: Annotated[str, StringConstraints(min_length=8)]

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain a lowercase letter")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain an uppercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain a digit")
        if not re.search(r"[@$!%*?&]", v):
            raise ValueError("Password must contain a special character")
        return v


class LoginSchema(BaseModel):
    username: str
    password: str
    keystroke_data: list = []
    device_fingerprint: dict = {}
    behavioral_data: dict = {}
    device_id: str = ""
    trust_device: bool = False


class ForgotPasswordSchema(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None

    @model_validator(mode="after")
    def require_at_least_one(self) -> "ForgotPasswordSchema":
        if not self.username and not self.email:
            raise ValueError("Must provide at least one of 'username' or 'email'")
        return self


class ResetPasswordSchema(BaseModel):
    token: str
    new_password: Annotated[str, StringConstraints(min_length=8)]

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain a lowercase letter")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain an uppercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain a digit")
        if not re.search(r"[@$!%*?&]", v):
            raise ValueError("Password must contain a special character")
        return v


class MFAVerifySchema(BaseModel):
    session_id: str
    otp: Annotated[str, StringConstraints(min_length=6, max_length=6)]


class VerifyEmailSchema(BaseModel):
    token: str
