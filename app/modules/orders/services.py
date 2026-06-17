# app/modules/orders/services.py
from sqlalchemy.orm import Session
from . import models
from app.modules.courses.models import Course


def create_order(db: Session, user_id: int, course: Course):
    db_order = models.Order(
        user_id=user_id,
        total_amount=course.price,
        status="pending"
    )
    db.add(db_order)
    db.commit()
    db.refresh(db_order)
    return db_order


def verify_and_enroll(db: Session, order: models.Order, course_id: int):
    # ۱. آپدیت وضعیت فاکتور به پرداخت شده
    import random
    order.status = "paid"
    order.tracking_code = f"MOCK-{random.randint(100000, 999999)}"  # شماره پیگیری فیک

    # ۲. ایجاد دسترسی دوره برای کاربر (ثبت‌نام)
    db_enrollment = models.Enrollment(
        user_id=order.user_id,
        course_id=course_id,
        order_id=order.id,
        purchased_price=order.total_amount
    )
    db.add(db_enrollment)
    db.commit()
    db.refresh(order)
    return order
