document.addEventListener('DOMContentLoaded', () => {
  const navbarToggle = document.querySelector('.navbar-toggle');
  const navbarMenu = document.querySelector('.navbar-menu');

  navbarToggle.addEventListener('click', () => {
    navbarMenu.classList.toggle('active');
  });

  // Smooth scrolling for anchor links
  document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function(e) {
      e.preventDefault();
      document.querySelector(this.getAttribute('href')).scrollIntoView({
        behavior: 'smooth'
      });
    });
  });

  // Highlight code blocks on click
  document.querySelectorAll('pre code').forEach((block) => {
    block.addEventListener('click', () => {
      const selection = window.getSelection();
      const range = document.createRange();
      range.selectNodeContents(block);
      selection.removeAllRanges();
      selection.addRange(range);
    });
  });

  // Add hover effect to endpoint sections
  const endpoints = document.querySelectorAll('.endpoint');
  endpoints.forEach((endpoint) => {
    endpoint.addEventListener('mouseenter', () => {
      endpoint.style.transform = 'translateY(-5px)';
      endpoint.style.transition = 'transform 0.3s ease-in-out';
    });
    endpoint.addEventListener('mouseleave', () => {
      endpoint.style.transform = 'translateY(0)';
    });
  });
});
