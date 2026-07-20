// Dynamic Quiz Engine
document.addEventListener('DOMContentLoaded', () => {
    const quizForm = document.getElementById('quiz-submit-form');
    if (!quizForm) return;

    const quizId = quizForm.getAttribute('data-quiz-id');
    const submitBtn = document.getElementById('quiz-submit-btn');
    const resultsContainer = document.getElementById('quiz-results');

    submitBtn.addEventListener('click', async (e) => {
        e.preventDefault();
        
        // Collect answers
        const answers = {};
        const questionsList = quizForm.querySelectorAll('.quiz-question-block');
        
        let answeredCount = 0;
        questionsList.forEach(qBlock => {
            const qId = qBlock.getAttribute('data-question-id');
            const selected = qBlock.querySelector('input[type="radio"]:checked');
            if (selected) {
                answers[qId] = parseInt(selected.value);
                answeredCount++;
            }
        });

        if (answeredCount < questionsList.length) {
            if (!confirm("You have not answered all questions. Submit anyway?")) {
                return;
            }
        }

        try {
            submitBtn.disabled = true;
            submitBtn.innerText = 'Submitting...';

            const res = await LMS.request(`/student/quizzes/${quizId}/submit`, 'POST', { answers });
            
            // Render results
            quizForm.style.display = 'none';
            resultsContainer.style.display = 'block';

            const statusClass = res.passed ? 'alert-success' : 'alert-danger';
            const statusText = res.passed ? 'Passed 🎉' : 'Failed ❌';

            resultsContainer.innerHTML = `
                <div class="alert ${statusClass}">
                    <strong>Result: ${statusText}</strong>
                </div>
                <div class="card" style="margin-top: 1rem;">
                    <h3>Quiz Stats</h3>
                    <p style="margin: 0.5rem 0;">Your Score: <strong>${res.score}%</strong></p>
                    <p style="margin: 0.5rem 0;">Correct Answers: <strong>${res.correct_count} / ${res.total_questions}</strong></p>
                    <p style="margin: 0.5rem 0;">Passing Score Required: <strong>${res.passing_score}%</strong></p>
                    
                    <div style="margin-top: 1.5rem; display: flex; gap: 1rem;">
                        <a href="/dashboard/" class="btn btn-primary">Return to Dashboard</a>
                        ${!res.passed ? `<button onclick="window.location.reload()" class="btn btn-secondary">Try Again</button>` : ''}
                    </div>
                </div>
            `;
        } catch (error) {
            submitBtn.disabled = false;
            submitBtn.innerText = 'Submit Answers';
            alert('Error submitting quiz responses.');
        }
    });
});
