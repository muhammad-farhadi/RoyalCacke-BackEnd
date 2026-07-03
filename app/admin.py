# app/admin.py
import os
from markupsafe import Markup
import uuid
from sqladmin import Admin, ModelView
from sqladmin.authentication import AuthenticationBackend
from starlette.requests import Request
from starlette.datastructures import UploadFile
from jose import jwt, JWTError

# فرم‌ها و فیلدهای آپلود فایل WTForms
from wtforms import FileField
from wtforms.widgets import FileInput

from app.modules.highlights.models import HighlightItem, HighlightCategory

# پچ کردن باگ WTForms روی پایتون 3.14 برای حل ارور BooleanInputWidget
try:
    import wtforms.widgets.core

    if not hasattr(wtforms.widgets.core.Input, "validation_attrs"):
        wtforms.widgets.core.Input.validation_attrs = property(lambda self: [])
except Exception:
    pass

from app.core.database import engine, SessionLocal
from app.core.security import verify_password, create_access_token, SECRET_KEY, ALGORITHM

# ایمپورت تمامی مدل‌های پروژه شما
from app.modules.users.models import User, Role, Permission
from app.modules.articles.models import Article
from app.modules.courses.models import Course, Lesson, CourseReview
from app.modules.gallery.models import GalleryItem
from app.modules.index.models import ContactMessage
from app.modules.orders.models import Cart, CartItem, Discount, Order, OrderItem, Payment, Enrollment
from app.modules.support.models import SupportMessage


# =========================================================================
# بخش اول: سیستم احراز هویت هوشمند (مخصوص کاربران Superuser آکادمی)
# =========================================================================
class AdminAuth(AuthenticationBackend):
    async def login(self, request: Request) -> bool:
        form = await request.form()
        phone_number = form.get("username")
        password = form.get("password")

        db = SessionLocal()
        try:
            user = db.query(User).filter(User.phone_number == phone_number).first()
            if user and verify_password(password, user.hashed_password):
                if user.is_superuser:
                    token = create_access_token(data={"sub": str(user.id), "is_superuser": True})
                    request.session.update({"token": token})
                    return True
        finally:
            db.close()

        return False

    async def logout(self, request: Request) -> bool:
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        token = request.session.get("token")
        if not token:
            return False

        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            if payload.get("is_superuser") is True:
                return True
        except JWTError:
            return False

        return False


authentication_backend = AdminAuth(secret_key="secure-session-key-for-royal-cake-academy")


# =========================================================================
# تابع کمکی برای ذخیره فیزیکی فایل‌های آپلود شده روی هارد سرور
# =========================================================================
async def save_uploaded_file(upload_file: UploadFile, folder_name: str) -> str | None:
    if not upload_file or not upload_file.filename:
        return None

    # خواندن محتوای ابتدایی برای تست خالی نبودن فایل
    content = await upload_file.read()
    if not content:
        return None

    base_dir = f"app/static/{folder_name}"
    os.makedirs(base_dir, exist_ok=True)

    # ساخت یک نام منحصربه‌فرد برای جلوگیری از تداخل نام فایل‌ها
    ext = os.path.splitext(upload_file.filename)[1]
    unique_filename = f"{uuid.uuid4().hex}{ext}"
    file_path = os.path.join(base_dir, unique_filename)

    with open(file_path, "wb") as f:
        f.write(content)

    # برگرداندن آدرس فرانت فایل برای ذخیره در دیتابیس
    return f"/static/{folder_name}/{unique_filename}"


# =========================================================================
# بخش دوم: مدیریت دسترسی‌ها و کاربران (ماژول Users)
# =========================================================================
class UserAdmin(ModelView, model=User):
    name = "کاربر"
    name_plural = "۱. کاربران سیستم"
    icon = "fa-solid fa-users"

    column_list = ["id", "full_name", "phone_number", "national_id", "is_superuser", "is_active", "is_verified",
                   "created_at"]
    column_searchable_list = ["full_name", "phone_number", "national_id"]
    form_columns = ["full_name", "phone_number", "national_id", "is_active", "is_verified", "is_superuser", "roles"]

    column_labels = {
        "id": "شناسه کاربر",
        "full_name": "نام و نام خانوادگی",
        "phone_number": "شماره تماس",
        "national_id": "کد ملی",
        "is_superuser": "مدیر کل (Superuser)",
        "is_active": "وضعیت فعالیت",
        "is_verified": "احراز هویت شده",
        "created_at": "تاریخ ثبت‌نام",
        "roles": "نقش‌های کاربری"
    }


