# TikTok Review Checklist

Before submitting the app, replace placeholders in:
- `index.html`
- `privacy-policy.html`
- `terms-of-service.html`

You need to prepare:
- a real support email
- a public URL for the website
- a public URL for the privacy policy
- a public URL for the terms of service
- the exact redirect URI you will use for Login Kit

Recommended minimal site structure:
- `/` -> landing page
- `/privacy-policy.html`
- `/terms-of-service.html`

What to show in the app review video:
- the app homepage
- the TikTok login/authorization step
- a local folder with example videos
- the scheduling screen or config
- one upload flow to an authorized TikTok account
- the resulting post status or private post visibility

Important current limitation from TikTok docs:
- unaudited clients can only post in `SELF_ONLY`
- unaudited clients have a cap of up to 5 users in a 24-hour window

For your target of 7 accounts:
- full production use will likely require review/audit approval
