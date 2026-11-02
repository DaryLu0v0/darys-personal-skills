# Overleaf-related skills

This category is part of the same repository as the [Hikari meeting assistant](../hikari/README.md)
and [personal assistant](../personal_assistant/README.md). See the
[shared research-toolkit guide](../docs/research-toolkit.md) for their entry points
and independent setup requirements. The reviewer remains in the directory below;
there is no second copy under Hikari.

## TeX Grammarly Reviewer

[`tex-grammarly-reviewer/`](tex-grammarly-reviewer/) contains:

- the `scientific-tex-reviewer` Codex skill;
- a conservative Python reviewer for a single UTF-8 `.tex` source file;
- Grammarly aggregate scoring and supervised UI-observation guidance;
- independent humanization, grammar, scientific-concept, citation/evidence, and venue-agnostic overview reviewers;
- optional venue profiles sourced from current official conference or journal guidance;
- comment-only LaTeX suggestions and validated native Overleaf-comment manifests;
- tests for source preservation, anchoring, reviewer roles, score acceptance, and manifest drift.

Native Overleaf publication remains a supervised step. The project never silently edits manuscript claims or impersonates separate reviewers.