class RoleAdmin(ModelView, model=Role):
    name = "نقش"
    name_plural = "۲. نقش‌های کاربری"
    icon = "fa-solid fa-user-shield"

    column_list = ["id", "name", "description"]
    column_searchable_list = ["name"]
    form_columns = ["name", "description", "users", "permissions"]

    column_labels = {
        "id": "شناسه نقش",
        "name": "نام نقش (لاتین)",
        "description": "توضیحات عملکرد نقش",
        "users": "کاربران دارای این نقش",
        "permissions": "مجوزهای دسترسی این نقش"
    }


class PermissionAdmin(ModelView, model=Permission):
    name = "مجوز"
    name_plural = "۳. سطوح دسترسی (Permissions)"
    icon = "fa-solid fa-key"

    column_list = ["id", "name", "description"]
    column_searchable_list = ["name"]
    form_columns = ["name", "description", "roles"]

    column_labels = {
        "id": "شناسه مجوز",
        "name": "کلید مجوز دسترسی",
        "description": "توضیحات سطح دسترسی",
        "roles": "نقش‌های مجاز"
    }


# =========================================================================
# بخش سوم: مدیریت دوره‌های آموزشی و جلسات (ماژول Courses با قابلیت آپلود)
# =========================================================================
class CourseAdmin(ModelView, model=Course):
    name = "دوره"
    name_plural = "۴. دوره‌های آکادمی"
    icon = "fa-solid fa-graduation-cap"

    column_list = ["id", "title", "price", "category", "session_count", "total_hours", "is_published"]
    column_searchable_list = ["title", "category"]
    form_columns = ["title", "description", "price", "session_count", "total_hours", "category", "level", "image_url",
                    "badge", "is_published"]

    # تبدیل فیلد متنی به فیلد آپلود فایل واقعی
    form_overrides = {"image_url": FileField}
    form_args = {"image_url": {"widget": FileInput()}}

    column_labels = {
        "id": "شناسه دوره",
        "title": "عنوان دوره آموزشی",
        "description": "توضیحات و سرفصل‌ها",
        "price": "قیمت دوره (تومان)",
        "category": "دسته‌بندی اصلی",
        "session_count": "تعداد کل جلسات",
        "total_hours": "مجموع زمان دوره",
        "level": "سطح برگزاری",
        "image_url": "انتخاب و آپلود پوستر دوره",
        "badge": "برچسب نمایشی",
        "is_published": "وضعیت انتشار در سایت"
    }

    async def on_model_change(self, data: dict, model: Course, is_created: bool, request: Request) -> None:
        if "image_url" in data and isinstance(data["image_url"], UploadFile):
            file_path = await save_uploaded_file(data["image_url"], "courses/images")
            if file_path:
                data["image_url"] = file_path
            elif not is_created:
                data.pop("image_url")  # اگر فایلی انتخاب نکرده بود، دیتای قبلی حفظ بشه


class LessonAdmin(ModelView, model=Lesson):
    name = "جلسه"
    name_plural = "۵. ویدیوها و جلسات دوره‌ها"
    icon = "fa-solid fa-video"

    column_list = ["id", "course_id", "title", "duration", "sort_order", "is_free", "created_at"]
    column_searchable_list = ["title"]
    form_columns = ["course_id", "title", "description", "video_url", "duration", "sort_order", "is_free"]

    form_overrides = {"video_url": FileField}
    form_args = {"video_url": {"widget": FileInput()}}

    column_labels = {
        "id": "شناسه ویدیو",
        "course_id": "دوره آموزشی مرتبط",
        "title": "عنوان این جلسه",
        "description": "خلاصه توضیحات جلسه",
        "video_url": "انتخاب و آپلود فایل ویدیو (MP4/HLS)",
        "duration": "مدت زمان (دقیقه)",
        "sort_order": "شماره قسمت (ترتیب)",
        "is_free": "قسمت معرفی (رایگان)",
        "created_at": "تاریخ بارگذاری فایل"
    }

    async def on_model_change(self, data: dict, model: Lesson, is_created: bool, request: Request) -> None:
        if "video_url" in data and isinstance(data["video_url"], UploadFile):
            file_path = await save_uploaded_file(data["video_url"], "courses/videos")
            if file_path:
                data["video_url"] = file_path
            elif not is_created:
                data.pop("video_url")


