document.addEventListener('DOMContentLoaded', () => {
    if (!window.dashboardCharts || !window.Chart) return;
    const palette = ['#9b82ff', '#568ef4', '#51c6d3', '#53c58c', '#edb75d', '#ed7f9b', '#928ba9'];
    const emotionCanvas = document.getElementById('emotion-chart');
    if (emotionCanvas) {
        new Chart(emotionCanvas, {
            type: 'doughnut',
            data: {
                labels: Object.keys(window.dashboardCharts.emotions).map(value => value[0].toUpperCase() + value.slice(1)),
                datasets: [{ data: Object.values(window.dashboardCharts.emotions), backgroundColor: palette, borderColor: '#171c30', borderWidth: 3, hoverOffset: 5 }]
            },
            options: {
                maintainAspectRatio: false,
                cutout: '68%',
                plugins: { legend: { position: 'right', labels: { color: '#aeb7ce', usePointStyle: true, pointStyle: 'circle', padding: 15, font: { size: 11 } } } }
            }
        });
    }
    const activityCanvas = document.getElementById('activity-chart');
    if (activityCanvas) {
        new Chart(activityCanvas, {
            type: 'bar',
            data: {
                labels: window.dashboardCharts.activity.map(item => new Date(`${item.date}T00:00:00`).toLocaleDateString(undefined, { weekday: 'short' })),
                datasets: [{ data: window.dashboardCharts.activity.map(item => item.count), backgroundColor: '#8066ee', hoverBackgroundColor: '#a091ff', borderRadius: 5, maxBarThickness: 26 }]
            },
            options: {
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    x: { grid: { display: false }, ticks: { color: '#8993ad' }, border: { display: false } },
                    y: { beginAtZero: true, ticks: { precision: 0, color: '#8993ad' }, grid: { color: 'rgba(159,169,211,.1)' }, border: { display: false } }
                }
            }
        });
    }

    const userSearch = document.getElementById('user-search');
    const userRoleFilter = document.getElementById('user-role-filter');
    if (userSearch && userRoleFilter) {
        const filterUsers = () => {
            const query = userSearch.value.trim().toLowerCase();
            const filter = userRoleFilter.value;
            document.querySelectorAll('[data-user-row]').forEach(row => {
                const matchesQuery = row.textContent.toLowerCase().includes(query);
                const matchesFilter = !filter || row.dataset.status === filter || row.dataset.role === filter;
                row.hidden = !(matchesQuery && matchesFilter);
            });
        };
        userSearch.addEventListener('input', filterUsers);
        userRoleFilter.addEventListener('change', filterUsers);
    }

    if (window.adminCharts && window.Chart) {
        const registrationCanvas = document.getElementById('registration-chart');
        if (registrationCanvas) {
            new Chart(registrationCanvas, {
                type: 'line',
                data: {
                    labels: window.adminCharts.registrations.map(item =>
                        new Date(`${item.date}T00:00:00`).toLocaleDateString(undefined, { weekday: 'short' })
                    ),
                    datasets: [{
                        data: window.adminCharts.registrations.map(item => item.count),
                        borderColor: '#9b82ff',
                        backgroundColor: 'rgba(126, 102, 238, .13)',
                        fill: true,
                        tension: .35,
                        pointBackgroundColor: '#b7aaff',
                        pointRadius: 3
                    }]
                },
                options: {
                    maintainAspectRatio: false,
                    plugins: { legend: { display: false } },
                    scales: {
                        x: { grid: { display: false }, ticks: { color: '#8993ad' }, border: { display: false } },
                        y: { beginAtZero: true, ticks: { precision: 0, color: '#8993ad' }, grid: { color: 'rgba(159,169,211,.1)' }, border: { display: false } }
                    }
                }
            });
        }
    }
});
