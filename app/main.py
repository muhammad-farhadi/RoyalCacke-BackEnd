# app/main.py
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.responses import Response

# ۱. این کلاس را برای ساخت میدل‌ور ایمپورت کنید
from starlette.middleware.base import BaseHTTPMiddleware

from app.modules.users.router import router as users_router
from app.modules.articles.router import router as articles_router
from app.modules.gallery.router import router as gallery_router
from app.modules.courses.router import router as courses_router
from app.modules.index.router import router as index_router
from app.modules.orders.router import router as order_router
from app.modules.support.router import router as support_router
from app.modules.highlights.router import router as highlights_router

from app.admin import init_admin

os.makedirs("app/static/gallery", exist_ok=True)
os.makedirs("app/static/courses/images", exist_ok=True)
os.makedirs("app/static/courses/videos", exist_ok=True)
os.makedirs("app/static/highlights", exist_ok=True)
app = FastAPI(
    title="Royal Cake Academy API",
    description="Backend services for the Academy Mobile App and Website",
    version="1.0.0"
)


# =========================================================================
# ۲. این میدل‌ور را اضافه کنید تا فست‌ای‌پی‌آی را پشت CDN مجبور به HTTPS کند
# =========================================================================
class ForceHTTPSMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        # تغییر دستی پروتکل ریکوئست به https برای گول زدن تابع url_for
        request.scope["scheme"] = "https"
        response = await call_next(request)
        return response


# ثبت میدل‌ور در اپلیکیشن (ترجیحاً اولین میدل‌ور باشد)
app.add_middleware(ForceHTTPSMiddleware)

# میدل‌ور قبلی شما برای CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class CORSStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope) -> Response:
        response = await super().get_response(path, scope)
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "*"
        return response


# استفاده از نام app_static برای جلوگیری از تداخل با استاتیک‌های داخلی sqladmin
app.mount("/static", CORSStaticFiles(directory="app/static"), name="app_static")

# راه‌اندازی پنل ادمین
init_admin(app)

# اتصال روترها
app.include_router(index_router, tags=["Website Index"])
app.include_router(users_router, prefix="/api/v1/users", tags=["Users"])
app.include_router(articles_router, prefix="/api/v1/articles", tags=["Articles"])
app.include_router(gallery_router, prefix="/api/v1/gallery", tags=["Gallery"])
app.include_router(courses_router, prefix="/api/v1/courses", tags=["Courses"])
app.include_router(order_router, prefix="/api/v1/orders", tags=["Orders"])
app.include_router(support_router, prefix="/api/v1/support", tags=["Support Chat"])
app.include_router(highlights_router, prefix="/api/v1/highlights", tags=["Highlights"])
