# app/modules/index/router.py
from fastapi import APIRouter, Depends, Request, Form, HTTPException, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import Optional

from app.core.database import get_db
from app.modules.courses.services import get_courses
from app.modules.articles.services import get_articles, get_article_by_slug
from app.modules.gallery.services import get_gallery_items
from . import models, schemas

router = APIRouter()

# آدرس‌دهی پوشه قالب‌ها
templates = Jinja2Templates(directory="templates")


# ۱. رندر صفحه اصلی (Index)
@router.get("/", response_class=HTMLResponse)
def render_home_page(request: Request, db: Session = Depends(get_db)):
    featured_courses = get_courses(db, limit=3)
    latest_articles = get_articles(db, limit=3)

    # تغییر این خط: لیمیت را بردار یا مقدار بزرگی مثل 100 بگذار تا تمام عکس‌های گالری لود شوند
    gallery_images = get_gallery_items(db, limit=300)

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "courses": featured_courses,
            "articles": latest_articles,
            "gallery": gallery_images
        }
    )


# ۲. رندر صفحه آرشیو مقالات (Blog)
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


# ۳. رندر صفحه تکی مقاله (Single Blog) بر اساس Slug برای سئوی عالی
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


# ۴. دریافت فرم تماس با ما (ارسال به صورت Form URL-Encoded از فرانت)
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
