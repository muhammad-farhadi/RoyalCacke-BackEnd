# app/modules/orders/schemas.py
from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime


# === شمای سبد خرید ===
class CartItemAdd(BaseModel):
    course_id: int


class CartItemResponse(BaseModel):
    id: int
    course_id: int
    course_title: Optional[str] = None  # برای نمایش نام دوره در سبد خرید
    price: Optional[int] = None
    model_config = ConfigDict(from_attributes=True)


class CartResponse(BaseModel):
    id: int
    user_id: int
    items: List[CartItemResponse] = []
    total_price: int = 0
    model_config = ConfigDict(from_attributes=True)


# === شمای فاکتور و پرداخت ===
class CheckoutRequest(BaseModel):
    discount_code: Optional[str] = None  # کاربر میتونه کد تخفیف بفرسته یا نفرسته


class OrderItemResponse(BaseModel):
    course_id: int
    price: int
    model_config = ConfigDict(from_attributes=True)


class OrderResponse(BaseModel):
    id: int
    user_id: int
    original_amount: int
    discount_amount: int
    total_amount: int
    status: str
    items: List[OrderItemResponse] = []
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class VerifyPaymentRequest(BaseModel):
    order_id: int
    authority: str  # توکنی که درگاه بعد از پرداخت برمی‌گردونه


class DiscountCreate(BaseModel):
    code: str  # مثل: ROYAL2026
    percent: int  # درصد تخفیف (مثلا 20)
    max_discount_amount: Optional[int] = None  # سقف مبلغ تخفیف به تومان
    usage_limit: Optional[int] = 100  # تعداد دفعات مجاز استفاده
    valid_until: Optional[datetime] = None  # تاریخ انقضا
    is_active: Optional[bool] = True


class DiscountResponse(DiscountCreate):
    id: int
    used_count: int

    model_config = ConfigDict(from_attributes=True)


class DiscountUpdate(BaseModel):
    code: Optional[str] = None
    percent: Optional[int] = None
    max_discount_amount: Optional[int] = None
    usage_limit: Optional[int] = None
    valid_until: Optional[datetime] = None
    is_active: Optional[bool] = None
