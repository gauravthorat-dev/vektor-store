(function () {
  'use strict';

  function initReveal() {
    var reveals = document.querySelectorAll('.reveal');

    /* Hero + flash: force active immediately — CSS keyframes handle the animation */
    reveals.forEach(function(el) {
      if (el.closest('.hero') || el.classList.contains('flash')) {
        el.classList.add('active');
      }
    });

    /* All others: IntersectionObserver */
    var below = Array.from(reveals).filter(function(el) {
      return !el.closest('.hero') && !el.classList.contains('flash');
    });

    if (!('IntersectionObserver' in window)) {
      below.forEach(function(el) { el.classList.add('active'); });
      return;
    }

    var obs = new IntersectionObserver(function(entries) {
      entries.forEach(function(e) {
        if (e.isIntersecting) {
          e.target.classList.add('active');
          obs.unobserve(e.target);
        }
      });
    }, { threshold: 0.1, rootMargin: '0px 0px -30px 0px' });

    below.forEach(function(el) { obs.observe(el); });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initReveal);
  } else {
    initReveal();
  }
})();