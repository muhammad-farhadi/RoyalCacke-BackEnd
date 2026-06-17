# app/modules/courses/models.py
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base


class Course(Base):
    __tablename__ = "courses"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    price = Column(Integer, default=0)  # به تومان
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


class Lesson(Base):
    __tablename__ = "lessons"

    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)

    # مسیر فایل استریم HLS (مانند: /static/videos/course_1/lesson_3/playlist.m3u8)
    video_url = Column(String, nullable=False)
    duration = Column(Integer, default=0)  # زمان این جلسه به دقیقه
    sort_order = Column(Integer, default=1)  # ترتیب نمایش ویدیوها (قسمت ۱، ۲ و...)
    is_free = Column(Boolean, default=False)  # آیا برای پیش‌نمایش رایگان است؟

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # رابطه معکوس با دوره
    course = relationship("Course", back_populates="lessons")
