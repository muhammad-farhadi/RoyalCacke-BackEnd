# app/admin.py
import os
import uuid
from markupsafe import Markup
from sqladmin import Admin, ModelView, BaseView, expose
from sqladmin.authentication import AuthenticationBackend
from starlette.requests import Request
from starlette.datastructures import UploadFile, FormData
from jose import jwt, JWTError, ExpiredSignatureError
from starlette.responses import JSONResponse
import jdatetime
from datetime import datetime
from wtforms import FileField
from wtforms.widgets import FileInput
# این خط را پیدا کنید و get_password_hash را به آن اضافه کنید:
from app.core.security import verify_password, create_access_token, SECRET_KEY, ALGORITHM, get_password_hash
from app.modules.highlights.models import HighlightItem, HighlightCategory
from wtforms.validators import Optional
from concurrent.futures import ThreadPoolExecutor

# پچ کردن باگ WTForms روی پایتون 3.14 برای حل ارور BooleanInputWidget
try:
    import wtforms.widgets.core

    if not hasattr(wtforms.widgets.core.Input, "validation_attrs"):
        wtforms.widgets.core.Input.validation_attrs = property(lambda self: [])
except Exception:
    pass

from app.core.database import engine, SessionLocal
from app.core.security import verify_password, create_access_token, SECRET_KEY, ALGORITHM, create_refresh_token

# ایمپورت تمامی مدل‌های پروژه شما
from app.modules.users.models import User, Role, Permission
from app.modules.articles.models import Article
from app.modules.courses.models import Course, Lesson, CourseReview
from app.modules.gallery.models import GalleryItem
from app.modules.index.models import ContactMessage
from app.modules.orders.models import Cart, CartItem, Discount, Order, OrderItem, Payment, Enrollment
from app.modules.support.models import SupportMessage

# این ایمپورت‌ها را به بالای فایل admin.py اضافه کنید
import os
import time
import uuid
import asyncio
import subprocess

# مسیر امن ذخیره ویدیوها (همان مسیری که در روتر داشتید)
PRIVATE_VIDEO_DIR = "app/private_assets/courses/videos"
os.makedirs(PRIVATE_VIDEO_DIR, exist_ok=True)

video_executor = ThreadPoolExecutor(max_workers=1)


# =========================================================================
# تابع کمکی برای تبدیل تاریخ میلادی دیتابیس به شمسی برای نمایش در پنل
# =========================================================================
def to_shamsi(dt_obj):
    if not dt_obj or not isinstance(dt_obj, datetime):
        return "-"
    # تبدیل تاریخ به شمسی و فرمت‌بندی به شکل (سال/ماه/روز ساعت:دقیقه)
    j_date = jdatetime.datetime.fromgregorian(datetime=dt_obj)
    return j_date.strftime("%Y/%m/%d - %H:%M")


STATUS_FA = {
    "pending": "در انتظار پرداخت",
    "completed": "تکمیل شده",
    "paid": "پرداخت موفق",
    "failed": "پرداخت ناموفق",
    "canceled": "لغو شده"
}


def translate_status(status_en):
    if not status_en:
        return "-"
    # اگر کلمه در دیکشنری بود ترجمه میکند، وگرنه همان کلمه انگلیسی را نشان میدهد
    return STATUS_FA.get(status_en.lower(), status_en)


class OptionalFileInput(FileInput):
    """
    این ویجت سفارشی صفت required را از تگ HTML حذف می‌کند
    تا مرورگر در هنگام ویرایش به خالی بودن فایل ایراد نگیرد.
    """

    def __call__(self, field, **kwargs):
        # غیرفعال کردن پرچم اجباری در سطح WTForms
        field.flags.required = False
        # حذف قطعی صفت required از خروجی تگ HTML مرورگر
        kwargs.pop("required", None)
        return super().__call__(field, **kwargs)


