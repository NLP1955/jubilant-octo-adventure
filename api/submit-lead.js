// Vercel serverless function: creates/updates a HubSpot contact for every
// website lead, and best-effort logs the case details as a note on it.
//
// Setup (see README for full steps):
//   1. In HubSpot, create a Private App with the `crm.objects.contacts.write`
//      and `crm.objects.notes.write` scopes, and copy its access token.
//   2. In your hosting provider's project settings, add an environment
//      variable: HUBSPOT_PRIVATE_APP_TOKEN = <that token>
//   3. Deploy. This endpoint is then live at /api/submit-lead.
//
// Requires hosting with serverless functions (Vercel, Netlify, etc.) — a
// plain static host (GitHub Pages, S3) cannot run this file. The site keeps
// working without it: Web3Forms (see assets/js/script.js) is the guaranteed
// email path regardless of where this is deployed.
//
// The front end calls this best-effort and ignores failures (including a
// 404 on hosts that don't run serverless functions at all) — it never blocks
// the Web3Forms email that visitors see confirmed on screen.

const HUBSPOT_API = 'https://api.hubapi.com';

module.exports = async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') {
    res.status(204).end();
    return;
  }

  if (req.method !== 'POST') {
    res.status(405).json({ success: false, error: 'Method not allowed' });
    return;
  }

  const token = process.env.HUBSPOT_PRIVATE_APP_TOKEN;
  if (!token) {
    res.status(500).json({ success: false, error: 'HUBSPOT_PRIVATE_APP_TOKEN is not configured' });
    return;
  }

  const body = req.body && typeof req.body === 'object' ? req.body : JSON.parse(req.body || '{}');
  const {
    name = '',
    email = '',
    phone = '',
    'service-type': serviceType = '',
    urgency = '',
    details = ''
  } = body;

  if (!email) {
    res.status(400).json({ success: false, error: 'Email is required' });
    return;
  }

  const [firstname, ...rest] = String(name).trim().split(/\s+/).filter(Boolean);
  const lastname = rest.join(' ');

  const hubspotHeaders = {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${token}`
  };

  try {
    const contactId = await upsertContact(hubspotHeaders, { email, firstname, lastname, phone });

    // Best-effort: log the case details as a note on the contact. A failure
    // here (e.g. an association type mismatch) never fails lead capture —
    // the contact itself is the part that matters most.
    try {
      await logNote(hubspotHeaders, contactId, { serviceType, urgency, details });
    } catch (noteError) {
      console.error('HubSpot note logging failed (non-fatal):', noteError);
    }

    res.status(200).json({ success: true, contactId });
  } catch (error) {
    console.error('HubSpot contact upsert failed:', error);
    res.status(502).json({ success: false, error: 'Failed to reach HubSpot' });
  }
};

async function upsertContact(headers, { email, firstname, lastname, phone }) {
  const properties = { email };
  if (firstname) properties.firstname = firstname;
  if (lastname) properties.lastname = lastname;
  if (phone) properties.phone = phone;

  const createResponse = await fetch(`${HUBSPOT_API}/crm/v3/objects/contacts`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ properties })
  });

  if (createResponse.ok) {
    const created = await createResponse.json();
    return created.id;
  }

  // 409 = a contact with this email already exists — look it up and update it.
  if (createResponse.status === 409) {
    const searchResponse = await fetch(`${HUBSPOT_API}/crm/v3/objects/contacts/search`, {
      method: 'POST',
      headers,
      body: JSON.stringify({
        filterGroups: [{ filters: [{ propertyName: 'email', operator: 'EQ', value: email }] }],
        limit: 1
      })
    });
    const searchResult = await searchResponse.json();
    const existingId = searchResult.results && searchResult.results[0] && searchResult.results[0].id;
    if (!existingId) throw new Error('Contact reported as duplicate but could not be found');

    await fetch(`${HUBSPOT_API}/crm/v3/objects/contacts/${existingId}`, {
      method: 'PATCH',
      headers,
      body: JSON.stringify({ properties })
    });
    return existingId;
  }

  throw new Error(`HubSpot contact create failed: ${createResponse.status} ${await createResponse.text()}`);
}

async function logNote(headers, contactId, { serviceType, urgency, details }) {
  const noteBody =
    'New website lead\n' +
    `Service needed: ${serviceType || 'n/a'}\n` +
    `Urgency: ${urgency || 'n/a'}\n` +
    `Case details: ${details || 'n/a'}`;

  const noteResponse = await fetch(`${HUBSPOT_API}/crm/v3/objects/notes`, {
    method: 'POST',
    headers,
    body: JSON.stringify({
      properties: {
        hs_note_body: noteBody,
        hs_timestamp: Date.now()
      },
      associations: [
        {
          to: { id: contactId },
          types: [{ associationCategory: 'HUBSPOT_DEFINED', associationTypeId: 202 }]
        }
      ]
    })
  });

  if (!noteResponse.ok) {
    throw new Error(`HubSpot note create failed: ${noteResponse.status} ${await noteResponse.text()}`);
  }
}
