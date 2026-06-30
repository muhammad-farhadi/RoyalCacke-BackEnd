# app/modules/orders/router.py
from typing import List
import requests
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_active_user, RequirePermission
from app.modules.users.models import User
from app.modules.courses.models import Course
from . import schemas, services, models
import random

router = APIRouter()

# تنظیمات زرین‌پال (بهتر است بعداً به فایل .env منتقل شود)
ZARINPAL_MERCHANT_ID = "00000000-0000-0000-0000-000000000000"
ZARINPAL_REQUEST_URL = "https://api.zarinpal.com/pg/v4/payment/request.json"
ZARINPAL_VERIFY_URL = "https://api.zarinpal.com/pg/v4/payment/verify.json"
ZARINPAL_STARTPAY_URL = "https://www.zarinpal.com/pg/StartPay/"
# این آدرس باید دقیقاً همانی باشد که فرانت‌اند یا سرور شما به عنوان برگشت روی آن گوش می‌دهد
CALLBACK_URL = "http://localhost:8000/orders/verify-payment"


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
@router.post("/checkout")
def checkout(data: schemas.CheckoutRequest, db: Session = Depends(get_db),
             current_user: User = Depends(get_current_active_user)):
    """
    تبدیل سبد خرید به فاکتور نهایی و ارجاع به درگاه زرین‌پال
    """
    order = services.process_checkout(db, current_user.id, data.discount_code)

    # ۱. اگر مبلغ کل صفر شد (مثلاً تخفیف ۱۰۰٪)، نیازی به درگاه نیست
    if order.total_amount == 0:
        order.status = "paid"
        for item in order.items:
            enrollment = models.Enrollment(
                user_id=order.user_id, course_id=item.course_id, order_id=order.id, purchased_price=0
            )
            db.add(enrollment)
        db.commit()
        return {"message": "سفارش با موفقیت و به صورت رایگان ثبت شد.", "payment_url": None, "order_id": order.id}

    # ۲. درخواست ایجاد تراکنش به زرین‌پال
    payload = {
        "merchant_id": ZARINPAL_MERCHANT_ID,
        "amount": order.total_amount,
        "currency": "IRT",  # واحد پول تومان
        "callback_url": CALLBACK_URL,
        "description": f"خرید دوره از آکادمی - فاکتور شماره {order.id}",
        "metadata": {"mobile": current_user.phone_number}
    }

    try:
        response = requests.post(ZARINPAL_REQUEST_URL, json=payload, timeout=10)
        res_data = response.json()

        # بررسی موفقیت‌آمیز بودن درخواست
        if res_data.get("data") and res_data["data"].get("code") == 100:
            authority = res_data["data"]["authority"]
            payment_url = f"{ZARINPAL_STARTPAY_URL}{authority}"

            # ۳. ذخیره در جدول Payment
            payment = models.Payment(
                order_id=order.id,
                amount=order.total_amount,
                gateway="zarinpal",
                authority=authority,
                status="pending"
            )
            db.add(payment)
            db.commit()

            return {"message": "در حال انتقال به درگاه...", "payment_url": payment_url, "order_id": order.id}
        else:
            errors = res_data.get("errors", "خطای نامشخص")
            raise HTTPException(status_code=400, detail=f"خطا در ایجاد تراکنش: {errors}")

    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail="خطا در ارتباط با سرورهای زرین‌پال.")


