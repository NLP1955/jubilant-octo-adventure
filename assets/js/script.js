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
  // Submissions are delivered by Web3Forms (https://web3forms.com) directly
  // to your inbox — no backend to run. Get a free access key at
  // web3forms.com (just enter the email you want leads sent to, no account
  // or password required) and paste it into the hidden "access_key" field
  // in index.html, replacing YOUR_WEB3FORMS_ACCESS_KEY.
  var WEB3FORMS_ENDPOINT = 'https://api.web3forms.com/submit';

  var form = document.getElementById('contact-form');
  var note = document.getElementById('form-note');

  if (form && note) {
    form.addEventListener('submit', function (event) {
      event.preventDefault();

      if (!form.checkValidity()) {
        form.reportValidity();
        return;
      }

      var accessKey = form.elements['access_key'] ? form.elements['access_key'].value : '';
      if (!accessKey || accessKey === 'YOUR_WEB3FORMS_ACCESS_KEY') {
        note.textContent = 'This form isn’t connected yet — add a Web3Forms access key in index.html to start receiving leads by email.';
        note.classList.add('is-error');
        return;
      }

      var submitButton = form.querySelector('button[type="submit"]');
      var originalLabel = submitButton ? submitButton.textContent : '';
      if (submitButton) {
        submitButton.disabled = true;
        submitButton.textContent = 'Sending…';
      }
      note.classList.remove('is-error');
      note.textContent = '';

      var formValues = Object.fromEntries(new FormData(form));

      // Best-effort HubSpot sync — only live once /api/submit-lead is
      // deployed (see api/submit-lead.js). Runs in parallel and never blocks
      // or affects the visitor-facing result below, which depends on
      // Web3Forms alone.
      fetch('/api/submit-lead', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formValues)
      }).catch(function () {
        /* no serverless functions on this host, or HubSpot isn't configured
           yet — Web3Forms below still delivers the lead by email. */
      });

      fetch(WEB3FORMS_ENDPOINT, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        body: JSON.stringify(formValues)
      })
        .then(function (response) { return response.json(); })
        .then(function (result) {
          if (result && result.success) {
            note.textContent = 'Thanks — your request was received. We will reach out within one business hour.';
            form.reset();
          } else {
            note.textContent = 'Something went wrong sending your request — please call us instead.';
            note.classList.add('is-error');
          }
        })
        .catch(function () {
          note.textContent = 'Something went wrong sending your request — please call us instead.';
          note.classList.add('is-error');
        })
        .finally(function () {
          if (submitButton) {
            submitButton.disabled = false;
            submitButton.textContent = originalLabel;
          }
        });
    });
  }
})();
