# Michigan Data Center Tracker editorial guide

The daily content lives in `content-data.js`. The page layout, map, mobile behavior and visual design should not need to be edited for routine updates.

## Non-negotiable editorial rules

1. Write every tracker headline and summary in original language.
2. Do not copy or lightly rearrange a publisher’s headline.
3. Link directly to the source supporting the claim.
4. Prefer official agendas, minutes, filings, ordinances and direct statements.
5. If only reporting is available, label the record `Reported`.
6. Never add a placeholder meeting, quote, post, URL, coordinate or statistic.
7. Public posts document the conversation; inclusion is not endorsement.
8. Use municipality-level coordinates unless a public source identifies a precise site. Say when a marker is approximate.
9. Update `updated_at` whenever editorial content changes.

## Mailchimp connection

Copy the Mailchimp embedded-form `action` URL into:

```js
newsletter: {
  form_action: "https://YOUR-ACCOUNT.usXX.list-manage.com/subscribe/post?u=...&id=..."
}
```

The signup field already uses Mailchimp’s standard `EMAIL` name. Until a real action URL is present, the form clearly says that no address was submitted.

## X and Reddit feed connection

Do not put X, Reddit or other API secrets in this repository. GitHub Pages is public.

Have the feed service expose a read-only HTTPS JSON endpoint, then place it here:

```js
feeds: {
  public_monitor_url: "https://your-secure-service.example/public-monitor.json"
}
```

The endpoint may return an array or `{ "items": [...] }`. Each item must have:

```json
{
  "account_name": "Display name",
  "platform": "X or Reddit",
  "posted_at": "2026-06-22",
  "text": "A concise original tracker summary, not a copied post",
  "post_url": "https://direct-original-post-url",
  "context_note": "Why this post is relevant and who is speaking"
}
```

The browser limits the display to 12 valid items and falls back to the editorial snapshot if the live feed is unavailable.

## Grok update checklist

- Return valid JSON only.
- Use exact source URLs.
- Distinguish government meetings from rallies or advocacy events.
- Do not infer exact project coordinates.
- Do not combine values from unlike datasets into one number.
- Flag uncertain claims instead of filling gaps.
- Rewrite source headlines and post text in original language.
- Keep summaries factual and under 55 words.

## Publishing check

Before publishing:

- Open the homepage, map and methodology page on desktop and phone sizes.
- Confirm there is no horizontal scrolling.
- Confirm all external links show `↗`.
- Confirm the email form is connected to the intended Mailchimp audience.
- Confirm live-feed URLs use HTTPS and expose no credentials.
- Confirm the update timestamp is current.
