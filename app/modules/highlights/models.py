# app/modules/highlights/models.py
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base


class HighlightCategory(Base):
    __tablename__ = "highlight_categories"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    cover_url = Column(String, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    items = relationship("HighlightItem", back_populates="category", cascade="all, delete-orphan")

    # 🔴 این تابع جادویی را اضافه کنید تا اسم دسته در فرم آپلودِ عکس‌ها درست نمایش داده شود
    def __str__(self):
        return self.title


class HighlightItem(Base):
    __tablename__ = "highlight_items"

    id = Column(Integer, primary_key=True, index=True)
    category_id = Column(Integer, ForeignKey("highlight_categories.id", ondelete="CASCADE"), nullable=False)
    image_url = Column(String, nullable=True)
    video_url = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))  # تاریخ ثبت همین عکس

    # رابطه برگشتی به دسته
    category = relationship("HighlightCategory", back_populates="items")

    def __str__(self):
        return self.category.title
