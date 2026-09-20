# Citation and evidence review

Use this workflow when checking whether claims are cited, whether existing citations support their claims, or whether a new source should be suggested.

## Evidence levels

Keep these findings distinct:

1. **Citation coverage:** a claim appears to need support or its citation placement is ambiguous.
2. **Bibliographic integrity:** the citation key resolves and its title, authors, venue, year, and DOI or stable URL are verified.
3. **Claim support:** the verified source actually supports the nearby claim at the stated strength.
4. **Suggested addition:** a verified source is relevant enough to propose as a comment-only addition.

Do not infer levels 2–4 from a citation key, search-result snippet, model memory, or plausible-sounding metadata.

## Verification

- Prefer primary papers, publisher pages, DOI records, official proceedings, or authoritative repositories.
- Verify title, authors, year, and DOI or stable URL before proposing a source.
- Inspect the abstract or full text for claim support. If access is insufficient, label support as unverified.
- Do not cite a review article for an original result when the primary work is available, unless the review itself is the intended source.
- Never generate BibTeX from memory. Obtain it from a verified record or construct it only from independently verified fields.

## Output

Keep every finding attached to an exact source anchor. A suggested citation comment should state:

- why a citation is needed;
- the verified source and DOI or stable URL;
- which part of the claim it supports and any limitation;
- proposed BibTeX when verified;
- whether author approval or further source checking is required.

Do not edit the `.tex` or `.bib` file unless the user explicitly approves the specific additions. The automatic panel can identify coverage and placement issues, but specific citation recommendations require a web-backed verification pass.
