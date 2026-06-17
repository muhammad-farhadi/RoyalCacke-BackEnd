// جاوااسکریپت پرش خودکار بین اینپوت‌ها
function moveNext(current, nextId) {
    if (current.value.length >= 1 && nextId !== "") {
        document.getElementById(nextId).focus();
    }
}

let timeLeft = 120;
let countdownInterval; // تعریف متغیر به صورت عمومی
const timerSpan = document.getElementById('timer');
const timerBox = document.getElementById('timerBox');
const resendBtn = document.getElementById('resendBtn');

function startCountdown() {
    // جلوگیری از تداخل تایمرها
    clearInterval(countdownInterval);

    countdownInterval = setInterval(() => {
        let minutes = Math.floor(timeLeft / 60);
        let seconds = timeLeft % 60;
        seconds = seconds < 10 ? '0' + seconds : seconds;
        timerSpan.textContent = `0${minutes}:${seconds}`;

        if (timeLeft <= 0) {
            clearInterval(countdownInterval);
            timerBox.style.display = 'none';
            resendBtn.style.display = 'block';
        }
        timeLeft--;
    }, 1000);
}

function restartTimer() {
    timeLeft = 120;
    timerBox.style.display = 'block';
    resendBtn.style.display = 'none';
    startCountdown();
}

// اجرای اولیه
startCountdown();


// جاوااسکریپت پرش خودکار به جلو (کد قبلی شما)
function moveNext(current, nextId) {
    if(current.value.length >= 1 && nextId !== "") {
        document.getElementById(nextId).focus();
    }
}

// تابع جدید: مدیریت دکمه بک‌اسپیس برای برگشت به عقب و پاک کردن
function moveBack(event, prevId) {
    // بررسی اینکه آیا دکمه فشرده شده Backspace است یا خیر
    if (event.key === "Backspace") {
        const currentInput = event.target;
        
        // اگر اینپوت فعلی خالی است، به اینپوت قبلی برو و آن را پاک کن
        if (currentInput.value === "" && prevId !== "") {
            const prevInput = document.getElementById(prevId);
            prevInput.focus();
            prevInput.value = ""; // پاک کردن مقدار اینپوت قبلی
            event.preventDefault(); // جلوگیری از رفتار پیش‌فرض مرورگر
        }
    }
}