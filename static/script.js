document.addEventListener('DOMContentLoaded', () => {
    const questionInput = document.getElementById('questionInput');
    const sendBtn = document.getElementById('sendBtn');
    const errorMsg = document.getElementById('errorMsg');
    const resultCard = document.getElementById('resultCard');

    const resQuestion = document.getElementById('resQuestion');
    const resIntent = document.getElementById('resIntent');
    const resConfidence = document.getElementById('resConfidence');
    const resMatched = document.getElementById('resMatched');
    const resAnswer = document.getElementById('resAnswer');

    // Send on button click or Enter (when not holding Shift)
    sendBtn.addEventListener('click', () => sendQuestion());
    questionInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendQuestion();
        }
    });

    // Suggestion buttons
    document.querySelectorAll('.suggest').forEach((btn) => {
        btn.addEventListener('click', () => {
            questionInput.value = btn.textContent;
        });
    });

    async function sendQuestion() {
        const question = questionInput.value.trim();
        if (!question) return;

        sendBtn.disabled = true;
        sendBtn.textContent = 'Thinking...';
        errorMsg.style.display = 'none';
        resultCard.style.display = 'none';

        try {
            const response = await fetch('http://127.0.0.1:5000/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ question })
            });

            if (!response.ok) {
                const txt = await response.text().catch(()=>'');
                throw new Error(txt || 'Network response was not ok');
            }

            const data = await response.json();

            resQuestion.textContent = data.question || '';
            resIntent.textContent = data.intent || '';
            resConfidence.textContent = data.confidence || '';
            resMatched.textContent = data.matched_question || '';
            resAnswer.textContent = data.answer || '';

            resultCard.classList.add('fade-in');
            resultCard.style.display = 'block';
        } catch (error) {
            errorMsg.textContent = 'Unable to contact backend.';
            errorMsg.style.display = 'block';
        } finally {
            sendBtn.disabled = false;
            sendBtn.textContent = 'Send';
        }
    }
    });
});