# تابع تبدیل ویدیو به HLS (دقیقاً مشابه روتر شما)
# تابع تبدیل ویدیو به HLS (آپدیت شده با چرخه وضعیت دیتابیس)
def process_video_to_hls(lesson_id: int, input_video_path: str, output_dir: str):
    db = SessionLocal()
    try:
        # ۱. به محض ورود، وضعیت این درس را به "در حال پردازش" تغییر می‌دهیم
        lesson = db.query(Lesson).filter(Lesson.id == lesson_id).first()
        if lesson:
            lesson.video_status = "processing"
            db.commit()

        playlist_path = os.path.join(output_dir, "playlist.m3u8")
        segment_path = os.path.join(output_dir, "segment_%03d.ts")

        command = [
            "ffmpeg",
            "-i", input_video_path,
            "-threads", "1",  # 🔴 تغییر مهم: استفاده فقط از یک هسته پردازشی برای جلوگیری از انفجار رم
            "-preset", "veryfast",  # 🔴 تغییر مهم: سبک‌ترین حالت پردازش تصویر برای سرعت و مصرف رم بهینه
            "-profile:v", "baseline",
            "-level", "3.0",
            "-start_number", "0",
            "-hls_time", "10",
            "-hls_list_size", "0",
            "-hls_playlist_type", "vod",
            "-f", "hls",
            "-hls_segment_filename", segment_path,
            playlist_path
        ]

        # اجرای دستور بدون check=True تا اگر خطا داد اسکریپت کرش نکند و بتونیم خطا رو بگیریم
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        # بازخوانی درس برای اعمال وضعیت نهایی
        lesson = db.query(Lesson).filter(Lesson.id == lesson_id).first()

        if result.returncode == 0:
            # ۲. اگر تبدیل موفقیت‌آمیز بود وضعیت "تکمیل شده" می‌شود
            if os.path.exists(input_video_path):
                os.remove(input_video_path)
            if lesson:
                lesson.video_status = "completed"
            print(f"✅ تبدیل ویدیو با موفقیت تمام شد: {output_dir}")
        else:
            # ۳. اگر خود FFmpeg خطا داد وضعیت "ناموفق" می‌شود
            if lesson:
                lesson.video_status = "failed"
            print(f"❌ خطا در تبدیل ویدیو به HLS: {result.stderr.decode()}")

        db.commit()

    except Exception as e:
        # ۴. در صورت خطاهای غیرمنتظره سیستمی هم وضعیت به "ناموفق" تغییر کند تا ادمین متوجه شود
        print(f"❌ خطای غیرمنتظره در پردازش ویدیو: {e}")
        lesson = db.query(Lesson).filter(Lesson.id == lesson_id).first()
        if lesson:
            lesson.video_status = "failed"
            db.commit()
    finally:
        db.close()


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
                    # ساخت اکسس توکن و رفرش توکن
                    payload_data = {"sub": str(user.phone_number), "is_superuser": True}
                    token = create_access_token(data=payload_data)
                    refresh_token = create_refresh_token(data=payload_data)

                    # ذخیره هر دو توکن در سشن ادمین پنل
                    request.session.update({
                        "token": token,
                        "refresh_token": refresh_token
                    })
                    return True
        finally:
            db.close()

        return False

    async def logout(self, request: Request) -> bool:
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        token = request.session.get("token")
        refresh_token = request.session.get("refresh_token")

        if not token:
            return False

        try:
            # ۱. اول سعی می‌کنیم اکسس توکن فعلی را دیکود کنیم
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            if payload.get("is_superuser") is True:
                return True

        except ExpiredSignatureError:
            # ۲. اگر اکسس توکن باطل شده بود (ارور Expired)، سراغ رفرش توکن می‌رویم
            if not refresh_token:
                return False

            try:
                # بررسی می‌کنیم که آیا رفرش توکن هنوز معتبر است یا خیر
                refresh_payload = jwt.decode(refresh_token, SECRET_KEY, algorithms=[ALGORITHM])

                if refresh_payload.get("is_superuser") is True:
                    # ۳. ساخت اکسس توکن جدید با اطلاعات داخل رفرش توکن
                    new_token = create_access_token(
                        data={"sub": refresh_payload.get("sub"), "is_superuser": True}
                    )

                    # ۴. آپدیت سشن با اکسس توکن جدید (کاربر متوجه قطعی نمیشود و لاگین می‌ماند)
                    request.session.update({"token": new_token})
                    return True

            except JWTError:
                # اگر رفرش توکن هم باطل شده بود، کلا میندازیمش بیرون تا دوباره لاگین کنه
                request.session.clear()
                return False

        except JWTError:
            # برای سایر ارورهای مربوط به توکن (مثلا توکن دستکاری شده)
            return False

        return False


authentication_backend = AdminAuth(secret_key="secure-session-key-for-royal-cake-academy")


# =========================================================================
# تابع کمکی برای ذخیره فیزیکی فایل‌های آپلود شده روی هارد سرور
# =========================================================================
# =========================================================================
# تابع کمکی برای ذخیره فیزیکی فایل‌های آپلود شده روی هارد سرور
# =========================================================================
async def save_uploaded_file(upload_file: UploadFile, folder_name: str) -> str | None:
    if not upload_file or not hasattr(upload_file, "filename") or not upload_file.filename:
        return None

    base_dir = f"app/static/{folder_name}"
    os.makedirs(base_dir, exist_ok=True)

    ext = os.path.splitext(upload_file.filename)[1]
    unique_filename = f"{uuid.uuid4().hex}{ext}"
    file_path = os.path.join(base_dir, unique_filename)

    # 🔴 آپدیت مهم برای فایل‌های حجیم (ویدیو): ذخیره یک مگابایت به یک مگابایت
    with open(file_path, "wb") as f:
        while chunk := await upload_file.read(1024 * 1024):
            f.write(chunk)

    return f"/static/{folder_name}/{unique_filename}"


