# app/modules/articles/services.py
from sqlalchemy.orm import Session
from . import models, schemas


def get_articles(db: Session, skip: int = 0, limit: int = 10):
    # مقالات رو به ترتیب جدیدترین‌ها برمی‌گردونیم
    return db.query(models.Article).order_by(models.Article.created_at.desc()).offset(skip).limit(limit).all()


def get_article_by_slug(db: Session, slug: str):
    return db.query(models.Article).filter(models.Article.slug == slug).first()


def create_article(db: Session, article: schemas.ArticleCreate, author_id: int):
    # دیکشنری دیتای ورودی رو باز می‌کنیم و آیدی نویسنده رو بهش اضافه می‌کنیم
    db_article = models.Article(**article.model_dump(), author_id=author_id)
    db.add(db_article)
    db.commit()
    db.refresh(db_article)
    return db_article


def update_article(db: Session, article_id: int, article_in: schemas.ArticleUpdate):
    db_article = db.query(models.Article).filter(models.Article.id == article_id).first()
    if not db_article:
        return None

    # گرفتن دیتایی که کاربر فرستاده (فقط فیلدهایی که مقدار دارن)
    update_data = article_in.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_article, key, value)

    db.commit()
    db.refresh(db_article)
    return db_article


def delete_article(db: Session, article_id: int):
    db_article = db.query(models.Article).filter(models.Article.id == article_id).first()
    if db_article:
        db.delete(db_article)
        db.commit()
        return True
    return False
