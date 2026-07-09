# app/modules/users/services.py
import random
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from melipayamak import Api
from . import models, schemas
from app.core.security import get_password_hash, verify_password
from .models import User


def get_user_by_phone(db: Session, phone_number: str):
    return db.query(models.User).filter(models.User.phone_number == phone_number).first()


# تنظیمات پنل پیامک بر اساس داکیومنت جدید (SendByBaseNumber)
# SMS_PANEL_USERNAME = "9127612655"
# SMS_PANEL_PASSWORD = "f50de101-ceaa-49f5-be7c-9ee19f583263"
username = '9127612655'
password = "f50de101-ceaa-49f5-be7c-9ee19f583263"
SMS_BODY_ID = 484958


def send_otp_sms(phone_number: str, otp_code: str):
    try:
        api = Api(username, password)
        sms_soap = api.sms('soap')
        text_parameters = [f"{otp_code}"]
        response = sms_soap.send_by_base_number(text_parameters, phone_number, SMS_BODY_ID)
        print(response)
        try:
            status_code = int(response)
            if status_code > 100:
                return True
            else:
                print(f"[SMS ERROR] Failed to send to {phone_number}. Error Code: {status_code}")
                return False
        except ValueError:
            if response and len(str(response)) >= 10:
                return True
            print(f"[SMS ERROR] Unexpected response format: {response}")
            return False

    except Exception as e:
        print(f"[SMS EXCEPTION] Failed to connect or send via SOAP: {str(e)}")
        return False


# =========================================================================


def create_user_and_send_otp(db: Session, user: schemas.UserCreate):
    # ۱. تولید کد ۶ رقمی تصادفی
    otp = str(random.randint(100000, 999999))
    expire_time = datetime.now(timezone.utc) + timedelta(minutes=2)

    # ۲. هش کردن پسورد
    hashed_password = get_password_hash(user.password)

    # ۳. ذخیره کاربر به صورت تایید نشده
    db_user = models.User(
        full_name=user.full_name,
        phone_number=user.phone_number,
        hashed_password=hashed_password,
        is_verified=False,
        otp_code=otp,
        otp_expire=expire_time
    )

    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    # ۴. ارسال پیامک واقعی با ساختار جدید الگو محور
    send_otp_sms(user.phone_number, otp)

    return db_user


def create_user(db: Session, user: schemas.UserCreate):
    # هش کردن پسورد قبل از ذخیره در دیتابیس
    hashed_password = get_password_hash(user.password)

    db_user = models.User(
        full_name=user.full_name,
        phone_number=user.phone_number,
        hashed_password=hashed_password
    )

    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


#
# def create_user_and_send_otp(db: Session, user: schemas.UserCreate):
#     # ۱. تولید کد ۶ رقمی تصادفی
#     otp = str(random.randint(100000, 999999))
#     expire_time = datetime.now(timezone.utc) + timedelta(minutes=2)  # اعتبار ۲ دقیقه‌ای
#
#     # ۲. هش کردن پسورد
#     hashed_password = get_password_hash(user.password)
#
#     # ۳. ذخیره کاربر به صورت تایید نشده
#     db_user = models.User(
#         full_name=user.full_name,
#         phone_number=user.phone_number,
#         hashed_password=hashed_password,
#         is_verified=False,
#         otp_code=otp,
#         otp_expire=expire_time
#     )
#
#     db.add(db_user)
#     db.commit()
#     db.refresh(db_user)
#
#     # ۴. اینجا بعداً API پنل پیامک رو صدا می‌زنی. فعلاً فقط چاپش می‌کنیم:
#     print(f"\n{'=' * 40}\n[SMS MOCK] ارسال پیامک به {user.phone_number}:\nکد تایید آکادمی شما: {otp}\n{'=' * 40}\n")
#
#     return db_user


def authenticate_user(db: Session, phone_number: str, password: str):
    user = db.query(models.User).filter(models.User.phone_number == phone_number).first()
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user


def update_user_info(db: Session, user_id: int, user_in: schemas.UserUpdate):
    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    if not db_user:
        return None

    update_data = user_in.model_dump(exclude_unset=True)

    # اگر ادمین رمز عبور جدید فرستاده بود، جداگانه هش می‌کنیم
    if "password" in update_data:
        raw_password = update_data.pop("password")
        db_user.hashed_password = get_password_hash(raw_password)

    for key, value in update_data.items():
        setattr(db_user, key, value)

    db.commit()
    db.refresh(db_user)
    return db_user


def get_all_users(db: Session, skip: int = 0, limit: int = 50):
    """
    دریافت لیست تمام کاربران با قابلیت صفحه‌بندی (Pagination)
    """
    return db.query(models.User).order_by(models.User.created_at.desc()).offset(skip).limit(limit).all()


def get_user_permissions(user: models.User) -> list[str]:
    """
    استخراج تمام دسترسی‌های کاربر از روی نقش‌هایی که دارد
    """
    permissions = set()

    # پیمایش در نقش‌های کاربر و استخراج دسترسی‌ها
    for role in user.roles:
        for perm in role.permissions:
            permissions.add(perm.name)

    # اگر کاربر ادمین کل است، یک دسترسی ویژه به نام all_access به فرانت بدهیم (اختیاری)
    if user.is_superuser:
        permissions.add("all_access")

    return list(permissions)
