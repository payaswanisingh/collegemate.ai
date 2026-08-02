document.addEventListener('DOMContentLoaded', () => {
    // ===== DOM Elements =====
    const questionInput = document.getElementById('questionInput');
    const sendBtn = document.getElementById('sendBtn');
    const chatList = document.getElementById('chatList');
    const sidebarPanel = document.getElementById('sidebarPanel');
    const newChatBtn = document.getElementById('newChatBtn');
    const themeToggle = document.getElementById('themeToggle');
    const clock = document.getElementById('clock');
    const currentDate = document.getElementById('currentDate');
    const settingsBtn = document.getElementById('settingsBtn');
    const closeSettings = document.getElementById('closeSettings');
    const settingsPanel = document.getElementById('settingsPanel');
    const settingsScrim = settingsPanel.querySelector('.settings-scrim');
    const sidebarCategories = document.getElementById('sidebarCategories');
    const chatHistoryList = document.getElementById('chatHistoryList');
    const clearChatBtn = document.getElementById('clearChatBtn');
    const themeControl = document.getElementById('themeControl');
    const accentControl = document.getElementById('accentControl');
    const fontSizeControl = document.getElementById('fontSizeControl');
    const logoutBtn = document.getElementById('logoutBtn');
    const fileInput = document.getElementById('fileInput');
    const fileUploadBtn = document.getElementById('fileUploadBtn');
    const filePreview = document.getElementById('filePreview');
    const filePreviewName = document.getElementById('filePreviewName');
    const removeFileBtn = document.getElementById('removeFileBtn');
    const logoutConfirmModal = document.getElementById('logoutConfirmModal');
    const cancelLogoutBtn = document.getElementById('cancelLogoutBtn');
    const confirmLogoutBtn = document.getElementById('confirmLogoutBtn');
    const toast = document.getElementById('toast');
    let selectedFiles = [];

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
    const categories = [
        { icon: icons.fees, name: 'Fees', query: 'Fee Structure' },
        { icon: icons.examinations, name: 'Examinations', query: 'Exam Dates' },
        { icon: icons.admissions, name: 'Admissions', query: 'Admission Process' },
        { icon: icons.hostel, name: 'Hostel', query: 'Hostel Facilities' },
        { icon: icons.placements, name: 'Placements', query: 'Placement Cell' },
        { icon: icons.library, name: 'Library', query: 'Library Timings' },
        { icon: icons.campusLife, name: 'Campus Life', query: 'Student Services' },
    ];

    // ===== Storage Keys =====
    const THEME_KEY = 'campusmate-theme';
    const ACCENT_KEY = 'campusmate-accent';
    const FONT_SIZE_KEY = 'campusmate-font-size';
    const WELCOME_STORAGE_KEY = 'campusmate-welcome-displayed';

    // ===== State =====
    let messageCount = 0;
    let currentConversationId = null;
    let conversationsCache = [];
    let welcomeMessageShown = false;

    // ===== Initialize =====
    function init() {
        applyStoredTheme();
        applyStoredAccent();
        applyStoredFontSize();
        updateClock();
        updateDate();
        renderSidebarCategories();
        setupEventListeners();
        syncSettingsUI();
        fetchChatHistory(false);
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

    function createClientId() {
        if (window.crypto && crypto.randomUUID) {
            return crypto.randomUUID();
        }
        return `cid-${Math.random().toString(36).slice(2)}-${Date.now()}`;
    }

    function setActiveHistoryItem(conversationId) {
        if (!chatHistoryList) return;
        chatHistoryList.querySelectorAll('.history-item').forEach((item) => {
            item.classList.toggle('active', item.dataset.conversationId === String(conversationId));
        });
    }

    function renderHistoryList(conversations) {
        if (!chatHistoryList) return;
        chatHistoryList.innerHTML = '';

        if (!conversations || conversations.length === 0) {
            chatHistoryList.innerHTML = '<div class="history-empty">No saved conversations yet.</div>';
            return;
        }

        conversations.forEach((conversation) => {
            const item = document.createElement('div');
            item.className = 'history-item';
            item.dataset.conversationId = conversation.conversation_id;
            item.innerHTML = `
                <button class="history-item-main" type="button">
                    <span class="history-item-title">${escapeHtml(conversation.title)}</span>
                </button>
                <button class="history-delete-btn" type="button" aria-label="Delete conversation" title="Delete conversation">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path><line x1="10" y1="11" x2="10" y2="17"></line><line x1="14" y1="11" x2="14" y2="17"></line></svg>
                </button>
            `;

            const mainButton = item.querySelector('.history-item-main');
            const deleteButton = item.querySelector('.history-delete-btn');

            mainButton.addEventListener('click', () => {
                const selected = conversationsCache.find((c) => c.conversation_id === conversation.conversation_id);
                if (selected) {
                    loadConversation(selected);
                    setActiveHistoryItem(selected.conversation_id);
                }
            });

            deleteButton.addEventListener('click', async (event) => {
                event.stopPropagation();
                const targetId = conversation.conversation_id;
                const confirmed = window.confirm(`Delete "${conversation.title || 'this conversation'}"?`);
                if (!confirmed) return;

                try {
                    const response = await fetch(`/chat/history/${targetId}`, { method: 'DELETE' });
                    const data = await response.json().catch(() => ({}));
                    if (!response.ok) {
                        throw new Error(data.error || 'Unable to delete conversation.');
                    }

                    if (currentConversationId === targetId) {
                        currentConversationId = null;
                        clearChat();
                        welcomeMessageShown = false;
                    }

                    await fetchChatHistory(false);
                    showToast('Conversation deleted');
                } catch (error) {
                    console.error(error);
                    showToast('Unable to delete conversation.');
                }
            });

            chatHistoryList.appendChild(item);
        });

        setActiveHistoryItem(currentConversationId);
    }

    function loadConversation(conversation) {
        if (!conversation) return;
        currentConversationId = conversation.conversation_id;
        clearChat();

        if (conversation.messages && conversation.messages.length) {
            conversation.messages.forEach((message) => {
                addMessage('user', message.question, new Date(message.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }));
                addMessage('assistant', message.answer, message.source || 'CampusMate AI');
            });
            messageCount = conversation.messages.length * 2;
            scrollToBottom();
        }

        setActiveHistoryItem(currentConversationId);
        scrollToBottom();
    }

    async function fetchChatHistory(loadLatest = true) {
        if (!chatHistoryList) return;
        try {
            const response = await fetch('/chat/history');
            const data = await response.json();
            if (!response.ok) {
                throw new Error(data.error || 'Unable to load chat history.');
            }

            conversationsCache = Array.isArray(data.conversations) ? data.conversations : [];
            renderHistoryList(conversationsCache);

            if (loadLatest && !currentConversationId && conversationsCache.length) {
                const latestWithMessages = conversationsCache.find((c) => c.message_count > 0) || conversationsCache[0];
                if (latestWithMessages.message_count > 0) {
                    loadConversation(latestWithMessages);
                } else {
                    currentConversationId = latestWithMessages.conversation_id;
                }
            }

            if (!currentConversationId && messageCount === 0 && !welcomeMessageShown) {
                showWelcomeAssistantMessage();
            }
        } catch (error) {
            console.warn('Failed to load chat history:', error);
            if (!currentConversationId && messageCount === 0 && !welcomeMessageShown) {
                showWelcomeAssistantMessage();
            }
        }
    }

    async function startNewConversation() {
        try {
            const response = await fetch('/chat/new', { method: 'POST' });
            const data = await response.json();
            if (!response.ok) {
                throw new Error(data.error || 'Unable to start new chat.');
            }
            currentConversationId = data.conversation_id;
            clearChat();
            welcomeMessageShown = false;
            try {
                sessionStorage.removeItem(WELCOME_STORAGE_KEY);
            } catch (e) {
                // Ignore storage failures.
            }
            showWelcomeAssistantMessage();
            await fetchChatHistory(false);
        } catch (error) {
            showToast('Unable to start a new chat.');
            console.error(error);
        }
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

    function scrollToBottom() {
        if (!chatList) return;

        const scroll = () => {
            if ('scrollTo' in chatList) {
                chatList.scrollTo({ top: chatList.scrollHeight, behavior: 'smooth' });
            } else {
                chatList.scrollTop = chatList.scrollHeight;
            }
        };

        if (window.requestAnimationFrame) {
            window.requestAnimationFrame(scroll);
        } else {
            setTimeout(scroll, 0);
        }
    }

    function updateFilePreview() {
        if (!filePreview || !filePreviewName) return;
        if (!selectedFiles.length) {
            filePreview.classList.add('hidden');
            filePreviewName.textContent = '';
            return;
        }

        const names = selectedFiles.map((file) => file.name).join(', ');
        filePreviewName.textContent = names;
        filePreview.classList.remove('hidden');
    }

    function clearSelectedFiles() {
        selectedFiles = [];
        if (fileInput) {
            fileInput.value = '';
        }
        updateFilePreview();
    }

    function clearClientChatState() {
        currentConversationId = null;
        conversationsCache = [];
        messageCount = 0;
        welcomeMessageShown = false;
        selectedFiles = [];
        if (chatList) {
            chatList.innerHTML = '';
        }
        if (chatHistoryList) {
            chatHistoryList.querySelectorAll('.history-item').forEach((item) => item.classList.remove('active'));
        }
        if (fileInput) {
            fileInput.value = '';
        }
        updateFilePreview();
        try {
            sessionStorage.removeItem(WELCOME_STORAGE_KEY);
        } catch (e) {
            // Ignore storage failures.
        }
    }

    function openLogoutConfirmModal() {
        if (!logoutConfirmModal) return;
        logoutConfirmModal.classList.remove('hidden');
        logoutConfirmModal.setAttribute('aria-hidden', 'false');
    }

    function closeLogoutConfirmModal() {
        if (!logoutConfirmModal) return;
        logoutConfirmModal.classList.add('hidden');
        logoutConfirmModal.setAttribute('aria-hidden', 'true');
    }

    async function handleLogout() {
        closeLogoutConfirmModal();
        clearClientChatState();

        try {
            await fetch('/logout', {
                method: 'GET',
                credentials: 'same-origin',
                headers: { Accept: 'text/html' },
            });
        } catch (error) {
            // Ignore network errors and continue to the landing page.
        }

        window.location.assign('/');
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

    function addMessage(type, text, meta) {
        const row = createMessageRow(type, text, meta);
        chatList.appendChild(row);
        scrollToBottom();
    }

    function addTyping() {
        const typingRow = createTypingIndicator();
        chatList.appendChild(typingRow);
        scrollToBottom();
        return typingRow;
    }

    // ===== Welcome Message =====
    function clearChat() {
        chatList.innerHTML = '';
        messageCount = 0;
    }

    function showWelcomeAssistantMessage() {
        if (welcomeMessageShown) return;

        const storedFlag = (() => {
            try {
                return sessionStorage.getItem(WELCOME_STORAGE_KEY);
            } catch (e) {
                return null;
            }
        })();
        if (storedFlag === '1') {
            welcomeMessageShown = true;
            return;
        }

        const userName = window.CampusMateUser?.fullName || '';
        const greeting = userName ? `👋 Hi, ${userName}!` : '👋 Hi there!';
        const welcomeText = [
            `${greeting}`,
            'Welcome back to CampusMate AI.',
            '',
            "I'm your smart university assistant, here to help you navigate every aspect of campus life from admissions and academics to exams, scholarships, placements, hostel facilities, and student services.",
            '',
            'What would you like to explore today?'
        ].join('\n');

        addMessage('assistant', welcomeText, 'CampusMate AI');
        welcomeMessageShown = true;
        try {
            sessionStorage.setItem(WELCOME_STORAGE_KEY, '1');
        } catch (e) {
            // Ignore storage failures.
        }
    }

    async function sendQuestion() {
        let question = questionInput.value.trim();
        const hasFiles = selectedFiles.length > 0;
        if (!question && !hasFiles) return;

        if (!question && hasFiles) {
            question = `Uploaded ${selectedFiles.length} attachment${selectedFiles.length > 1 ? 's' : ''}`;
        }

        messageCount++;
        addMessage('user', question, new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }));
        questionInput.value = '';
        questionInput.style.height = 'auto';
        questionInput.focus();

        const typingRow = addTyping();
        sendBtn.disabled = true;

        try {
            let response;
            if (hasFiles) {
                const formData = new FormData();
                formData.append('question', question);
                if (currentConversationId) {
                    formData.append('conversation_id', currentConversationId);
                }
                formData.append('client_id', createClientId());
                selectedFiles.forEach((file) => {
                    formData.append('files', file);
                });

                response = await fetch('/chat', {
                    method: 'POST',
                    body: formData,
                });
            } else {
                response = await fetch('/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        question,
                        conversation_id: currentConversationId,
                        client_id: createClientId(),
                    }),
                });
            }

            const data = await response.json();
            const answer = data.answer || data.error || 'Sorry, I could not answer that right now.';

            if (typingRow.parentNode) {
                chatList.removeChild(typingRow);
            }
            addMessage('assistant', answer, 'CampusMate AI');

            if (data.conversation_id) {
                currentConversationId = data.conversation_id;
            }

            if (hasFiles) {
                clearSelectedFiles();
            }

            await fetchChatHistory(false);
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
            });
            sidebarCategories.appendChild(item);
        });
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

        if (fileUploadBtn && fileInput) {
            fileUploadBtn.addEventListener('click', () => fileInput.click());
        }

        if (fileInput) {
            fileInput.addEventListener('change', (event) => {
                selectedFiles = Array.from(event.target.files || []);
                updateFilePreview();
            });
        }

        if (removeFileBtn) {
            removeFileBtn.addEventListener('click', clearSelectedFiles);
        }

        // Theme toggle (topbar icon)
        if (themeToggle) {
            themeToggle.addEventListener('click', toggleTheme);
        }

        // New chat
        if (newChatBtn) {
            newChatBtn.addEventListener('click', startNewConversation);
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

        if (logoutBtn) {
            logoutBtn.addEventListener('click', openLogoutConfirmModal);
        }

        if (cancelLogoutBtn) {
            cancelLogoutBtn.addEventListener('click', closeLogoutConfirmModal);
        }

        if (confirmLogoutBtn) {
            confirmLogoutBtn.addEventListener('click', handleLogout);
        }

        if (logoutConfirmModal) {
            logoutConfirmModal.addEventListener('click', (event) => {
                if (event.target === logoutConfirmModal) {
                    closeLogoutConfirmModal();
                }
            });
        }

        // Close settings with Escape key
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                if (settingsPanel.classList.contains('visible')) {
                    closeSettingsPanel();
                }
                if (logoutConfirmModal && !logoutConfirmModal.classList.contains('hidden')) {
                    closeLogoutConfirmModal();
                }
            }
        });
    }

    // ===== Initialize App =====
    init();
});
