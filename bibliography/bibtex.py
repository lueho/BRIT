import re
from datetime import date


class BibtexArticleParseError(ValueError):
    pass


_FIELD_NAME_RE = re.compile(r"[A-Za-z0-9_-]+")
_DATE_RE = re.compile(
    r"^\s*(?P<year>\d{4})(?:[-/](?P<month>\d{1,2})(?:[-/](?P<day>\d{1,2}))?)?\s*$"
)
_FIELD_ALIASES = {
    "article_number": "eid",
    "articlenumber": "eid",
    "eid": "eid",
    "issue": "number",
    "number": "number",
    "journaltitle": "journal",
}
_MONTH_NAMES_BY_NUMBER = {
    "1": "jan",
    "2": "feb",
    "3": "mar",
    "4": "apr",
    "5": "may",
    "6": "jun",
    "7": "jul",
    "8": "aug",
    "9": "sep",
    "10": "oct",
    "11": "nov",
    "12": "dec",
}
_MONTH_NAMES_BY_TEXT = {
    "jan": "jan",
    "january": "jan",
    "feb": "feb",
    "february": "feb",
    "mar": "mar",
    "march": "mar",
    "apr": "apr",
    "april": "apr",
    "may": "may",
    "jun": "jun",
    "june": "jun",
    "jul": "jul",
    "july": "jul",
    "aug": "aug",
    "august": "aug",
    "sep": "sep",
    "sept": "sep",
    "september": "sep",
    "oct": "oct",
    "october": "oct",
    "nov": "nov",
    "november": "nov",
    "dec": "dec",
    "december": "dec",
}


def parse_bibtex_article_entry(raw_entry: str) -> dict:
    entries = parse_bibtex_article_entries(raw_entry)
    if len(entries) != 1:
        raise BibtexArticleParseError("Expected exactly one BibTeX @article entry.")
    return entries[0]


def parse_bibtex_article_entries(raw_entries: str) -> list[dict]:
    entry_text = (raw_entries or "").strip()
    if not entry_text:
        raise BibtexArticleParseError("BibTeX entry cannot be empty.")

    entries = []
    index = 0
    while index < len(entry_text):
        while index < len(entry_text) and entry_text[index].isspace():
            index += 1
        if index >= len(entry_text):
            break
        if entry_text[index] != "@":
            raise BibtexArticleParseError(
                "BibTeX input must contain only @article entries."
            )

        raw_entry, index = _extract_bibtex_entry(entry_text, index)
        entries.append(_parse_single_bibtex_article_entry(raw_entry))

    if not entries:
        raise BibtexArticleParseError("BibTeX entry cannot be empty.")
    return entries


def _extract_bibtex_entry(text: str, start_index: int) -> tuple[str, int]:
    match = re.match(r"@\s*([A-Za-z]+)\s*\{", text[start_index:])
    if not match:
        raise BibtexArticleParseError("Invalid BibTeX entry header.")

    open_brace_index = start_index + match.end() - 1
    close_brace_index = _find_matching_brace(text, open_brace_index)
    return text[start_index : close_brace_index + 1], close_brace_index + 1


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


def _parse_single_bibtex_article_entry(raw_entry: str) -> dict:
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

    year_from_date, month_from_date = _parse_date_parts(fields.get("date"))
    title = _flatten_bibtex_text(fields.get("title"))
    journal = _flatten_bibtex_text(fields.get("journal"))
    year = _parse_year(fields.get("year")) or year_from_date

    if not title:
        raise BibtexArticleParseError("BibTeX @article entries must include a title.")
    if not journal:
        raise BibtexArticleParseError("BibTeX @article entries must include a journal.")
    if year is None:
        raise BibtexArticleParseError("BibTeX @article entries must include a year.")

    return {
        "entry_type": entry_type,
        "citation_key": _flatten_bibtex_text(citation_key) or None,
        "title": title,
        "journal": journal,
        "year": year,
        "volume": _flatten_bibtex_text(fields.get("volume")) or None,
        "number": _flatten_bibtex_text(fields.get("number")) or None,
        "eid": _normalize_identifier(fields.get("eid")),
        "pages": _normalize_pages(fields.get("pages")),
        "month": _normalize_month(fields.get("month")) or month_from_date,
        "doi": _normalize_identifier(fields.get("doi")),
        "url": _normalize_identifier(fields.get("url")),
        "publisher": _flatten_bibtex_text(fields.get("publisher")) or None,
        "abstract": _flatten_bibtex_text(fields.get("abstract")) or None,
        "authors": _parse_authors_best_effort(fields.get("author")),
    }


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
        key = _normalize_field_name(match.group(0))
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
        if key in fields:
            raise BibtexArticleParseError(f"Duplicate BibTeX field '{key}'.")
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


def _flatten_bibtex_text(value: str | None) -> str:
    text = str(value or "").replace("{", "").replace("}", "")
    return " ".join(text.replace("\r", " ").replace("\n", " ").split())


