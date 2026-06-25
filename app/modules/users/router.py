# app/modules/users/router.py
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from jose import jwt, JWTError
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import create_access_token, SECRET_KEY, ALGORITHM, create_refresh_token
from app.core.dependencies import get_current_active_user, RequirePermission, get_current_user
import random
from datetime import datetime, timedelta, timezone
from . import schemas, services, models
from .models import User

router = APIRouter()


@router.post("/register", response_model=schemas.UserResponse, status_code=status.HTTP_201_CREATED)
def register_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    # بررسی تکراری نبودن شماره موبایل
    db_user = services.get_user_by_phone(db, phone_number=user.phone_number)
    if db_user:
        raise HTTPException(status_code=400, detail="این شماره موبایل قبلاً ثبت شده است.")

    return services.create_user_and_send_otp(db=db, user=user)


@router.post("/verify-otp")
def verify_otp(data: schemas.VerifyOTP, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.phone_number == data.phone_number).first()
    if not user:
        raise HTTPException(status_code=404, detail="کاربر یافت نشد.")
    if user.is_verified:
        raise HTTPException(status_code=400, detail="این حساب قبلاً تایید شده است.")

    # همسان‌سازی منطقه زمانی (UTC) برای جلوگیری از ارور offset-naive
    now_utc = datetime.now(timezone.utc)
    expire_time = user.otp_expire
    if expire_time and expire_time.tzinfo is None:
        expire_time = expire_time.replace(tzinfo=timezone.utc)

    # بررسی صحت و انقضای کد
    if user.otp_code != data.otp_code or expire_time is None or now_utc > expire_time:
        raise HTTPException(status_code=400, detail="کد تایید نامعتبر است یا منقضی شده.")

    # تایید حساب
    user.is_verified = True
    user.otp_code = None
    user.otp_expire = None
    db.commit()
    return {"message": "حساب کاربری شما با موفقیت تایید شد."}


@router.post("/login", response_model=schemas.Token)
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = services.authenticate_user(db, phone_number=form_data.username, password=form_data.password)
    if not user:
        raise HTTPException(status_code=401, detail="شماره موبایل یا رمز عبور اشتباه است.")
    if not user.is_verified:
        raise HTTPException(status_code=403, detail="لطفا ابتدا حساب کاربری خود را تایید کنید.")

    # تولید هر دو توکن
    access_token = create_access_token(data={"sub": user.phone_number})
    refresh_token = create_refresh_token(data={"sub": user.phone_number})

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }


