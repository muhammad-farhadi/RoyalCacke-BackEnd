# app/modules/support/schemas.py
from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class MessageResponse(BaseModel):
    id: int
    room_user_id: int
    sender_id: int
    content: Optional[str] = None
    attachment_url: Optional[str] = None   # فیلد جدید
    attachment_type: Optional[str] = None  # فیلد جدید
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True


class ConversationResponse(BaseModel):
    user_id: int
    user_full_name: str
    last_message: str
    unread_count: int
    last_activity: datetime
