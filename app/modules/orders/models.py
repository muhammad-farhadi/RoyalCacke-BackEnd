# app/modules/orders/models.py
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from app.core.database import Base


# ================= 1. سبد خرید =================
class Cart(Base):
    __tablename__ = "carts"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    items = relationship("CartItem", back_populates="cart", cascade="all, delete-orphan")


class CartItem(Base):
    __tablename__ = "cart_items"
    id = Column(Integer, primary_key=True, index=True)
    cart_id = Column(Integer, ForeignKey("carts.id", ondelete="CASCADE"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    cart = relationship("Cart", back_populates="items")


# ================= 2. کدهای تخفیف =================
class Discount(Base):
    __tablename__ = "discounts"
    id = Column(Integer, primary_key=True, index=True)
    code = Column(String, unique=True, index=True, nullable=False)
    percent = Column(Integer, nullable=False)  # درصد تخفیف (مثلا 20)
    max_discount_amount = Column(Integer, nullable=True)  # سقف مبلغ تخفیف (مثلا تا 50 هزار تومن)
    usage_limit = Column(Integer, default=100)  # ظرفیت استفاده از کد
    used_count = Column(Integer, default=0)  # تعداد دفعاتی که تا الان استفاده شده
    valid_until = Column(DateTime, nullable=True)  # تاریخ انقضا
    is_active = Column(Boolean, default=True)


# ================= 3. فاکتور و اقلام =================
class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    # مبالغ
    original_amount = Column(Integer, nullable=False)  # قیمت کل بدون تخفیف
    discount_amount = Column(Integer, default=0)  # مبلغی که تخفیف داده شده
    total_amount = Column(Integer, nullable=False)  # مبلغ نهایی قابل پرداخت

    discount_id = Column(Integer, ForeignKey("discounts.id", ondelete="SET NULL"), nullable=True)
    status = Column(String, default="pending")  # pending, paid, canceled

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="order", cascade="all, delete-orphan")


class OrderItem(Base):
    __tablename__ = "order_items"
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    price = Column(Integer, nullable=False)
    order = relationship("Order", back_populates="items")


# ================= 4. تراکنش بانکی =================
class Payment(Base):
    __tablename__ = "payments"
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    amount = Column(Integer, nullable=False)
    gateway = Column(String, default="zarinpal")
    authority = Column(String, nullable=True, index=True)
    ref_id = Column(String, nullable=True)
    status = Column(String, default="pending")  # pending, success, failed
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    order = relationship("Order", back_populates="payments")


# ================= 5. دسترسی دوره‌ها =================
class Enrollment(Base):
    __tablename__ = "enrollments"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="SET NULL"), nullable=True)
    purchased_price = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
