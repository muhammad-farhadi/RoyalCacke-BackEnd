# app/modules/orders/router.py
from typing import List
import requests
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from starlette.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from app.core.database import get_db
from app.core.dependencies import get_current_active_user, RequirePermission
from app.modules.users.models import User
from app.modules.courses.models import Course
from . import schemas, services, models
import random

from .models import Enrollment

router = APIRouter()

# تنظیمات زرین‌پال (بهتر است بعداً به فایل .env منتقل شود)
ZARINPAL_MERCHANT_ID = "2045c3ee-1054-46ad-8769-7fa7cb492535"
ZARINPAL_REQUEST_URL = "https://api.zarinpal.com/pg/v4/payment/request.json"
ZARINPAL_VERIFY_URL = "https://api.zarinpal.com/pg/v4/payment/verify.json"
ZARINPAL_STARTPAY_URL = "https://www.zarinpal.com/pg/StartPay/"
# این آدرس باید دقیقاً همانی باشد که فرانت‌اند یا سرور شما به عنوان برگشت روی آن گوش می‌دهد
CALLBACK_URL = "https://royalcakes.ir/api/v1/orders/verify-payment"
templates = Jinja2Templates(directory="templates")


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
    """ مشاهده سبد خرید فعلی با احتساب تخفیف‌های زمان‌دار """
    cart = services.get_or_create_cart(db, current_user.id)

    response_data = {"id": cart.id, "user_id": cart.user_id, "items": [], "total_price": 0}
    for item in cart.items:
        course = db.query(Course).filter(Course.id == item.course_id).first()
        if course:
            # 🔴 اصلاح کلیدی: خواندن قیمت نهایی لحظه‌ای (تخفیف‌دار) به جای قیمت ثابت اصلی
            current_price = course.final_price

            response_data["items"].append({
                "id": item.id,
                "course_id": course.id,
                "course_title": course.title,
                "price": current_price
            })
            response_data["total_price"] += current_price

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


@router.get("/verify-payment", response_class=HTMLResponse)
def verify_zarinpal_payment(
        request: Request,
        Authority: str,
        Status: str,
        db: Session = Depends(get_db)
):
    """
    آدرس بازگشتی از درگاه زرین‌پال. بررسی، تایید نهایی و رندر صفحه رسید HTML.
    """
    # ۱. پیدا کردن رکورد پرداخت با استفاده از Authority
    payment = db.query(models.Payment).filter(models.Payment.authority == Authority).first()

    # اگر اصلاً چنین تراکنشی در دیتابیس نبود
    if not payment:
        return templates.TemplateResponse(
            request=request,
            name="payment_result.html",
            context={
                "success": False,
                "order_id": "نامشخص",
                "ref_id": None,
                "amount": "۰"
            },
            status_code=404
        )

    # فرمت کردن مبلغ به همراه کاما برای نمایش شکیل‌تر در رسید
    formatted_amount = "{:,}".format(payment.amount)

    # اگر تراکنش قبلاً پرداخت و تایید شده باشد
    if payment.status == "paid":
        return templates.TemplateResponse(
            request=request,
            name="payment_result.html",
            context={
                "success": True,
                "order_id": payment.order_id,
                "ref_id": payment.ref_id,
                "amount": formatted_amount
            }
        )

    # ۲. اگر کاربر پرداخت را در درگاه بانک لغو کرده باشد (وضعیت NOK شما)
    if Status != "OK":
        payment.status = "canceled"
        db.commit()

        return templates.TemplateResponse(
            request=request,
            name="payment_result.html",
            context={
                "success": False,
                "order_id": payment.order_id,
                "ref_id": None,
                "amount": formatted_amount
            }
        )

    # ۳. تایید نهایی تراکنش از سرور زرین‌پال (Verify)
    verify_payload = {
        "merchant_id": ZARINPAL_MERCHANT_ID,
        "amount": payment.amount,
        "authority": Authority
    }

    try:
        response = requests.post(ZARINPAL_VERIFY_URL, json=verify_payload, timeout=10)
        res_data = response.json()

        if res_data.get("data") and res_data["data"].get("code") in [100, 101]:
            ref_id = res_data["data"]["ref_id"]

            payment.status = "paid"
            payment.ref_id = str(ref_id)

            order = db.query(models.Order).filter(models.Order.id == payment.order_id).first()
            if order:
                order.status = "paid"

                for item in order.items:
                    enrollment = models.Enrollment(
                        user_id=order.user_id,
                        course_id=item.course_id,
                        order_id=order.id,
                        purchased_price=item.price
                    )
                    db.add(enrollment)

            db.commit()

            return templates.TemplateResponse(
                request=request,
                name="payment_result.html",
                context={
                    "success": True,
                    "order_id": payment.order_id,
                    "ref_id": str(ref_id),
                    "amount": formatted_amount
                }
            )

        else:
            payment.status = "failed"
            db.commit()

            return templates.TemplateResponse(
                request=request,
                name="payment_result.html",
                context={
                    "success": False,
                    "order_id": payment.order_id,
                    "ref_id": None,
                    "amount": formatted_amount
                }
            )

    except requests.exceptions.RequestException:
        return templates.TemplateResponse(
            request=request,
            name="payment_result.html",
            context={
                "success": False,
                "order_id": payment.order_id,
                "ref_id": None,
                "amount": formatted_amount
            },
            status_code=500
        )


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


@router.post("/{course_id}/enroll-free", status_code=status.HTTP_201_CREATED)
def enroll_in_free_course(
        course_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_active_user)  # اجبار کاربر به لاگین بودن
):
    # ۱. بررسی وجود داشتن دوره
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="دوره آموزشی یافت نشد.")

    # ۲. بررسی اینکه دوره واقعاً رایگان باشد (قیمت صفر)
    if course.price > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="این دوره رایگان نیست و باید از طریق سبد خرید اقدام کنید."
        )

    # ۳. بررسی اینکه کاربر از قبل این دوره را فعال نکرده باشد
    existing_enrollment = db.query(Enrollment).filter(
        Enrollment.user_id == current_user.id,
        Enrollment.course_id == course_id
    ).first()

    if existing_enrollment:
        return {"detail": "شما از قبل به این دوره دسترسی دارید."}

    # ۴. صدور دسترسی مستقیم با مبلغ صفر ریال
    new_enrollment = Enrollment(
        user_id=current_user.id,
        course_id=course_id,
        purchased_price=0
    )
    db.add(new_enrollment)
    db.commit()

    return {"detail": "دوره رایگان با موفقیت برای شما فعال شد و به لیست دوره‌های من اضافه گردید."}
