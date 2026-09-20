from tex_reviewer.latex import LatexValidationError, latex_to_plain_text, validate_revision


ORIGINAL = r"""\documentclass{article}
\usepackage{amsmath}
\begin{document}
\section{Results}
This are a result from our device \cite{smith2025}. See Fig.~\ref{fig:one}.
\begin{equation}
x = y + 1
\end{equation}
\label{sec:results}
\end{document}
"""


def test_extracts_prose_and_omits_math_and_citations() -> None:
    text = latex_to_plain_text(ORIGINAL)
    assert "Results" in text
    assert "This are a result" in text
    assert "smith2025" not in text
    assert "x = y" not in text


def test_allows_prose_only_revision() -> None:
    candidate = ORIGINAL.replace("This are a result", "This is a result")
    validate_revision(ORIGINAL, candidate)


def test_rejects_changed_citation() -> None:
    candidate = ORIGINAL.replace("smith2025", "other2025")
    try:
        validate_revision(ORIGINAL, candidate)
    except LatexValidationError as exc:
        assert "protected" in str(exc)
    else:
        raise AssertionError("changed citation was accepted")


def test_rejects_changed_preamble() -> None:
    candidate = ORIGINAL.replace("amsmath", "mathtools").replace(
        "This are a result", "This is a result"
    )
    try:
        validate_revision(ORIGINAL, candidate)
    except LatexValidationError as exc:
        assert "preamble" in str(exc)
    else:
        raise AssertionError("changed preamble was accepted")


def test_rejects_changed_equation() -> None:
    candidate = ORIGINAL.replace("x = y + 1", "x = y + 2").replace(
        "This are a result", "This is a result"
    )
    try:
        validate_revision(ORIGINAL, candidate)
    except LatexValidationError as exc:
        assert "mathematical" in str(exc)
    else:
        raise AssertionError("changed equation was accepted")


def test_rejects_changed_number_in_prose() -> None:
    numbered = ORIGINAL.replace("our device", "our 16-element device")
    candidate = numbered.replace("16-element", "32-element").replace(
        "This are a result", "This is a result"
    )
    try:
        validate_revision(numbered, candidate)
    except LatexValidationError as exc:
        assert "numeric" in str(exc)
    else:
        raise AssertionError("changed prose number was accepted")
