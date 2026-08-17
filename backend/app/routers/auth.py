from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.tables import User
from app.auth.security import hash_password, verify_password, create_access_token
from app.auth.dependencies import get_current_user
from app.auth.schemas import SignupRequest, LoginRequest, TokenResponse, UserResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def signup(req: SignupRequest, db: Session = Depends(get_db)):
    existing = db.query(User).filter_by(email=req.email).first()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    password_hash, salt = hash_password(req.password)
    user = User(email=req.email, password_hash=password_hash, password_salt=salt)
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(user_id=user.id)
    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter_by(email=req.email).first()

    # Deliberately identical error for "no such user" and "wrong
    # password" — a distinct "email not found" message lets an
    # attacker enumerate which emails are registered.
    invalid_credentials = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password"
    )

    if user is None:
        raise invalid_credentials
    if not verify_password(req.password, user.password_hash, user.password_salt):
        raise invalid_credentials

    token = create_access_token(user_id=user.id)
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user