# =========================================================================
# بخش دوم: مدیریت دسترسی‌ها و کاربران (ماژول Users)
# =========================================================================
class UserAdmin(ModelView, model=User):
    name = "کاربر"
    name_plural = "۱. کاربران سیستم"
    icon = "fa-solid fa-users"
    list_template = "custom_list.html"
    column_formatters = {User.created_at: lambda m, a: to_shamsi(m.created_at)}
    column_formatters_detail = {User.created_at: lambda m, a: to_shamsi(m.created_at)}
    column_list = ["id", "full_name", "phone_number", "national_id", "is_superuser", "is_active", "is_verified",
                   "created_at"]
    column_searchable_list = ["full_name", "phone_number", "national_id"]
    form_columns = ["full_name", "phone_number", "national_id", "is_active", "is_verified", "is_superuser", "roles"]

    column_labels = {
        "id": "شناسه کاربر", "full_name": "نام و نام خانوادگی", "phone_number": "شماره تماس",
        "national_id": "کد ملی", "is_superuser": "مدیر کل (Superuser)", "is_active": "وضعیت فعالیت",
        "is_verified": "احراز هویت شده", "created_at": "تاریخ ثبت‌نام", "roles": "نقش‌های کاربری"
    }

    # 🔴 این بلاک را به انتهای کلاس اضافه کنید
    async def on_model_change(self, data: dict, model: Any, is_created: bool, request: Request) -> None:
        if is_created:
            # اگر کاربر جدید در حال ساخته شدن است و رمز عبوری ندارد:
            # شماره موبایلش را می‌گیریم و به عنوان رمز عبور هش‌شده ذخیره می‌کنیم
            phone = data.get("phone_number", "12345678")
            data["hashed_password"] = get_password_hash(phone)


class RoleAdmin(ModelView, model=Role):
    name = "نقش"
    name_plural = "۲. نقش‌های کاربری"
    icon = "fa-solid fa-user-shield"
    column_list = ["id", "name", "description"]
    column_searchable_list = ["name"]
    form_columns = ["name", "description", "users", "permissions"]
    column_labels = {
        "id": "شناسه نقش", "name": "نام نقش (لاتین)", "description": "توضیحات عملکرد نقش",
        "users": "کاربران دارای این نقش", "permissions": "مجوزهای دسترسی این نقش"
    }


class PermissionAdmin(ModelView, model=Permission):
    name = "مجوز"
    name_plural = "۳. سطوح دسترسی (Permissions)"
    icon = "fa-solid fa-key"
    column_list = ["id", "name", "description"]
    column_searchable_list = ["name"]
    form_columns = ["name", "description", "roles"]
    column_labels = {
        "id": "شناسه مجوز", "name": "کلید مجوز دسترسی", "description": "توضیحات سطح دسترسی", "roles": "نقش‌های مجاز"
    }


# =========================================================================
# بخش سوم: مدیریت دوره‌های آموزشی و جلسات (ماژول Courses)
# =========================================================================
class CourseAdmin(ModelView, model=Course):
    name = "دوره"
    name_plural = "۴. دوره‌های آکادمی"
    icon = "fa-solid fa-graduation-cap"
    list_template = "custom_list.html"

    column_list = ["id", "title", "price", "category", "session_count", "total_hours", "is_published"]
    column_searchable_list = ["title", "category"]
    form_columns = ["title", "description", "price", "session_count", "total_hours", "category", "level", "image_url",
                    "badge", "is_published"]

    form_overrides = {"image_url": FileField}
    form_args = {"image_url": {"widget": FileInput()}}

    column_labels = {
        "id": "شناسه دوره", "title": "عنوان دوره آموزشی", "description": "توضیحات و سرفصل‌ها",
        "price": "قیمت دوره (تومان)", "category": "دسته‌بندی اصلی", "session_count": "تعداد کل جلسات",
        "total_hours": "مجموع زمان دوره", "level": "سطح برگزاری", "image_url": "آپلود پوستر جدید دوره",
        "badge": "برچسب نمایشی", "is_published": "وضعیت انتشار"
    }

    async def on_model_change(self, data: dict, model: Course, is_created: bool, request: Request) -> None:
        if "image_url" in data:
            val = data["image_url"]
            if isinstance(val, UploadFile) and val.filename:
                file_path = await save_uploaded_file(val, "courses/images")
                if file_path:
                    data["image_url"] = file_path
                else:
                    data.pop("image_url", None)
            else:
                data.pop("image_url", None)

    # 🟢 هوک جدید: حذف فیزیکی تمام ویدیوهای دوره در صورت حذف خود دوره
    async def on_model_delete(self, model: Any, request: Request) -> None:
        import shutil
        # تک‌تک جلسات این دوره را بررسی می‌کند و پوشه ویدیوهایشان را پاک می‌کند
        for lesson in model.lessons:
            if lesson.video_url:
                lesson_dir = os.path.join(PRIVATE_VIDEO_DIR, lesson.video_url)
                if os.path.exists(lesson_dir):
                    shutil.rmtree(lesson_dir)
                    print(f"🗑️ پوشه ویدیوهای جلسه '{lesson.title}' به علت حذف دوره پاک شد.")


