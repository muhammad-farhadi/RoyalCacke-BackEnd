# app/modules/index/schemas.py
from typing import Optional

from pydantic import BaseModel, Field


class ContactFormRequest(BaseModel):
    name: str = Field(..., min_length=2)
    phone_number: str = Field(..., pattern=r"^09\d{9}$")
    message: str = Field(..., min_length=5)


class BannerResponse(BaseModel):
    id: int
    title: str
    subtitle: Optional[str] = None
    image_url: str
    course_id: Optional[int] = None

    class Config:
        from_attributes = True
