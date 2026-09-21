# Paper library schema

Use this reference when assigning metadata, completing a reading note, or
interpreting search results.

## Identity and provenance

- `paper_id`: generated stable identifier. DOI has priority, then arXiv ID,
  canonical URL, then normalized title and year.
- `title`, `authors`, `year`, `venue`, `doi`, and `url`: copy from the paper or
  its authoritative landing page. Leave unavailable values empty.
- `source_type`: `pdf`, `url`, or `manual`.
- `source_ref`: original local path or URL supplied at import.
- `pdf`: Obsidian link to a copied PDF, or an external local path when copying
  is disabled.

## Reading state

Use exactly one:

- `interested`: saved because it may be relevant; not queued for a full read.
- `to-read`: intentionally queued.
- `reading`: a substantive reading is in progress.
- `read`: the important argument, methods, evidence, and limitations were read.
- `archived`: retained but no longer active.

`priority` is `low`, `normal`, or `high`. It expresses the user's attention,
not paper quality.

## Labels

- `fields`: broad, stable disciplines such as `electromagnetics`,
  `machine-learning`, or `spectroscopy`.
- `topics`: narrower subjects such as `metasurface-beamforming`,
  `characteristic-mode-analysis`, or `sim-to-real-transfer`.
- `methods`: techniques demonstrably used, such as `finite-element-method`,
  `cst-studio-suite`, `foldy-lax`, or `convolutional-neural-network`.
- `tags`: personal workflow or cross-cutting labels that do not fit the three
  semantic lists.

Labels are lower-case, hyphenated, and singular where natural. Reuse an
existing label when it means the same thing. Do not assign methods from related
work or speculate from the title alone.

## Reading-note evidence

The generated note contains a `Claims and Evidence` table. For consequential
claims record:

- the claim in the paper's terms;
- the supporting result or reasoning;
- a page, section, figure, table, or equation location;
- a calibrated confidence based on what was actually inspected.

Keep `Connections` and `Ideas and Hypotheses` separate. The former may synthesize
relationships to other saved papers; the latter is explicitly not source
evidence.
