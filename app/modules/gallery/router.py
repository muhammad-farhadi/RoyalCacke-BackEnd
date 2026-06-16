# app/modules/gallery/router.py
import os
import time
import shutil
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import List, Optional

from app.core.database import get_db
from app.core.dependencies import RequirePermission
from . import schemas, services

router = APIRouter()

# مسیر ذخیره فیزیکی فایل‌ها
UPLOAD_DIR = "app/static/gallery"
os.makedirs(UPLOAD_DIR, exist_ok=True)


# روت آپلود عکس (فقط ادمین با پرمیژن gallery:write)
@router.post("/", response_model=schemas.GalleryResponse, status_code=status.HTTP_201_CREATED)
def upload_image(
        title: str = Form(...),
        alt_text: Optional[str] = Form(None),
        category: Optional[str] = Form(None),
        file: UploadFile = File(...),
        db: Session = Depends(get_db),
        current_user=Depends(RequirePermission("gallery:write"))
):
    # ۱. بررسی پسوند فایل برای امنیت بیشتر
    allowed_extensions = ["jpg", "jpeg", "png", "webp"]
    file_ext = file.filename.split(".")[-1].lower()
    if file_ext not in allowed_extensions:
        raise HTTPException(status_code=400, detail="فرمت فایل نامعتبر است. فقط تصاویر مجاز هستند.")

    # ۲. تولید نام یکتا برای فایل جهت جلوگیری از Overwrite شدن تصاویر هم‌نام
    filename = f"{int(time.time())}_{file.filename}"
    file_path = os.path.join(UPLOAD_DIR, filename)

    # ۳. ذخیره فایل روی دیسک سرور
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # ۴. ست کردن آدرس URL برای دسترسی کلاینت (فرانت و موبایل)
    image_url = f"/static/gallery/{filename}"

    # ۵. ذخیره اطلاعات در دیتابیس
    return services.create_gallery_item(
        db=db, title=title, image_url=image_url, alt_text=alt_text, category=category
    )


# روت عمومی دریافت تصاویر گالری (بدون نیاز به لاگین)
@router.get("/", response_model=List[schemas.GalleryResponse])
def read_gallery(
        category: Optional[str] = None,
        skip: int = 0,
        limit: int = 12,
        db: Session = Depends(get_db)
):
    return services.get_gallery_items(db, category=category, skip=skip, limit=limit)


# روت حذف عکس از دیتابیس و دیسک (فقط ادمین با پرمیژن gallery:delete)
@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_gallery_item(
        item_id: int,
        db: Session = Depends(get_db),
        current_user=Depends(RequirePermission("gallery:delete"))
):
    deleted_item = services.delete_gallery_item(db, item_id)
    if not deleted_item:
        raise HTTPException(status_code=404, detail="آیتم مورد نظر در گالری یافت نشد.")

    # حذف فیزیکی فایل از روی هارد سرور
    # تبدیل آدرس URL به مسیر فیزیکی سیستم
    relative_path = f"app{deleted_item.image_url}"
    if os.path.exists(relative_path):
        os.remove(relative_path)

    return None
