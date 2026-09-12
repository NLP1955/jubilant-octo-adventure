# Process Server Plus

Marketing/lead-gen website for **Process Server Plus** — a static site (no build step, no backend) built to get visitors to request service or call.

## Structure

```
index.html              Full site markup (hero, services, how it works, why us,
                         testimonials, FAQ, contact form, footer)
assets/css/styles.css   All styling — colors/fonts are CSS variables at the top
assets/js/script.js     Mobile nav toggle, footer year, contact form handling
```

## Before you launch — replace these placeholders

Search the files for the following and swap in real info:

| Placeholder | Where | Replace with |
|---|---|---|
| `(555) 123-4567` | header, hero, contact, footer | your real phone number |
| `info@processserverplus.com` | contact, footer | your real email |
| `[Street Address, City, State ZIP]` | footer | your business address |
| `[License #]` / `[State]` | footer | your license number and state(s) served |
| Testimonial quotes | `#testimonials` section in `index.html` | real client testimonials (marked with an HTML comment in the file) |

## Wiring up the contact form

The form in `#contact` currently validates and shows a success message client-side only — it does not send anywhere yet. Pick one:

- **Form service (fastest):** point the form at [Formspree](https://formspree.io) or [Netlify Forms](https://docs.netlify.com/forms/setup/) — a few lines of markup/JS, no backend to run.
- **Your own backend:** replace the `fetch`-free placeholder in `assets/js/script.js`'s submit handler with a real `fetch()` call to your API route, which can email the lead, save it to a database, or push it into a CRM.

## Deploying

This is a plain static site — deploy it anywhere that serves static files:

- **Netlify / Vercel:** drag-and-drop the folder, or connect this repo for automatic deploys.
- **GitHub Pages:** enable Pages on this repo pointed at this branch/root.
- **Any web host:** upload `index.html` and the `assets/` folder as-is.

## Local preview

No build tools required — just open `index.html` in a browser, or serve it locally:

```bash
python3 -m http.server 8000
# then visit http://localhost:8000
```
