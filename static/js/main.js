document.addEventListener('DOMContentLoaded', () => {
    // 1. Theme Selector logic
    const themeSelector = document.getElementById('theme-selector');
    const currentTheme = localStorage.getItem('theme') || 'light';
    
    // Set initial theme
    document.documentElement.setAttribute('data-theme', currentTheme);
    
    if (themeSelector) {
        themeSelector.value = currentTheme;
        themeSelector.addEventListener('change', (e) => {
            const selectedTheme = e.target.value;
            document.documentElement.setAttribute('data-theme', selectedTheme);
            localStorage.setItem('theme', selectedTheme);
        });
    }
    
    // Backward compatibility for old toggle button if present
    const themeToggleBtn = document.getElementById('theme-toggle-btn');
    if (themeToggleBtn) {
        themeToggleBtn.addEventListener('click', () => {
            let theme = document.documentElement.getAttribute('data-theme');
            let newTheme = 'light';
            if (theme === 'light') newTheme = 'dark';
            else if (theme === 'dark') newTheme = 'midnight';
            else if (theme === 'midnight') newTheme = 'corporate';
            else if (theme === 'corporate') newTheme = 'purple';
            
            document.documentElement.setAttribute('data-theme', newTheme);
            localStorage.setItem('theme', newTheme);
            if (themeSelector) themeSelector.value = newTheme;
        });
    }
    
    // 2. Flash message automatic dismissal
    const alerts = document.querySelectorAll('.alert-dismissible');
    alerts.forEach(alert => {
        setTimeout(() => {
            alert.classList.add('fade');
            setTimeout(() => {
                alert.remove();
            }, 150);
        }, 5000);
    });
});
