"""The language check: English text against the writing standard in docs/prd.md, Section 17.

The check reads every file in the repository that holds English text for people: the README,
the documents, the dashboard text, the patient plan templates, and the comments and strings of
the code. It reports each word or phrase from the list of words to avoid (words_to_avoid.yaml)
and each American spelling from the same file, because the project uses Indian English.

Some text must keep its original wording, so the check skips it: the list of words to avoid
itself, the "Not:" examples in the writing standard, the titles of references, the names of
other projects and datasets, web addresses, code and the column names of the datasets.
"""

from __future__ import annotations

import io
import json
import re
import subprocess
import tokenize
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import yaml

from rozmarra.config import REPO_ROOT

RULES_FILE = Path(__file__).with_name("words_to_avoid.yaml")

URL = re.compile(r"https?://\S+|www\.\S+")
INLINE_CODE = re.compile(r"`[^`]*`")
JINJA = re.compile(r"\{%.*?%\}|\{\{.*?\}\}|\{#.*?#\}", re.S)
HTML_TAG = re.compile(r"<[^>]+>")
JSON_VALUE = re.compile(r'^\s*"[^"]*"\s*:\s*"(?P<value>.*)",?\s*$')


@dataclass(frozen=True)
class Rule:
    pattern: re.Pattern[str]
    use_instead: str
    kind: str  # "word" for the words to avoid, or "spelling" for American spellings


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    found: str
    use_instead: str
    kind: str

    def __str__(self) -> str:
        what = "American spelling" if self.kind == "spelling" else "Word to avoid"
        return f'{self.path}:{self.line}: {what} "{self.found}". Use instead: {self.use_instead}.'


def load_rules(path: Path = RULES_FILE) -> tuple[list[Rule], dict]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    rules = []
    for kind, entries in (("word", data["words"]), ("spelling", data["spellings"])):
        for entry in entries:
            flags = 0 if entry.get("case_sensitive") else re.IGNORECASE
            rules.append(Rule(re.compile(entry["pattern"], flags), entry["use_instead"], kind))
    return rules, data["skip"]


# --- Reading the English text of each kind of file --------------------------------------------


def _markdown_lines(text: str) -> Iterator[tuple[int, str]]:
    in_code = False
    for number, line in enumerate(text.splitlines(), start=1):
        if line.lstrip().startswith("```"):
            in_code = not in_code
            continue
        if not in_code:
            yield number, INLINE_CODE.sub(" ", line)


def _python_lines(text: str, strings: bool) -> Iterator[tuple[int, str]]:
    wanted = {tokenize.COMMENT}
    if strings:
        wanted |= {tokenize.STRING, getattr(tokenize, "FSTRING_MIDDLE", tokenize.STRING)}
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(text).readline))
    except (tokenize.TokenError, SyntaxError):
        return
    for token in tokens:
        if token.type in wanted:
            for offset, line in enumerate(token.string.splitlines()):
                yield token.start[0] + offset, line


def _script_comment_lines(text: str, marker: str) -> Iterator[tuple[int, str]]:
    for number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if stripped.startswith(marker) and not stripped.startswith("#!"):
            yield number, stripped


def _typescript_comment_lines(text: str) -> Iterator[tuple[int, str]]:
    in_block = False
    for number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if in_block:
            yield number, stripped
            in_block = "*/" not in stripped
            continue
        if "/*" in stripped and not stripped.startswith(("'", '"')):
            yield number, stripped[stripped.index("/*") :]
            in_block = "*/" not in stripped
            continue
        match = re.search(r"(^|\s)//(?!/)(.*)$", line)
        if match:
            yield number, match.group(2)


def _json_value_lines(text: str) -> Iterator[tuple[int, str]]:
    for number, line in enumerate(text.splitlines(), start=1):
        match = JSON_VALUE.match(line)
        if match:
            yield number, json.loads(f'"{match.group("value")}"')


def _template_lines(text: str) -> Iterator[tuple[int, str]]:
    # Jinja tags and comments can span lines, so they are removed line by line after a
    # replacement that keeps the line numbers.
    cleaned = JINJA.sub(lambda m: "\n" * m.group(0).count("\n"), text)
    for number, line in enumerate(cleaned.splitlines(), start=1):
        yield number, HTML_TAG.sub(" ", line)


def english_lines(path: Path, relative: str) -> Iterator[tuple[int, str]]:
    text = path.read_text(encoding="utf-8", errors="replace")
    suffix = path.suffix
    if suffix == ".md":
        yield from _markdown_lines(text)
    elif suffix == ".py":
        yield from _python_lines(text, strings=not relative.startswith("backend/tests/"))
    elif suffix in {".ts", ".tsx"}:
        yield from _typescript_comment_lines(text)
    elif suffix == ".json":
        yield from _json_value_lines(text)
    elif suffix == ".j2":
        yield from _template_lines(text)
    elif suffix in {".ps1", ".sh", ".yml", ".yaml", ".toml"}:
        yield from _script_comment_lines(text, "#")


# --- Choosing the files and the lines to skip -------------------------------------------------


def files_to_check(root: Path, skip: dict) -> list[str]:
    try:
        listed = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.splitlines()
    except (OSError, subprocess.CalledProcessError):
        listed = [p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()]
    include = [re.compile(p) for p in skip["include_files"]]
    exclude = [re.compile(p) for p in skip["exclude_files"]]
    return sorted(
        p
        for p in listed
        if any(r.search(p) for r in include)
        and not any(r.search(p) for r in exclude)
        and (root / p).is_file()
    )


def _skipped_sections(path: str, lines: list[str], skip: dict) -> set[int]:
    """Line numbers inside a Markdown section that keeps its original wording."""
    skipped: set[int] = set()
    for section in skip["sections"]:
        if not re.search(section["file"], path):
            continue
        inside, level = False, 0
        for number, line in enumerate(lines, start=1):
            heading = re.match(r"^(#+)\s", line)
            if heading and inside and len(heading.group(1)) <= level:
                inside = False
            if heading and line.strip().startswith(section["heading"]):
                inside, level = True, len(heading.group(1))
                continue
            if inside:
                skipped.add(number)
    return skipped


def check(root: Path = REPO_ROOT, rules_file: Path = RULES_FILE) -> list[Finding]:
    rules, skip = load_rules(rules_file)
    keep = [re.compile(p, re.IGNORECASE) for p in skip["original_wording"]]
    skip_lines = [
        (re.compile(item["file"]), re.compile(item["line"])) for item in skip["line_patterns"]
    ]
    exclamation_files = [re.compile(p) for p in skip["no_exclamation_files"]]
    findings: list[Finding] = []
    for relative in files_to_check(root, skip):
        path = root / relative
        all_lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        skipped = _skipped_sections(relative, all_lines, skip)
        check_exclamation = any(r.search(relative) for r in exclamation_files)
        for number, line in english_lines(path, relative):
            if number in skipped:
                continue
            raw = all_lines[number - 1] if number <= len(all_lines) else line
            if any(f.search(relative) and p.search(raw) for f, p in skip_lines):
                continue
            text = URL.sub(" ", line)
            for name in keep:
                text = name.sub(" ", text)
            for rule in rules:
                for match in rule.pattern.finditer(text):
                    findings.append(
                        Finding(relative, number, match.group(0), rule.use_instead, rule.kind)
                    )
            if check_exclamation and "!" in text:
                findings.append(Finding(relative, number, "!", "a full stop", "word"))
    return findings
