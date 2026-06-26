# app/modules/support/models.py
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base


class SupportMessage(Base):
    __tablename__ = "support_messages"

    id = Column(Integer, primary_key=True, index=True)
    room_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    sender_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    # محتوای متنی (میتواند کپشن عکس باشد یا اگر فقط ویس است، خالی باشد)
    content = Column(Text, nullable=True)

    # --- فیلدهای جدید برای مدیا ---
    attachment_url = Column(String, nullable=True)  # مسیر فایل (مثلا /static/support/img.png)
    attachment_type = Column(String, nullable=True)  # نوع فایل (image, voice, document, video)
    # -----------------------------

    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    room_user = relationship("User", foreign_keys=[room_user_id])
    sender = relationship("User", foreign_keys=[sender_id])
