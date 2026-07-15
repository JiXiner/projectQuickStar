"""Language detection based on source file extensions."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Iterable


LANGUAGE_EXTENSIONS: dict[str, frozenset[str]] = {
    "Python": frozenset({".py", ".pyw", ".pyi"}),
    "Java": frozenset({".java", ".jsp"}),
    "PHP": frozenset({".php", ".phtml"}),
    "Go": frozenset({".go"}),
    "JavaScript": frozenset({".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".vue"}),
}

_EXTENSION_LANGUAGE = {
    extension: language
    for language, extensions in LANGUAGE_EXTENSIONS.items()
    for extension in extensions
}


def language_for_path(path: str | Path) -> str | None:
    """Return the supported language for *path*, or ``None``."""

    return _EXTENSION_LANGUAGE.get(Path(path).suffix.lower())


def detect_languages(paths: Iterable[str | Path]) -> dict[str, int]:
    """Count supported source files, ordered by descending frequency."""

    counts = Counter(
        language
        for path in paths
        if (language := language_for_path(path)) is not None
    )
    return dict(counts.most_common())


def matches_language(path: str | Path, selected_language: str) -> bool:
    """Whether a path is relevant to a user-selected language."""

    if selected_language == "自动检测":
        return True
    detected = language_for_path(path)
    return detected is None or detected == selected_language
