// sidebar.js
document.addEventListener("DOMContentLoaded", function() {
    const sidebarHTML = `
    <aside class="w-64 bg-gray-900 text-white flex flex-col justify-between hidden md:flex z-10 shadow-lg h-screen sticky top-0">
        <div class="p-5">
            <h1 class="text-xl font-bold border-b border-gray-700 pb-4 text-center text-green-400">مدیریت آکادمی</h1>
            <nav class="mt-6 space-y-1">
                <a href="index.html" id="menu-index" class="w-full flex items-center space-x-reverse space-x-3 px-4 py-3 rounded-lg text-gray-300 hover:bg-gray-800 transition">
                    <span>📊</span> <span>داشبورد اصلی</span>
                </a>
                <a href="courses.html" id="menu-courses" class="w-full flex items-center space-x-reverse space-x-3 px-4 py-3 rounded-lg text-gray-300 hover:bg-gray-800 transition">
                    <span>🎓</span> <span>دوره‌ها و دروس</span>
                </a>
                <a href="users.html" id="menu-users" class="w-full flex items-center space-x-reverse space-x-3 px-4 py-3 rounded-lg text-gray-300 hover:bg-gray-800 transition">
                    <span>👥</span> <span>کاربران و دسترسی‌ها</span>
                </a>
                <a href="orders.html" id="menu-orders" class="w-full flex items-center space-x-reverse space-x-3 px-4 py-3 rounded-lg text-gray-300 hover:bg-gray-800 transition">
                    <span>💳</span> <span>سفارشات و مالی</span>
                </a>
                <a href="gallery.html" id="menu-gallery" class="w-full flex items-center space-x-reverse space-x-3 px-4 py-3 rounded-lg text-gray-300 hover:bg-gray-800 transition">
                    <span>🖼️</span> <span>گالری تصاویر</span>
                </a>
            </nav>
        </div>
        <div class="p-4 border-t border-gray-800 text-xs text-center text-gray-500">نسخه دیتابیس: Alembic v1.2</div>
    </aside>
    `;

    // تزریق سایدبار به ابتدای تگ body در تمام صفحات
    document.body.insertAdjacentHTML('afterbegin', sidebarHTML);

    // پیدا کردن صفحه فعلی و روشن کردن دکمه فعال آن در منو
    const currentPage = window.location.pathname.split("/").pop() || "panelmangemnt.html";
    const activeMenu = document.getElementById(`menu-${currentPage.replace('.html', '')}`);
    if (activeMenu) {
        activeMenu.classList.remove('text-gray-300', 'hover:bg-gray-800');
        activeMenu.classList.add('bg-green-600', 'text-white');
    }
});