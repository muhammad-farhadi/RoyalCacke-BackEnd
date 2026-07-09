# app/modules/highlights/router.py
from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, joinedload
from app.core.database import get_db
from app.modules.highlights.models import HighlightCategory
from app.modules.highlights.schemas import HighlightCategoryResponse

router = APIRouter()


@router.get("", response_model=List[HighlightCategoryResponse])
def get_all_highlights(db: Session = Depends(get_db)):
    # دریافت دسته‌بندی‌ها به همراه آیتم‌های داخل آن‌ها با استفاده از joinedload برای بهینه‌بودن کوئری
    categories = (
        db.query(HighlightCategory)
        .options(joinedload(HighlightCategory.items))
        .order_by(HighlightCategory.created_at.desc())
        .all()
    )
    return categories
