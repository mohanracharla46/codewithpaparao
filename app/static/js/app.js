// codewithpaparao LMS Core Client Script
const LMS = {
    // Retrieve CSRF token from meta tags
    getCsrfToken() {
        const meta = document.querySelector('meta[name="csrf-token"]');
        return meta ? meta.getAttribute('content') : '';
    },

    // HTTP Helper
    async request(url, method = 'POST', data = null) {
        const headers = {
            'Content-Type': 'application/json',
            'X-CSRFToken': this.getCsrfToken()
        };

        const config = {
            method,
            headers
        };

        if (data) {
            config.body = JSON.stringify(data);
        }

        try {
            const response = await fetch(url, config);
            if (!response.ok) {
                const errData = await response.json();
                throw new Error(errData.error || `HTTP ${response.status}`);
            }
            return await response.json();
        } catch (error) {
            console.error('LMS Request Error:', error);
            throw error;
        }
    },

    // Toggle Bookmarks
    async toggleBookmark(lessonId, button) {
        try {
            const res = await this.request(`/courses/lessons/${lessonId}/bookmark`);
            if (res.status === 'success') {
                if (res.bookmarked) {
                    button.classList.add('active');
                    button.innerHTML = '⭐️ Bookmarked';
                } else {
                    button.classList.remove('active');
                    button.innerHTML = '☆ Bookmark';
                }
            }
        } catch (error) {
            alert('Failed to update bookmark.');
        }
    },

    // Complete Lessons
    async completeLesson(lessonId, button) {
        try {
            button.disabled = true;
            button.innerText = 'Updating...';
            
            const res = await this.request(`/courses/lessons/${lessonId}/complete`);
            if (res.status === 'success') {
                button.classList.remove('btn-primary');
                button.classList.add('btn-secondary');
                button.innerText = '✓ Completed';
                
                // Show completion banner if certificate issued
                if (res.certificate_generated) {
                    showCertificateAlert(res.certificate_code);
                }
                
                // Reload progress components if they exist on the page
                const progBar = document.getElementById('course-progress-bar');
                const progText = document.getElementById('course-progress-text');
                if (progBar && res.progress_pct !== undefined) {
                    progBar.style.width = `${res.progress_pct}%`;
                    if (progText) progText.innerText = `${res.progress_pct}% completed`;
                }
            }
        } catch (error) {
            button.disabled = false;
            button.innerText = 'Mark as Complete';
            alert('Failed to update lesson completion status.');
        }
    },

    // Read Notification
    async markNotificationRead(notifId, notifElement) {
        try {
            const res = await this.request(`/student/notifications/${notifId}/read`);
            if (res.status === 'success') {
                notifElement.classList.add('read');
                notifElement.remove(); // Remove or fade out
            }
        } catch (error) {
            console.error(error);
        }
    }
};

function showCertificateAlert(code) {
    const alertOverlay = document.createElement('div');
    alertOverlay.style.cssText = `
        position: fixed;
        top: 0; left: 0; width: 100%; height: 100%;
        background-color: rgba(0,0,0,0.5);
        display: flex; align-items: center; justify-content: center;
        z-index: 999; backdrop-filter: blur(4px);
    `;
    
    alertOverlay.innerHTML = `
        <div class="card" style="max-width: 400px; text-align: center; background: var(--bg-secondary);">
            <h2>Course Completed! 🎉</h2>
            <p style="margin: 1rem 0; color: var(--text-secondary);">
                Congratulations! You have completed all lessons and earned a certificate.
            </p>
            <div style="font-family: monospace; padding: 0.5rem; background: var(--bg-tertiary); margin-bottom: 1.5rem; border-radius: 4px;">
                Code: ${code}
            </div>
            <a href="/courses/certificates/download/${code}" class="btn btn-primary" style="display: block; margin-bottom: 0.5rem;">View Certificate</a>
            <button class="btn btn-secondary" onclick="this.closest('.app-overlay').remove()" style="width: 100%;">Dismiss</button>
        </div>
    `;
    alertOverlay.classList.add('app-overlay');
    document.body.appendChild(alertOverlay);
}
