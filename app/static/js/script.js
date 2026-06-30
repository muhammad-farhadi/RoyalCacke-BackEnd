// ================= مدیریت اسلایدر تصاویر (رویال کیک) =================
let slideIndex = 1;
let slideInterval;
const slides = document.getElementsByClassName("slide");
const dotsContainer = document.getElementById("dotsContainer");

// ۱. ساخت نقطه‌ها به صورت کاملاً خودکار به تعداد عکس‌ها
function createDots() {
    if (!dotsContainer) return;
    dotsContainer.innerHTML = ""; // خالی کردن کانتینر
    for (let i = 0; i < slides.length; i++) {
        const dot = document.createElement("span");
        dot.className = "dot";
        dot.addEventListener("click", function() {
            currentSlide(i + 1);
        });
        dotsContainer.appendChild(dot);
    }
}

// ۲. تابع اصلی نمایش اسلایدها و فعال‌سازی نقطه‌ها
function showSlides(n) {
    if (slides.length === 0) return;
    let i;
    const dots = document.getElementsByClassName("dot");
    
    if (n > slides.length) { slideIndex = 1; }
    if (n < 1) { slideIndex = slides.length; }
    
    // مخفی کردن تمام اسلایدها
    for (i = 0; i < slides.length; i++) {
        slides[i].style.display = "none";
    }
    
    // حذف کلاس active از تمام نقطه‌ها
    for (i = 0; i < dots.length; i++) {
        dots[i].className = dots[i].className.replace(" active", "");
    }
    
    // نمایش اسلاید فعلی و فعال کردن نقطه هم‌ردیف
    if (slides[slideIndex - 1]) {
        slides[slideIndex - 1].style.display = "block"; 
    }
    if (dots[slideIndex - 1]) {
        dots[slideIndex - 1].className += " active";
    }
}

// ۳. توابع کنترل حرکتی اسلایدر و ریست تایمر خودکار
function changeSlide(n) {
    showSlides(slideIndex += n);
    resetInterval(); 
}

function currentSlide(n) {
    showSlides(slideIndex = n);
    resetInterval(); 
}

function startAutoSlide() {
    clearInterval(slideInterval); 
    slideInterval = setInterval(function() {
        changeSlide(1);
    }, 4000); // ورق زدن خودکار هر ۴ ثانیه
}

function resetInterval() {
    clearInterval(slideInterval);
    startAutoSlide();
}


// ================= منوی ریسپانسیو (موبایل) =================
const mobileMenu = document.getElementById('mobile-menu');
const navElements = document.querySelector('.nav-elements');

if (mobileMenu && navElements) {
    mobileMenu.addEventListener('click', () => {
        navElements.classList.toggle('active');
        const icon = mobileMenu.querySelector('i');
        if (icon) {
            if (navElements.classList.contains('active')) {
                icon.classList.remove('fa-bars');
                icon.classList.add('fa-times');
            } else {
                icon.classList.remove('fa-times');
                icon.classList.add('fa-bars');
            }
        }
    });
}


// ================= مدیریت کارت‌ها، گالری و لایک‌ها پس از لود صفحه =================
document.addEventListener('DOMContentLoaded', () => {
    // اجرای اولیه اسلایدر
    createDots(); 
    showSlides(slideIndex); 
    startAutoSlide();

    // انیمیشن ورود کارت‌ها با اسکرول
    const courseCards = document.querySelectorAll('.course-card');
    if (courseCards.length > 0) {
        const observerOptions = {
            root: null,
            threshold: 0.1,
            rootMargin: "0px"
        };

        const cardObserver = new IntersectionObserver((entries, observer) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.style.opacity = '1';
                    entry.target.style.transform = 'translateY(0)';
                    observer.unobserve(entry.target);
                }
            });
        }, observerOptions);

        courseCards.forEach(card => {
            card.style.opacity = '0';
            card.style.transform = 'translateY(40px)';
            card.style.transition = 'all 0.6s cubic-bezier(0.25, 1, 0.5, 1)';
            cardObserver.observe(card);
        });

        // افکت ۳ بعدی حرکتی ماوس روی کارت‌ها
        courseCards.forEach(card => {
            card.addEventListener('mousemove', (e) => {
                const cardRect = card.getBoundingClientRect();
                const x = e.clientX - cardRect.left;
                const y = e.clientY - cardRect.top;
                const midCardX = cardRect.width / 2;
                const midCardY = cardRect.height / 2;
                const angleX = -(y - midCardY) / (midCardY / 10);
                const angleY = (x - midCardX) / (midCardX / 10);
                card.style.transform = `perspective(1000px) rotateX(${angleX}deg) rotateY(${angleY}deg) translateY(-8px)`;
            });

            card.addEventListener('mouseleave', () => {
                card.style.transform = 'perspective(1000px) rotateX(0deg) rotateY(0deg) translateY(0)';
            });
        });
    }

    // سیستم هوشمند مشاهده بیشتر گالری
    initGallery();
});


