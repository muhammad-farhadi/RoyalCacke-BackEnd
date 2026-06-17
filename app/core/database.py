# app/core/database.py
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# فرمت: postgresql://[user]:[password]@[host]:[port]/[database_name]
SQLALCHEMY_DATABASE_URL = "postgresql://postgres:12345mfe@localhost:5432/royalcake_db"

# در پستگرس نیازی به check_same_thread نیست
engine = create_engine(SQLALCHEMY_DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