# =========================================================================
# بخش چهارم: مدیریت فاکتورها، تراکنش‌ها و تخفیف‌ها (ماژول Orders)
# =========================================================================
class OrderAdmin(ModelView, model=Order):
    name = "سفارش"
    name_plural = "۶. فاکتورهای سفارشات"
    icon = "fa-solid fa-file-invoice-dollar"

    column_list = ["id", "user_id", "original_amount", "discount_amount", "total_amount", "status", "created_at"]
    column_searchable_list = ["id", "user_id"]
    form_columns = ["user_id", "original_amount", "discount_amount", "total_amount", "discount_id", "status"]

    column_labels = {
        "id": "شماره فاکتور خرید",
        "user_id": "مشتری (شناسه کاربر)",
        "original_amount": "مبلغ پایه (بدون تخفیف)",
        "discount_amount": "مبلغ کسر شده تخفیف",
        "total_amount": "مبلغ نهایی قابل پرداخت",
        "discount_id": "ککد تخفیف استفاده شده",
        "status": "وضعیت پرداخت فاکتور",
        "created_at": "تاریخ صدور فاکتور"
    }


class OrderItemAdmin(ModelView, model=OrderItem):
    name = "آیتم فاکتور"
    name_plural = "۷. اقلام ریز فاکتورها"
    icon = "fa-solid fa-box-open"

    column_list = ["id", "order_id", "course_id", "price"]
    form_columns = ["order_id", "course_id", "price"]

    column_labels = {
        "id": "شناسه ردیف",
        "order_id": "شماره فاکتور مبدا",
        "course_id": "دوره خریداری شده",
        "price": "قیمت نهایی فروش"
    }


class PaymentAdmin(ModelView, model=Payment):
    name = "تراکنش"
    name_plural = "۸. تراکنش‌های بانکی"
    icon = "fa-solid fa-credit-card"

    column_list = ["id", "order_id", "amount", "gateway", "authority", "ref_id", "status", "created_at"]
    column_searchable_list = ["authority", "ref_id", "order_id"]

    column_labels = {
        "id": "شناسه تراکنش",
        "order_id": "شماره فاکتور خرید",
        "amount": "مبلغ واریزی",
        "gateway": "درگاه پرداخت",
        "authority": "کد تراکنش بانکی (Authority)",
        "ref_id": "شماره پیگیری بانک (RefID)",
        "status": "وضعیت پورتال بانک",
        "created_at": "زمان دقیق تراکنش"
    }


class DiscountAdmin(ModelView, model=Discount):
    name = "کد تخفیف"
    name_plural = "۹. کدهای تخفیف"
    icon = "fa-solid fa-percent"

    column_list = ["id", "code", "percent", "usage_limit", "used_count", "is_active", "valid_until"]
    column_searchable_list = ["code"]

    column_labels = {
        "id": "شناسه تخفیف",
        "code": "عبارت کد تخفیف",
        "percent": "درصد تخفیف (٪)",
        "max_discount_amount": "سقف مبلغ تخفیف",
        "usage_limit": "سقف دفعات استفاده",
        "used_count": "تعداد دفعات استفاده شده",
        "valid_until": "تاریخ و زمان انقضا",
        "is_active": "وضعیت اعتبار کد"
    }


