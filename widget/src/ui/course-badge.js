export function showCourseBadge(courseName) {
    if (document.getElementById('course-badge')) return;

    const badge = document.createElement('div');
    badge.id = 'course-badge';
    badge.className = 'aicc-course-badge';
    badge.innerHTML = `You are entering <b>${courseName}</b>`;

    document.body.appendChild(badge);

    window.setTimeout(() => {
        badge.style.opacity = '0';
        window.setTimeout(() => badge.remove(), 800);
    }, 4000);
}
