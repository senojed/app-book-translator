"""
Načtení zdrojové knihy (EPUB nebo TXT) a rozdělení na kapitoly.

EPUB: použijeme ebooklib, z každého dokumentu v čítacím pořadí (spine)
vytáhneme čistý text (BeautifulSoup), kapitoly = jednotlivé XHTML dokumenty
ve spine, které obsahují netriviální množství textu (přeskočíme obálku,
copyright stránku apod. na základě minimální délky textu).

TXT: očekáváme, že kapitoly jsou odděleny řádkem odpovídajícím vzoru
"Kapitola N" / "Chapter N" / "CHAPTER N" apod., nebo explicitním
oddělovačem "---". Pokud nic nenajdeme, celý text je jedna "kapitola"
a uživatel to musí doladit ručně - ingest to nahlásí.
"""
import re
from dataclasses import dataclass

MIN_CHAPTER_CHARS = 500  # kratší bloky v EPUB spine bereme jako ne-kapitoly (titulní strana atd.)

CHAPTER_HEADING_RE = re.compile(
    r"^\s*(chapter|kapitola)\s+([0-9ivxlcdm]+|[a-z]+)\s*[:.]?\s*$",
    re.IGNORECASE,
)


@dataclass
class Chapter:
    index: int          # pořadí od 1
    title: str
    raw_text: str        # originální (anglický) text kapitoly


def load_book(path: str) -> list[Chapter]:
    if path.lower().endswith(".epub"):
        return _load_epub(path)
    elif path.lower().endswith(".txt"):
        return _load_txt(path)
    else:
        raise ValueError(f"Nepodporovaný formát souboru: {path}. Použij .epub nebo .txt.")


def _load_epub(path: str) -> list[Chapter]:
    import ebooklib
    from ebooklib import epub
    from bs4 import BeautifulSoup

    book = epub.read_epub(path)

    # Dokumenty bereme v pořadí ČTENÍ (spine), ne v pořadí uložení v souboru.
    # get_items_of_type() vrací pořadí z manifestu, které nemusí sedět - kapitoly
    # by pak vyšly přeházené. book.spine je seznam (idref, linear); dokument
    # dohledáme přes get_item_with_id.
    items = []
    for entry in book.spine:
        idref = entry[0] if isinstance(entry, (tuple, list)) else entry
        item = book.get_item_with_id(idref)
        if item is not None:
            items.append(item)
    if not items:
        # spine prázdný nebo nestandardní EPUB - fallback na původní chování
        items = list(book.get_items_of_type(ebooklib.ITEM_DOCUMENT))

    chapters = []
    idx = 0
    for item in items:
        if item.get_type() != ebooklib.ITEM_DOCUMENT:
            continue
        soup = BeautifulSoup(item.get_content(), "html.parser")
        text = soup.get_text(separator="\n").strip()
        # normalizace vícenásobných prázdných řádků
        text = re.sub(r"\n{3,}", "\n\n", text)
        if len(text) < MIN_CHAPTER_CHARS:
            continue
        idx += 1
        title = _guess_title(soup, idx)
        chapters.append(Chapter(index=idx, title=title, raw_text=text))
    if not chapters:
        raise RuntimeError(
            "V EPUB souboru se nenašla žádná kapitola nad minimální délkou. "
            f"Zkontroluj MIN_CHAPTER_CHARS ({MIN_CHAPTER_CHARS}) nebo strukturu EPUB."
        )
    return chapters


def _guess_title(soup, fallback_idx: int) -> str:
    heading = soup.find(["h1", "h2", "h3"])
    if heading and heading.get_text(strip=True):
        return heading.get_text(strip=True)
    return f"Kapitola {fallback_idx}"


def _load_txt(path: str) -> list[Chapter]:
    with open(path, "r", encoding="utf-8") as f:
        raw = f.read()

    lines = raw.splitlines()
    boundaries = []  # indexy řádků, kde začíná nová kapitola
    for i, line in enumerate(lines):
        if CHAPTER_HEADING_RE.match(line.strip()):
            boundaries.append(i)

    if not boundaries:
        # Nenašli jsme žádné nadpisy - vrátíme celý text jako jednu kapitolu
        # a necháme volajícího vědět, že segmentace selhala.
        return [Chapter(index=1, title="Celá kniha (nerozpoznána segmentace)", raw_text=raw.strip())]

    chapters = []
    for n, start in enumerate(boundaries):
        end = boundaries[n + 1] if n + 1 < len(boundaries) else len(lines)
        title = lines[start].strip()
        body = "\n".join(lines[start + 1:end]).strip()
        # Explicitní nadpis "Chapter N" je dost silný signál - na rozdíl od EPUB
        # spine tady netřídíme podle délky (jinak by krátká kapitola zmizela).
        if not body:
            continue
        chapters.append(Chapter(index=len(chapters) + 1, title=title, raw_text=body))
    return chapters


def split_into_scenes(text: str, word_threshold: int) -> list[str]:
    """
    Pokud je kapitola nad prahem slov, rozdělí ji na scény podle typických
    oddělovačů (prázdný řádek + volitelně '***' nebo podobně). Používá se
    interně orchestrátorem, navenek zůstává jednotka "kapitola".
    """
    word_count = len(text.split())
    if word_count <= word_threshold:
        return [text]

    # rozdělení podle explicitních oddělovačů scén nebo dvojitých prázdných řádků
    parts = re.split(r"\n\s*(?:\*\s*\*\s*\*|#+|—{3,})\s*\n", text)
    if len(parts) == 1:
        parts = re.split(r"\n{2,}", text)

    # pokud je jednotlivých kousků moc (rozdělilo to po odstavcích), radši
    # vrátíme celý text jako jeden blok - lepší dlouhý kontext než přehnané drobení
    if len(parts) > max(2, word_count // word_threshold + 2):
        return [text]

    return [p.strip() for p in parts if p.strip()]
