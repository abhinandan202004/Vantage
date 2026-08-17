"""
FastAPI dependency that extracts the current user from an
`Authorization: Bearer <token>` header. Use as a route dependency to
protect any endpoint that should require login:

    @router.get("/something")
    def something(user: User = Depends(get_current_user)):
        ...
"""
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.tables import User
from app.auth.security import decode_access_token

# tokenUrl is just for the auto-generated /docs "Authorize" button to
# know which endpoint issues tokens — doesn't affect actual auth logic.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        user_id = decode_access_token(token)
    except jwt.PyJWTError:
        raise credentials_error

    user = db.query(User).filter_by(id=user_id).first()
    if user is None:
        # token is validly signed but the user it refers to no longer
        # exists (e.g. deleted account) — same 401, don't leak which
        # case it was
        raise credentials_error

    return user
