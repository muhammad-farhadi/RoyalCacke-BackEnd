# app/modules/orders/router.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_active_user
from app.modules.users.models import User
from app.modules.courses.services import get_course_by_id
from . import schemas, services, models
from ..courses.models import Course

router = APIRouter()


# مرحله اول: درخواست خرید دوره و ساخت فاکتور
@router.post("/checkout", response_model=schemas.OrderResponse)
def checkout_course(
        data: schemas.CheckoutRequest,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_active_user)
):
    course = get_course_by_id(db, course_id=data.course_id)
    if not course:
        raise HTTPException(status_code=404, detail="دوره یافت نشد.")

    # چک کردن اینکه آیا کاربر قبلاً این دوره رو خریده یا نه
    existing_enrollment = db.query(models.Enrollment).filter(
        models.Enrollment.user_id == current_user.id,
        models.Enrollment.course_id == course.id
    ).first()

    if existing_enrollment:
        raise HTTPException(status_code=400, detail="شما قبلاً این دوره را خریداری کرده‌اید.")

    # ساخت فاکتور
    order = services.create_order(db, user_id=current_user.id, course=course)

    # در واقعیت اینجا به جای برگردوندن فاکتور، کاربر رو ریدایرکت می‌کنیم به لینک درگاه پرداخت
    return order


# مرحله دوم: کال‌بک درگاه پرداخت (شبیه‌ساز)
@router.post("/mock-verify")
def mock_verify_payment(
        data: schemas.VerifyPaymentRequest,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_active_user)
):
    order = db.query(models.Order).filter(
        models.Order.id == data.order_id,
        models.Order.user_id == current_user.id
    ).first()

    if not order:
        raise HTTPException(status_code=404, detail="فاکتور یافت نشد.")

    if order.status == "paid":
        return {"message": "این فاکتور قبلاً پرداخت شده است.", "tracking_code": order.tracking_code}

    # پیدا کردن دوره مربوط به این فاکتور (چون فعلاً تک‌محصولی زدیم، مستقیم پیداش می‌کنیم)
    # در سیستم‌های واقعی باید از جدول OrderItem بخونیم
    course_price = order.total_amount
    course = db.query(Course).filter(Course.price == course_price).first()

    # تایید تراکنش و باز کردن دسترسی
    completed_order = services.verify_and_enroll(db, order=order, course_id=course.id)

    return {
        "success": True,
        "message": "پرداخت با موفقیت شبیه‌سازی شد و دسترسی دوره باز شد.",
        "tracking_code": completed_order.tracking_code
    }
