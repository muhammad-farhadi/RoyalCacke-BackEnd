# populate_gallery.py
import os
import shutil
import time
from app.core.database import SessionLocal
from app.modules.gallery.models import GalleryItem

# مسیرهای مبدا (فایل‌های سنگین فرانت)
SOURCE_DIRS = {
    "cake": "app/static/img/cake/gallery",
    "cheesecake": "app/static/img/cheesecake/gallery",
    "pastry": "app/static/img/sweet/gallery"  # در فرانت شیرینی‌ها در sweet هستند
}

# مسیر مقصد (پوشه استاندارد گالری در بک‌اند)
DEST_DIR = "app/static/gallery"
os.makedirs(DEST_DIR, exist_ok=True)


def populate_gallery():
    db = SessionLocal()
    added_count = 0

    try:
        for category, source_path in SOURCE_DIRS.items():
            if not os.path.exists(source_path):
                print(f"[WARNING] مسیر {source_path} یافت نشد. پرش از این دسته...")
                continue

            for filename in os.listdir(source_path):
                # فیلتر کردن فرمت‌های معتبر
                if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
                    old_file_path = os.path.join(source_path, filename)

                    # تولید نام یکتا برای جلوگیری از تداخل اسم‌ها
                    new_filename = f"{category}_{int(time.time() * 1000)}_{filename}"
                    new_file_path = os.path.join(DEST_DIR, new_filename)

                    # کپی فایل به مسیر اصلی
                    shutil.copy2(old_file_path, new_file_path)

                    # ذخیره در دیتابیس پستگرس
                    image_url = f"/static/gallery/{new_filename}"
                    title = filename.split('.')[0].replace('_', ' ').replace('-', ' ')  # ساخت تایتل از اسم فایل

                    new_item = GalleryItem(
                        title=title,
                        image_url=image_url,
                        category=category,
                        alt_text=f"تصویر {title} از دسته {category}"
                    )
                    db.add(new_item)
                    added_count += 1

        db.commit()
        print(f"\n[SUCCESS] تعداد {added_count} تصویر با موفقیت به پستگرس و پوشه اصلی گالری منتقل شد!")

    except Exception as e:
        db.rollback()
        print(f"[ERROR] خطایی رخ داد: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    populate_gallery()