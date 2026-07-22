document.addEventListener('DOMContentLoaded', () => {
    const questionInput = document.getElementById('questionInput');
    const sendBtn = document.getElementById('sendBtn');
    const chatList = document.getElementById('chatList');
    const quickPrompts = document.getElementById('quickPrompts');
    const sidebarToggle = document.getElementById('sidebarToggle');
    const sidebarPanel = document.getElementById('sidebarPanel');
    const sidebarScrim = document.getElementById('sidebarScrim');
    const newChatBtn = document.getElementById('newChatBtn');
    const themeToggle = document.getElementById('themeToggle');
    const clock = document.getElementById('clock');

    const quickTopics = [
        'Fee Structure',
        'Exam Dates',
        'Placement Cell',
        'Hostel Facilities',
        'Library Timings',
        'Course Registration',
        'Scholarships',
        'Student Services',
    ];

    const categories = [
        'Fees',
        'Exams',
        'Hostel',
        'Placements',
        'Library',
        'Admissions',
        'Campus Life',
    ];

    function updateClock() {
        if (!clock) return;
        const now = new Date();
        const hours = now.getHours().toString().padStart(2, '0');
        const minutes = now.getMinutes().toString().padStart(2, '0');
        clock.textContent = `${hours}:${minutes}`;
    }

    function escapeHtml(value) {
        return String(value)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

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

    function scrollToBottom() {
        chatList.scrollTop = chatList.scrollHeight;
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

    function clearChat() {
        chatList.innerHTML = '';
        addMessage('assistant', 'Hi there! Ask me anything about campus life, fees, exams, or admissions.', 'Ready to help');
    }

    function renderQuickPrompts() {
        quickPrompts.innerHTML = '';
        quickTopics.forEach((topic) => {
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'action-chip';
            btn.textContent = topic;
            btn.addEventListener('click', () => {
                questionInput.value = topic;
                questionInput.focus();
            });
            quickPrompts.appendChild(btn);
        });
    }

    function renderSidebarCategories() {
        const container = document.getElementById('sidebarCategories');
        if (!container) return;
        container.innerHTML = '';
        categories.forEach((category) => {
            const chip = document.createElement('button');
            chip.type = 'button';
            chip.className = 'action-chip';
            chip.textContent = category;
            chip.addEventListener('click', () => {
                questionInput.value = category;
                questionInput.focus();
            });
            container.appendChild(chip);
        });
    }

    function toggleSidebar(open) {
        if (!sidebarPanel || !sidebarScrim) return;
        sidebarPanel.classList.toggle('visible', open);
        sidebarScrim.classList.toggle('visible', open);
        sidebarToggle.setAttribute('aria-expanded', String(open));
    }

    function toggleTheme() {
        document.body.classList.toggle('light');
    }

    async function sendQuestion() {
        const question = questionInput.value.trim();
        if (!question) return;

        addMessage('user', question, new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }));
        questionInput.value = '';
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

            chatList.removeChild(typingRow);
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

    sendBtn.addEventListener('click', sendQuestion);
    questionInput.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault();
            sendQuestion();
        }
    });

    if (newChatBtn) {
        newChatBtn.addEventListener('click', clearChat);
    }

    if (sidebarToggle) {
        sidebarToggle.addEventListener('click', () => toggleSidebar(true));
    }

    if (sidebarScrim) {
        sidebarScrim.addEventListener('click', () => toggleSidebar(false));
    }

    if (themeToggle) {
        themeToggle.addEventListener('click', toggleTheme);
    }

    updateClock();
    setInterval(updateClock, 60 * 1000);
    renderQuickPrompts();
    renderSidebarCategories();
    clearChat();
});
