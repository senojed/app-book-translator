"""Parsování odpovědí modelu. Bez importu anthropic."""
import json
import re


def split_sections(raw: str, markers: list[str]) -> dict[str, str]:
    """Rozdělí odpověď podle markerů. Klíč = marker bez '=', hodnota = text
    mezi tímto a následujícím markerem. Text před prvním markerem se zahodí."""
    out: dict[str, str] = {}
    text = raw
    for i, marker in enumerate(markers):
        if marker not in text:
            continue
        after = text.split(marker, 1)[1]
        nxt = markers[i + 1] if i + 1 < len(markers) else None
        if nxt and nxt in after:
            value = after.split(nxt, 1)[0]
        else:
            value = after
        out[marker.strip("=")] = value.strip()
        text = after
    return out


def extract_json(raw: str) -> dict:
    """Vytáhne JSON z odpovědi - snese ```json fence i okolní text."""
    cleaned = re.sub(r"^```json\s*|\s*```$", "", raw.strip()).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
        raise ValueError(f"Nevalidní JSON. Raw:\n{raw[:2000]}")
