# app/modules/orders/services.py
from sqlalchemy.orm import Session
from fastapi import HTTPException
from datetime import datetime, timezone
from . import models
from app.modules.courses.models import Course
from .schemas import DiscountCreate, DiscountUpdate


def get_or_create_cart(db: Session, user_id: int):
    cart = db.query(models.Cart).filter(models.Cart.user_id == user_id).first()
    if not cart:
        cart = models.Cart(user_id=user_id)
        db.add(cart)
        db.commit()
        db.refresh(cart)
    return cart


def add_course_to_cart(db: Session, user_id: int, course_id: int):
    cart = get_or_create_cart(db, user_id)

    # بررسی اینکه این دوره قبلا تو سبد خرید نباشه
    existing_item = db.query(models.CartItem).filter(
        models.CartItem.cart_id == cart.id,
        models.CartItem.course_id == course_id
    ).first()

    if existing_item:
        raise HTTPException(status_code=400, detail="این دوره از قبل در سبد خرید شما موجود است.")

    new_item = models.CartItem(cart_id=cart.id, course_id=course_id)
    db.add(new_item)
    db.commit()
    return cart


def process_checkout(db: Session, user_id: int, discount_code: str = None):
    cart = db.query(models.Cart).filter(models.Cart.user_id == user_id).first()
    if not cart or not cart.items:
        raise HTTPException(status_code=400, detail="سبد خرید شما خالی است.")

    # ۱. محاسبه قیمت کل دوره‌های داخل سبد
    original_amount = 0
    course_items = []
    for item in cart.items:
        course = db.query(Course).filter(Course.id == item.course_id).first()
        if course:
            original_amount += course.price
            course_items.append({"course_id": course.id, "price": course.price})

    # ۲. اعمال منطق کد تخفیف
    discount_amount = 0
    discount_obj = None

    if discount_code:
        discount_obj = db.query(models.Discount).filter(models.Discount.code == discount_code).first()
        if not discount_obj:
            raise HTTPException(status_code=404, detail="کد تخفیف معتبر نیست.")
        if not discount_obj.is_active:
            raise HTTPException(status_code=400, detail="این کد تخفیف غیرفعال شده است.")
        if discount_obj.valid_until and discount_obj.valid_until < datetime.now(timezone.utc):
            raise HTTPException(status_code=400, detail="تاریخ انقضای این کد تخفیف گذشته است.")
        if discount_obj.used_count >= discount_obj.usage_limit:
            raise HTTPException(status_code=400, detail="ظرفیت استفاده از این کد تخفیف به پایان رسیده است.")

        # محاسبه مبلغ تخفیف
        calculated_discount = (original_amount * discount_obj.percent) // 100
        # چک کردن سقف تخفیف
        if discount_obj.max_discount_amount and calculated_discount > discount_obj.max_discount_amount:
            discount_amount = discount_obj.max_discount_amount
        else:
            discount_amount = calculated_discount

    total_amount = original_amount - discount_amount
    if total_amount < 0: total_amount = 0

    # ۳. ساخت فاکتور (Order)
    new_order = models.Order(
        user_id=user_id,
        original_amount=original_amount,
        discount_amount=discount_amount,
        total_amount=total_amount,
        discount_id=discount_obj.id if discount_obj else None
    )
    db.add(new_order)
    db.flush()  # آیدی فاکتور رو میگیریم ولی کامیت نمیکنیم تا بقیه کارها انجام شه

    # ۴. ساخت اقلام فاکتور
    for item in course_items:
        order_item = models.OrderItem(order_id=new_order.id, course_id=item["course_id"], price=item["price"])
        db.add(order_item)

    # ۵. آپدیت تعداد دفعات استفاده کد تخفیف
    if discount_obj:
        discount_obj.used_count += 1

    # ۶. خالی کردن سبد خرید
    db.query(models.CartItem).filter(models.CartItem.cart_id == cart.id).delete()

    db.commit()
    db.refresh(new_order)

    return new_order


def create_discount_code(db: Session, discount_in: DiscountCreate):
    """
    ذخیره کد تخفیف جدید در دیتابیس
    """
    valid_until = discount_in.valid_until
    if valid_until and valid_until.tzinfo is None:
        valid_until = valid_until.replace(tzinfo=timezone.utc)

    db_discount = models.Discount(
        code=discount_in.code.strip().upper(),  # ذخیره به صورت حروف بزرگ برای جلوگیری از حساسیت به حروف
        percent=discount_in.percent,
        max_discount_amount=discount_in.max_discount_amount,
        usage_limit=discount_in.usage_limit,
        valid_until=valid_until,
        is_active=discount_in.is_active
    )
    db.add(db_discount)
    db.commit()
    db.refresh(db_discount)
    return db_discount


# به انتهای فایل app/modules/orders/services.py اضافه شود

def get_all_discounts(db: Session, skip: int = 0, limit: int = 100):
    """
    دریافت لیست کدهای تخفیف به همراه صفحه‌بندی
    """
    return db.query(models.Discount).order_by(models.Discount.id.desc()).offset(skip).limit(limit).all()


def update_discount_code(db: Session, discount_id: int, discount_in: DiscountUpdate):
    """
    بروزرسانی اطلاعات یک کد تخفیف موجود
    """
    db_discount = db.query(models.Discount).filter(models.Discount.id == discount_id).first()
    if not db_discount:
        return None

    # تبدیل به دیکشنری و حذف فیلدهایی که فرستاده نشده‌اند
    update_data = discount_in.model_dump(exclude_unset=True)

    # استانداردسازی کد در صورت تغییر
    if "code" in update_data and update_data["code"]:
        update_data["code"] = update_data["code"].strip().upper()

    # تنظیم منطقه زمانی در صورت تغییر تاریخ انقضا
    if "valid_until" in update_data and update_data["valid_until"]:
        if update_data["valid_until"].tzinfo is None:
            update_data["valid_until"] = update_data["valid_until"].replace(tzinfo=timezone.utc)

    # اعمال تغییرات روی مدل دیتابیس
    for key, value in update_data.items():
        setattr(db_discount, key, value)

    db.commit()
    db.refresh(db_discount)
    return db_discount
