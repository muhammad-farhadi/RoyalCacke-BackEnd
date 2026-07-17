# app/modules/highlights/schemas.py
from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional


class HighlightItemResponse(BaseModel):
    id: int
    image_url: Optional[str] = None
    video_url: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class HighlightCategoryResponse(BaseModel):
    id: int
    title: str
    cover_url: str
    created_at: datetime
    items: List[HighlightItemResponse] = []  # لیست عکس‌های درون این دسته

    class Config:
        from_attributes = True
