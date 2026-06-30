import requests

# تنظیمات سرور (اگر پورت یا پیشوند روت‌هایت فرق دارد اینجا اصلاح کن)
BASE_URL = "http://localhost:8000"

# اطلاعات یک کاربر که قبلا در دیتابیس ثبت‌نام و وریفای شده است
PHONE_NUMBER = "09214526850"  # شماره موبایل خودت را اینجا بذار
PASSWORD = "123456"  # رمز عبورت را اینجا بذار
COURSE_ID_TO_BUY = 1  # آیدی یکی از دوره‌های موجود در دیتابیس


def run_test():
    print("🔄 ۱. در حال ورود به حساب کاربری...")
    # دقت کن که لاگین با فرمت فرم دیتا (data) ارسال می‌شود نه json
    login_response = requests.post(
        f"{BASE_URL}/login",  # اگر روت لاگین زیرمجموعه users است، بکن /users/login
        data={"username": PHONE_NUMBER, "password": PASSWORD}
    )

    if login_response.status_code != 200:
        print("❌ ورود ناموفق بود! چک کن کاربر تایید شده باشه و رمز درست باشه.")
        print("متن ارور:", login_response.json())
        return

    token = login_response.json().get("access_token")
    headers = {"Authorization": f"Bearer {token}"}
    print("✅ ورود موفق! توکن دریافت شد.")

    print(f"\n🔄 ۲. در حال اضافه کردن دوره {COURSE_ID_TO_BUY} به سبد خرید...")
    cart_payload = {"course_id": COURSE_ID_TO_BUY}
    cart_response = requests.post(f"{BASE_URL}/cart", json=cart_payload, headers=headers)  # /orders/cart

    # اگر ارور 400 بده ممکنه دوره از قبل تو سبد باشه یا قبلا خریده باشیش، که مشکلی نیست ادامه میدیم
    if cart_response.status_code in [200, 201]:
        print("✅ دوره به سبد خرید اضافه شد.")
    else:
        print("⚠️ وضعیت سبد خرید:", cart_response.json().get('detail'))

    print("\n🔄 ۳. در حال درخواست فاکتور و اتصال به درگاه...")
    checkout_payload = {"discount_code": None}
    checkout_response = requests.post(f"{BASE_URL}/checkout", json=checkout_payload,
                                      headers=headers)  # /orders/checkout

    if checkout_response.status_code == 200:
        data = checkout_response.json()
        print("\n" + "=" * 60)
        print("🎉 فاکتور با موفقیت ایجاد شد!")
        print(f"شناسه فاکتور (Order ID): {data.get('order_id')}")
        print("\n🔗 برای پرداخت روی لینک زیر کلیک کن (CTRL + Click):")
        print(data.get("payment_url"))
        print("=" * 60 + "\n")
        print("📌 راهنما:")
        print("۱. لینک بالا رو باز کن.")
        print("۲. چون محیط سندباکس/تستی هست، زرین‌پال یه صفحه میاره که میتونی پرداخت موفق یا ناموفق رو انتخاب کنی.")
        print("۳. بعد از انتخاب، دکمه تکمیل رو بزن تا زرین‌پال تو رو به سرورت (آدرس CALLBACK_URL) برگردونه.")
        print("۴. تو ترمینال سرورت (FastAPI) لاگ‌ها رو چک کن ببین وضعیت فاکتور و دسترسی دوره‌ها آپدیت میشه یا نه.")
    else:
        print("❌ خطا در مرحله پرداخت!")
        print("کد ارور:", checkout_response.status_code)
        print("متن ارور:", checkout_response.json())


if __name__ == "__main__":
    run_test()