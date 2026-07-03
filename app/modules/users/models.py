# app/modules/users/models.py
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Table
from sqlalchemy.orm import relationship
from app.core.database import Base

# جدول واسط رابطه چندبه‌چند: کاربر <-> نقش
user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", Integer, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True)
)

# جدول واسط رابطه چندبه‌چند: نقش <-> دسترسی
role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", Integer, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", Integer, ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True)
)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String, nullable=False)
    phone_number = Column(String, unique=True, index=True, nullable=False)
    national_id = Column(String, unique=True, index=True,
                         nullable=True)  # برای کاربران احتمالی خارجی تهی‌پذیر در نظر گرفته شده
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)

    is_verified = Column(Boolean, default=False)
    otp_code = Column(String, nullable=True)
    otp_expire = Column(DateTime, nullable=True)

    is_superuser = Column(Boolean, default=False, nullable=False)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))
    current_session_id = Column(String, nullable=True)
    # روابط (Relationships)
    roles = relationship("Role", secondary=user_roles, back_populates="users")


class Role(Base):
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)  # مانند: admin, teacher, student
    description = Column(String, nullable=True)

    # روابط (Relationships)
    users = relationship("User", secondary=user_roles, back_populates="roles")
    permissions = relationship("Permission", secondary=role_permissions, back_populates="roles")


class Permission(Base):
    __tablename__ = "permissions"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)  # مانند: course:write, article:delete, gallery:upload
    description = Column(String, nullable=True)

    # روابط (Relationships)
    roles = relationship("Role", secondary=role_permissions, back_populates="permissions")
