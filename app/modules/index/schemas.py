# app/modules/index/schemas.py
from pydantic import BaseModel, Field


class ContactFormRequest(BaseModel):
    name: str = Field(..., min_length=2)
    phone_number: str = Field(..., pattern=r"^09\d{9}$")
    message: str = Field(..., min_length=5)
