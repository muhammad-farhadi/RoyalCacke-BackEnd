# app/modules/articles/models.py
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base


class Article(Base):
    __tablename__ = "articles"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    # Slug برای سئو به‌شدت مهمه (مثلاً: /how-to-bake-a-cake)
    slug = Column(String, unique=True, index=True, nullable=False)
    content = Column(Text, nullable=False)  # متن اصلی مقاله (می‌تونه HTML یا Markdown باشه)
    meta_description = Column(String, nullable=True)  # تگ متای توضیحات برای گوگل
    tags = Column(String, nullable=True)  # تگ‌ها (می‌تونیم با ویرگول جدا کنیم)

    # ارتباط با جدول کاربران (نویسنده)
    author_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    # اگر نیاز داشتی از سمت مقاله به دیتای یوزر برسی:
    # author = relationship("User", backref="articles")
