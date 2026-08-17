from pydantic import BaseModel, EmailStr, field_validator


class SignupRequest(BaseModel):
    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        # Minimum length only — NOT enforcing complexity rules
        # (uppercase/digit/symbol requirements). Those rules are
        # widely considered to push users toward predictable
        # patterns (Password1!) rather than actual strength; length
        # is the single strongest lever for password strength per
        # current guidance (e.g. NIST SP 800-63B).
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: int
    email: str

    class Config:
        from_attributes = True
