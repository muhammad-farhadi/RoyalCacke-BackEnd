# app/modules/articles/models.py
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base


class Article(Base):
    __tablename__ = "articles"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    slug = Column(String, unique=True, index=True, nullable=False)

    # --- این فیلد اضافه شد ---
    image_url = Column(String, nullable=True)
    # -------------------------

    content = Column(Text, nullable=False)
    meta_description = Column(String, nullable=True)
    tags = Column(String, nullable=True)
    author_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))
