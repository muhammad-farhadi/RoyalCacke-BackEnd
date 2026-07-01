// js/api.js

// آدرس پایه به همراه پروکسی معکوس برای دور زدن دائمی خطای CORS در فرانت‌اند (محیط توسعه محلی)
const API_BASE = 'https://royalcakes.ir/api/v1';

// =========================================================================
// سامانه کَش هوشمند (Memory Cache) جهت جلوگیری از رکوئست‌های تکراری و کند شبکه
// =========================================================================
const _apiCache = new Map();
const CACHE_DURATION = 5 * 60 * 1000; // مدت زمان اعتبار کَش: ۵ دقیقه

// تابع کمکی برای مدیریت خروج موقت یا دائم کَش
function clearCacheByKeyPrefix(prefix) {
    for (const key of _apiCache.keys()) {
        if (key.startsWith(prefix)) {
            _apiCache.delete(key);
        }
    }
}

const ApiService = {
    // برای جلوگیری از حلقه تکرار بی‌نهایت در صورت خراب بودن رفرش‌توکن
    isRefreshing: false,

    // ==========================================
    // ۰. هسته مرکزی و هوشمند مدیریت درخواست‌ها
    // ==========================================
    async request(endpoint, options = {}) {
        const url = `${API_BASE}${endpoint}`;
        
        // ایجاد یک کپی عمیق از هدرها برای جلوگیری از تداخل در درخواست‌های مجدد
        options.headers = { ...options.headers };
        
        // تشخیص خودکار هدر برای ارسال اطلاعات متنی یا فایل
        if (options.body && !(options.body instanceof FormData)) {
            options.headers['Content-Type'] = 'application/json';
        }
        
        options.headers['accept'] = 'application/json';
        
        // تزریق خودکار اکسس توکن به درخواست‌ها
        const token = localStorage.getItem('access_token');
        if (token) {
            options.headers['Authorization'] = `Bearer ${token}`;
        }

        try {
            const response = await fetch(url, options);

            // 🔴 اگر توکن منقضی شده بود (خطای 401)
            if (response.status === 401 && !this.isRefreshing) {
                console.warn(`Token expired for ${endpoint}. Attempting to refresh...`);
                
                // تلاش برای گرفتن اکسس توکن جدید با استفاده از رفرش توکن
                const refreshed = await this.refreshToken();
                
                if (refreshed) {
                    // دریافت توکن جدیدِ ذخیره شده
                    const newToken = localStorage.getItem('access_token');
                    
                    // هدر درخواست قبلی را کاملاً پاکسازی و با توکن جدید به‌روزرسانی می‌کنیم
                    options.headers['Authorization'] = `Bearer ${newToken}`;
                    
                    // درخواست را مجدداً تکرار می‌کنیم و خروجی را برمی‌گردانیم
                    return await this.request(endpoint, options);
                } else {
                    // اگر رفرش توکن هم اکسپایر شده بود، کاربر باید دوباره لاگین کند
                    this.logout();
                    return;
                }
            }

            if (response.status === 204) return true;

            const data = await response.json().catch(() => ({}));

            if (!response.ok) {
                throw new Error(data.detail || `خطای سرور: ${response.status}`);
            }

            return data;
        } catch (error) {
            console.error(`API Error [${options.method || 'GET'} ${endpoint}]:`, error);
            throw error;
        }
    },

    // ==========================================
    // ۱. سرویس‌های احراز هویت و مدیریت کاربران
    // ==========================================
    
    // متد ورود (Form URL Encoded)
    async login(mobile, password) {
        const params = new URLSearchParams();
        params.append('grant_type', 'password');
        params.append('username', mobile);
        params.append('password', password);
        params.append('scope', '');
        params.append('client_id', 'string');
        params.append('client_secret', '********');

        const response = await fetch(`${API_BASE}/users/login`, {
            method: 'POST',
            headers: {
                'accept': 'application/json',
                'Content-Type': 'application/x-www-form-urlencoded'
            },
            body: params.toString()
        });

        if (!response.ok) {
            const err = await response.json().catch(() => ({}));
            throw new Error(err.detail || 'شماره موبایل یا رمز عبور اشتباه است.');
        }

        const data = await response.json();
        
        // ذخیره هر دو توکن دریافتی از بک‌اَند
        if (data.access_token && data.refresh_token) {
            localStorage.setItem('access_token', data.access_token);
            localStorage.setItem('refresh_token', data.refresh_token);
        }
        return data;
    },

    // تابع تمدید توکن پشت صحنه (کاملاً سایلنت و بدون دخالت کاربر)
    async refreshToken() {
        const refreshToken = localStorage.getItem('refresh_token');
        if (!refreshToken) return false;

        this.isRefreshing = true;
        try {
            const response = await fetch(`${API_BASE}/users/refresh`, {
                method: 'POST',
                headers: {
                    'accept': 'application/json',
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ refresh_token: refreshToken })
            });

            if (!response.ok) throw new Error('Refresh token expired');

            const data = await response.json();
            
            // جایگذاری توکن‌های جدیدِ تمدید شده در مرورگر
            if (data.access_token && data.refresh_token) {
                localStorage.setItem('access_token', data.access_token);
                localStorage.setItem('refresh_token', data.refresh_token);
            }
            
            console.log('Tokens refreshed successfully in background.');
            this.isRefreshing = false;
            return true;
        } catch (err) {
            console.error('Failed to refresh token seamlessly:', err);
            this.isRefreshing = false;
            return false;
        }
    },

    // خروج از حساب کاربری
    logout() {
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        localStorage.removeItem('user_mobile');
        _apiCache.clear(); // پاکسازی کامل حافظه کش در هنگام خروج ادمین
        alert('جلسه کاری شما پایان یافته است. لطفاً مجدداً وارد شوید.');
        window.location.href = 'login-sigunp_page.html';
    },

    // دریافت لیست کاربران (با فیلتر تعداد و لودینگ هوشمند)
    async getUsers(skip = 0, limit = 50) {
        const cacheKey = `users_${skip}_${limit}`;
        const cached = _apiCache.get(cacheKey);
        if (cached && (Date.now() - cached.timestamp < CACHE_DURATION)) {
            return cached.data;
        }

        const data = await this.request(`/users/?skip=${skip}&limit=${limit}`, { method: 'GET' });
        _apiCache.set(cacheKey, { data, timestamp: Date.now() });
        return data;
    },

    // ویرایش اطلاعات کاربر
    async updateUser(userId, userData) {
        const result = await this.request(`/users/${userId}`, {
            method: 'PUT',
            body: JSON.stringify(userData)
        });
        clearCacheByKeyPrefix('users_'); // پاکسازی کش کاربران
        return result;
    },

    // دریافت اطلاعات ادمین فعلی
    async getCurrentUser() {
        return this.request('/users/me');
    },

    // حذف کاربر
    async deleteUser(userId) {
        const result = await this.request(`/users/${userId}`, { method: 'DELETE' });
        clearCacheByKeyPrefix('users_'); // پاکسازی کش کاربران
        return result;
    },

    // ==========================================
    // ۲. سرویس‌های مدیریت گالری تصاویر (Gallery)
    // ==========================================
    async getImages() {
        const cacheKey = 'gallery_list';
        const cached = _apiCache.get(cacheKey);
        if (cached && (Date.now() - cached.timestamp < CACHE_DURATION)) {
            return cached.data;
        }

        const data = await this.request('/gallery/');
        _apiCache.set(cacheKey, { data, timestamp: Date.now() });
        return data;
    },

    async addImage(title, altText, fileObject, category = "cake") {
        const formData = new FormData();
        formData.append('title', title);
        formData.append('alt_text', altText);
        formData.append('category', category);
        formData.append('file', fileObject);

        const result = await this.request('/gallery/', {
            method: 'POST',
            body: formData
        });
        _apiCache.delete('gallery_list'); // انقضای فوری کش گالری
        return result;
    },

    async deleteImage(imageId) {
        const result = await this.request(`/gallery/${imageId}`, { method: 'DELETE' });
        _apiCache.delete('gallery_list'); // انقضای فوری کش گالری
        return result;
    },

    // ==========================================
    // ۳. سرویس‌های مدیریت دوره‌ها و دروس (Courses & Lessons)
    // ==========================================
    async getCourses() {
        const cacheKey = 'courses_list';
        const cached = _apiCache.get(cacheKey);
        if (cached && (Date.now() - cached.timestamp < CACHE_DURATION)) {
            return cached.data;
        }

        const data = await this.request('/courses/');
        _apiCache.set(cacheKey, { data, timestamp: Date.now() });
        return data;
    },

    async getCourseById(courseId) {
        return this.request(`/courses/${courseId}`);
    },

    async createCourse(formDataObject) {
        const result = await this.request('/courses/', {
            method: 'POST',
            body: formDataObject 
        });
        _apiCache.delete('courses_list');
        return result;
    },

    async updateCourse(courseId, updatedData) {
        const result = await this.request(`/courses/${courseId}`, {
            method: 'PUT',
            body: JSON.stringify(updatedData)
        });
        _apiCache.delete('courses_list');
        return result;
    },

    async deleteCourse(courseId) {
        const result = await this.request(`/courses/${courseId}`, { method: 'DELETE' });
        _apiCache.delete('courses_list');
        return result;
    },

    async createLesson(formDataObject) {
        return this.request('/courses/lessons', {
            method: 'POST',
            body: formDataObject
        });
    },

    async deleteLesson(lessonId) {
        return this.request(`/lessons/${lessonId}`, { 
            method: 'DELETE' 
        });
    },

    // ==========================================
    // ۴. سرویس‌های مدیریت سفارشات و مالی (Orders)
    // ==========================================
    async getOrders() {
        return this.request('/orders/');
    },

    async getOrderById(orderId) {
        return this.request(`/orders/${orderId}`);
    },

    async updateOrderStatus(orderId, status) {
        return this.request(`/orders/${orderId}/status`, {
            method: 'PATCH',
            body: JSON.stringify({ status })
        });
    },

    // ==========================================
    // ۵. سرویس‌های مدیریت مقالات و وبلاگ (Articles)
    // ==========================================
    
    // دریافت تمامی مقالات (مجهز به سیستم سرعت‌دهنده لایتنینگ کَش)
    async getArticles(skip = 0, limit = 50) {
        const cacheKey = `articles_${skip}_${limit}`;
        const cachedData = _apiCache.get(cacheKey);
        const now = Date.now();

        // لود آنی دیتای کَش شده بدون اشغال ترافیک سرور
        if (cachedData && (now - cachedData.timestamp < CACHE_DURATION)) {
            console.log('%c⚡ لود آنی لیست مقالات از حافظه کَش موقت فرانت‌اند', 'color: #10b981; font-weight: bold;');
            return cachedData.data;
        }

        const data = await this.request(`/articles/?skip=${skip}&limit=${limit}`, {
            method: 'GET'
        });

        // ذخیره خروجی معتبر جدید بر روی مَپ
        _apiCache.set(cacheKey, {
            data: data,
            timestamp: now
        });

        return data;
    },

    // دریافت اطلاعات یک مقاله بر اساس شناسه اختصاصی
    async getArticleById(articleId) {
        return this.request(`/articles/${articleId}`, {
            method: 'GET'
        });
    },

    // ساخت مقاله جدید بر اساس ساختار multipart/form-data
    async createArticle(title, slug, content, metaDescription, tags, fileObject) {
        const formData = new FormData();
        formData.append('title', title);
        formData.append('slug', slug);
        formData.append('content', content);
        formData.append('meta_description', metaDescription);
        formData.append('tags', tags);
        
        if (fileObject) {
            formData.append('image', fileObject);
        }

        const result = await this.request('/articles/', {
            method: 'POST',
            body: formData
        });

        // انقضای کَش قبلی مقالات جهت اعمال تغییرات جدید در لود بعدی
        clearCacheByKeyPrefix('articles_');
        return result;
    },

    // ویرایش و به‌روزرسانی مقاله (پشتیبانی هوشمند از ویرایش متن یا تغییر عکس)
    async updateArticle(articleId, title, slug, content, metaDescription, tags, fileObject = null) {
        const formData = new FormData();
        formData.append('title', title);
        formData.append('slug', slug);
        formData.append('content', content);
        formData.append('meta_description', metaDescription);
        formData.append('tags', tags);
        
        if (fileObject) {
            formData.append('image', fileObject);
        } else {
            formData.append('image', ''); 
        }

        const result = await this.request(`/articles/${articleId}`, {
            method: 'PUT',
            body: formData
        });

        // انقضای کَش قبلی مقالات جهت اعمال تغییرات جدید در لود بعدی
        clearCacheByKeyPrefix('articles_');
        return result;
    },

    // حذف قطعی مقاله از سیستم
    async deleteArticle(articleId) {
        const result = await this.request(`/articles/${articleId}`, {
            method: 'DELETE'
        });

        // انقضای کَش قبلی مقالات جهت اعمال تغییرات جدید در لود بعدی
        clearCacheByKeyPrefix('articles_');
        return result;
    },
    // ارسال پیام کاربر به صورت x-www-form-urlencoded
    async sendContactMessage(name, phoneNumber, message) {
        const params = new URLSearchParams();
        params.append('name', name);
        params.append('phone_number', phoneNumber);
        params.append('message', message);

        return this.request('/contact', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded'
            },
            body: params.toString()
        });
    }
};