@router.get("/verify-payment")
def verify_zarinpal_payment(Authority: str, Status: str, db: Session = Depends(get_db)):
    """
    آدرس بازگشتی از درگاه زرین‌پال. بررسی و تایید نهایی پرداخت.
    """
    # ۱. پیدا کردن رکورد پرداخت با استفاده از Authority
    payment = db.query(models.Payment).filter(models.Payment.authority == Authority).first()

    if not payment:
        raise HTTPException(status_code=404, detail="تراکنش مورد نظر یافت نشد.")

    if payment.status == "paid":
        return {"message": "این تراکنش قبلاً با موفقیت تایید شده است."}

    # ۲. اگر کاربر پرداخت را لغو کرده باشد
    if Status != "OK":
        payment.status = "canceled"
        db.commit()
        # در سیستم واقعی بهتر است اینجا کاربر را به یک صفحه HTML (مثل صفحه پرداخت ناموفق) ریدایرکت کنید
        raise HTTPException(status_code=400, detail="پرداخت ناموفق بود یا توسط شما لغو شد.")

    # ۳. تایید نهایی تراکنش (Verify)
    verify_payload = {
        "merchant_id": ZARINPAL_MERCHANT_ID,
        "amount": payment.amount,
        "authority": Authority
    }

    try:
        response = requests.post(ZARINPAL_VERIFY_URL, json=verify_payload, timeout=10)
        res_data = response.json()

        # کد 100 یعنی پرداخت موفق، کد 101 یعنی پرداخت قبلا تایید شده
        if res_data.get("data") and res_data["data"].get("code") in [100, 101]:
            ref_id = res_data["data"]["ref_id"]

            # آپدیت وضعیت پرداخت
            payment.status = "paid"
            payment.ref_id = str(ref_id)

            # آپدیت وضعیت فاکتور
            order = db.query(models.Order).filter(models.Order.id == payment.order_id).first()
            if order:
                order.status = "paid"

                # ایجاد دسترسی دوره‌ها برای کاربر
                for item in order.items:
                    enrollment = models.Enrollment(
                        user_id=order.user_id,
                        course_id=item.course_id,
                        order_id=order.id,
                        purchased_price=item.price
                    )
                    db.add(enrollment)

            db.commit()

            # در سیستم واقعی اینجا باید یک ریدایرکت به صفحه پرداخت موفق فرانت‌اند انجام دهید:
            # from fastapi.responses import RedirectResponse
            # return RedirectResponse(url=f"http://your-frontend.com/payment/success?ref={ref_id}")

            return {"success": True, "message": "پرداخت با موفقیت انجام شد.", "ref_id": ref_id}

        else:
            payment.status = "failed"
            db.commit()
            errors = res_data.get("errors", "خطا در تایید تراکنش")
            raise HTTPException(status_code=400, detail=f"پرداخت تایید نشد: {errors}")

    except requests.exceptions.RequestException:
        raise HTTPException(status_code=500, detail="خطا در ارتباط با سرور زرین‌پال جهت تایید تراکنش.")


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


@router.delete("/cart/{course_id}", status_code=status.HTTP_200_OK)
def remove_from_cart(
        course_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_active_user)
):
    """
    حذف یک دوره از سبد خرید
    """
    services.remove_course_from_cart(db, current_user.id, course_id)
    return {"success": True, "message": "دوره با موفقیت از سبد خرید حذف شد."}


# --- دوره‌های من ---
@router.get("/my-courses", response_model=List[schemas.EnrollmentResponse])
def get_my_courses(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_active_user)
):
    """
    دریافت لیست دوره‌هایی که کاربر با موفقیت خریداری کرده است
    """
    enrollments = services.get_user_enrollments(db, current_user.id)
    response_data = []

    for en in enrollments:
        # پیدا کردن اطلاعات دوره برای نمایش به کاربر
        course = db.query(Course).filter(Course.id == en.course_id).first()
        if course:
            response_data.append({
                "id": en.id,
                "course_id": en.course_id,
                "course_title": course.title,
                "course_image": getattr(course, 'image_url', None),
                "purchased_price": en.purchased_price,
                "created_at": en.created_at
            })

    return response_data


# --- تاریخچه پرداخت‌ها ---
@router.get("/my-payments", response_model=List[schemas.PaymentResponse])
def get_my_payments(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_active_user)
):
    """
    دریافت لیست تمام پرداخت‌های موفق و ناموفق کاربر
    """
    return services.get_user_payments(db, current_user.id)
