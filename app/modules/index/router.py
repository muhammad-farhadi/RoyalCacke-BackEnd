# app/modules/index/router.py
import os

from fastapi import APIRouter, Depends, Request, Form, HTTPException, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from fastapi.responses import FileResponse

from app.core.database import get_db
from app.modules.courses.services import get_courses
from app.modules.articles.services import get_articles, get_article_by_slug
from app.modules.gallery.services import get_gallery_items
from . import models, schemas

import jdatetime
from datetime import datetime

router = APIRouter()
templates = Jinja2Templates(directory="templates")
APK_FILE_PATH = "app/static/apps/RoyalCake.apk"


def to_jalali_filter(date_obj: datetime):
    if not date_obj:
        return ""
    jdate = jdatetime.datetime.fromgregorian(datetime=date_obj, locale='fa_IR')
    return jdate.strftime("%d %B %Y")


templates.env.filters["jalali"] = to_jalali_filter


@router.get("/", response_class=HTMLResponse)
def render_home_page(request: Request, db: Session = Depends(get_db)):
    featured_courses = get_courses(db, limit=3)
    latest_articles = get_articles(db, limit=3)

    gallery_images = get_gallery_items(db, limit=100)

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "courses": featured_courses,
            "articles": latest_articles,
            "gallery": gallery_images
        }
    )


@router.get("/blog", response_class=HTMLResponse)
def render_blog_archive(request: Request, skip: int = 0, limit: int = 9, db: Session = Depends(get_db)):
    all_articles = get_articles(db, skip=skip, limit=limit)
    return templates.TemplateResponse(
        request=request,
        name="blog.html",
        context={
            "articles": all_articles
        }
    )


@router.get("/blog/{slug}", response_class=HTMLResponse)
def render_single_article(request: Request, slug: str, db: Session = Depends(get_db)):
    article = get_article_by_slug(db, slug=slug)
    if not article:
        raise HTTPException(status_code=404, detail="مقاله یافت نشد")

    return templates.TemplateResponse(
        request=request,
        name="single-blog.html",
        context={
            "article": article
        }
    )


@router.post("/contact", status_code=status.HTTP_201_CREATED)
def handle_contact_submit(
        name: str = Form(...),
        phone_number: str = Form(...),
        message: str = Form(...),
        db: Session = Depends(get_db)
):
    # ولیدیشن دستی یا با pydantic
    try:
        form_data = schemas.ContactFormRequest(name=name, phone_number=phone_number, message=message)
    except Exception as e:
        raise HTTPException(status_code=400, detail="اطلاعات فرم معتبر نیست. شماره موبایل را بررسی کنید.")

    db_message = models.ContactMessage(**form_data.model_dump())
    db.add(db_message)
    db.commit()
    return {"success": True, "message": "پیام شما با موفقیت ثبت شد."}


@router.get("/course", response_class=HTMLResponse)
def render_courses_page(request: Request, db: Session = Depends(get_db)):
    """
    رندر کردن صفحه لیست تمامی دوره‌های آموزشی برای کاربران (فرانت‌اند)
    """
    # واکشی تمام دوره‌ها (می‌توانید limit را بردارید یا عدد بزرگی بدهید)
    all_courses = get_courses(db, limit=100)

    return templates.TemplateResponse(
        request=request,
        name="course.html",  # نام فایل قالب فرانت‌اند
        context={
            "courses": all_courses
        }
    )


@router.get("/course/{course_id}", response_class=HTMLResponse)
def render_single_course(request: Request, course_id: int, db: Session = Depends(get_db)):
    """
    رندر کردن صفحه داخلی یک دوره خاص (اگر قالبی برای آن دارید)
    """
    # توجه: برای این بخش شما نیاز به یک قالب مثلاً single-course.html دارید
    # فعلا برای جلوگیری از خطای 404 اگر کاربر روی "مشاهده دوره" کلیک کرد این روت را گذاشتیم
    from app.modules.courses.services import get_course_by_id
    course = get_course_by_id(db, course_id=course_id)
    if not course:
        raise HTTPException(status_code=404, detail="دوره یافت نشد")

    # اگر قالب single-course.html را فرانت کار زده، نام آن را اینجا بگذارید
    # در غیر این صورت فعلا به همان صفحه دوره‌ها برش می‌گردانیم یا پیام می‌دهیم
    return templates.TemplateResponse(
        request=request,
        name="course.html",  # موقتاً به همین صفحه هدایت شود تا زمانی که قالب تکی آماده شود
        context={
            "courses": [course]
        }
    )


@router.get("/download/android", response_class=FileResponse)
def download_android_apk():
    """
    روتر دانلود مستقیم آخرین نسخه اپلیکیشن اندروید رویال کیک
    """
    # ۱. بررسی فیزیکی وجود فایل روی سرور برای جلوگیری از کرش کردن سیستم
    if not os.path.exists(APK_FILE_PATH):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="فایل اپلیکیشن اندروید در حال حاضر روی سرور بارگذاری نشده است. لطفاً با پشتیبانی تماس بگیرید."
        )

    # ۲. تعیین نام فایل هنگام دانلود در گوشی کاربر
    download_filename = "RoyalCake.apk"

    # ۳. ارسال فایل به صورت دانلود مستقیم (Attachment)
    return FileResponse(
        path=APK_FILE_PATH,
        media_type="application/vnd.android.package-archive",
        filename=download_filename
    )
