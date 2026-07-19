# app/modules/courses/models.py
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base


class CourseImage(Base):
    __tablename__ = "course_images"

    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    image_url = Column(String, nullable=False)  # آدرس عکس فرعی آلبوم
    created_at = Column(DateTime, default=datetime.utcnow)

    # رابطه با جدول دوره
    course = relationship("Course", back_populates="images")


class Course(Base):
    __tablename__ = "courses"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    price = Column(Integer, default=0)  # به تومان

    # 🔴 ستون‌های جدید برای مدیریت تخفیف‌های زمان‌دار
    discount_price = Column(Integer, nullable=True)  # به تومان
    discount_start = Column(DateTime, nullable=True)  # تاریخ و ساعت شروع
    discount_end = Column(DateTime, nullable=True)  # تاریخ و ساعت پایان

    session_count = Column(Integer, default=0)  # تعداد کل جلسات
    total_hours = Column(Integer, default=0)  # مجموع زمان دوره
    category = Column(String, index=True, nullable=False)  # کیک، چیزکیک، شیرینی
    level = Column(String, default="مبتدی تا پیشرفته")
    image_url = Column(String, nullable=True)  # کاور دوره
    badge = Column(String, nullable=True)  # مثل: محبوب‌ترین
    is_published = Column(Boolean, default=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    # رابطه با جلسات دوره (در صورت حذف دوره، تمام ویدیوها هم حذف می‌شوند)
    lessons = relationship("Lesson", back_populates="course", cascade="all, delete-orphan")
    documents = relationship("CourseDocument", back_populates="course", cascade="all, delete-orphan")
    images = relationship("CourseImage", back_populates="course", cascade="all, delete-orphan")

    # 🔴 پراپرتی هوشمند برای سنجش لحظه‌ای وضعیت تخفیف بر اساس زمان UTC سرور
    @property
    def is_discount_active(self) -> bool:
        if not self.discount_price or not self.discount_start or not self.discount_end:
            return False

        now = datetime.now(timezone.utc)

        # هماهنگ‌سازی زون زمانی برای مقایسه دقیق دیتابیس
        start = self.discount_start.replace(
            tzinfo=timezone.utc) if self.discount_start.tzinfo is None else self.discount_start
        end = self.discount_end.replace(tzinfo=timezone.utc) if self.discount_end.tzinfo is None else self.discount_end

        return start <= now <= end

    # 🔴 پراپرتی هوشمند جهت بازگرداندن قیمت نهایی و قابل پرداخت در این ثانیه
    @property
    def final_price(self) -> int:
        if self.is_discount_active:
            return self.discount_price
        return self.price

    def __str__(self):
        return self.title


class CourseDocument(Base):
    __tablename__ = "course_documents"

    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    title = Column(String, nullable=False)
    file_name = Column(String, nullable=False)
    cover_url = Column(String, nullable=True)  # 🔴 اضافه شدن این خط برای ذخیره عکس کاور فایل
    created_at = Column(DateTime, default=datetime.utcnow)

    course = relationship("Course", back_populates="documents")

    def __str__(self):
        return self.title


class Lesson(Base):
    __tablename__ = "lessons"

    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)

    video_url = Column(String, nullable=False)
    duration = Column(Integer, default=0)
    sort_order = Column(Integer, default=1)
    is_free = Column(Boolean, default=False)

    video_status = Column(String, default="pending", nullable=False)

    cover_url = Column(String, nullable=True)
    caption = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # رابطه معکوس با دوره
    course = relationship("Course", back_populates="lessons")

    def __str__(self):
        return self.title


class CourseReview(Base):
    __tablename__ = "course_reviews"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)

    content = Column(Text, nullable=False)  # متن نظر هنرجو
    image_url = Column(String, nullable=True)  # عکس ضمیمه نظر (اختیاری)
    is_approved = Column(Boolean, default=False, nullable=False)  # وضعیت تایید ادمین

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # روابط (Relationships)
    user = relationship("User")
    course = relationship("Course")

    def __str__(self):
        return f"{self.user.full_name}-{self.course.name}"