def _normalize_field_name(name: str) -> str:
    normalized = name.lower().replace("-", "_")
    return _FIELD_ALIASES.get(normalized, normalized)


def _parse_year(value: str | None) -> int | None:
    cleaned = _normalize_identifier(value)
    if not cleaned:
        return None
    if not cleaned.isdigit():
        raise BibtexArticleParseError("BibTeX year must be a valid integer.")
    return int(cleaned)


def _normalize_pages(value: str | None) -> str | None:
    return _normalize_identifier(value)


def _parse_date_parts(value: str | None) -> tuple[int | None, str | None]:
    cleaned = _normalize_identifier(value)
    if not cleaned:
        return None, None

    match = _DATE_RE.match(cleaned)
    if match is None:
        raise BibtexArticleParseError(
            "BibTeX date must use YYYY, YYYY-MM, or YYYY-MM-DD."
        )

    year = int(match.group("year"))
    month_value = match.group("month")
    day_value = match.group("day")
    if month_value is None:
        return year, None

    month_number = int(month_value)
    if not 1 <= month_number <= 12:
        raise BibtexArticleParseError("BibTeX date month must be between 1 and 12.")

    if day_value is not None:
        try:
            date(year, month_number, int(day_value))
        except ValueError as exc:
            raise BibtexArticleParseError(
                "BibTeX date must be a valid calendar date."
            ) from exc

    return year, _MONTH_NAMES_BY_NUMBER[str(month_number)]


def _normalize_month(value: str | None) -> str | None:
    cleaned = _normalize_identifier(value)
    if not cleaned:
        return None

    normalized = cleaned.strip().rstrip(".").lower()
    if normalized.isdigit():
        month = _MONTH_NAMES_BY_NUMBER.get(str(int(normalized)))
        if month is None:
            raise BibtexArticleParseError("BibTeX month must be between 1 and 12.")
        return month

    month = _MONTH_NAMES_BY_TEXT.get(normalized)
    if month is None:
        raise BibtexArticleParseError(
            "BibTeX month must be a valid month name or number."
        )
    return month


def _normalize_identifier(value: str | None) -> str | None:
    cleaned = _flatten_bibtex_text(value)
    return cleaned or None


def _parse_authors_best_effort(value: str | None) -> list[dict]:
    raw_value = str(value or "").strip()
    if not raw_value:
        return []

    authors = []
    for chunk in _split_author_chunks_best_effort(raw_value):
        name = chunk.strip()
        if not name:
            continue
        authors.append(_parse_single_author_best_effort(name))
    return authors


def _split_author_chunks_best_effort(raw_value: str) -> list[str]:
    chunks = []
    start = 0
    depth = 0
    in_quote = False
    escape = False
    index = 0

    while index < len(raw_value):
        char = raw_value[index]
        if escape:
            escape = False
            index += 1
            continue
        if char == "\\":
            escape = True
            index += 1
            continue
        if char == '"':
            in_quote = not in_quote
            index += 1
            continue
        if in_quote:
            index += 1
            continue
        if char == "{":
            depth += 1
            index += 1
            continue
        if char == "}":
            depth = max(depth - 1, 0)
            index += 1
            continue

        if depth == 0 and raw_value[index : index + 3].lower() == "and":
            previous_char = raw_value[index - 1] if index > 0 else " "
            next_char = raw_value[index + 3] if index + 3 < len(raw_value) else " "
            if previous_char.isspace() and next_char.isspace():
                chunks.append(raw_value[start:index].strip())
                index += 3
                start = index
                continue

        index += 1

    chunks.append(raw_value[start:].strip())
    return [chunk for chunk in chunks if chunk]


def _parse_single_author_best_effort(name: str) -> dict:
    raw_name = name.strip()
    if _is_fully_braced(raw_name):
        return {
            "first_names": "",
            "last_names": _flatten_bibtex_text(raw_name[1:-1]),
            "suffix": "",
        }

    cleaned = _flatten_bibtex_text(raw_name)
    if "," in cleaned:
        parts = [part.strip() for part in cleaned.split(",") if part.strip()]
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

    parts = cleaned.split()
    if len(parts) <= 1:
        return {"first_names": "", "last_names": cleaned, "suffix": ""}

    last_name_start = len(parts) - 1
    while last_name_start > 0 and _looks_like_name_particle(parts[last_name_start - 1]):
        last_name_start -= 1

    return {
        "first_names": " ".join(parts[:last_name_start]),
        "last_names": " ".join(parts[last_name_start:]),
        "suffix": "",
    }


def _is_fully_braced(value: str) -> bool:
    stripped = value.strip()
    if not stripped.startswith("{") or not stripped.endswith("}"):
        return False
    try:
        return _find_matching_brace(stripped, 0) == len(stripped) - 1
    except BibtexArticleParseError:
        return False


def _looks_like_name_particle(token: str) -> bool:
    cleaned = re.sub(r"[^A-Za-zÀ-ÖØ-öø-ÿ'’-]", "", token)
    return bool(cleaned) and cleaned == cleaned.lower()
