# app/modules/courses/schemas.py
from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime


# --- اسکیماهای مربوط به جلسات (ویدیوها) ---
class LessonBase(BaseModel):
    title: str
    description: Optional[str] = None
    duration: int
    sort_order: int = 1
    is_free: bool = False


class LessonCreate(LessonBase):
    course_id: int


class LessonResponse(LessonBase):
    id: int
    course_id: int
    video_url: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- اسکیماهای مربوط به خود دوره ---
class CourseBase(BaseModel):
    title: str
    description: str
    price: int
    session_count: int
    total_hours: int
    category: str
    level: Optional[str] = "مبتدی تا پیشرفته"
    badge: Optional[str] = None
    is_published: Optional[bool] = True


class CourseCreate(CourseBase):
    pass


class CourseUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    price: Optional[int] = None
    session_count: Optional[int] = None
    total_hours: Optional[int] = None
    category: Optional[str] = None
    level: Optional[str] = None
    badge: Optional[str] = None
    is_published: Optional[bool] = None


# خروجی کامل دوره به همراه لیست ویدیوها
class CourseResponse(CourseBase):
    id: int
    image_url: Optional[str] = None
    lessons: List[LessonResponse] = []  # تزریق خودکار ویدیوها به دوره
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReviewUserSchema(BaseModel):
    full_name: str

    class Config:
        from_attributes = True


# خروجی نهایی برای نمایش به بقیه
class ReviewResponseSchema(BaseModel):
    id: int
    content: str
    image_url: Optional[str] = None
    created_at: datetime
    user: ReviewUserSchema  # برای اینکه فرانت نام نویسنده را داشته باشد

    class Config:
        from_attributes = True
