import re


class BibtexArticleParseError(ValueError):
    pass


_FIELD_NAME_RE = re.compile(r"[A-Za-z0-9_-]+")


def parse_bibtex_article_entry(raw_entry: str) -> dict:
    entry = (raw_entry or "").strip()
    if not entry:
        raise BibtexArticleParseError("BibTeX entry cannot be empty.")
    if not entry.startswith("@"):
        raise BibtexArticleParseError("BibTeX entry must start with '@'.")

    match = re.match(r"@\s*([A-Za-z]+)\s*\{", entry)
    if not match:
        raise BibtexArticleParseError("Invalid BibTeX entry header.")

    entry_type = match.group(1).lower()
    if entry_type != "article":
        raise BibtexArticleParseError("Only BibTeX @article entries are supported.")

    open_brace_index = match.end() - 1
    close_brace_index = _find_matching_brace(entry, open_brace_index)
    if entry[close_brace_index + 1 :].strip():
        raise BibtexArticleParseError("Invalid trailing content after BibTeX entry.")

    body = entry[open_brace_index + 1 : close_brace_index].strip()
    citation_key, fields_part = _split_citation_key_and_fields(body)
    fields = _parse_bibtex_fields(fields_part)

    title = _normalize_bibtex_text(fields.get("title"))
    journal = _normalize_bibtex_text(fields.get("journal"))
    year = _parse_year(fields.get("year"))

    if not title:
        raise BibtexArticleParseError("BibTeX @article entries must include a title.")
    if not journal:
        raise BibtexArticleParseError("BibTeX @article entries must include a journal.")
    if year is None:
        raise BibtexArticleParseError("BibTeX @article entries must include a year.")

    return {
        "entry_type": entry_type,
        "citation_key": _normalize_bibtex_text(citation_key) or None,
        "title": title,
        "journal": journal,
        "year": year,
        "volume": _normalize_bibtex_text(fields.get("volume")) or None,
        "number": _normalize_bibtex_text(fields.get("number")) or None,
        "pages": _normalize_pages(fields.get("pages")),
        "month": _normalize_month(fields.get("month")),
        "doi": _normalize_identifier(fields.get("doi")),
        "url": _normalize_identifier(fields.get("url")),
        "publisher": _normalize_bibtex_text(fields.get("publisher")) or None,
        "abstract": _normalize_bibtex_text(fields.get("abstract")) or None,
        "authors": _parse_authors(fields.get("author")),
    }


def _find_matching_brace(text: str, open_index: int) -> int:
    depth = 0
    in_quote = False
    escape = False
    for index in range(open_index, len(text)):
        char = text[index]
        if escape:
            escape = False
            continue
        if char == "\\":
            escape = True
            continue
        if char == '"':
            in_quote = not in_quote
            continue
        if in_quote:
            continue
        if char == "{":
            depth += 1
            continue
        if char == "}":
            depth -= 1
            if depth == 0:
                return index
    raise BibtexArticleParseError("BibTeX entry has unmatched braces.")


def _split_citation_key_and_fields(body: str) -> tuple[str, str]:
    depth = 0
    in_quote = False
    escape = False
    for index, char in enumerate(body):
        if escape:
            escape = False
            continue
        if char == "\\":
            escape = True
            continue
        if char == '"':
            in_quote = not in_quote
            continue
        if in_quote:
            continue
        if char == "{":
            depth += 1
            continue
        if char == "}":
            depth -= 1
            continue
        if char == "," and depth == 0:
            citation_key = body[:index].strip()
            fields_part = body[index + 1 :].strip()
            if not citation_key:
                raise BibtexArticleParseError(
                    "BibTeX entry must include a citation key."
                )
            return citation_key, fields_part
    raise BibtexArticleParseError("BibTeX entry must include a citation key.")


def _parse_bibtex_fields(fields_part: str) -> dict:
    fields = {}
    index = 0
    length = len(fields_part)

    while index < length:
        while index < length and fields_part[index] in " \t\r\n,":
            index += 1
        if index >= length:
            break

        match = _FIELD_NAME_RE.match(fields_part, index)
        if match is None:
            raise BibtexArticleParseError("Invalid BibTeX field name.")
        key = match.group(0).lower()
        index = match.end()

        while index < length and fields_part[index].isspace():
            index += 1
        if index >= length or fields_part[index] != "=":
            raise BibtexArticleParseError(f"Missing '=' after BibTeX field '{key}'.")
        index += 1

        while index < length and fields_part[index].isspace():
            index += 1
        if index >= length:
            raise BibtexArticleParseError(f"Missing value for BibTeX field '{key}'.")

        value, index = _parse_bibtex_value(fields_part, index)
        fields[key] = value

    return fields


def _parse_bibtex_value(text: str, index: int) -> tuple[str, int]:
    if text[index] == "{":
        end = _find_matching_brace(text, index)
        return text[index + 1 : end], end + 1

    if text[index] == '"':
        index += 1
        value = []
        escape = False
        while index < len(text):
            char = text[index]
            if escape:
                value.append(char)
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                return "".join(value), index + 1
            else:
                value.append(char)
            index += 1
        raise BibtexArticleParseError("BibTeX quoted field has no closing quote.")

    start = index
    while index < len(text) and text[index] not in ",\r\n":
        index += 1
    return text[start:index], index


def _normalize_bibtex_text(value: str | None) -> str:
    text = (value or "").replace("{", " ").replace("}", " ")
    return " ".join(text.replace("\r", " ").replace("\n", " ").split())


def _parse_year(value: str | None) -> int | None:
    cleaned = _normalize_identifier(value)
    if not cleaned:
        return None
    if not cleaned.isdigit():
        raise BibtexArticleParseError("BibTeX year must be a valid integer.")
    return int(cleaned)


def _normalize_pages(value: str | None) -> str | None:
    cleaned = _normalize_identifier(value)
    if not cleaned:
        return None
    return cleaned.replace("--", "-")


def _normalize_month(value: str | None) -> str | None:
    cleaned = _normalize_bibtex_text(value)
    if not cleaned:
        return None
    return cleaned.lower()


def _normalize_identifier(value: str | None) -> str | None:
    cleaned = _normalize_bibtex_text(value)
    return cleaned or None


def _parse_authors(value: str | None) -> list[dict]:
    cleaned = _normalize_bibtex_text(value)
    if not cleaned:
        return []

    authors = []
    for chunk in re.split(r"\s+and\s+", cleaned, flags=re.IGNORECASE):
        name = chunk.strip()
        if not name:
            continue
        authors.append(_parse_single_author(name))
    return authors


def _parse_single_author(name: str) -> dict:
    if "," in name:
        parts = [part.strip() for part in name.split(",") if part.strip()]
        if len(parts) == 2:
            return {
                "first_names": parts[1],
                "last_names": parts[0],
                "suffix": "",
            }
        if len(parts) >= 3:
            return {
                "first_names": " ".join(parts[2:]),
                "last_names": parts[0],
                "suffix": parts[1],
            }

    parts = name.split()
    if len(parts) <= 1:
        return {"first_names": "", "last_names": name, "suffix": ""}
    return {
        "first_names": " ".join(parts[:-1]),
        "last_names": parts[-1],
        "suffix": "",
    }