class EnrollmentAdmin(ModelView, model=Enrollment):
    name = "دسترسی"
    name_plural = "۱۰. دسترسی‌های ثبت‌شده کاربران"
    icon = "fa-solid fa-id-card"

    column_list = ["id", "user_id", "course_id", "purchased_price", "created_at"]
    column_searchable_list = ["user_id", "course_id"]

    column_labels = {
        "id": "شناسه ثبت‌نام",
        "user_id": "دانشجو (شناسه کاربر)",
        "course_id": "دوره باز شده",
        "order_id": "فاکتور خرید مرتبط",
        "purchased_price": "مبلغ نهایی معامله",
        "created_at": "تاریخ اعطای دسترسی"
    }


# =========================================================================
# بخش پنجم: سبد خرید موقت (Carts)
# =========================================================================
class CartAdmin(ModelView, model=Cart):
    name = "سبد خرید"
    name_plural = "۱۱. سبدهای خرید موقت"
    icon = "fa-solid fa-shopping-cart"

    column_list = ["id", "user_id"]
    column_labels = {"id": "شناسه سبد خرید", "user_id": "شناسه کاربر صاحب سبد"}


class CartItemAdmin(ModelView, model=CartItem):
    name = "آیتم سبد"
    name_plural = "۱۲. اقلام سبدهای خرید"
    icon = "fa-solid fa-cart-arrow-down"

    column_list = ["id", "cart_id", "course_id"]
    column_labels = {"id": "شناسه ردیف", "cart_id": "شناسه سبد خرید اصلی", "course_id": "شناسه دوره انتخابی"}


# =========================================================================
# بخش ششم: وبلاگ، گالری و تماس با ما (Articles, Gallery با قابلیت آپلود)
# =========================================================================
class ArticleAdmin(ModelView, model=Article):
    name = "مقاله"
    name_plural = "۱۳. مقالات وبلاگ"
    icon = "fa-solid fa-newspaper"

    column_list = ["id", "title", "slug", "author_id", "created_at"]
    column_searchable_list = ["title", "slug", "tags"]
    form_columns = ["title", "slug", "image_url", "content", "meta_description", "tags", "author_id"]

    form_overrides = {"image_url": FileField}
    form_args = {"image_url": {"widget": FileInput()}}

    column_labels = {
        "id": "شناسه مقاله",
        "title": "عنوان مقاله وبلاگ",
        "slug": "نامک سئو گوگل (Slug)",
        "image_url": "انتخاب و آپلود تصویر شاخص مقاله",
        "content": "متن اصلی مقاله (HTML/Text)",
        "meta_description": "توضیحات متای سئو",
        "tags": "کلمات کلیدی (با کاما)",
        "author_id": "نویسنده (شناسه کاربر)",
        "created_at": "تاریخ ایجاد مقاله"
    }

    async def on_model_change(self, data: dict, model: Article, is_created: bool, request: Request) -> None:
        if "image_url" in data and isinstance(data["image_url"], UploadFile):
            file_path = await save_uploaded_file(data["image_url"], "articles")
            if file_path:
                data["image_url"] = file_path
            elif not is_created:
                data.pop("image_url")


class GalleryItemAdmin(ModelView, model=GalleryItem):
    name = "تصویر گالری"
    name_plural = "۱۴. تصاویر گالری نمونه‌کارها"
    icon = "fa-solid fa-images"

    column_list = ["id", "title", "category", "image_url", "created_at"]
    column_searchable_list = ["title", "category"]
    form_columns = ["title", "category", "image_url", "alt_text"]

    form_overrides = {"image_url": FileField}
    form_args = {"image_url": {"widget": FileInput()}}

    column_labels = {
        "id": "شناسه تصویر",
        "title": "عنوان نمونه‌کار تولیدی",
        "image_url": "انتخاب و آپلود تصویر نمونه‌کار",
        "alt_text": "توضیح جایگزین عکس (Alt)",
        "category": "دسته‌بندی (کیک خامه ای/شیرینی خشک/چیزکیک)",
        "created_at": "تاریخ ثبت عکس"
    }

    async def on_model_change(self, data: dict, model: GalleryItem, is_created: bool, request: Request) -> None:
        if "image_url" in data and isinstance(data["image_url"], UploadFile):
            file_path = await save_uploaded_file(data["image_url"], "gallery")
            if file_path:
                data["image_url"] = file_path
            elif not is_created:
                data.pop("image_url")


