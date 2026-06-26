# app/modules/courses/router.py
import os
import time
import shutil
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List, Optional

from app.core.database import get_db
# شما باید get_current_user را در فایل dependencies.py خود داشته باشید
from app.core.dependencies import RequirePermission, get_current_user
from app.modules.orders.models import Enrollment  # برای بررسی دسترسی کاربر به دوره
from app.modules.courses.models import Lesson  # برای کوئری مستقیم جلسات
from . import schemas, services

router = APIRouter()

# --- تغییر ۱: تغییر مسیر ذخیره ویدیوها به یک پوشه خصوصی ---
IMAGE_UPLOAD_DIR = "app/static/courses/images"
PRIVATE_VIDEO_DIR = "app/private_assets/courses/videos"  # مسیر جدید و امن

os.makedirs(IMAGE_UPLOAD_DIR, exist_ok=True)
os.makedirs(PRIVATE_VIDEO_DIR, exist_ok=True)


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


# --- روت استریم و پخش ویدیو (تغییر ۳: اضافه شده برای فلاتر) ---
@router.get("/{lesson_id}/stream/{filename}")
def stream_course_video(
        lesson_id: int,
        filename: str,
        db: Session = Depends(get_db),
        current_user=Depends(get_current_user)  # نیازمند ارسال توکن از سمت فلاتر
):
    # ۱. پیدا کردن جلسه
    lesson = db.query(Lesson).filter(Lesson.id == lesson_id).first()
    if not lesson:
        raise HTTPException(status_code=404, detail="جلسه یافت نشد.")

    # ۲. بررسی خرید دوره (اگر رایگان نیست و کاربر ادمین نیست)
    if not lesson.is_free and not getattr(current_user, 'is_superuser', False):
        has_access = db.query(Enrollment).filter(
            Enrollment.user_id == current_user.id,
            Enrollment.course_id == lesson.course_id
        ).first()

        if not has_access:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="لطفاً ابتدا دوره را خریداری کنید."
            )

    # ۳. پیدا کردن فایل در پوشه خصوصی بر اساس video_url که نام پوشه را نگه میدارد
    # جلوگیری از directory traversal attacks
    safe_filename = os.path.basename(filename)
    video_path = os.path.join(PRIVATE_VIDEO_DIR, lesson.video_url, safe_filename)

    if not os.path.exists(video_path) or not os.path.isfile(video_path):
        raise HTTPException(status_code=404, detail="فایل ویدیو یافت نشد.")

    # ۴. تعیین Media Type برای HLS
    if filename.endswith(".m3u8"):
        media_type = "application/x-mpegURL"
    elif filename.endswith(".ts"):
        media_type = "video/MP2T"
    else:
        media_type = "application/octet-stream"

    # ارسال امن فایل بدون اینکه کاربر بتواند آن را مستقیما با IDM دانلود کند
    return FileResponse(path=video_path, media_type=media_type)


# --- روت‌های مدیریت ادمین (Admin Panel) ---

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


# --- تغییر ۲: اصلاح روت آپلود ویدیو ---
@router.post("/lessons", response_model=schemas.LessonResponse, status_code=status.HTTP_201_CREATED)
def add_video_to_course(
        course_id: int = Form(...),
        title: str = Form(...),
        description: Optional[str] = Form(None),
        duration: int = Form(...),
        sort_order: int = Form(1),
        is_free: bool = Form(False),
        video_file: UploadFile = File(...),
        db: Session = Depends(get_db),
        current_user=Depends(RequirePermission("course:write"))
):
    course = services.get_course_by_id(db, course_id=course_id)
    if not course:
        raise HTTPException(status_code=404, detail="دوره مورد نظر یافت نشد.")

    # ذخیره در پوشه امن (PRIVATE_VIDEO_DIR)
    lesson_folder_name = f"course_{course_id}_lesson_{int(time.time())}"
    lesson_dir = os.path.join(PRIVATE_VIDEO_DIR, lesson_folder_name)
    os.makedirs(lesson_dir, exist_ok=True)

    mock_playlist_path = os.path.join(lesson_dir, "playlist.m3u8")
    temp_video_path = os.path.join(lesson_dir, "raw_video.mp4")

    with open(temp_video_path, "wb") as buffer:
        shutil.copyfileobj(video_file.file, buffer)

    with open(mock_playlist_path, "w") as f:
        f.write("#EXTM3U\n#EXT-X-VERSION:3\n# MOCK HLS PLAYLIST FOR SECURITY")

    # مهم: به جای آدرس پابلیک، فقط نام پوشه را در دیتابیس ذخیره می‌کنیم
    # تا اندپوینت استریم بتواند پوشه را پیدا کند
    video_folder_reference = lesson_folder_name

    lesson_data = schemas.LessonCreate(
        course_id=course_id, title=title, description=description,
        duration=duration, sort_order=sort_order, is_free=is_free
    )
    return services.create_lesson(db=db, lesson=lesson_data, video_url=video_folder_reference)


# --- تغییر ۴: اصلاح روت حذف برای پوشه خصوصی ---
@router.delete("/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_course(course_id: int, db: Session = Depends(get_db),
                  current_user=Depends(RequirePermission("course:delete"))):
    course = services.get_course_by_id(db, course_id=course_id)
    if not course:
        raise HTTPException(status_code=404, detail="دوره یافت نشد.")

    if course.image_url:
        img_path = f"app{course.image_url}"
        if os.path.exists(img_path):
            os.remove(img_path)

    # حذف فایل‌ها از پوشه خصوصی
    for lesson in course.lessons:
        # چون حالا video_url فقط نام پوشه است
        lesson_dir = os.path.join(PRIVATE_VIDEO_DIR, lesson.video_url)
        if os.path.exists(lesson_dir):
            shutil.rmtree(lesson_dir)

    services.delete_course(db, course_id)
    return None
