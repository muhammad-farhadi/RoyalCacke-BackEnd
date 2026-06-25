# app/modules/users/schemas.py
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
from datetime import datetime


# اسکیماهای مربوط به پرمیژن‌ها
class PermissionBase(BaseModel):
    name: str
    description: Optional[str] = None


class PermissionResponse(PermissionBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


# اسکیماهای مربوط به نقش‌ها
class RoleBase(BaseModel):
    name: str
    description: Optional[str] = None


class RoleResponse(RoleBase):
    id: int
    permissions: List[PermissionResponse] = []
    model_config = ConfigDict(from_attributes=True)


# اسکیماهای مربوط به کاربر
class UserBase(BaseModel):
    full_name: str
    phone_number: str = Field(..., pattern=r"^09\d{9}$", description="شماره موبایل معتبر ایران")


class UserCreate(UserBase):
    password: str = Field(..., min_length=4, max_length=50)


class UserResponse(UserBase):
    id: int
    is_active: bool
    is_superuser: bool
    roles: List[RoleResponse] = []
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class VerifyOTP(BaseModel):
    phone_number: str
    otp_code: str


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    phone_number: str


class ResetPasswordRequest(BaseModel):
    phone_number: str
    otp_code: str
    new_password: str = Field(..., min_length=6)


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    phone_number: Optional[str] = Field(None, pattern=r"^09\d{9}$")
    password: Optional[str] = Field(None, min_length=6, description="تغییر رمز عبور توسط ادمین")
    is_active: Optional[bool] = None
    is_verified: Optional[bool] = None  # ادمین بتونه یوزر رو دستی تایید کنه


class ResendOTPRequest(BaseModel):
    phone_number: str


class UserMeResponse(UserBase):
    id: int
    is_active: bool
    is_superuser: bool
    permissions: List[str] = []

    model_config = ConfigDict(from_attributes=True)
