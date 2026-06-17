# app/modules/courses/router.py
import os
import time
import shutil
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import List, Optional

from app.core.database import get_db
from app.core.dependencies import RequirePermission
from . import schemas, services

router = APIRouter()

IMAGE_UPLOAD_DIR = "app/static/courses/images"
VIDEO_UPLOAD_DIR = "app/static/courses/videos"
os.makedirs(IMAGE_UPLOAD_DIR, exist_ok=True)
os.makedirs(VIDEO_UPLOAD_DIR, exist_ok=True)


# --- روت‌های پابلیک (موبایل و وب‌سایت) ---

@router.get("/", response_model=List[schemas.CourseResponse])
def read_all_courses(category: Optional[str] = None, skip: int = 0, limit: int = 10, db: Session = Depends(get_db)):
    return services.get_courses(db, category=category, only_published=True, skip=skip, limit=limit)


@router.get("/{course_id}", response_model=schemas.CourseResponse)
def read_single_course(course_id: int, db: Session = Depends(get_db)):
    course = services.get_course_by_id(db, course_id=course_id)
    if not course:
        raise HTTPException(status_code=404, detail="دوره آموزشی یافت نشد.")
    return course


# --- روت‌های مدیریت ادمین (Admin Panel) ---

# ایجاد دوره جدید (همراه با کاور)
@router.post("/", response_model=schemas.CourseResponse, status_code=status.HTTP_201_CREATED)
def create_new_course(
        title: str = Form(...),
        description: str = Form(...),
        price: int = Form(...),
        total_hours: int = Form(...),
        category: str = Form(...),
        level: Optional[str] = Form("مبتدی تا پیشرفته"),
        badge: Optional[str] = Form(None),
        image_file: UploadFile = File(...),
        db: Session = Depends(get_db),
        current_user=Depends(RequirePermission("course:write"))
):
    ext = image_file.filename.split(".")[-1].lower()
    if ext not in ["jpg", "jpeg", "png", "webp"]:
        raise HTTPException(status_code=400, detail="فرمت تصویر کاور مجاز نیست.")

    filename = f"cover_{int(time.time())}.{ext}"
    file_path = os.path.join(IMAGE_UPLOAD_DIR, filename)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(image_file.file, buffer)

    image_url = f"/static/courses/images/{filename}"

    course_data = schemas.CourseCreate(
        title=title, description=description, price=price,
        session_count=0, total_hours=total_hours, category=category,
        level=level, badge=badge
    )
    return services.create_course(db=db, course=course_data, image_url=image_url)


# آپلود ویدیو برای یک دوره (تبدیل به ساختار پوشه‌ای HLS ضد دانلود)
@router.post("/lessons", response_model=schemas.LessonResponse, status_code=status.HTTP_201_CREATED)
def add_video_to_course(
        course_id: int = Form(...),
        title: str = Form(...),
        description: Optional[str] = Form(None),
        duration: int = Form(...),
        sort_order: int = Form(1),
        is_free: bool = Form(False),
        video_file: UploadFile = File(...),  # ویدیو اصلی MP4 که ادمین آپلود میکنه
        db: Session = Depends(get_db),
        current_user=Depends(RequirePermission("course:write"))
):
    # ۱. بررسی وجود دوره
    course = services.get_course_by_id(db, course_id=course_id)
    if not course:
        raise HTTPException(status_code=404, detail="دوره مورد نظر یافت نشد.")

    # ۲. ایجاد پوشه اختصاصی HLS برای این قسمت از دوره جهت امنیت بیشتر
    lesson_folder_name = f"course_{course_id}_lesson_{int(time.time())}"
    lesson_dir = os.path.join(VIDEO_UPLOAD_DIR, lesson_folder_name)
    os.makedirs(lesson_dir, exist_ok=True)

    # ۳. منطق ساختار فایل ضد دانلود (HLS Stream Setup)
    # در پروژه عملی، این فایل MP4 در پس‌زمینه با ffmpeg به فایل‌های playlist.m3u8 و chunk.ts تبدیل میشه.
    # برای دمو، ما فایل اصلی رو ذخیره و آدرس صوری پلی‌لیست رو در دیتابیس ثبت می‌کنیم تا معماری فرانت و موبایل آماده باشه.
    mock_playlist_path = os.path.join(lesson_dir, "playlist.m3u8")

    # ذخیره موقت فایل (اینجا برای تست فایل ام پی ۴ ذخیره میشه)
    temp_video_path = os.path.join(lesson_dir, "raw_video.mp4")
    with open(temp_video_path, "wb") as buffer:
        shutil.copyfileobj(video_file.file, buffer)

    # ساخت یک فایل متنی فیک m3u8 جهت بالا نیامدن خطای ۴۰۴ در کلاینت
    with open(mock_playlist_path, "w") as f:
        f.write("#EXTM3U\n#EXT-X-VERSION:3\n# MOCK HLS PLAYLIST FOR SECURITY")

    video_url = f"/static/courses/videos/{lesson_folder_name}/playlist.m3u8"

    lesson_data = schemas.LessonCreate(
        course_id=course_id, title=title, description=description,
        duration=duration, sort_order=sort_order, is_free=is_free
    )
    return services.create_lesson(db=db, lesson=lesson_data, video_url=video_url)


# حذف دوره به همراه کل پوشه ویدیوها و کاورها
@router.delete("/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_course(course_id: int, db: Session = Depends(get_db),
                  current_user=Depends(RequirePermission("course:delete"))):
    course = services.get_course_by_id(db, course_id=course_id)
    if not course:
        raise HTTPException(status_code=404, detail="دوره یافت نشد.")

    # حذف فیزیکی کاور
    if course.image_url:
        img_path = f"app{course.image_url}"
        if os.path.exists(img_path):
            os.remove(img_path)

    # حذف فیزیکی تمام پوشه‌های ویدیوهای زیرمجموعه دوره
    for lesson in course.lessons:
        # استخراج پوشه والد فایل m3u8
        lesson_dir = os.path.dirname(f"app{lesson.video_url}")
        if os.path.exists(lesson_dir):
            shutil.rmtree(lesson_dir)

    services.delete_course(db, course_id)
    return None
