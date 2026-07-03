# app/modules/courses/router.py
import os
import subprocess
import time
import shutil
from datetime import timedelta, datetime
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, BackgroundTasks, Query
from fastapi.responses import FileResponse
from jose import jwt
from sqlalchemy.orm import Session
from typing import List, Optional

from starlette.responses import PlainTextResponse

from app.core.database import get_db
# شما باید get_current_user را در فایل dependencies.py خود داشته باشید
from app.core.dependencies import RequirePermission, get_current_user
from app.modules.orders.models import Enrollment  # برای بررسی دسترسی کاربر به دوره
from app.modules.courses.models import Lesson, CourseReview  # برای کوئری مستقیم جلسات
from . import schemas, services
from .schemas import ReviewResponseSchema
from ..users.models import User
from ...admin import save_uploaded_file
from ...core.security import SECRET_KEY

router = APIRouter()

# --- تغییر ۱: تغییر مسیر ذخیره ویدیوها به یک پوشه خصوصی ---
IMAGE_UPLOAD_DIR = "app/static/courses/images"
PRIVATE_VIDEO_DIR = "app/private_assets/courses/videos"  # مسیر جدید و امن

os.makedirs(IMAGE_UPLOAD_DIR, exist_ok=True)
os.makedirs(PRIVATE_VIDEO_DIR, exist_ok=True)


# --- روت‌های پابلیک (موبایل و وب‌سایت) ---
def process_video_to_hls(input_video_path: str, output_dir: str):
    """
    این تابع توسط BackgroundTasks فراخوانی می‌شود.
    فایل MP4 خام را می‌گیرد و به یک فایل playlist.m3u8 و ده‌ها فایل .ts ده‌ثانیه‌ای تبدیل می‌کند.
    """
    playlist_path = os.path.join(output_dir, "playlist.m3u8")
    # نام‌گذاری تکه ویدیوها مثلا: segment_000.ts, segment_001.ts
    segment_path = os.path.join(output_dir, "segment_%03d.ts")

    # دستور استاندارد FFmpeg برای استریم VOD (Video On Demand)
    command = [
        "ffmpeg",
        "-i", input_video_path,
        "-profile:v", "baseline",  # سازگاری با اکثر دستگاه‌ها (موبایل و وب)
        "-level", "3.0",
        "-start_number", "0",
        "-hls_time", "10",  # طول هر تکه ویدیو ۱۰ ثانیه باشد
        "-hls_list_size", "0",  # 0 یعنی کل ویدیو در لیست بماند (برای استریم زنده نیست)
        "-hls_playlist_type", "vod",
        "-f", "hls",
        "-hls_segment_filename", segment_path,
        playlist_path
    ]

    try:
        # اجرای دستور تبدیل در پس‌زمینه
        subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        # پس از پایان موفقیت‌آمیز تبدیل، فایل خام MP4 را پاک می‌کنیم تا فضای سرور پر نشود
        if os.path.exists(input_video_path):
            os.remove(input_video_path)

        print(f"پردازش ویدیو با موفقیت تمام شد: {output_dir}")

    except subprocess.CalledProcessError as e:
        # در صورت بروز خطا (مثلا فایل خراب باشد)
        error_msg = e.stderr.decode()
        print(f"خطا در تبدیل ویدیو به HLS: {error_msg}")
        # در یک پروژه بزرگ‌تر، اینجا می‌توانید وضعیت رکورد دیتابیس را به "خطا در پردازش" تغییر دهید


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
        ticket: str = Query(...),  # <--- گرفتن تیکت از URL
        db: Session = Depends(get_db)
):
    # ۱. اعتبارسنجی بلیت ۳ ساعته
    try:
        payload = jwt.decode(ticket, SECRET_KEY, algorithms=["HS256"])
        if payload.get("lesson_id") != lesson_id:
            raise HTTPException(status_code=403, detail="بلیت متعلق به این ویدیو نیست")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="اعتبار بلیت تمام شده است")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="بلیت نامعتبر است")

    # ۲. پیدا کردن مسیر فایل ویدیو در پوشه خصوصی
    lesson = db.query(Lesson).filter(Lesson.id == lesson_id).first()
    safe_filename = os.path.basename(filename)
    video_path = os.path.join(PRIVATE_VIDEO_DIR, lesson.video_url, safe_filename)

    if not os.path.exists(video_path):
        raise HTTPException(status_code=404, detail="فایل ویدیو یافت نشد.")

    # ۳. جادوی اصلی: تزریق بلیت به داخل فایل m3u8
    if filename.endswith(".m3u8"):
        with open(video_path, "r", encoding="utf-8") as f:
            content = f.read()
        # اضافه کردن تیکت به انتهای نام فایل‌های ts.
        modified_content = content.replace(".ts", f".ts?ticket={ticket}")
        return PlainTextResponse(content=modified_content, media_type="application/x-mpegURL")

    # ۴. ارسال تکه‌های ویدیو
    if filename.endswith(".ts"):
        return FileResponse(path=video_path, media_type="video/MP2T")

    return FileResponse(path=video_path, media_type="application/octet-stream")


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
        background_tasks: BackgroundTasks,  # <--- این پارامتر حیاتی برای تسک‌های پس‌زمینه اضافه شد
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

    # ذخیره در پوشه امن
    lesson_folder_name = f"course_{course_id}_lesson_{int(time.time())}"
    lesson_dir = os.path.join(PRIVATE_VIDEO_DIR, lesson_folder_name)
    os.makedirs(lesson_dir, exist_ok=True)

    # ذخیره موقت فایل MP4 که ادمین آپلود کرده است
    temp_video_path = os.path.join(lesson_dir, "raw_video.mp4")
    with open(temp_video_path, "wb") as buffer:
        shutil.copyfileobj(video_file.file, buffer)

    # <--- تغییر اساسی: ارجاع تبدیل ویدیو به بک‌گراند تسک --->
    # ریکوئست منتظر پایان این تابع نمی‌ماند و فوراً ریسپانس ۲۰۰ را برمی‌گرداند
    background_tasks.add_task(process_video_to_hls, temp_video_path, lesson_dir)

    # ذخیره نام پوشه در دیتابیس
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


