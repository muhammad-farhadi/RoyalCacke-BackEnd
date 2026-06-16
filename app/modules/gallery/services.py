# app/modules/gallery/services.py
from sqlalchemy.orm import Session
from . import models


def get_gallery_items(db: Session, category: str = None, skip: int = 0, limit: int = 12):
    query = db.query(models.GalleryItem)
    if category:
        query = query.filter(models.GalleryItem.category == category)
    return query.order_by(models.GalleryItem.created_at.desc()).offset(skip).limit(limit).all()


def create_gallery_item(db: Session, title: str, image_url: str, alt_text: str, category: str):
    db_item = models.GalleryItem(
        title=title,
        image_url=image_url,
        alt_text=alt_text,
        category=category
    )
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item


def delete_gallery_item(db: Session, item_id: int):
    db_item = db.query(models.GalleryItem).filter(models.GalleryItem.id == item_id).first()
    if db_item:
        db.delete(db_item)
        db.commit()
        return db_item
    return None