class LessonAdmin(ModelView, model=Lesson):
    name = "جلسه"
    name_plural = "۵. ویدیوها و جلسات دوره‌ها"
    icon = "fa-solid fa-video"
    list_template = "custom_list.html"

    # اضافه شدن cover_url به لیست ستون‌های جدول
    column_list = ["id", "course", "title", "cover_url", "duration", "sort_order", "is_free", "video_status",
                   "created_at"]
    column_searchable_list = ["title"]

    # اضافه شدن cover_url به فیلدهای فرم آپلود/ویرایش
    form_columns = ["course", "title", "description", "cover_url", "video_url", "sort_order", "is_free"]

    column_formatters = {
        Lesson.created_at: lambda m, a: to_shamsi(m.created_at),
        Lesson.video_status: lambda m, a: {
            "pending": "⏳ در انتظار",
            "processing": "⚙️ در حال پردازش",
            "completed": "✅ آماده نمایش",
            "failed": "❌ خطا در پردازش"
        }.get(m.video_status, m.video_status),
        # رندر کردن عکس کاور در جدول برای زیبایی و مدیریت بهتر
        "cover_url": lambda m, a: Markup(
            f'<a href="{m.cover_url}" target="_blank">'
            f'<img src="{m.cover_url}" style="max-height: 45px; border-radius: 6px; object-fit: cover; border: 1px solid #ddd;" />'
            f'</a>'
        ) if getattr(m, "cover_url", None) else "بدون کاور"
    }

    column_formatters_detail = {
        Lesson.created_at: lambda m, a: to_shamsi(m.created_at)
    }

    # معرفی هر دو فیلد کاور و ویدیو به عنوان FileField به فرم‌ساز
    form_overrides = {
        "video_url": FileField,
        "cover_url": FileField
    }

    # اختیاری کردن هر دو فیلد هنگام ویرایش برای جلوگیری از خطای مرورگر
    form_args = {
        "video_url": {
            "widget": OptionalFileInput(),
            "validators": [Optional()]
        },
        "cover_url": {
            "widget": OptionalFileInput(),
            "validators": [Optional()]
        }
    }

    create_template = "custom_create.html"
    edit_template = "custom_edit.html"

    column_labels = {
        "id": "شناسه ویدیو", "course": "دوره آموزشی مرتبط", "title": "عنوان این جلسه",
        "description": "خلاصه توضیحات جلسه",
        "cover_url": "عکس کاور جلسه",  # لیبل جدید
        "video_url": "آپلود فایل ویدیو (MP4)",
        "duration": "مدت زمان (دقیقه)", "sort_order": "شماره قسمت", "is_free": "قسمت معرفی (رایگان)",
        "video_status": "وضعیت پردازش ویدیو", "created_at": "تاریخ ثبت"
    }

    async def on_model_change(self, data: dict, model: Any, is_created: bool, request: Request) -> None:
        # ۱. پردازش و ذخیره عکس کاور (بخش جدید)
        if "cover_url" in data:
            cover_val = data["cover_url"]
            # بررسی اینکه آیا فایل جدیدی آپلود شده است
            if hasattr(cover_val, "filename") and cover_val.filename:
                # استفاده از تابع کمکی موجود برای ذخیره عکس
                file_path = await save_uploaded_file(cover_val, "courses/lessons/covers")
                if file_path:
                    data["cover_url"] = file_path
                else:
                    data.pop("cover_url", None)
            else:
                # اگر فایلی آپلود نشده، کلید را حذف می‌کنیم تا مقدار قبلی در دیتابیس پاک نشود
                data.pop("cover_url", None)

        # ۲. پردازش و ذخیره ویدیو (کد دست‌نخورده قبلی)
        if "video_url" in data:
            val = data["video_url"]

            if hasattr(val, "filename") and val.filename:
                folder_name = f"lesson_{int(time.time())}_{uuid.uuid4().hex[:6]}"
                lesson_dir = os.path.join(PRIVATE_VIDEO_DIR, folder_name)
                os.makedirs(lesson_dir, exist_ok=True)

                temp_video_path = os.path.join(lesson_dir, "raw_video.mp4")

                with open(temp_video_path, "wb") as f:
                    while chunk := await val.read(1024 * 1024):
                        f.write(chunk)

                data["video_url"] = folder_name
                data["video_status"] = "pending"
                request.state.run_ffmpeg = True

                try:
                    ffprobe_cmd = [
                        "ffprobe", "-v", "error",
                        "-show_entries", "format=duration",
                        "-of", "default=noprint_wrappers=1:nokey=1",
                        temp_video_path
                    ]
                    result = subprocess.run(ffprobe_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                            timeout=10)
                    if result.returncode == 0 and result.stdout.strip():
                        seconds = float(result.stdout.strip())
                        minutes = max(1, round(seconds / 60))
                        data["duration"] = minutes
                    else:
                        data["duration"] = 0
                except Exception as e:
                    print(f"❌ خطا در اجرای ffprobe: {e}")
                    data["duration"] = 0
            else:
                if is_created:
                    raise ValueError("آپلود فایل ویدیو برای ایجاد جلسه جدید الزامی است!")
                else:
                    data.pop("video_url", None)
                    data.pop("video_status", None)
                    data.pop("duration", None)

    async def after_model_change(self, data: dict, model: Any, is_created: bool, request: Request) -> None:
        if getattr(request.state, "run_ffmpeg", False):
            folder_name = model.video_url
            lesson_dir = os.path.join(PRIVATE_VIDEO_DIR, folder_name)
            temp_video_path = os.path.join(lesson_dir, "raw_video.mp4")

            loop = asyncio.get_running_loop()
            loop.run_in_executor(video_executor, process_video_to_hls, model.id, temp_video_path, lesson_dir)

    async def on_model_delete(self, model: Any, request: Request) -> None:
        import shutil
        if model.video_url:
            lesson_dir = os.path.join(PRIVATE_VIDEO_DIR, model.video_url)
            if os.path.exists(lesson_dir):
                shutil.rmtree(lesson_dir)
                print(f"🗑️ پوشه فیزیکی جلسه با موفقیت حذف شد: {lesson_dir}")