@router.post("/refresh", response_model=schemas.Token)
def refresh_token(data: schemas.RefreshTokenRequest, db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="رفرش توکن نامعتبر است یا منقضی شده.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        # دیکد کردن رفرش توکن
        payload = jwt.decode(data.refresh_token, SECRET_KEY, algorithms=[ALGORITHM])

        # بررسی نوع توکن که حتماً رفرش باشه
        if payload.get("type") != "refresh":
            raise credentials_exception

        phone_number: str = payload.get("sub")
        if phone_number is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    # بررسی وجود کاربر و فعال بودن آن
    user = db.query(models.User).filter(models.User.phone_number == phone_number).first()
    if user is None or not user.is_active:
        raise credentials_exception

    # صدور اکسس توکن جدید (اختیاری: می‌تونی اینجا یک رفرش توکن جدید هم صادر کنی)
    new_access_token = create_access_token(data={"sub": user.phone_number})

    return {
        "access_token": new_access_token,
        "refresh_token": data.refresh_token,  # همون رفرش توکن قبلی رو برمی‌گردونیم
        "token_type": "bearer"
    }


@router.post("/forgot-password")
def request_password_reset(data: schemas.ForgotPasswordRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.phone_number == data.phone_number).first()
    if not user:
        # برای جلوگیری از لو رفتن شماره موبایل‌های ثبت‌شده، خطای 404 نمی‌دیم
        return {"message": "اگر این شماره در سیستم باشد، کد تایید ارسال خواهد شد."}

    # تولید کد و زمان انقضا
    otp = str(random.randint(100000, 999999))
    user.otp_code = otp
    user.otp_expire = datetime.now(timezone.utc) + timedelta(minutes=2)
    db.commit()

    # ماک ارسال پیامک
    print(f"\n{'=' * 40}\n[SMS MOCK] بازیابی رمز عبور برای {user.phone_number}:\nکد: {otp}\n{'=' * 40}\n")

    return {"message": "اگر این شماره در سیستم باشد، کد تایید ارسال خواهد شد."}


@router.post("/reset-password")
def reset_password(data: schemas.ResetPasswordRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.phone_number == data.phone_number).first()
    if not user:
        raise HTTPException(status_code=400, detail="اطلاعات نامعتبر است.")

    # همسان‌سازی منطقه زمانی (UTC) برای جلوگیری از ارور offset-naive
    now_utc = datetime.now(timezone.utc)
    expire_time = user.otp_expire
    if expire_time and expire_time.tzinfo is None:
        expire_time = expire_time.replace(tzinfo=timezone.utc)

    # بررسی صحت و انقضای کد
    if user.otp_code != data.otp_code or expire_time is None or now_utc > expire_time:
        raise HTTPException(status_code=400, detail="کد تایید نامعتبر است یا منقضی شده.")

    from app.core.security import get_password_hash
    user.hashed_password = get_password_hash(data.new_password)
    user.otp_code = None
    user.otp_expire = None
    db.commit()

    return {"message": "رمز عبور با موفقیت تغییر کرد."}


@router.put("/{user_id}", response_model=schemas.UserResponse)
def edit_user(
        user_id: int,
        user_in: schemas.UserUpdate,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(RequirePermission("user:update"))
):
    # چک کردن تکراری نبودن شماره موبایل (اگر ادمین خواست شماره یوزر رو عوض کنه)
    if user_in.phone_number:
        existing_user = services.get_user_by_phone(db, phone_number=user_in.phone_number)
        if existing_user and existing_user.id != user_id:
            raise HTTPException(status_code=400, detail="این شماره موبایل قبلاً برای شخص دیگری ثبت شده است.")

    updated_user = services.update_user_info(db, user_id, user_in)
    if not updated_user:
        raise HTTPException(status_code=404, detail="کاربر یافت نشد.")

    return updated_user


@router.post("/resend-otp")
def resend_otp(data: schemas.ResendOTPRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.phone_number == data.phone_number).first()

    if not user:
        raise HTTPException(status_code=404, detail="کاربر یافت نشد.")

    if user.is_verified:
        raise HTTPException(status_code=400, detail="این حساب کاربری قبلاً تایید شده است و نیازی به کد ندارد.")

    # تولید کد جدید و تمدید زمان انقضا (۲ دقیقه)
    otp = str(random.randint(100000, 999999))
    user.otp_code = otp
    user.otp_expire = datetime.now(timezone.utc) + timedelta(minutes=2)
    db.commit()

    # ماک ارسال پیامک (در آینده اینجا به API کاوه نگار یا ملی پیامک وصل می‌شود)
    print(f"\n{'=' * 40}\n[SMS MOCK] ارسال مجدد کد تایید برای {user.phone_number}:\nکد: {otp}\n{'=' * 40}\n")

    return {"message": "کد تایید جدید با موفقیت به شماره شما ارسال شد."}


@router.get("/", response_model=List[schemas.UserResponse])
def get_all_users(
        skip: int = 0,
        limit: int = 50,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(RequirePermission("user:read"))
):
    """
    دریافت لیست تمامی کاربران (مخصوص مدیریت)
    """
    users = services.get_all_users(db, skip=skip, limit=limit)
    return users


@router.get("/me", response_model=schemas.UserMeResponse)
def get_current_user_info(
        current_user: models.User = Depends(get_current_active_user)
):
    """
    دریافت اطلاعات کاربری که لاگین کرده به همراه لیست دسترسی‌ها
    """
    # استخراج پرمیژن‌ها با استفاده از سرویسی که نوشتیم
    user_permissions = services.get_user_permissions(current_user)

    # مپ کردن دیتا با اسکیما
    return {
        "id": current_user.id,
        "full_name": current_user.full_name,
        "phone_number": current_user.phone_number,
        "is_active": current_user.is_active,
        "is_superuser": current_user.is_superuser,
        "permissions": user_permissions
    }
