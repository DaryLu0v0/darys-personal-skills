from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import sys

from .clients import GrammarlyClient, OpenAIEditor, OpenAIPanelReviewer, ServiceError
from .latex import latex_to_plain_text
from .panel import generate_panel
from .reviewers import DEFAULT_REVIEWERS, REVIEWER_ROLES, get_reviewer_roles
from .workflow import ReviewConfig, review_document


def _unit_interval(value: str) -> float:
    number = float(value)
    if not 0.0 <= number <= 1.0:
        raise argparse.ArgumentTypeError("must be between 0 and 1")
    return number


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tex-review",
        description="Score and conservatively revise LaTeX prose with Grammarly.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    score = subparsers.add_parser("score", help="Score a .tex file without editing it")
    score.add_argument("tex", type=Path)

    panel = subparsers.add_parser(
        "panel",
        help="generate validated, role-specific comments for later Overleaf publishing",
    )
    panel.add_argument("tex", type=Path)
    panel.add_argument("--output-dir", type=Path)
    panel.add_argument("--model", default=None)
    panel.add_argument(
        "--reviewers",
        nargs="+",
        choices=tuple(REVIEWER_ROLES),
        default=list(DEFAULT_REVIEWERS),
    )
    panel.add_argument("--max-comments-per-reviewer", type=int, default=12)

    review = subparsers.add_parser("review", help="Iteratively revise and rescore a .tex file")
    review.add_argument("tex", type=Path)
    review.add_argument("-o", "--output", type=Path)
    review.add_argument(
        "--apply",
        action="store_true",
        help="write the accepted revision instead of comment-only suggestions",
    )
    review.add_argument("--in-place", action="store_true")
    review.add_argument("--model", default=None)
    review.add_argument(
        "--preference",
        choices=("scientific", "general"),
        default="scientific",
        help="editor preference profile (default: scientific)",
    )
    review.add_argument(
        "--style-note",
        default="",
        help="additional author-supplied style preference",
    )
    review.add_argument("--max-attempts", type=int, default=5)
    review.add_argument("--patience", type=int, default=2)
    review.add_argument("--target-ai", type=_unit_interval, default=0.20)
    review.add_argument("--target-issue-level", type=_unit_interval, default=0.05)
    review.add_argument("--tolerance", type=_unit_interval, default=0.0)
    return parser


def _read_tex(path: Path) -> str:
    if path.suffix.lower() != ".tex":
        raise ValueError(f"expected a .tex file, got {path}")
    return path.read_text(encoding="utf-8")


def _run_dir(tex: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    root = tex.parent / ".tex-reviewer"
    candidate = root / f"{tex.stem}-{stamp}"
    serial = 1
    while candidate.exists():
        serial += 1
        candidate = root / f"{tex.stem}-{stamp}-{serial}"
    return candidate


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        source = _read_tex(args.tex.resolve())
        scorer = GrammarlyClient()
        if args.command == "score":
            score = scorer.assess(latex_to_plain_text(source))
            print(json.dumps(score.to_dict(), indent=2))
            return 0

        if args.command == "panel":
            if args.max_comments_per_reviewer < 1:
                raise ValueError("--max-comments-per-reviewer must be positive")
            score = scorer.assess(latex_to_plain_text(source))
            reviewer = OpenAIPanelReviewer(model=args.model)
            output_dir = (
                args.output_dir.resolve()
                if args.output_dir
                else _run_dir(args.tex.resolve())
            )
            result = generate_panel(
                source,
                filename=args.tex.name,
                score=score,
                reviewer=reviewer,
                roles=get_reviewer_roles(tuple(args.reviewers)),
                output_dir=output_dir,
                max_comments_per_reviewer=args.max_comments_per_reviewer,
            )
            print(
                json.dumps(
                    {
                        "manifest": str(result.manifest_path),
                        "markdown": str(result.markdown_path),
                        "accepted_comments": result.accepted_comments,
                        "rejected_comments": result.rejected_comments,
                        "publication_status": "not-published",
                    },
                    indent=2,
                )
            )
            return 0

        if args.max_attempts < 1 or args.patience < 1:
            raise ValueError("--max-attempts and --patience must be positive")
        if args.in_place and not args.apply:
            raise ValueError("--in-place requires --apply; comment mode never overwrites the source")
        editor = OpenAIEditor(
            model=args.model,
            preference=args.preference,
            style_note=args.style_note,
        )
        run_dir = _run_dir(args.tex.resolve())
        result = review_document(
            source,
            scorer=scorer,
            editor=editor,
            run_dir=run_dir,
            config=ReviewConfig(
                max_attempts=args.max_attempts,
                patience=args.patience,
                target_ai=args.target_ai,
                target_issue_level=args.target_issue_level,
                tolerance=args.tolerance,
                preference=args.preference,
            ),
        )

        if args.apply and args.in_place:
            output = args.tex.resolve()
            backup = run_dir / "pre-overwrite-original.tex"
            shutil.copy2(output, backup)
            output_content = result.latex
        else:
            default_name = (
                f"{args.tex.stem}.reviewed.tex"
                if args.apply
                else f"{args.tex.stem}.review-comments.tex"
            )
            output = (args.output or args.tex.with_name(default_name)).resolve()
            if output == args.tex.resolve():
                if args.apply:
                    raise ValueError("use --in-place with --apply to overwrite the source")
                raise ValueError("the comment report must not overwrite the source")
            output_content = result.latex if args.apply else result.annotated_latex
        output.write_text(output_content, encoding="utf-8")
        print(
            json.dumps(
                {
                    "output": str(output),
                    "output_mode": "applied" if args.apply else "comments",
                    "preference": args.preference,
                    "run_dir": str(result.run_dir),
                    "stop_reason": result.stop_reason,
                    "accepted_revisions": result.accepted_revisions,
                    "attempts": result.attempts,
                    "score": result.score.to_dict(),
                },
                indent=2,
            )
        )
        return 0
    except (OSError, ValueError, ServiceError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
