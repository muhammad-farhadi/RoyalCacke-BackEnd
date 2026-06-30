# app/modules/users/services.py
import random
import requests
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from . import models, schemas
from app.core.security import get_password_hash, verify_password
from . import models, schemas
from app.core.security import get_password_hash
from .models import User


def get_user_by_phone(db: Session, phone_number: str):
    return db.query(models.User).filter(models.User.phone_number == phone_number).first()


SMS_PANEL_USERNAME = ""
SMS_PANEL_PASSWORD = ""
SMS_PRIMARY_LINE = ""  # خط عمومی اول
SMS_SUPPORT_LINE_1 = "مثلا_5000xxxx"  # خط عمومی دوم (بکاپ)
SMS_SUPPORT_LINE_2 = "مثلا_1000xxxx"  # خط عمومی سوم (بکاپ)
SMS_PANEL_API_URL = "https://rest.payamak-panel.com/api/SmartSMS/Send"


def send_otp_sms(phone_number: str, otp_code: str):
    """
    ارسال پیامک تایید با استفاده از وب‌سرویس SmartSMS و خطوط اشتراکی پشتیبان
    """
    payload = {
        "username": SMS_PANEL_USERNAME,
        "password": SMS_PANEL_PASSWORD,
        "to": phone_number,
        "from": SMS_PRIMARY_LINE,  # تلاش اول با این خط
        "fromSupportOne": SMS_SUPPORT_LINE_1,  # تلاش دوم در صورت شکست
        "fromSupportTwo": SMS_SUPPORT_LINE_2,  # تلاش سوم در صورت شکست
        "text": f"کد تایید شما در رویال کیک:\n{otp_code}"
    }

    try:
        response = requests.post(SMS_PANEL_API_URL, json=payload, timeout=10)
        data = response.json()

        if data.get("RetStatus") == 1 and data.get("StrRetStatus") == "Ok":
            return True
        else:
            print(f"[SMS ERROR] Failed to send to {phone_number}. Response: {data}")
            return False
    except Exception as e:
        print(f"[SMS EXCEPTION] {str(e)}")
        return False

# =========================================================================

# بقیه توابع بالا مثل get_user_by_phone و create_user سر جای خودشان بمانند...

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

    # ۴. ارسال پیامک واقعی به جای Mock
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


def create_user_and_send_otp(db: Session, user: schemas.UserCreate):
    # ۱. تولید کد ۶ رقمی تصادفی
    otp = str(random.randint(100000, 999999))
    expire_time = datetime.now(timezone.utc) + timedelta(minutes=2)  # اعتبار ۲ دقیقه‌ای

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

    # ۴. اینجا بعداً API پنل پیامک رو صدا می‌زنی. فعلاً فقط چاپش می‌کنیم:
    print(f"\n{'=' * 40}\n[SMS MOCK] ارسال پیامک به {user.phone_number}:\nکد تایید آکادمی شما: {otp}\n{'=' * 40}\n")

    return db_user


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
