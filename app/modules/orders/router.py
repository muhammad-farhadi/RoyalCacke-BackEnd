# app/modules/orders/router.py
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_active_user, RequirePermission
from app.modules.users.models import User
from app.modules.courses.models import Course
from . import schemas, services, models
import random

router = APIRouter()


# --- مدیریت سبد خرید ---
@router.post("/cart", response_model=schemas.CartResponse)
def add_to_cart(data: schemas.CartItemAdd, db: Session = Depends(get_db),
                current_user: User = Depends(get_current_active_user)):
    """ اضافه کردن دوره به سبد خرید """
    course = db.query(Course).filter(Course.id == data.course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="دوره یافت نشد.")

    # بررسی اینکه قبلا نخریده باشه
    has_enrolled = db.query(models.Enrollment).filter(
        models.Enrollment.user_id == current_user.id,
        models.Enrollment.course_id == data.course_id
    ).first()
    if has_enrolled:
        raise HTTPException(status_code=400, detail="شما قبلا این دوره را خریداری کرده‌اید.")

    services.add_course_to_cart(db, current_user.id, data.course_id)
    return get_user_cart(db, current_user)


@router.get("/cart", response_model=schemas.CartResponse)
def get_user_cart(db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """ مشاهده سبد خرید فعلی """
    cart = services.get_or_create_cart(db, current_user.id)

    response_data = {"id": cart.id, "user_id": cart.user_id, "items": [], "total_price": 0}
    for item in cart.items:
        course = db.query(Course).filter(Course.id == item.course_id).first()
        if course:
            response_data["items"].append({
                "id": item.id,
                "course_id": course.id,
                "course_title": course.title,
                "price": course.price
            })
            response_data["total_price"] += course.price

    return response_data


# --- پرداخت و فاکتور ---
@router.post("/checkout", response_model=schemas.OrderResponse)
def checkout(data: schemas.CheckoutRequest, db: Session = Depends(get_db),
             current_user: User = Depends(get_current_active_user)):
    """
    تبدیل سبد خرید به فاکتور نهایی و محاسبه کد تخفیف
    در سیستم واقعی بعد از این مرحله، باید کاربر رو به لینک درگاه پرداخت ریدایرکت کنید.
    """
    order = services.process_checkout(db, current_user.id, data.discount_code)

    # اینجا می‌تونید رکورد Payment رو بسازید و وصل بشید به زرین‌پال
    # payment = models.Payment(order_id=order.id, amount=order.total_amount, gateway="zarinpal")

    return order


@router.post("/mock-verify")
def mock_verify_payment(data: schemas.VerifyPaymentRequest, db: Session = Depends(get_db),
                        current_user: User = Depends(get_current_active_user)):
    """ شبیه‌سازی بازگشت از درگاه پرداخت و باز کردن دسترسی دوره‌ها """
    order = db.query(models.Order).filter(models.Order.id == data.order_id,
                                          models.Order.user_id == current_user.id).first()

    if not order:
        raise HTTPException(status_code=404, detail="فاکتور یافت نشد.")
    if order.status == "paid":
        raise HTTPException(status_code=400, detail="این فاکتور قبلا پرداخت شده است.")

    # ۱. آپدیت فاکتور و پرداخت
    order.status = "paid"

    # ۲. ایجاد دسترسی برای تک تک آیتم‌های فاکتور
    for item in order.items:
        enrollment = models.Enrollment(
            user_id=order.user_id,
            course_id=item.course_id,
            order_id=order.id,
            purchased_price=item.price
        )
        db.add(enrollment)

    db.commit()
    return {"success": True, "message": "پرداخت موفق بود و دوره‌ها به حساب شما اضافه شد."}


@router.post("/discounts", response_model=schemas.DiscountResponse, status_code=status.HTTP_201_CREATED)
def create_new_discount(
        data: schemas.DiscountCreate,
        db: Session = Depends(get_db),
        current_user: User = Depends(RequirePermission("discount:create"))
):
    """
    ساخت کد تخفیف جدید (مخصوص مدیریت)
    نیاز به پرمیژن discount:create دارد
    """
    # بررسی تکراری نبودن کد تخفیف
    normalized_code = data.code.strip().upper()
    existing_discount = db.query(models.Discount).filter(models.Discount.code == normalized_code).first()

    if existing_discount:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="کد تخفیفی با این نام قبلاً در سیستم ثبت شده است."
        )

    return services.create_discount_code(db, data)


# به انتهای فایل app/modules/orders/router.py اضافه شود

@router.get("/discounts", response_model=List[schemas.DiscountResponse])
def list_all_discounts(
        skip: int = 0,
        limit: int = 100,
        db: Session = Depends(get_db),
        current_user: User = Depends(RequirePermission("discount:read"))
):
    """
    دریافت لیست تمامی کدهای تخفیف (مخصوص مدیریت)
    نیاز به پرمیژن discount:read دارد
    """
    return services.get_all_discounts(db, skip=skip, limit=limit)


@router.put("/discounts/{discount_id}", response_model=schemas.DiscountResponse)
def edit_discount_code(
        discount_id: int,
        data: schemas.DiscountUpdate,
        db: Session = Depends(get_db),
        current_user: User = Depends(RequirePermission("discount:update"))
):
    """
    ویرایش یک کد تخفیف موجود (مخصوص مدیریت)
    نیاز به پرمیژن discount:update دارد
    """
    # اگر نام کد تخفیف تغییر کرده، بررسی تکراری نبودن آن با دیگر کدهای موجود
    if data.code:
        normalized_code = data.code.strip().upper()
        existing_discount = db.query(models.Discount).filter(
            models.Discount.code == normalized_code,
            models.Discount.id != discount_id
        ).first()

        if existing_discount:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="کد تخفیفی با این نام قبلاً در سیستم ثبت شده است."
            )

    updated_discount = services.update_discount_code(db, discount_id, data)
    if not updated_discount:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="کد تخفیف مورد نظر یافت نشد."
        )

    return updated_discount
