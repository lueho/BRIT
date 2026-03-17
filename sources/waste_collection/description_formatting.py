import re

_LEGACY_SECTION_SEPARATOR_RE = re.compile(r"(?:\s*;\s*){2,}")


def normalize_collection_description(value):
    text = "" if value is None else str(value)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if _LEGACY_SECTION_SEPARATOR_RE.search(text) is None:
        return text
    parts = [part.strip() for part in _LEGACY_SECTION_SEPARATOR_RE.split(text)]
    return "\n".join(part for part in parts if part)


def flatten_collection_description(value):
    text = normalize_collection_description(value)
    return "; ".join(line.strip() for line in text.splitlines() if line.strip())
