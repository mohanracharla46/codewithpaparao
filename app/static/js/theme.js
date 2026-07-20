// Dark / Light Theme Manager
document.addEventListener('DOMContentLoaded', () => {
    const currentTheme = localStorage.getItem('theme') || 'light';
    document.documentElement.setAttribute('data-theme', currentTheme);
    
    const toggleBtn = document.getElementById('theme-toggle');
    if (toggleBtn) {
        // Set initial icon or state
        updateToggleIcon(toggleBtn, currentTheme);
        
        toggleBtn.addEventListener('click', () => {
            let theme = document.documentElement.getAttribute('data-theme');
            let nextTheme = theme === 'dark' ? 'light' : 'dark';
            
            document.documentElement.setAttribute('data-theme', nextTheme);
            localStorage.setItem('theme', nextTheme);
            updateToggleIcon(toggleBtn, nextTheme);
        });
    }
});

function updateToggleIcon(btn, theme) {
    if (theme === 'dark') {
        btn.innerHTML = '🌙'; // Moon icon for Dark mode (click to toggle light)
        btn.title = 'Switch to Light Mode';
    } else {
        btn.innerHTML = '☀️'; // Sun icon for Light mode (click to toggle dark)
        btn.title = 'Switch to Dark Mode';
    }
}
