# app/modules/orders/schemas.py
from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime


class CheckoutRequest(BaseModel):
    course_id: int  # فعلاً برای سادگی، خرید یک دوره در هر ریکوئست رو هندل می‌کنیم


class OrderResponse(BaseModel):
    id: int
    user_id: int
    total_amount: int
    status: str
    tracking_code: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class VerifyPaymentRequest(BaseModel):
    order_id: int
    # در واقعیت اینجا authority_code زرین‌پال یا پی‌پال رو هم می‌گیریم