# =========================================================================
# بخش چهارم: مدیریت فاکتورها، تراکنش‌ها و تخفیف‌ها (ماژول Orders)
# =========================================================================
class OrderAdmin(ModelView, model=Order):
    name = "سفارش"
    name_plural = "۶. فاکتورهای سفارشات"
    list_template = "custom_list.html"
    icon = "fa-solid fa-file-invoice-dollar"
    # 🔴 تغییر ۱: کلمه user_id به user تغییر کرد
    column_list = ["id", "user.phone_number", "original_amount", "discount_amount", "total_amount", "status",
                   "created_at"]

    column_formatters = {
        Order.created_at: lambda m, a: to_shamsi(m.created_at),
        Order.status: lambda m, a: translate_status(m.status)  # 🔴 اضافه شدن فرمت وضعیت
    }

    column_formatters_detail = {
        Order.created_at: lambda m, a: to_shamsi(m.created_at),
        Order.status: lambda m, a: translate_status(m.status)  # 🔴 اضافه شدن فرمت وضعیت
    }
    # 🔴 تغییر ۲: حالا می‌توانید علاوه بر شماره فاکتور، بر اساس "نام مشتری" و "شماره تماس" هم در پنل سرچ کنید!
    column_searchable_list = ["id", "user.full_name", "user.phone_number"]
    # 🔴 تغییر ۳: در فرم ایجاد/ویرایش فاکتور هم user_id به user تغییر کرد تا منوی کشویی نام‌ها باز شود
    form_columns = ["user", "original_amount", "discount_amount", "total_amount", "discount_id", "status"]
    column_labels = {
        "id": "شماره فاکتور",
        "user": "انتخاب مشتری",  # این لیبل برای فرم افزودن/ویرایش است
        "user.phone_number": "شماره موبایل مشتری",  # 🔴 این لیبل برای جدول لیست سفارشات است
        "original_amount": "مبلغ پایه",
        "discount_amount": "تخفیف",
        "total_amount": "مبلغ نهایی",
        "discount_id": "کد تخفیف",
        "status": "وضعیت پرداخت",
        "created_at": "تاریخ صدور"
    }


class OrderItemAdmin(ModelView, model=OrderItem):
    name = "آیتم فاکتور"
    name_plural = "۷. اقلام ریز فاکتورها"
    list_template = "custom_list.html"
    icon = "fa-solid fa-box-open"
    column_list = ["id", "order_id", "course_id", "price"]
    form_columns = ["order_id", "course_id", "price"]
    column_labels = {"id": "ردیف", "order_id": "شماره فاکتور", "course_id": "دوره", "price": "قیمت نهایی"}


class PaymentAdmin(ModelView, model=Payment):
    name = "تراکنش"
    name_plural = "۸. تراکنش‌های بانکی"
    icon = "fa-solid fa-credit-card"
    list_template = "custom_list.html"
    column_formatters = {
        Payment.created_at: lambda m, a: to_shamsi(m.created_at),
        Payment.status: lambda m, a: translate_status(m.status)  # 🔴 اضافه شدن فرمت وضعیت
    }
    column_formatters_detail = {
        Payment.created_at: lambda m, a: to_shamsi(m.created_at),
        Payment.status: lambda m, a: translate_status(m.status)  # 🔴 اضافه شدن فرمت وضعیت
    }
    column_list = ["id", "order_id", "amount", "gateway", "authority", "ref_id", "status", "created_at"]
    column_searchable_list = ["authority", "ref_id", "order_id"]
    column_labels = {
        "id": "شناسه تراکنش", "order_id": "فاکتور", "amount": "مبلغ پرداختی",
        "gateway": "درگاه", "authority": "کد تراکنش", "ref_id": "کد پیگیری", "status": "وضعیت",
        "created_at": "تاریخ و زمان"
    }


class DiscountAdmin(ModelView, model=Discount):
    name = "کد تخفیف"
    name_plural = "۹. کدهای تخفیف"
    list_template = "custom_list.html"
    icon = "fa-solid fa-percent"
    column_list = ["id", "code", "percent", "usage_limit", "used_count", "is_active", "valid_until"]
    column_searchable_list = ["code"]
    column_labels = {
        "id": "شناسه", "code": "کد تخفیف", "percent": "درصد (٪)", "usage_limit": "سقف استفاده",
        "used_count": "تعداد استفاده شده", "valid_until": "تاریخ انقضا", "is_active": "وضعیت اعتبار"
    }


