from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from app.chat.agent import run_chat_turn
from app.chat.schemas import ChatRequest, ChatResponse, ChatMessage
from app.db import get_db

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
def chat(req: ChatRequest, db: Session = Depends(get_db)):
    """
    Stateless chat turn: send the full conversation so far, get back
    the updated conversation with the model's new turn(s) appended.
    The frontend is responsible for keeping the running message list
    and sending it back on each call — no server-side session state.
    """
    messages_as_dicts = [m.model_dump(exclude_none=True) for m in req.messages]

    try:
        updated = run_chat_turn(db, messages_as_dicts)
    except RuntimeError as e:
        # missing API key, etc. — a config problem, not a bad request
        raise HTTPException(status_code=503, detail=str(e))

    return ChatResponse(messages=[ChatMessage(**m) for m in updated])
