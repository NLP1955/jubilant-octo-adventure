// Process Server Plus — site interactions
// No external dependencies. Progressive enhancement only.

(function () {
  'use strict';

  // ---------- mobile nav toggle ----------
  var navToggle = document.getElementById('nav-toggle');
  var mainNav = document.getElementById('main-nav');

  if (navToggle && mainNav) {
    navToggle.addEventListener('click', function () {
      var isOpen = mainNav.classList.toggle('open');
      navToggle.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
    });

    // Close the mobile menu after a nav link is tapped
    mainNav.querySelectorAll('a').forEach(function (link) {
      link.addEventListener('click', function () {
        mainNav.classList.remove('open');
        navToggle.setAttribute('aria-expanded', 'false');
      });
    });
  }

  // ---------- footer year ----------
  var yearEl = document.getElementById('year');
  if (yearEl) {
    yearEl.textContent = new Date().getFullYear();
  }

  // ---------- contact form ----------
  // NOTE: This form is front-end only right now. Before going live, wire the
  // submit handler below to a real endpoint — e.g. a form backend such as
  // Formspree/Netlify Forms, or your own API route that emails/stores leads.
  var form = document.getElementById('contact-form');
  var note = document.getElementById('form-note');

  if (form && note) {
    form.addEventListener('submit', function (event) {
      event.preventDefault();

      if (!form.checkValidity()) {
        form.reportValidity();
        return;
      }

      // Placeholder success state — replace with a real fetch() call to your
      // form backend once one is connected.
      note.textContent = 'Thanks — your request was received. We will reach out within one business hour.';
      form.reset();
    });
  }
})();
