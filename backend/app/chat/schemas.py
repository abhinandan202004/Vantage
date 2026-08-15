from pydantic import BaseModel


class ChatMessage(BaseModel):
    role: str  # "user" | "assistant" | "tool"
    content: str | None = None
    tool_calls: list[dict] | None = None
    tool_call_id: str | None = None


class ChatRequest(BaseModel):
    messages: list[ChatMessage]  # full conversation so far, ending with the newest user message


class ChatResponse(BaseModel):
    messages: list[ChatMessage]  # updated conversation, including the model's new turn(s)
