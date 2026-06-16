# app/core/database.py
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# آدرس دیتابیس (بعداً می‌تونی این رو از فایل .env بخونی)
# مثال برای PostgreSQL: "postgresql://user:password@localhost/dbname"
SQLALCHEMY_DATABASE_URL = "sqlite:///./academy.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    # این آرگومان فقط برای SQLite نیازه، برای دیتابیس‌های دیگه پاکش کن
    connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


# Dependency برای تزریق سشن دیتابیس توی روت‌ها
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
