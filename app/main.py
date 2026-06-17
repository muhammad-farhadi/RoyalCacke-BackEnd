# app/main.py
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.modules.users.router import router as users_router
from app.modules.articles.router import router as articles_router
from app.modules.gallery.router import router as gallery_router
from app.modules.courses.router import router as courses_router
from app.modules.index.router import router as index_router  # ایمپورت جدید

os.makedirs("app/static/gallery", exist_ok=True)
os.makedirs("app/static/courses/images", exist_ok=True)
os.makedirs("app/static/courses/videos", exist_ok=True)

app = FastAPI(
    title="Royal Cake Academy API",
    description="Backend services for the Academy Mobile App and Website",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

# اتصال روترها (روتر ایندکس بدون پیشوند متصل می‌شود تا روت‌های اصلی / و /blog رو مستقیم هندل کنه)
app.include_router(index_router, tags=["Website Index"])
app.include_router(users_router, prefix="/api/v1/users", tags=["Users"])
app.include_router(articles_router, prefix="/api/v1/articles", tags=["Articles"])
app.include_router(gallery_router, prefix="/api/v1/gallery", tags=["Gallery"])
app.include_router(courses_router, prefix="/api/v1/courses", tags=["Courses"])
