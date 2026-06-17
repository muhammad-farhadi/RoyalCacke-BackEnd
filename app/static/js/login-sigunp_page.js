        function switchTab(type) {
            document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
            document.querySelectorAll('.auth-form').forEach(form => form.classList.remove('active'));
            
            if(type === 'login') {
                document.querySelectorAll('.tab-btn')[0].classList.add('active');
                document.getElementById('loginForm').classList.add('active');
            } else {
                document.querySelectorAll('.tab-btn')[1].classList.add('active');
                document.getElementById('registerForm').classList.add('active');
            }
        }