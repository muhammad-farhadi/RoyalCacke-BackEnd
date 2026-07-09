# app/core/dependencies.py
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import SECRET_KEY, ALGORITHM
from app.modules.users import models

# روت لاگین رو به Swagger معرفی می‌کنیم
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/users/login")


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="توکن نامعتبر است یا منقضی شده.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        phone_number: str = payload.get("sub")
        # 🔴 دریافت شناسه سشن از اکسس توکن فرستاده شده
        token_session_id: str = payload.get("session_id")

        if phone_number is None or token_session_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(models.User).filter(models.User.phone_number == phone_number).first()
    if user is None:
        raise credentials_exception

    # 🔴 ۵. اصلی‌ترین بخش کنترل: مقایسه سشنِ توکن با سشنِ زنده دیتابیس
    if user.current_session_id != token_session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="سشن شما به دلیل ورود دستگاه جدید منقضی شده است.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


def get_current_active_user(current_user: models.User = Depends(get_current_user)):
    # نکته: اگر فیلد is_verified رو در مدل‌ها حذف کردی، اینجا هم باید پاکش کنی.
    # اگر هنوز هست که هیچی، همین خط درسته.
    if not current_user.is_active or getattr(current_user, 'is_verified', False) == False:
        raise HTTPException(status_code=400, detail="حساب کاربری غیرفعال یا تایید نشده است.")
    return current_user


# کلاس بررسی دینامیک پرمیژن‌ها
class RequirePermission:
    def __init__(self, required_permission: str):
        self.required_permission = required_permission

    def __call__(self, current_user: models.User = Depends(get_current_active_user)):
        # --- بخش اضافه شده: بررسی مدیر کل (سوپریوزر) ---
        # اگر کاربر سوپریوزر بود، بدون چک کردن پرمیژن‌ها، اجازه عبور می‌دهیم
        if current_user.is_superuser:
            return current_user
        # -----------------------------------------------

        user_permissions = set()
        for role in current_user.roles:
            for perm in role.permissions:
                user_permissions.add(perm.name)

        if self.required_permission not in user_permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="شما دسترسی لازم برای این عملیات را ندارید."
            )
        return current_user
