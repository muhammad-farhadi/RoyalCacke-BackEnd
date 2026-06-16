# app/main.py
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# ایمپورت کردن روترهای ماژول‌هایی که تا الان ساختیم
from app.modules.users.router import router as users_router
from app.modules.articles.router import router as articles_router
from app.modules.gallery.router import router as gallery_router

# اطمینان از وجود پوشه استاتیک برای جلوگیری از خطای احتمالی در زمان ران شدن اپلیکیشن
os.makedirs("app/static/gallery", exist_ok=True)

app = FastAPI(
    title="Royal Cake Academy API",
    description="Backend services for the Academy Mobile App and Website",
    version="1.0.0"
)

# تنظیمات CORS برای ارتباط بدون مشکل فرانت‌اند (وب) و کلاینت فلاتر (موبایل)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # در زمان پروداکشن، دامنه اصلی سایت رو اینجا قرار می‌دیم
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# متصل کردن پوشه استاتیک به روت /static برای سرو کردن مستقیم عکس‌ها
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/", tags=["Health Check"])
def root_check():
    return {"message": "Welcome to the Academy API. System is up and running!"}


# رجیستر کردن روترها با پیشوند و تگ‌های استاندارد
app.include_router(users_router, prefix="/api/v1/users", tags=["Users"])
app.include_router(articles_router, prefix="/api/v1/articles", tags=["Articles"])
app.include_router(gallery_router, prefix="/api/v1/gallery", tags=["Gallery"])
