# app/modules/gallery/schemas.py
from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime


class GalleryResponse(BaseModel):
    id: int
    title: str
    image_url: str
    alt_text: Optional[str] = None
    category: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
