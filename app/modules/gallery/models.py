# app/modules/gallery/models.py
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime
from app.core.database import Base


class GalleryItem(Base):
    __tablename__ = "gallery"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    image_url = Column(String, nullable=False)  # مسیر دسترسی به عکس (مثلا: /static/gallery/cake1.jpg)
    alt_text = Column(String, nullable=True)  # متن جایگزین برای سئو گوگل
    category = Column(String, index=True, nullable=True)  # دسته‌بندی مثل: کیک خامه ای، شیرینی خشک

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    def __str__(self):
        return self.title