class ContactMessageAdmin(ModelView, model=ContactMessage):
    name = "پیام ارتباط"
    name_plural = "۱۵. پیام‌های فرم تماس با ما"
    icon = "fa-solid fa-envelope-open-text"

    column_list = ["id", "name", "phone_number", "message", "created_at"]
    column_searchable_list = ["name", "phone_number", "message"]

    column_labels = {
        "id": "شناسه پیام",
        "name": "نام و نام خانوادگی",
        "phone_number": "شماره تماس فرستنده",
        "message": "متن پیام ارسالی",
        "created_at": "تاریخ و زمان ارسال"
    }


# =========================================================================
# بخش هفتم: چت و پشتیبانی (Support)
# =========================================================================
class SupportMessageAdmin(ModelView, model=SupportMessage):
    name = "پیام چت"
    name_plural = "۱۶. پیام‌های پشتیبانی زنده"
    icon = "fa-solid fa-comments"

    column_list = ["id", "room_user_id", "sender_id", "content", "attachment_type", "is_read", "created_at"]
    column_searchable_list = ["content"]

    column_labels = {
        "id": "شناسه پیام چت",
        "room_user_id": "شناسه اتاق کاربر",
        "sender_id": "شناسه فرستنده",
        "content": "محتوای متنی گفتگو",
        "attachment_url": "مسیر فایل ضمیمه",
        "attachment_type": "نوع فایل ضمیمه",
        "is_read": "وضعیت خوانده شده",
        "created_at": "زمان پیام"
    }


# =========================================================================
# بخش هشتم: مدیریت هایلایت‌ها و استوری‌ها (ماژول Highlights با قابلیت آپلود)
# =========================================================================
UPLOAD_DIR = "app/static/highlights"


class HighlightCategoryAdmin(ModelView, model=HighlightCategory):
    name = "دسته هایلایت"
    name_plural = "۱۷. دسته‌بندی‌های هایلایت"
    icon = "fa-solid fa-folder-open"

    column_list = ["id", "title", "created_at"]
    form_columns = ["title", "cover_url"]

    form_overrides = {
        "cover_url": FileField
    }
    form_args = {"cover_url": {"widget": FileInput()}}

    # 🔴 تغییر کلیدی: جایگزین کردن column_labels به جای form_labels برای فارسی‌سازی قطعی
    column_labels = {
        "id": "شناسه دسته",
        "title": "عنوان هایلایت (مثلا: رضایت هنرجویان)",
        "cover_url": "تصویر کاور دایره‌ای (Choose File)",
        "created_at": "تاریخ ایجاد دسته"
    }

    async def on_model_change(self, data: dict, model: HighlightCategory, is_created: bool, request: Request) -> None:
        if "cover_url" in data and data["cover_url"] is not None:
            file_obj = data["cover_url"]
            if hasattr(file_obj, "filename") and file_obj.filename:
                ext = os.path.splitext(file_obj.filename)[1]
                filename = f"category_{uuid.uuid4().hex}{ext}"
                filepath = os.path.join(UPLOAD_DIR, filename)

                content = await file_obj.read()
                with open(filepath, "wb") as f:
                    f.write(content)

                data["cover_url"] = f"/static/highlights/{filename}"
            else:
                if not is_created:
                    data.pop("cover_url", None)

    def is_accessible(self, request: Request) -> bool:
        return True


