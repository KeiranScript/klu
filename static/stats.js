document.addEventListener('DOMContentLoaded', () => {
  const navbarToggle = document.querySelector('.navbar-toggle');
  const navbarMenu = document.querySelector('.navbar-menu');

  navbarToggle.addEventListener('click', () => {
    navbarMenu.classList.toggle('active');
  });

  fetchStats();
});

async function fetchStats() {
  try {
    const response = await fetch('/info');
    const data = await response.json();

    document.getElementById('storage-used').textContent = data.storage_used;
    document.getElementById('total-uploads').textContent = data.uploads;
    document.getElementById('total-users').textContent = data.users;

    // Add animation to stat values
    const statValues = document.querySelectorAll('.stat-value');
    statValues.forEach(value => {
      value.classList.add('animate-pulse');
    });
  } catch (error) {
    console.error('Error fetching stats:', error);
    document.getElementById('stats-container').innerHTML = '<p class="error-message">Error loading statistics. Please try again later.</p>';
  }
}
