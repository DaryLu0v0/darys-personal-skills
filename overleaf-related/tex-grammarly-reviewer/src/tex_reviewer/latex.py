from __future__ import annotations

import re


class LatexValidationError(ValueError):
    pass


_DOCUMENT_BEGIN = r"\begin{document}"
_PROTECTED_COMMANDS = (
    "bibliography",
    "bibliographystyle",
    "cite",
    "citealp",
    "citeauthor",
    "citep",
    "citet",
    "cref",
    "Cref",
    "eqref",
    "href",
    "include",
    "includegraphics",
    "include",
    "input",
    "input",
    "label",
    "pageref",
    "ref",
    "url",
)
_DROP_ENVIRONMENTS = (
    "align",
    "align*",
    "equation",
    "equation*",
    "gather",
    "gather*",
    "lstlisting",
    "math",
    "multline",
    "multline*",
    "picture",
    "tikzpicture",
    "verbatim",
)
_DROP_COMMANDS_WITH_ARG = (
    "bibliography",
    "bibliographystyle",
    "cite",
    "citealp",
    "citeauthor",
    "citep",
    "citet",
    "cref",
    "Cref",
    "eqref",
    "includegraphics",
    "label",
    "pageref",
    "ref",
    "url",
)


def _strip_comments(source: str) -> str:
    lines: list[str] = []
    for line in source.splitlines():
        escaped = False
        kept: list[str] = []
        for char in line:
            if char == "%" and not escaped:
                break
            kept.append(char)
            if char == "\\":
                escaped = not escaped
            else:
                escaped = False
        lines.append("".join(kept))
    return "\n".join(lines)


def _remove_balanced_command(source: str, command: str) -> str:
    pattern = re.compile(rf"\\{re.escape(command)}\s*(?:\[[^\]]*\]\s*)?\{{")
    while True:
        match = pattern.search(source)
        if not match:
            return source
        depth = 1
        index = match.end()
        while index < len(source) and depth:
            if source[index] == "{" and (index == 0 or source[index - 1] != "\\"):
                depth += 1
            elif source[index] == "}" and (index == 0 or source[index - 1] != "\\"):
                depth -= 1
            index += 1
        source = source[: match.start()] + " " + source[index:]


def latex_to_plain_text(source: str) -> str:
    """Extract reviewable prose without executing TeX or following includes."""
    text = _strip_comments(source)
    if _DOCUMENT_BEGIN in text:
        text = text.split(_DOCUMENT_BEGIN, 1)[1]
    text = text.replace(r"\end{document}", " ")

    for environment in _DROP_ENVIRONMENTS:
        text = re.sub(
            rf"\\begin\{{{re.escape(environment)}\}}.*?\\end\{{{re.escape(environment)}\}}",
            " ",
            text,
            flags=re.DOTALL,
        )

    text = re.sub(r"\$\$.*?\$\$", " ", text, flags=re.DOTALL)
    text = re.sub(r"(?<!\\)\$.*?(?<!\\)\$", " ", text, flags=re.DOTALL)
    text = re.sub(r"\\\[.*?\\\]", " ", text, flags=re.DOTALL)
    text = re.sub(r"\\\(.*?\\\)", " ", text, flags=re.DOTALL)

    for command in _DROP_COMMANDS_WITH_ARG:
        text = _remove_balanced_command(text, command)

    text = re.sub(r"\\begin\{[^}]+\}(?:\[[^\]]*\])?", " ", text)
    text = re.sub(r"\\end\{[^}]+\}", " ", text)
    text = re.sub(r"\\[a-zA-Z@]+\*?(?:\[[^\]]*\])?", " ", text)
    text = re.sub(r"\\.", " ", text)
    text = text.replace("{", " ").replace("}", " ")
    text = text.replace("~", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _preamble(source: str) -> str:
    if _DOCUMENT_BEGIN not in source:
        return ""
    return source.split(_DOCUMENT_BEGIN, 1)[0]


def _balanced_braces(source: str) -> bool:
    depth = 0
    escaped = False
    for char in _strip_comments(source):
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth < 0:
                return False
    return depth == 0


def _environments(source: str) -> tuple[tuple[str, str], ...]:
    return tuple(
        (kind, name)
        for kind, name in re.findall(r"\\(begin|end)\{([^}]+)\}", _strip_comments(source))
    )


def _balanced_argument(source: str, opening: int) -> tuple[str, int]:
    depth = 0
    for index in range(opening, len(source)):
        char = source[index]
        if char == "{" and (index == 0 or source[index - 1] != "\\"):
            depth += 1
        elif char == "}" and (index == 0 or source[index - 1] != "\\"):
            depth -= 1
            if depth == 0:
                return source[opening : index + 1], index + 1
    return source[opening:], len(source)


def _protected_tokens(source: str) -> tuple[str, ...]:
    cleaned = _strip_comments(source)
    names = "|".join(re.escape(name) for name in _PROTECTED_COMMANDS)
    pattern = re.compile(rf"\\(?:{names})\*?")
    tokens: list[str] = []
    for match in pattern.finditer(cleaned):
        index = match.end()
        token = match.group(0)
        while index < len(cleaned) and cleaned[index].isspace():
            index += 1
        if index < len(cleaned) and cleaned[index] == "[":
            close = cleaned.find("]", index + 1)
            if close != -1:
                token += cleaned[index : close + 1]
                index = close + 1
                while index < len(cleaned) and cleaned[index].isspace():
                    index += 1
        argument_count = 2 if match.group(0).rstrip("*") == r"\href" else 1
        for _ in range(argument_count):
            if index < len(cleaned) and cleaned[index] == "{":
                argument, index = _balanced_argument(cleaned, index)
                token += argument
            while index < len(cleaned) and cleaned[index].isspace():
                index += 1
        tokens.append(token)
    return tuple(tokens)


def _math_tokens(source: str) -> tuple[str, ...]:
    cleaned = _strip_comments(source)
    pattern = re.compile(
        r"\\begin\{(equation\*?|align\*?|gather\*?|multline\*?|math)\}"
        r".*?\\end\{\1\}"
        r"|\$\$.*?\$\$"
        r"|\\\[.*?\\\]"
        r"|\\\(.*?\\\)"
        r"|(?<!\\)\$(?!\$).*?(?<!\\)\$",
        flags=re.DOTALL,
    )
    return tuple(match.group(0) for match in pattern.finditer(cleaned))


def _numeric_tokens(source: str) -> tuple[str, ...]:
    return tuple(
        re.findall(
            r"(?<![A-Za-z])[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?(?![A-Za-z])",
            _strip_comments(source),
        )
    )


def validate_revision(original: str, candidate: str) -> None:
    if not candidate.strip():
        raise LatexValidationError("candidate is empty")
    if "```" in candidate:
        raise LatexValidationError("candidate contains Markdown fences")
    if _preamble(original) != _preamble(candidate):
        raise LatexValidationError("LaTeX preamble changed")
    if not _balanced_braces(candidate):
        raise LatexValidationError("candidate has unbalanced braces")
    if _environments(original) != _environments(candidate):
        raise LatexValidationError("LaTeX environment inventory changed")
    if _protected_tokens(original) != _protected_tokens(candidate):
        raise LatexValidationError("protected citations, references, labels, or file links changed")
    if _math_tokens(original) != _math_tokens(candidate):
        raise LatexValidationError("mathematical content changed")
    if _numeric_tokens(original) != _numeric_tokens(candidate):
        raise LatexValidationError("numeric content changed")
    if latex_to_plain_text(original) == latex_to_plain_text(candidate):
        raise LatexValidationError("candidate did not change reviewable prose")
