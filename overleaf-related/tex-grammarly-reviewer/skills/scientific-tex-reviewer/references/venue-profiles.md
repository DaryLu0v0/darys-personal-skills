# Venue profiles

The core scientific overview is venue-agnostic. Use a venue profile only when the user identifies a target conference, journal, track, and preferably year.

## Build a profile

1. Retrieve the current official author instructions, reviewer criteria, ethics rules, and track-specific requirements.
2. Record the venue, year, track or article type, source links, and date checked.
3. Extract only criteria that affect the review: scope, contribution standard, evidence expectations, reproducibility, formatting, disclosure, and submission-specific requirements.
4. Save the resulting criteria as UTF-8 text and pass them with `--venue` and `--venue-guidance`.

Do not rely on a previous year's policy when a current one is available. Do not silently apply an ICLR, NeurIPS, AAAI, or publisher rubric to a general manuscript.

## Boundaries

- Venue criteria modify the overview reviewer, not the humanization, grammar, or scientific-fact standards.
- Track-specific rules override broad venue conventions.
- A venue profile supports author pre-review; it does not predict acceptance or impersonate an official reviewer.
- If no current official rubric is supplied, use the general scientific overview and label the review venue-agnostic.
