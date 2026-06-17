# app/modules/orders/models.py
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from app.core.database import Base


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    total_amount = Column(Integer, nullable=False)  # مبلغ کل فاکتور
    status = Column(String, default="pending")  # وضعیت: pending (در انتظار)، paid (موفق)، failed (ناموفق)
    tracking_code = Column(String, nullable=True)  # شماره پیگیری درگاه پرداخت

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Enrollment(Base):
    __tablename__ = "enrollments"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="SET NULL"), nullable=True)
    purchased_price = Column(Integer, nullable=False)  # قیمتی که اون لحظه خریده (شاید بعداً قیمت دوره عوض بشه)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
