"""String utilities for the demo — several functions intentionally lack tests."""


def slugify(text: str) -> str:
    """Lowercase a string and replace runs of non-alphanumerics with dashes."""
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in text)
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    return cleaned.strip("-")


def initials(full_name: str) -> str:
    """First letter of each whitespace-separated word, uppercase."""
    return "".join(word[0].upper() for word in full_name.split() if word)


def truncate(text: str, limit: int, suffix: str = "...") -> str:
    """Cut text to `limit` characters, appending `suffix` when cut."""
    if limit <= 0:
        return ""
    if len(text) <= limit:
        return text
    cut = text[: max(limit - len(suffix), 0)].rstrip()
    return cut + suffix


def word_count(text: str) -> int:
    """Number of whitespace-separated words."""
    return len(text.split())