class EnrollmentAdmin(ModelView, model=Enrollment):
    name = "دسترسی"
    name_plural = "۱۰. دسترسی‌های دانشجویان"
    icon = "fa-solid fa-id-card"
    list_template = "custom_list.html"

    # نمایش عنوان دوره در جدول لیست دسترسی‌ها
    column_list = ["id", "user.phone_number", "course.title", "purchased_price", "created_at"]

    # امکان جستجو
    column_searchable_list = ["id", "user.phone_number", "user.full_name"]

    # 🔴 استفاده از course (به جای course_id) برای ساخته شدن منوی کشویی
    form_columns = ["user", "course", "purchased_price"]

    # 🔴 اختیاری کردن مبلغ خرید (اگر خالی بماند، صفر رد می‌شود)
    form_args = {
        "purchased_price": {
            "default": 0,
            "validators": [Optional()]
        }
    }

    column_labels = {
        "id": "شناسه",
        "user": "انتخاب دانشجو",
        "user.phone_number": "موبایل دانشجو",
        "course": "انتخاب دوره",
        "course.title": "عنوان دوره",
        "purchased_price": "مبلغ خرید (تومان)",
        "created_at": "تاریخ دسترسی"
    }

    column_formatters = {
        Enrollment.created_at: lambda m, a: to_shamsi(m.created_at)
    }
    column_formatters_detail = {
        Enrollment.created_at: lambda m, a: to_shamsi(m.created_at)
    }


# =========================================================================
# بخش پنجم: سبد خرید موقت (Carts)
# =========================================================================
class CartAdmin(ModelView, model=Cart):
    name = "سبد خرید"
    name_plural = "۱۱. سبدهای موقت"
    list_template = "custom_list.html"
    icon = "fa-solid fa-shopping-cart"
    column_list = ["id", "user_id"]
    column_labels = {"id": "شناسه سبد", "user_id": "صاحب سبد"}


class CartItemAdmin(ModelView, model=CartItem):
    name = "آیتم سبد"
    name_plural = "۱۲. اقلام سبد خرید"
    list_template = "custom_list.html"
    icon = "fa-solid fa-cart-arrow-down"
    column_list = ["id", "cart_id", "course_id"]
    column_labels = {"id": "ردیف", "cart_id": "سبد خرید", "course_id": "دوره"}


# =========================================================================
# بخش ششم: وبلاگ، گالری و تماس با ما
# =========================================================================
class ArticleAdmin(ModelView, model=Article):
    name = "مقاله"
    name_plural = "۱۳. مقالات وبلاگ"
    list_template = "custom_list.html"
    icon = "fa-solid fa-newspaper"
    column_formatters = {Article.created_at: lambda m, a: to_shamsi(m.created_at)}
    column_formatters_detail = {Article.created_at: lambda m, a: to_shamsi(m.created_at)}
    column_list = ["id", "title", "slug", "author_id", "created_at"]
    column_searchable_list = ["title", "slug"]
    form_columns = ["title", "slug", "image_url", "content", "meta_description", "tags", "author_id"]

    form_overrides = {"image_url": FileField}
    form_args = {"image_url": {"widget": FileInput()}}

    column_labels = {
        "id": "شناسه", "title": "عنوان مقاله", "slug": "نامک سئو (Slug)", "image_url": "آپلود تصویر جدید شاخص",
        "content": "متن مقاله", "meta_description": "متای سئو", "tags": "کلمات کلیدی", "author_id": "نویسنده",
        "created_at": "تاریخ ثبت"
    }

    async def on_model_change(self, data: dict, model: Article, is_created: bool, request: Request) -> None:
        if "image_url" in data:
            val = data["image_url"]
            if isinstance(val, UploadFile) and val.filename:
                file_path = await save_uploaded_file(val, "articles")
                if file_path:
                    data["image_url"] = file_path
                else:
                    data.pop("image_url", None)
            else:
                data.pop("image_url", None)


class GalleryItemAdmin(ModelView, model=GalleryItem):
    name = "تصویر گالری"
    name_plural = "۱۴. گالری نمونه‌کارها"
    list_template = "custom_list.html"
    icon = "fa-solid fa-images"
    column_formatters = {GalleryItem.created_at: lambda m, a: to_shamsi(m.created_at)}
    column_formatters_detail = {GalleryItem.created_at: lambda m, a: to_shamsi(m.created_at)}
    column_list = ["id", "title", "category", "image_url", "created_at"]
    column_searchable_list = ["title", "category"]
    form_columns = ["title", "category", "image_url", "alt_text"]

    form_overrides = {"image_url": FileField}
    form_args = {"image_url": {"widget": FileInput()}}

    column_labels = {
        "id": "شناسه", "title": "عنوان نمونه‌کار", "image_url": "آپلود تصویر نمونه‌کار",
        "alt_text": "توضیح جایگزین عکس (Alt)", "category": "دسته‌بندی", "created_at": "تاریخ آپلود"
    }

    async def on_model_change(self, data: dict, model: GalleryItem, is_created: bool, request: Request) -> None:
        if "image_url" in data:
            val = data["image_url"]
            if isinstance(val, UploadFile) and val.filename:
                file_path = await save_uploaded_file(val, "gallery")
                if file_path:
                    data["image_url"] = file_path
                else:
                    data.pop("image_url", None)
            else:
                data.pop("image_url", None)


class ContactMessageAdmin(ModelView, model=ContactMessage):
    name = "پیام فرم تماس"
    name_plural = "۱۵. پیام‌های تماس با ما"
    list_template = "custom_list.html"
    icon = "fa-solid fa-envelope-open-text"
    column_list = ["id", "name", "phone_number", "message", "created_at"]
    column_formatters = {ContactMessage.created_at: lambda m, a: to_shamsi(m.created_at)}
    column_formatters_detail = {ContactMessage.created_at: lambda m, a: to_shamsi(m.created_at)}
    column_searchable_list = ["name", "phone_number"]
    column_labels = {"id": "شناسه", "name": "فرستنده", "phone_number": "شماره تماس", "message": "متن پیام",
                     "created_at": "تاریخ ارسال"}


