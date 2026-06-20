# app/modules/articles/router.py
import os
import shutil
import uuid

from fastapi import APIRouter, Depends, Form, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from typing import List, Optional

from app.core.database import get_db
from app.core.dependencies import RequirePermission
from app.modules.users.models import User
from . import schemas, services

router = APIRouter()
os.makedirs("app/static/blog", exist_ok=True)


# ساخت مقاله (ترکیب دریافت متن و عکس به صورت فرم)
@router.post("/", response_model=schemas.ArticleResponse, status_code=status.HTTP_201_CREATED)
def create_new_article(
        title: str = Form(...),
        slug: str = Form(...),
        content: str = Form(...),
        meta_description: Optional[str] = Form(None),
        tags: Optional[str] = Form(None),
        image: Optional[UploadFile] = File(None),  # عکس اختیاری است
        db: Session = Depends(get_db),
        current_user: User = Depends(RequirePermission("article:write"))
):
    # ۱. بررسی یکتا بودن Slug
    if services.get_article_by_slug(db, slug=slug):
        raise HTTPException(status_code=400, detail="این Slug قبلاً استفاده شده است. لطفا آدرس دیگری انتخاب کنید.")

    # ۲. پردازش و ذخیره عکس (در صورت ارسال)
    image_url = None
    if image and image.filename:
        allowed_extensions = [".jpg", ".jpeg", ".png", ".webp"]
        ext = os.path.splitext(image.filename)[1].lower()
        if ext not in allowed_extensions:
            raise HTTPException(status_code=400, detail="فرمت عکس نامعتبر است. فقط jpg, png و webp مجاز هستند.")

        unique_filename = f"{uuid.uuid4().hex}{ext}"
        file_path = os.path.join("app/static/blog", unique_filename)

        try:
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(image.file, buffer)
            image_url = f"/static/blog/{unique_filename}"
        except Exception as e:
            raise HTTPException(status_code=500, detail="خطا در ذخیره‌سازی عکس روی سرور")

    # ۳. جمع‌آوری اطلاعات و ساخت اسکیما برای ارسال به سرویس
    article_data = schemas.ArticleCreate(
        title=title,
        slug=slug,
        content=content,
        meta_description=meta_description,
        tags=tags,
        image_url=image_url
    )

    return services.create_article(db=db, article=article_data, author_id=current_user.id)


@router.put("/{article_id}", response_model=schemas.ArticleResponse)
def edit_article(
        article_id: int,
        title: Optional[str] = Form(None),
        slug: Optional[str] = Form(None),
        content: Optional[str] = Form(None),
        meta_description: Optional[str] = Form(None),
        tags: Optional[str] = Form(None),
        image: Optional[UploadFile] = File(None),  # در صورت ارسال، جایگزین عکس قبلی می‌شود
        db: Session = Depends(get_db),
        current_user: User = Depends(RequirePermission("article:update"))
):
    # بررسی تکراری نبودن اسلاگ جدید
    if slug:
        existing_article = services.get_article_by_slug(db, slug=slug)
        if existing_article and existing_article.id != article_id:
            raise HTTPException(status_code=400, detail="این Slug قبلاً استفاده شده است.")

    # پردازش عکس جدید در صورت ارسال
    image_url = None
    if image and image.filename:
        allowed_extensions = [".jpg", ".jpeg", ".png", ".webp"]
        ext = os.path.splitext(image.filename)[1].lower()
        if ext not in allowed_extensions:
            raise HTTPException(status_code=400, detail="فرمت عکس نامعتبر است.")

        unique_filename = f"{uuid.uuid4().hex}{ext}"
        file_path = os.path.join("app/static/blog", unique_filename)

        try:
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(image.file, buffer)
            image_url = f"/static/blog/{unique_filename}"
        except Exception:
            raise HTTPException(status_code=500, detail="خطا در ذخیره‌سازی عکس روی سرور")

    # ساخت آبجکت آپدیت
    article_update_data = schemas.ArticleUpdate(
        title=title,
        slug=slug,
        content=content,
        meta_description=meta_description,
        tags=tags,
        image_url=image_url
    )

    updated_article = services.update_article(db, article_id, article_update_data)
    if not updated_article:
        raise HTTPException(status_code=404, detail="مقاله یافت نشد.")
    return updated_article


# لیست مقالات (بدون نیاز به لاگین - پابلیک)
@router.get("/", response_model=List[schemas.ArticleResponse])
def read_all_articles(skip: int = 0, limit: int = 10, db: Session = Depends(get_db)):
    return services.get_articles(db, skip=skip, limit=limit)


# گرفتن یک مقاله با Slug
@router.get("/{slug}", response_model=schemas.ArticleResponse)
def read_single_article(slug: str, db: Session = Depends(get_db)):
    article = services.get_article_by_slug(db, slug=slug)
    if not article:
        raise HTTPException(status_code=404, detail="مقاله مورد نظر یافت نشد.")
    return article


@router.delete("/{article_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_article(
        article_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(RequirePermission("article:delete"))
):
    success = services.delete_article(db, article_id)
    if not success:
        raise HTTPException(status_code=404, detail="مقاله یافت نشد.")
    return None