class HighlightItemAdmin(ModelView, model=HighlightItem):
    name = "عکس هایلایت"
    name_plural = "۱۸. تصاویر داخل هایلایت‌ها"
    icon = "fa-solid fa-image"

    column_list = ["id", "category_id", "created_at"]
    form_columns = ["category", "image_url"]

    form_overrides = {
        "image_url": FileField
    }
    form_args = {"image_url": {"widget": FileInput()}}

    # 🔴 تغییر کلیدی: استفاده از کلمه استاندارد column_labels برای ترجمه هدرها و فرم آپلود
    column_labels = {
        "id": "شناسه تصویر",
        "category_id": "شناسه دسته مادر",
        "category": "انتخاب دسته مادر هایلایت",
        "image_url": "تصویر اصلی استوری/هایلایت (Choose File)",
        "created_at": "تاریخ بارگذاری تصویر"
    }

    async def on_model_change(self, data: dict, model: HighlightItem, is_created: bool, request: Request) -> None:
        if "image_url" in data and data["image_url"] is not None:
            file_obj = data["image_url"]
            if hasattr(file_obj, "filename") and file_obj.filename:
                ext = os.path.splitext(file_obj.filename)[1]
                filename = f"item_{uuid.uuid4().hex}{ext}"
                filepath = os.path.join(UPLOAD_DIR, filename)

                content = await file_obj.read()
                with open(filepath, "wb") as f:
                    f.write(content)

                data["image_url"] = f"/static/highlights/{filename}"
            else:
                if not is_created:
                    data.pop("image_url", None)

    def is_accessible(self, request: Request) -> bool:
        return True


class CourseReviewAdmin(ModelView, model=CourseReview):
    name = "نظر دوره"
    name_plural = "۱۹. نظرات دوره‌های آموزشی"
    icon = "fa-solid fa-comment-dots"

    # 🔴 اضافه کردن image_url به لیست ستون‌های جدول ادمین
    column_list = ["id", "course.title", "user.full_name", "image_url", "is_approved", "created_at"]

    # ادمین در فرم ویرایش فقط بتواند وضعیت تایید را تغییر دهد
    form_columns = ["is_approved"]

    column_labels = {
        "id": "شناسه ردیف",
        "course.title": "دوره آموزشی",
        "user.full_name": "نام هنرجو",
        "image_url": "عکس ضمیمه نظر",  # 🔴 لیبل ستون جدید عکس
        "is_approved": "وضعیت انتشار (تایید شده؟)",
        "created_at": "تاریخ ارسال نظر"
    }

    # 🔴 لود کردن و نمایش زنده عکس داخل جدول ادمین پنل با قالب‌دهی HTML
    column_formatters = {
        "image_url": lambda model, attribute: Markup(
            f'<a href="{model.image_url}" target="_blank">'
            f'<img src="{model.image_url}" style="max-height: 50px; max-width: 50px; border-radius: 8px; object-fit: cover; border: 1px solid #ddd;" />'
            f'</a>'
        ) if model.image_url else "بدون عکس"
    }

    def is_accessible(self, request: Request) -> bool:
        return True


# =========================================================================
# بخش پایانی: تابع تزریق و لود ساختار ادمین پنل با MutationObserver هوشمند
# =========================================================================
def init_admin(app):
    # عنوان رو کاملاً تمیز و بدون اسکریپت بنویس
    admin_title = "رویال کیک آکادمی"

    admin = Admin(
        app,
        engine,
        title=admin_title,
        base_url="/admin",
        templates_dir="templates",  # معرفی پوشه قالبی که الان ساختیم
        authentication_backend=authentication_backend
    )

    # ثبت ماژول‌ها به ترتیب منطقی
    admin.add_view(UserAdmin)
    admin.add_view(RoleAdmin)
    admin.add_view(PermissionAdmin)
    admin.add_view(CourseAdmin)
    admin.add_view(LessonAdmin)
    admin.add_view(OrderAdmin)
    admin.add_view(OrderItemAdmin)
    admin.add_view(PaymentAdmin)
    admin.add_view(DiscountAdmin)
    admin.add_view(EnrollmentAdmin)
    admin.add_view(CartAdmin)
    admin.add_view(CartItemAdmin)
    admin.add_view(ArticleAdmin)
    admin.add_view(GalleryItemAdmin)
    admin.add_view(ContactMessageAdmin)
    admin.add_view(SupportMessageAdmin)
    admin.add_view(HighlightCategoryAdmin)
    admin.add_view(HighlightItemAdmin)
    admin.add_view(CourseReviewAdmin)

    return admin
