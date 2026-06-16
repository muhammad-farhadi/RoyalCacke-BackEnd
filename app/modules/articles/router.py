# app/modules/articles/router.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.core.dependencies import RequirePermission
from app.modules.users.models import User
from . import schemas, services

router = APIRouter()


# ساخت مقاله (فقط کاربرانی که پرمیژن article:write دارن می‌تونن این روت رو صدا بزنن)
@router.post("/", response_model=schemas.ArticleResponse, status_code=status.HTTP_201_CREATED)
def create_new_article(
        article: schemas.ArticleCreate,
        db: Session = Depends(get_db),
        current_user: User = Depends(RequirePermission("article:write"))
):
    # بررسی یکتا بودن Slug
    if services.get_article_by_slug(db, slug=article.slug):
        raise HTTPException(status_code=400, detail="این Slug قبلاً استفاده شده است. لطفا آدرس دیگری انتخاب کنید.")

    return services.create_article(db=db, article=article, author_id=current_user.id)


# لیست مقالات (بدون نیاز به لاگین - پابلیک)
@router.get("/", response_model=List[schemas.ArticleResponse])
def read_all_articles(skip: int = 0, limit: int = 10, db: Session = Depends(get_db)):
    return services.get_articles(db, skip=skip, limit=limit)


# گرفتن یک مقاله با Slug (بدون نیاز به لاگین - پابلیک برای استفاده در فرانت‌اند و سئو)
@router.get("/{slug}", response_model=schemas.ArticleResponse)
def read_single_article(slug: str, db: Session = Depends(get_db)):
    article = services.get_article_by_slug(db, slug=slug)
    if not article:
        raise HTTPException(status_code=404, detail="مقاله مورد نظر یافت نشد.")
    return article


@router.put("/{article_id}", response_model=schemas.ArticleResponse)
def edit_article(
        article_id: int,
        article_in: schemas.ArticleUpdate,
        db: Session = Depends(get_db),
        current_user: User = Depends(RequirePermission("article:update"))
):
    # اگر اسلاگ جدید فرستاده شده، چک کنیم تکراری نباشه
    if article_in.slug:
        existing_article = services.get_article_by_slug(db, slug=article_in.slug)
        if existing_article and existing_article.id != article_id:
            raise HTTPException(status_code=400, detail="این Slug قبلاً استفاده شده است.")

    updated_article = services.update_article(db, article_id, article_in)
    if not updated_article:
        raise HTTPException(status_code=404, detail="مقاله یافت نشد.")
    return updated_article


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