@router.get("/{lesson_id}/stream-ticket")
def get_stream_ticket(lesson_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    # ۱. پیدا کردن جلسه و بررسی دسترسی کاربر (دقیقاً مثل کدهای قبلی خودتون)
    lesson = db.query(Lesson).filter(Lesson.id == lesson_id).first()
    if not lesson:
        raise HTTPException(status_code=404, detail="جلسه یافت نشد.")

    if not lesson.is_free and not getattr(current_user, 'is_superuser', False):
        has_access = db.query(Enrollment).filter(
            Enrollment.user_id == current_user.id,
            Enrollment.course_id == lesson.course_id
        ).first()
        if not has_access:
            raise HTTPException(status_code=403, detail="دسترسی ندارید")

    # ۲. ساخت یک بلیت (JWT) موقت با اعتبار ۳ ساعت فقط برای همین ویدیو
    expire = datetime.utcnow() + timedelta(hours=3)
    ticket_payload = {
        "sub": str(current_user.id),
        "lesson_id": lesson_id,
        "exp": expire
    }
    ticket = jwt.encode(ticket_payload, SECRET_KEY, algorithm="HS256")

    return {"ticket": ticket}


# 🔴 ۱. روت دریافت نظرات تایید شده یک دوره
@router.get("/{course_id}/reviews", response_model=List[ReviewResponseSchema])
def get_course_reviews(course_id: int, db: Session = Depends(get_db)):
    reviews = (
        db.query(CourseReview)
        .filter(CourseReview.course_id == course_id, CourseReview.is_approved == True)
        .order_by(CourseReview.created_at.desc())
        .all()
    )
    return reviews


# 🔴 ۲. روت ثبت نظر جدید (مخصوص خریداران دوره + پشتیبانی از آپلود عکس)
@router.post("/{course_id}/reviews", status_code=status.HTTP_201_CREATED)
async def submit_course_review(
        course_id: int,
        content: str = Form(...),
        image: Optional[UploadFile] = File(None),
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    # الف) بررسی اینکه آیا کاربر واقعاً این دوره را خریده است؟
    has_purchased = db.query(Enrollment).filter(
        Enrollment.user_id == current_user.id,
        Enrollment.course_id == course_id
    ).first()

    if not has_purchased:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="شما دانشجوی این دوره نیستید و اجازه ثبت نظر ندارید."
        )

    # ب) هندل کردن آپلود عکس اختیاری نظر
    uploaded_image_url = None
    if image and image.filename:
        # ذخیره در پوشه تفکیک شده نظرات
        uploaded_image_url = await save_uploaded_file(image, "courses/reviews")

    # ج) ثبت در دیتابیس (به صورت پیش‌فرض تایید نشده است تا ادمین تایید کند)
    new_review = CourseReview(
        user_id=current_user.id,
        course_id=course_id,
        content=content,
        image_url=uploaded_image_url,
        is_approved=False
    )

    db.add(new_review)
    db.commit()

    return {"detail": "نظر شما با موفقیت ثبت شد و پس از تایید مدیریت نمایش داده می‌شود."}
