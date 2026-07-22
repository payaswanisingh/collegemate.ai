// static/auth.js
// New file. Does not modify static/script.js.
// Provides a live password-strength indicator and confirm-password
// match hint on the registration page. This is a UX convenience only
// — the authoritative validation always happens server-side in
// auth/validators.py; nothing here can substitute for that.

(function () {
    function scorePassword(password) {
        let score = 0;
        if (!password) return 0;

        if (password.length >= 8) score++;
        if (password.length >= 12) score++;
        if (/[A-Z]/.test(password)) score++;
        if (/[a-z]/.test(password)) score++;
        if (/\d/.test(password)) score++;
        if (/[^\w\s]/.test(password)) score++;

        return Math.min(score, 6);
    }

    function describeStrength(score) {
        if (score <= 2) return { label: 'Weak', color: 'var(--danger)', percent: 25 };
        if (score <= 4) return { label: 'Fair', color: 'var(--warning)', percent: 60 };
        if (score <= 5) return { label: 'Strong', color: 'var(--secondary)', percent: 85 };
        return { label: 'Very strong', color: 'var(--success)', percent: 100 };
    }

    function initPasswordStrength() {
        const passwordInput = document.getElementById('password');
        const fill = document.getElementById('strengthFill');
        const label = document.getElementById('strengthLabel');

        if (!passwordInput || !fill || !label) return;

        passwordInput.addEventListener('input', () => {
            const value = passwordInput.value;
            if (!value) {
                fill.style.width = '0%';
                label.textContent = '';
                return;
            }
            const score = scorePassword(value);
            const { label: text, color, percent } = describeStrength(score);
            fill.style.width = percent + '%';
            fill.style.background = color;
            label.textContent = text;
        });
    }

    function initConfirmPasswordMatch() {
        const passwordInput = document.getElementById('password');
        const confirmInput = document.getElementById('confirm_password');
        const hint = document.getElementById('matchHint');

        if (!passwordInput || !confirmInput || !hint) return;

        function checkMatch() {
            if (!confirmInput.value) {
                hint.textContent = '';
                hint.className = 'match-hint';
                return;
            }
            if (confirmInput.value === passwordInput.value) {
                hint.textContent = 'Passwords match';
                hint.className = 'match-hint ok';
            } else {
                hint.textContent = 'Passwords do not match';
                hint.className = 'match-hint bad';
            }
        }

        passwordInput.addEventListener('input', checkMatch);
        confirmInput.addEventListener('input', checkMatch);
    }

    // ------------------------------------------------------------------
    // Registration form: show/hide fields based on selected account type,
    // and toggle `required` on inputs so hidden fields never block
    // submission or get sent for the wrong account type.
    // ------------------------------------------------------------------
    function setSectionRequired(sectionEl, isActive) {
        if (!sectionEl) return;
        sectionEl.querySelectorAll('input, select').forEach((el) => {
            // Never force-require the stream field here; that is handled
            // separately based on class_level.
            if (el.id === 'stream') return;
            el.required = isActive;
        });
    }

    function initUserTypeFields() {
        const userTypeSelect = document.getElementById('user_type');
        const collegeFields = document.getElementById('college-fields');
        const schoolFields = document.getElementById('school-fields');
        const parentFields = document.getElementById('parent-fields');
        const classLevelSelect = document.getElementById('class_level');
        const streamField = document.getElementById('stream-field');
        const streamSelect = document.getElementById('stream');

        if (!userTypeSelect || !collegeFields || !schoolFields) return;

        function updateStreamVisibility() {
            const cls = classLevelSelect ? classLevelSelect.value : '';
            const showStream = cls === '11' || cls === '12';
            if (streamField) streamField.style.display = showStream ? '' : 'none';
            if (streamSelect) streamSelect.required = showStream;
            if (!showStream && streamSelect) streamSelect.value = '';
        }

        function updateVisibility() {
            const type = userTypeSelect.value;

            collegeFields.style.display = type === 'college_student' ? '' : 'none';
            schoolFields.style.display = type === 'school_student' ? '' : 'none';
            if (parentFields) parentFields.style.display = type === 'parent' ? '' : 'none';

            setSectionRequired(collegeFields, type === 'college_student');
            setSectionRequired(schoolFields, type === 'school_student');

            if (type === 'school_student') {
                updateStreamVisibility();
            } else if (streamField) {
                streamField.style.display = 'none';
                if (streamSelect) { streamSelect.required = false; streamSelect.value = ''; }
            }
        }

        userTypeSelect.addEventListener('change', updateVisibility);
        if (classLevelSelect) classLevelSelect.addEventListener('change', updateStreamVisibility);

        // Run once on load in case the form is being re-rendered with a
        // previously-selected type (e.g. after a validation error).
        updateVisibility();
    }

    document.addEventListener('DOMContentLoaded', () => {
        initPasswordStrength();
        initConfirmPasswordMatch();
        initUserTypeFields();
    });
})();
