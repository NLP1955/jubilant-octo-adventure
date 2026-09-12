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

## Connecting the contact form (1 step, ~1 minute)

The form already POSTs to [Web3Forms](https://web3forms.com) — a free service that emails you every submission. No account, password, or backend required:

1. Go to **https://web3forms.com/**, enter the email address you want leads sent to, and click "Create Access Key". You'll get a key instantly.
2. Open `index.html`, find `YOUR_WEB3FORMS_ACCESS_KEY` (in the hidden `access_key` field near the top of the `<form id="contact-form">`), and replace it with your key.
3. Deploy. Every form submission now arrives by email — recipient name, phone, service type, urgency, and case details included.

Until step 2 is done, submitting the form shows a message telling the visitor it isn't connected yet instead of silently failing.

Want submissions to also land as CRM contacts (e.g. HubSpot) instead of/alongside email? That's a separate integration — ask and it can be added.

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
