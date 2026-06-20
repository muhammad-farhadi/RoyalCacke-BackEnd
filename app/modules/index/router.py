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

import jdatetime
from datetime import datetime

router = APIRouter()
templates = Jinja2Templates(directory="templates")


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