class SupportMessageAdmin(ModelView, model=SupportMessage):
    name = "پیام چت"
    name_plural = "۱۶. پیام‌های پشتیبانی زنده"
    list_template = "custom_list.html"
    icon = "fa-solid fa-comments"
    column_list = ["id", "room_user_id", "sender_id", "content", "is_read", "created_at"]
    column_formatters = {SupportMessage.created_at: lambda m, a: to_shamsi(m.created_at)}
    column_formatters_detail = {SupportMessage.created_at: lambda m, a: to_shamsi(m.created_at)}
    column_searchable_list = ["content"]
    column_labels = {"id": "شناسه", "room_user_id": "اتاق چت", "sender_id": "فرستنده", "content": "متن",
                     "is_read": "خوانده شده؟", "created_at": "زمان"}


# =========================================================================
# بخش هشتم: مدیریت هایلایت‌ها و استوری‌ها (ماژول Highlights)
# =========================================================================
class HighlightCategoryAdmin(ModelView, model=HighlightCategory):
    name = "دسته هایلایت"
    name_plural = "۱۷. دسته‌های هایلایت"
    icon = "fa-solid fa-folder-open"
    list_template = "custom_list.html"
    column_list = ["id", "title", "created_at"]
    column_formatters = {HighlightCategory.created_at: lambda m, a: to_shamsi(m.created_at)}
    column_formatters_detail = {HighlightCategory.created_at: lambda m, a: to_shamsi(m.created_at)}
    form_columns = ["title", "cover_url"]

    form_overrides = {"cover_url": FileField}
    form_args = {"cover_url": {"widget": FileInput()}}

    column_labels = {"id": "شناسه", "title": "عنوان هایلایت", "cover_url": "تصویر کاور جدید",
                     "created_at": "تاریخ ایجاد"}

    async def on_model_change(self, data: dict, model: HighlightCategory, is_created: bool, request: Request) -> None:
        if "cover_url" in data:
            val = data["cover_url"]
            if isinstance(val, UploadFile) and val.filename:
                file_path = await save_uploaded_file(val, "highlights")
                if file_path:
                    data["cover_url"] = file_path
                else:
                    data.pop("cover_url", None)
            else:
                data.pop("cover_url", None)

    def is_accessible(self, request: Request) -> bool:
        return True


class HighlightItemAdmin(ModelView, model=HighlightItem):
    name = "عکس هایلایت"
    name_plural = "۱۸. تصاویر هایلایت‌ها"
    icon = "fa-solid fa-image"
    list_template = "custom_list.html"

    column_list = ["id", "category_id", "created_at"]
    column_formatters = {HighlightItem.created_at: lambda m, a: to_shamsi(m.created_at)}
    column_formatters_detail = {HighlightItem.created_at: lambda m, a: to_shamsi(m.created_at)}
    form_columns = ["category", "image_url"]

    form_overrides = {"image_url": FileField}
    form_args = {"image_url": {"widget": FileInput()}}

    column_labels = {"id": "شناسه", "category_id": "شناسه دسته", "category": "انتخاب دسته",
                     "image_url": "آپلود تصویر جدید استوری", "created_at": "تاریخ"}

    async def on_model_change(self, data: dict, model: HighlightItem, is_created: bool, request: Request) -> None:
        if "image_url" in data:
            val = data["image_url"]
            if isinstance(val, UploadFile) and val.filename:
                file_path = await save_uploaded_file(val, "highlights")
                if file_path:
                    data["image_url"] = file_path
                else:
                    data.pop("image_url", None)
            else:
                data.pop("image_url", None)

    def is_accessible(self, request: Request) -> bool:
        return True


# =========================================================================
# بخش نهم: مدیریت نظرات هنرجویان دوره‌ها (Course Reviews)
# =========================================================================
class CourseReviewAdmin(ModelView, model=CourseReview):
    name = "نظر دوره"
    name_plural = "۱۹. نظرات دوره‌های آموزشی"
    icon = "fa-solid fa-comment-dots"
    list_template = "custom_list.html"

    column_list = ["id", "course.title", "user.full_name", "image_url", "is_approved", "created_at"]
    form_columns = ["is_approved"]

    column_labels = {
        "id": "شناسه ردیف", "course.title": "دوره آموزشی", "user.full_name": "نام هنرجو",
        "image_url": "عکس ارسالی هنرجو", "is_approved": "وضعیت انتشار (تایید شده؟)", "created_at": "تاریخ ارسال نظر"
    }

    column_formatters = {
        "image_url": lambda model, attribute: Markup(
            f'<a href="{model.image_url}" target="_blank">'
            f'<img src="{model.image_url}" style="max-height: 50px; border-radius: 8px; object-fit: cover; border: 1px solid #ddd;" />'
            f'</a>'
        ) if model.image_url else "بدون عکس",
        CourseReview.created_at: lambda m, a: to_shamsi(m.created_at)
    }

    column_formatters_detail = {
        CourseReview.created_at: lambda m, a: to_shamsi(m.created_at)
    }

    def is_accessible(self, request: Request) -> bool:
        return True