// ================= سیستم لایک تعاملی وبلاگ =================
const likeButtons = document.querySelectorAll('.like-btn');
likeButtons.forEach(btn => {
    btn.addEventListener('click', function (e) {
        e.preventDefault(); 
        const icon = this.querySelector('i');
        const countSpan = this.querySelector('.like-count');
        if (!countSpan || !icon) return;
        
        let currentCount = parseInt(countSpan.textContent) || 0;

        if (this.classList.contains('liked')) {
            this.classList.remove('liked');
            icon.classList.remove('fas');
            icon.classList.add('far');
            countSpan.textContent = currentCount - 1;
        } else {
            this.classList.add('liked');
            icon.classList.remove('far');
            icon.classList.add('fas');
            countSpan.textContent = currentCount + 1;
        }
    });
});


// ================= فیلتر گالری تصاویر =================
function filterGallery(category) {
    const buttons = document.querySelectorAll('.filter-btn');
    buttons.forEach(btn => btn.classList.remove('active'));
    if (window.event && window.event.target) {
        window.event.target.classList.add('active');
    }

    const items = document.querySelectorAll('.gallery-item');
    items.forEach(item => {
        if (category === 'all' || item.classList.contains(category)) {
            item.classList.remove('hide');
        } else {
            item.classList.add('hide');
        }
    });
}


// ================= سیستم گالری (تعداد آیتم‌های اولیه) =================
let currentItems = 6; 

function initGallery() {
    const galleryItems = document.querySelectorAll('.gallery-item');
    const loadMoreBtn = document.getElementById('loadMoreBtn');
    
    if (!galleryItems.length || !loadMoreBtn) return;

    for (let i = 0; i < galleryItems.length; i++) {
        if (i < currentItems) {
            galleryItems[i].style.display = 'block';
        } else {
            galleryItems[i].style.display = 'none';
        }
    }
    
    if (galleryItems.length <= currentItems) {
        loadMoreBtn.style.display = 'none';
    }
}

function loadMoreImages() {
    const galleryItems = document.querySelectorAll('.gallery-item');
    const loadMoreBtn = document.getElementById('loadMoreBtn');
    if (!galleryItems.length) return;
    
    const visibleItems = Array.from(galleryItems).filter(item => item.style.display === 'block').length;
    
    for (let i = visibleItems; i < visibleItems + currentItems && i < galleryItems.length; i++) {
        galleryItems[i].style.display = 'block';
    }
    
    const totalVisible = Array.from(galleryItems).filter(item => item.style.display === 'block').length;
    if (totalVisible >= galleryItems.length && loadMoreBtn) {
        loadMoreBtn.style.display = 'none';
    }
}


// ================= سیستم هوشمند فرم تماس و پاپ‌آپ بدون تغییر صفحه =================
function openContactModal() {
    // ۱. دریافت مقادیر ورودی‌ها
    const name = document.getElementById('contactName').value.trim();
    const phone = document.getElementById('contactPhone').value.trim();
    const message = document.getElementById('contactMessage').value.trim();
    const formElement = document.getElementById('royalContactForm');

    // ۲. بررسی خالی نبودن فیلدها
    if (!name || !phone || !message) {
        alert('لطفاً تمامی فیلدها را به درستی تکمیل کنید.');
        return;
    }

    // ۳. تغییر حالت دکمه به لودینگ فرضی برای جذابیت بصری
    const submitBtn = formElement.querySelector('.btn-submit-contact');
    const originalBtnText = submitBtn.innerHTML;
    submitBtn.innerHTML = 'در حال ارسال... <i class="fa-solid fa-spinner fa-spin"></i>';
    submitBtn.disabled = true;

    // ۴. باز کردن پاپ‌آپ روی همان صفحه بعد از یک مکث کوتاه نیم‌ثانیه‌ای
    setTimeout(() => {
        // اختصاصی کردن پیام داخل پاپ‌آپ با نام کاربر
        const modalMessage = document.getElementById('modalUserMessage');
        if (modalMessage) {
            modalMessage.textContent = `${name} عزیز، پیام شما با موفقیت دریافت شد. به زودی با شما تماس می‌گیریم.`;
        }

        // افزودن کلاس show برای نمایش پاپ‌آپ شیشه‌ای
        const modal = document.getElementById('contactModal');
        if (modal) {
            modal.classList.add('show');
        }

        // ریست فرم و بازگرداندن دکمه به حالت اولیه
        formElement.reset();
        submitBtn.innerHTML = originalBtnText;
        submitBtn.disabled = false;
    }, 600);
}

// تابع بستن پاپ‌آپ
function closeContactModal() {
    const modal = document.getElementById('contactModal');
    if (modal) {
        modal.classList.remove('show');
    }
}