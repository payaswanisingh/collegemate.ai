document.addEventListener('DOMContentLoaded', () => {
    // ===== DOM Elements =====
    const questionInput = document.getElementById('questionInput');
    const sendBtn = document.getElementById('sendBtn');
    const chatList = document.getElementById('chatList');
    const welcomeScreen = document.getElementById('welcomeScreen');
    const welcomePrompts = document.getElementById('welcomePrompts');
    const sidebarToggle = document.getElementById('sidebarToggle');
    const sidebarPanel = document.getElementById('sidebarPanel');
    const sidebarScrim = document.getElementById('sidebarScrim');
    const newChatBtn = document.getElementById('newChatBtn');
    const themeToggle = document.getElementById('themeToggle');
    const clock = document.getElementById('clock');
    const currentDate = document.getElementById('currentDate');
    const settingsBtn = document.getElementById('settingsBtn');
    const closeSettings = document.getElementById('closeSettings');
    const settingsPanel = document.getElementById('settingsPanel');
    const settingsScrim = settingsPanel.querySelector('.settings-scrim');
    const sidebarCategories = document.getElementById('sidebarCategories');
    const clearChatBtn = document.getElementById('clearChatBtn');
    const themeControl = document.getElementById('themeControl');
    const accentControl = document.getElementById('accentControl');
    const fontSizeControl = document.getElementById('fontSizeControl');
    const logoutBtn = document.getElementById('logoutBtn');
    const toast = document.getElementById('toast');

    // ===== Icon library (Lucide-style inline SVGs, no emojis) =====
    const icons = {
        admissions: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><line x1="19" y1="8" x2="19" y2="14"></line><line x1="22" y1="11" x2="16" y2="11"></line></svg>',
        fees: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><rect x="1" y="4" width="22" height="16" rx="2"></rect><line x1="1" y1="10" x2="23" y2="10"></line></svg>',
        scholarships: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="8" r="6"></circle><path d="M15.5 13.4L17 22l-5-3-5 3 1.5-8.6"></path></svg>',
        hostel: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"></path><polyline points="9 22 9 12 15 12 15 22"></polyline></svg>',
        library: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"></path><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"></path></svg>',
        placements: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="7" width="20" height="14" rx="2"></rect><path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"></path></svg>',
        attendance: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"></rect><path d="M9 12l2 2 4-4"></path></svg>',
        examinations: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="8" y1="13" x2="16" y2="13"></line><line x1="8" y1="17" x2="12" y2="17"></line></svg>',
        campusLife: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><path d="M23 21v-2a4 4 0 0 0-3-3.87"></path><path d="M16 3.13a4 4 0 0 1 0 7.75"></path></svg>',
    };

    // ===== Data =====
    const welcomeTopics = [
        { icon: icons.admissions, title: 'Admission Process', query: 'Admission Process' },
        { icon: icons.fees, title: 'Fee Structure', query: 'Fee Structure' },
        { icon: icons.scholarships, title: 'Scholarships', query: 'Scholarships' },
        { icon: icons.hostel, title: 'Hostel', query: 'Hostel Facilities' },
        { icon: icons.library, title: 'Library', query: 'Library Timings' },
        { icon: icons.placements, title: 'Placements', query: 'Placement Cell' },
        { icon: icons.attendance, title: 'Attendance', query: 'Attendance Policy' },
        { icon: icons.examinations, title: 'Examinations', query: 'Exam Dates' },
    ];

    const categories = [
        { icon: icons.fees, name: 'Fees', query: 'Fee Structure' },
        { icon: icons.examinations, name: 'Examinations', query: 'Exam Dates' },
        { icon: icons.admissions, name: 'Admissions', query: 'Admission Process' },
        { icon: icons.hostel, name: 'Hostel', query: 'Hostel Facilities' },
        { icon: icons.placements, name: 'Placements', query: 'Placement Cell' },
        { icon: icons.library, name: 'Library', query: 'Library Timings' },
        { icon: icons.campusLife, name: 'Campus Life', query: 'Student Services' },
    ];

    // ===== State =====
    let messageCount = 0;

    // ===== Storage Keys =====
    const THEME_KEY = 'campusmate-theme';
    const ACCENT_KEY = 'campusmate-accent';
    const FONT_SIZE_KEY = 'campusmate-font-size';

    // ===== Initialize =====
    function init() {
        applyStoredTheme();
        applyStoredAccent();
        applyStoredFontSize();
        updateClock();
        updateDate();
        renderWelcomePrompts();
        renderSidebarCategories();
        setupEventListeners();
        syncSettingsUI();
        setInterval(updateClock, 60 * 1000);
        setInterval(updateDate, 1000);
    }

    // ===== Clock & Date =====
    function updateClock() {
        if (!clock) return;
        const now = new Date();
        const hours = now.getHours().toString().padStart(2, '0');
        const minutes = now.getMinutes().toString().padStart(2, '0');
        clock.textContent = `${hours}:${minutes}`;
    }

    function updateDate() {
        if (!currentDate) return;
        const now = new Date();
        const options = { weekday: 'short', month: 'short', day: 'numeric' };
        currentDate.textContent = now.toLocaleDateString('en-US', options);
    }

    // ===== Theme Management =====
    function applyStoredTheme() {
        try {
            const saved = localStorage.getItem(THEME_KEY);
            if (saved === 'light') {
                document.body.classList.add('light');
            } else {
                document.body.classList.remove('light');
            }
        } catch (e) {
            // localStorage unavailable
        }
    }

    function setTheme(theme) {
        if (theme === 'light') {
            document.body.classList.add('light');
        } else {
            document.body.classList.remove('light');
        }
        try {
            localStorage.setItem(THEME_KEY, theme);
        } catch (e) {
            // ignore write failures
        }
        syncSettingsUI();
    }

    function toggleTheme() {
        const isLight = document.body.classList.contains('light');
        setTheme(isLight ? 'dark' : 'light');
    }

    // ===== Accent Color Management =====
    function applyStoredAccent() {
        try {
            const saved = localStorage.getItem(ACCENT_KEY) || 'blue';
            document.documentElement.setAttribute('data-accent', saved);
        } catch (e) {
            document.documentElement.setAttribute('data-accent', 'blue');
        }
    }

    function setAccent(accent) {
        document.documentElement.setAttribute('data-accent', accent);
        try {
            localStorage.setItem(ACCENT_KEY, accent);
        } catch (e) {
            // ignore write failures
        }
        syncSettingsUI();
    }

    // ===== Font Size Management =====
    function applyStoredFontSize() {
        try {
            const saved = localStorage.getItem(FONT_SIZE_KEY) || 'medium';
            document.documentElement.setAttribute('data-font-size', saved);
        } catch (e) {
            document.documentElement.setAttribute('data-font-size', 'medium');
        }
    }

    function setFontSize(size) {
        document.documentElement.setAttribute('data-font-size', size);
        try {
            localStorage.setItem(FONT_SIZE_KEY, size);
        } catch (e) {
            // ignore write failures
        }
        syncSettingsUI();
    }

    // ===== Sync Settings UI state =====
    function syncSettingsUI() {
        const isLight = document.body.classList.contains('light');
        const accent = document.documentElement.getAttribute('data-accent') || 'blue';
        const fontSize = document.documentElement.getAttribute('data-font-size') || 'medium';

        if (themeControl) {
            themeControl.querySelectorAll('.segmented-option').forEach((btn) => {
                btn.classList.toggle('active', btn.getAttribute('data-theme') === (isLight ? 'light' : 'dark'));
            });
        }

        if (accentControl) {
            accentControl.querySelectorAll('.accent-swatch').forEach((btn) => {
                btn.classList.toggle('active', btn.getAttribute('data-accent') === accent);
            });
        }

        if (fontSizeControl) {
            fontSizeControl.querySelectorAll('.segmented-option').forEach((btn) => {
                btn.classList.toggle('active', btn.getAttribute('data-size') === fontSize);
            });
        }
    }

    // ===== Toast =====
    function showToast(message) {
        if (!toast) return;
        toast.textContent = message;
        toast.classList.add('visible');
        setTimeout(() => toast.classList.remove('visible'), 2200);
    }

    // ===== Utility Functions =====
    function escapeHtml(value) {
        return String(value)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    // ===== Auto-scroll =====
    // The previous attempt scrolled `chatList` directly (chatList.scrollTop /
    // chatList.scrollTo). That only works if #chatList itself is the element
    // with overflow-y: auto/scroll. In this markup, #chatList is nested
    // inside <section class="chat-container">, and it's entirely possible
    // (and typical for this layout pattern) that the overflow/scrollbar
    // actually lives on .chat-container or another ancestor, while #chatList
    // just grows to fit its content with no scroll of its own. In that case
    // chatList.scrollHeight === chatList.clientHeight always, so setting
    // chatList.scrollTop does nothing — which is exactly why the fix
    // appeared to have no effect.
    //
    // Fix: don't hardcode which element scrolls. Walk up from #chatList at
    // runtime and find the nearest ancestor that actually has a vertical
    // scrollbar (overflowY is auto/scroll AND scrollHeight > clientHeight).
    // Cache it, but re-resolve if it's ever missing (e.g. after clearChat()
    // rebuilds the list before layout has happened, or on a page with
    // dynamic CSS).
    const AUTO_SCROLL_THRESHOLD = 120; // px from bottom still counted as "at bottom"
    let cachedScrollContainer = null;

    function findScrollContainer(startEl) {
        let node = startEl.parentElement;
        while (node && node !== document.body && node !== document.documentElement) {
            const style = window.getComputedStyle(node);
            const canScrollY = style.overflowY === 'auto' || style.overflowY === 'scroll';
            if (canScrollY && node.scrollHeight > node.clientHeight) {
                return node;
            }
            node = node.parentElement;
        }
        // Nothing in between scrolls — the page itself is the scroll container.
        return document.scrollingElement || document.documentElement;
    }

    function getChatScrollContainer() {
        if (!cachedScrollContainer || !document.body.contains(cachedScrollContainer)) {
            cachedScrollContainer = findScrollContainer(chatList);
        }
        return cachedScrollContainer;
    }

    function isNearBottom() {
        const container = getChatScrollContainer();
        return (
            container.scrollHeight - container.scrollTop - container.clientHeight <=
            AUTO_SCROLL_THRESHOLD
        );
    }

    // Scrolls the *actual* scrolling ancestor to its latest content, after
    // the new message node has already been inserted into the DOM.
    function scrollToBottom(smooth = true) {
        const container = getChatScrollContainer();
        const behavior = smooth ? 'smooth' : 'auto';
        if (container === document.documentElement || container === document.scrollingElement) {
            window.scrollTo({ top: container.scrollHeight, behavior });
        } else {
            container.scrollTo({ top: container.scrollHeight, behavior });
        }
    }

    // ===== Message Rendering =====
    function createMessageRow(type, message, meta) {
        const row = document.createElement('div');
        row.className = `message-row ${type}`;

        const avatar = document.createElement('div');
        avatar.className = `avatar ${type}`;
        avatar.textContent = type === 'assistant' ? 'AI' : 'You';

        const bubble = document.createElement('div');
        bubble.className = `bubble ${type}`;

        if (meta) {
            const header = document.createElement('div');
            header.className = 'message-header';
            const title = document.createElement('div');
            title.className = 'message-title';
            title.textContent = type === 'assistant' ? 'CampusMate AI' : 'You';
            const info = document.createElement('div');
            info.className = 'message-time';
            info.textContent = meta;
            header.appendChild(title);
            header.appendChild(info);
            bubble.appendChild(header);
        }

        const content = document.createElement('div');
        content.className = 'message-content';
        const text = document.createElement('p');
        text.innerHTML = escapeHtml(message).replace(/\n/g, '<br>');
        content.appendChild(text);
        bubble.appendChild(content);

        row.appendChild(avatar);
        row.appendChild(bubble);
        return row;
    }

    function createTypingIndicator() {
        const row = document.createElement('div');
        row.className = 'message-row assistant typing-indicator-row';

        const avatar = document.createElement('div');
        avatar.className = 'avatar assistant';
        avatar.textContent = 'AI';

        const bubble = document.createElement('div');
        bubble.className = 'bubble assistant typing-indicator';
        bubble.innerHTML = '<span></span><span></span><span></span>';

        row.appendChild(avatar);
        row.appendChild(bubble);
        return row;
    }

    // ===== addMessage: the single function that appends BOTH user and bot
    // bubbles to the DOM (chatList.appendChild(row)). This is the function
    // that needed fixing — sendQuestion() calls it once for the user's
    // message and once for the bot's answer, so fixing it here covers both
    // append paths, plus every append from history/other callers.
    function addMessage(type, text, meta) {
        // Read scroll position BEFORE appending: scrollHeight grows the
        // instant the node is inserted, so checking after would always
        // read "at bottom" even if the user had scrolled up to read
        // history — that's the condition we need to preserve.
        const shouldAutoScroll = isNearBottom();

        const row = createMessageRow(type, text, meta);
        chatList.appendChild(row); // <-- DOM update happens here

        // appendChild() is synchronous and the browser recalculates
        // scrollHeight/layout metrics immediately (no repaint needed to
        // read them), so scrollToBottom() is safe to call right here with
        // no setTimeout/requestAnimationFrame. It only fires post-append,
        // and only for the user who was already following the bottom.
        if (shouldAutoScroll) {
            scrollToBottom();
        }
    }

    function addTyping() {
        const shouldAutoScroll = isNearBottom();
        const typingRow = createTypingIndicator();
        chatList.appendChild(typingRow);
        if (shouldAutoScroll) {
            scrollToBottom();
        }
        return typingRow;
    }

    // ===== Welcome Screen =====
    function renderWelcomePrompts() {
        welcomePrompts.innerHTML = '';
        welcomeTopics.forEach((topic) => {
            const card = document.createElement('button');
            card.type = 'button';
            card.className = 'welcome-card';
            card.innerHTML = `
                <div class="welcome-card-icon">${topic.icon}</div>
                <div class="welcome-card-title">${topic.title}</div>
            `;
            card.addEventListener('click', () => {
                questionInput.value = topic.query;
                sendQuestion();
            });
            welcomePrompts.appendChild(card);
        });
    }

    function showWelcomeScreen() {
        if (welcomeScreen) {
            welcomeScreen.classList.remove('hidden');
        }
    }

    function hideWelcomeScreen() {
        if (welcomeScreen) {
            welcomeScreen.classList.add('hidden');
        }
    }

    // ===== Chat Management =====
    function clearChat() {
        chatList.innerHTML = '';
        messageCount = 0;
        showWelcomeScreen();
    }

    async function sendQuestion() {
        const question = questionInput.value.trim();
        if (!question) return;

        if (messageCount === 0) {
            hideWelcomeScreen();
        }

        messageCount++;
        addMessage('user', question, new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }));
        questionInput.value = '';
        questionInput.style.height = 'auto';
        questionInput.focus();

        const typingRow = addTyping();
        sendBtn.disabled = true;

        try {
            const response = await fetch('/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ question }),
            });

            const data = await response.json();
            const answer = data.answer || data.error || 'Sorry, I could not answer that right now.';
            const meta = data.intent ? `Intent: ${data.intent} • ${data.confidence || 'N/A'}` : 'CampusMate AI';

            if (typingRow.parentNode) {
                chatList.removeChild(typingRow);
            }
            addMessage('assistant', answer, meta);
        } catch (error) {
            if (typingRow.parentNode) {
                chatList.removeChild(typingRow);
            }
            addMessage('assistant', 'Unable to contact the backend. Please refresh or try again.', 'Error');
        } finally {
            sendBtn.disabled = false;
        }
    }

    // ===== Sidebar Rendering =====
    function renderSidebarCategories() {
        if (!sidebarCategories) return;
        sidebarCategories.innerHTML = '';
        categories.forEach((category) => {
            const item = document.createElement('button');
            item.type = 'button';
            item.className = 'nav-item';
            item.innerHTML = `${category.icon}<span>${category.name}</span>`;
            item.addEventListener('click', () => {
                questionInput.value = category.query;
                questionInput.focus();
                sendQuestion();
                toggleSidebar(false);
            });
            sidebarCategories.appendChild(item);
        });
    }

    // ===== Sidebar Toggle (mobile) =====
    function toggleSidebar(open) {
        if (!sidebarPanel || !sidebarScrim) return;
        sidebarPanel.classList.toggle('visible', open);
        sidebarScrim.classList.toggle('visible', open);
        sidebarToggle.setAttribute('aria-expanded', String(open));
    }

    // ===== Settings Drawer =====
    function openSettings() {
        settingsPanel.classList.add('visible');
        document.body.style.overflow = 'hidden';
        syncSettingsUI();
    }

    function closeSettingsPanel() {
        settingsPanel.classList.remove('visible');
        document.body.style.overflow = '';
    }

    // ===== Auto-resize textarea =====
    function autoResize() {
        questionInput.style.height = 'auto';
        questionInput.style.height = Math.min(questionInput.scrollHeight, 160) + 'px';
    }

    // ===== Event Listeners =====
    function setupEventListeners() {
        // Send message
        sendBtn.addEventListener('click', sendQuestion);
        questionInput.addEventListener('keydown', (event) => {
            if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault();
                sendQuestion();
            }
        });
        questionInput.addEventListener('input', autoResize);

        // Theme toggle (topbar icon)
        if (themeToggle) {
            themeToggle.addEventListener('click', toggleTheme);
        }

        // New chat
        if (newChatBtn) {
            newChatBtn.addEventListener('click', clearChat);
        }

        // Sidebar toggle
        if (sidebarToggle) {
            sidebarToggle.addEventListener('click', () => toggleSidebar(true));
        }

        if (sidebarScrim) {
            sidebarScrim.addEventListener('click', () => toggleSidebar(false));
        }

        // Settings drawer
        if (settingsBtn) {
            settingsBtn.addEventListener('click', openSettings);
        }

        if (closeSettings) {
            closeSettings.addEventListener('click', closeSettingsPanel);
        }

        if (settingsScrim) {
            settingsScrim.addEventListener('click', closeSettingsPanel);
        }

        // Theme segmented control
        if (themeControl) {
            themeControl.querySelectorAll('.segmented-option').forEach((btn) => {
                btn.addEventListener('click', () => {
                    setTheme(btn.getAttribute('data-theme'));
                });
            });
        }

        // Accent color swatches
        if (accentControl) {
            accentControl.querySelectorAll('.accent-swatch').forEach((btn) => {
                btn.addEventListener('click', () => {
                    setAccent(btn.getAttribute('data-accent'));
                });
            });
        }

        // Font size segmented control
        if (fontSizeControl) {
            fontSizeControl.querySelectorAll('.segmented-option').forEach((btn) => {
                btn.addEventListener('click', () => {
                    setFontSize(btn.getAttribute('data-size'));
                });
            });
        }

        // Clear chat from settings
        if (clearChatBtn) {
            clearChatBtn.addEventListener('click', () => {
                clearChat();
                closeSettingsPanel();
                showToast('Conversation cleared');
            });
        }

        // Logout (visual — does not alter backend/auth)
        if (logoutBtn) {
            logoutBtn.addEventListener('click', () => {
                showToast('Logout requires backend session handling');
            });
        }

        // Close settings with Escape key
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && settingsPanel.classList.contains('visible')) {
                closeSettingsPanel();
            }
        });
    }

    // ===== Initialize App =====
    init();
});