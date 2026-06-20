# seed_data.py
import json
import os
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.modules.users.models import Permission

JSON_FILE_PATH = "permissions.json"


def seed_permissions():
    if not os.path.exists(JSON_FILE_PATH):
        print(f"❌ فایل {JSON_FILE_PATH} یافت نشد!")
        return

    db: Session = SessionLocal()
    try:
        print("⏳ شروع ثبت پرمیژن‌ها در PostgreSQL...")
        with open(JSON_FILE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        permissions_list = data.get("permissions", [])
        if not permissions_list:
            print("⚠️ هیچ پرمیژنی در فایل JSON یافت نشد!")
            return

        added_count = 0
        for perm_data in permissions_list:
            # بررسی اینکه آیا پرمیژن از قبل در دیتابیس هست یا نه
            existing_perm = db.query(Permission).filter(Permission.name == perm_data["name"]).first()

            if not existing_perm:
                new_perm = Permission(name=perm_data["name"], description=perm_data["description"])
                db.add(new_perm)
                added_count += 1
                print(f"✅ پرمیژن جدید ثبت شد: {perm_data['name']}")
            else:
                print(f"ℹ️ پرمیژن از قبل وجود دارد (پرش): {perm_data['name']}")

        db.commit()
        print(f"🎉 عملیات پایان یافت. {added_count} پرمیژن جدید به دیتابیس اضافه شد.")

    except Exception as e:
        db.rollback()
        print(f"❌ خطایی در حین ثبت پرمیژن‌ها رخ داد: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    seed_permissions()