# =========================================================================
# پچ طلایی برای جلوگیری از کرش کردن هسته SQLAdmin هنگام ویرایش فایلی
# =========================================================================
# =========================================================================
# پچ طلایی برای جلوگیری از کرش کردن هسته SQLAdmin هنگام ویرایش فایلی
# =========================================================================
def apply_sqladmin_patch():
    original_handle_form_data = Admin._handle_form_data

    # 🔴 با اضافه شدن *args و **kwargs، تابع هم با ۱ ورودی (ایجاد) و هم با ۲ ورودی (ویرایش) کار می‌کند
    async def safe_handle_form_data(self, request: Request, *args, **kwargs):
        form = await request.form()
        new_data = []
        for k, v in form.multi_items():
            if isinstance(v, str):
                new_data.append((k, v))
            elif hasattr(v, "filename"):
                new_data.append((k, v))
            else:
                try:
                    from starlette.datastructures import UploadFile as StarletteUploadFile
                    new_data.append((k, StarletteUploadFile(filename=v.name, file=v.open())))
                except Exception:
                    new_data.append((k, v))
        return FormData(new_data)

    Admin._handle_form_data = safe_handle_form_data


apply_sqladmin_patch()


# =========================================================================
# بخش دهم: داشبورد چت و ارتباط هوشمند زنده با هنرجویان (Custom BaseView)
# =========================================================================
class SupportChatDashboard(BaseView):
    name = "اتاق چت آنلاین"
    icon = "fa-solid fa-headset"

    @expose("/support/live-chat", methods=["GET"])
    async def support_chat_page(self, request: Request):
        db = SessionLocal()
        rooms = []
        admin_token = request.session.get("token", "")

        try:
            distinct_rooms = db.query(SupportMessage.room_user_id).distinct().all()

            for room in distinct_rooms:
                room_id = room[0]
                user = db.query(User).filter(User.id == room_id).first()

                # استخراج آخرین پیام
                last_msg = db.query(SupportMessage).filter(
                    SupportMessage.room_user_id == room_id
                ).order_by(SupportMessage.created_at.desc()).first()

                # 🔴 محاسبه دقیق تعداد پیام‌های نخوانده کاربر
                unread_count = db.query(SupportMessage).filter(
                    SupportMessage.room_user_id == room_id,
                    SupportMessage.sender_id == room_id,  # فقط پیام‌هایی که هنرجو فرستاده
                    SupportMessage.is_read == False
                ).count()

                # تعیین زمان عددی برای مرتب‌سازی
                last_activity_ts = last_msg.created_at.timestamp() if last_msg and last_msg.created_at else 0

                rooms.append({
                    "id": room_id,
                    "name": user.full_name if user else f"هنرجوی شماره {room_id}",
                    "last_message": last_msg.content if last_msg else "فایلی ارسال شده است",
                    "is_read": unread_count == 0,
                    "unread_count": unread_count,
                    "last_activity": last_activity_ts
                })

            # 🔴 مرتب‌سازی جادویی: اول پیام‌های نخوانده، سپس بر اساس جدیدترین زمان
            rooms.sort(key=lambda x: (not x["is_read"], x["last_activity"]), reverse=True)

        finally:
            db.close()

        return await self.templates.TemplateResponse(
            request,
            "admin_chat.html",
            context={"rooms": rooms, "admin_token": admin_token}
        )

    @expose("/support/history/{user_id}", methods=["GET"])
    def chat_history_api(self, request: Request):
        if not request.session.get("token"):
            return JSONResponse({"detail": "Unauthorized"}, status_code=401)

        user_id = int(request.path_params["user_id"])
        db = SessionLocal()
        try:
            # 🔴 آپدیت وضعیت: به محض باز شدن چت، پیام‌های نخواندهِ این هنرجو تیک می‌خورند
            unread_msgs = db.query(SupportMessage).filter(
                SupportMessage.room_user_id == user_id,
                SupportMessage.sender_id == user_id,
                SupportMessage.is_read == False
            ).all()

            for msg in unread_msgs:
                msg.is_read = True

            if unread_msgs:
                db.commit()  # ذخیره تیک‌خوردن‌ها در دیتابیس

            # استخراج تاریخچه برای نمایش در صفحه
            messages = db.query(SupportMessage).filter(
                SupportMessage.room_user_id == user_id
            ).order_by(SupportMessage.created_at.asc()).all()

            history = []
            for m in messages:
                history.append({
                    "id": m.id,
                    "sender_id": m.sender_id,
                    "content": m.content,
                    "created_at": m.created_at.isoformat() if m.created_at else ""
                })
            return JSONResponse(history)
        finally:
            db.close()


# =========================================================================
# بخش پایانی: تابع تزریق و لود ساختار ادمین پنل
# =========================================================================
def init_admin(app):
    admin_title = "رویال کیک آکادمی"

    admin = Admin(
        app,
        engine,
        title=admin_title,
        base_url="/admin",
        templates_dir="templates",
        authentication_backend=authentication_backend
    )

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
    admin.add_base_view(SupportChatDashboard)

    return admin
