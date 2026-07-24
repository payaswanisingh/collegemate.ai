// static/theme.js
// Shared light/dark theme toggle with localStorage persistence.
// Used on landing / login / register / dashboard pages.
// Shares the same "campusmate-theme" storage key with index.html/script.js
// so the preference stays in sync across the whole app.

(function () {
    var STORAGE_KEY = 'campusmate-theme';

    function applyStoredTheme() {
        try {
            var saved = localStorage.getItem(STORAGE_KEY);
            if (saved === 'light') {
                document.body.classList.add('light');
            }
        } catch (e) {
            /* localStorage unavailable — fall back to default theme */
        }
    }

    function initThemeToggle() {
        var toggles = document.querySelectorAll('[data-theme-toggle]');
        if (!toggles.length) {
            var toggle = document.getElementById('themeToggle');
            if (!toggle) return;
            toggles = [toggle];
        }

        toggles.forEach(function (toggle) {
            toggle.addEventListener('click', function () {
                var isLight = document.body.classList.toggle('light');
                try {
                    localStorage.setItem(STORAGE_KEY, isLight ? 'light' : 'dark');
                } catch (e) {
                    /* ignore write failures */
                }
            });
        });
    }

    applyStoredTheme();
    document.addEventListener('DOMContentLoaded', initThemeToggle);
})();
