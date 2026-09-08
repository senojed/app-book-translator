"""Glosář termínů - logická vrstva nad SQLite tabulkou `glossary`.

Proč SQLite a ne JSON: glosář se mění při každé kapitole a jeho zápis musí být
ve stejné transakci jako commit kapitoly.

Klíčem entity je `term_id` (stabilní), ne povrch textu. Párování nového termínu
na existující řádek se ale dělá PODLE POVRCHU (`canonical_en` + `aliases`), aby
kandidát a pozdější schválený termín sdíleli jedno `term_id` a cizí klíče
z `term_mentions` držely.
"""
import json
import re

from src import state, textnorm


def slugify(text: str) -> str:
    """'The White Council' -> 'the-white-council'. Základ deterministického term_id."""
    s = re.sub(r"[^a-z0-9]+", "-", text.strip().lower())
    return s.strip("-") or "x"


def _row_to_dict(row) -> dict:
    d = dict(row)
    d["aliases"] = json.loads(d.get("aliases") or "[]")
    d["accepted_alt"] = json.loads(d.get("accepted_alt") or "[]")
    return d


def all_terms(db_path: str) -> list[dict]:
    with state.connect(db_path) as conn:
        rows = conn.execute("SELECT * FROM glossary ORDER BY term_id").fetchall()
    return [_row_to_dict(r) for r in rows]


def resolve_surface(db_path: str, surface: str):
    """Najde term_id podle povrchu (canonical_en nebo alias), case-insensitive."""
    if not surface:
        return None
    needle = surface.strip().lower()
    with state.connect(db_path) as conn:
        rows = conn.execute("SELECT term_id, canonical_en, aliases FROM glossary").fetchall()
    for r in rows:
        if (r["canonical_en"] or "").strip().lower() == needle:
            return r["term_id"]
        for a in json.loads(r["aliases"] or "[]"):
            if (a or "").strip().lower() == needle:
                return r["term_id"]
    return None


def resolve_term_or_surface(db_path: str, key: str):
    """`key` může být rovnou term_id (z otázky) nebo anglický povrch."""
    if not key:
        return None
    with state.connect(db_path) as conn:
        r = conn.execute("SELECT term_id FROM glossary WHERE term_id = ?", (key,)).fetchone()
    if r:
        return r["term_id"]
    return resolve_surface(db_path, key)


def _free_term_id(conn, base: str) -> str:
    """Dva různé povrchy se můžou slugifikovat stejně - přidej pořadový suffix."""
    tid = base
    n = 2
    while conn.execute("SELECT 1 FROM glossary WHERE term_id = ?", (tid,)).fetchone():
        tid = f"{base}_{n}"
        n += 1
    return tid


def add_candidate(db_path: str, term_en: str, cz: str, *, note: str = "",
                  type: str = "term") -> str:
    """Termín navržený translatorem. Existující povrch nepřepisuje."""
    existing = resolve_surface(db_path, term_en)
    if existing:
        return existing
    with state.connect(db_path) as conn:
        tid = _free_term_id(conn, "cand_" + slugify(term_en))
        conn.execute(
            "INSERT INTO glossary (term_id,canonical_en,aliases,cz,accepted_alt,"
            "note,type,status) VALUES (?,?,'[]',?,'[]',?,?,'candidate')",
            (tid, term_en, cz, note, type))
    return tid


def add_approved(db_path: str, canonical_en: str, cz: str, *, type: str = "term") -> str:
    """Odpověď člověka na termín, který v glosáři ještě není."""
    existing = resolve_surface(db_path, canonical_en)
    if existing:
        promote(db_path, existing, cz)
        return existing
    with state.connect(db_path) as conn:
        tid = _free_term_id(conn, "term_" + slugify(canonical_en))
        conn.execute(
            "INSERT INTO glossary (term_id,canonical_en,aliases,cz,accepted_alt,"
            "note,type,status) VALUES (?,?,'[]',?,'[]','',?,'approved')",
            (tid, canonical_en, cz, type))
    return tid


def promote(db_path: str, term_id: str, cz: str) -> None:
    with state.connect(db_path) as conn:
        conn.execute("UPDATE glossary SET status='approved', cz=?, "
                     "updated_at=CURRENT_TIMESTAMP WHERE term_id=?", (cz, term_id))


def add_accepted_alt(db_path: str, term_id: str, cz_form: str) -> None:
    """Další tvar, který člověk EXPLICITNĚ schválil. Pozorované tvary sem nepatří."""
    with state.connect(db_path) as conn:
        r = conn.execute("SELECT accepted_alt FROM glossary WHERE term_id=?",
                         (term_id,)).fetchone()
        if r is None:
            return
        alts = json.loads(r["accepted_alt"] or "[]")
        if cz_form not in alts:
            alts.append(cz_form)
        conn.execute("UPDATE glossary SET accepted_alt=?, updated_at=CURRENT_TIMESTAMP "
                     "WHERE term_id=?", (json.dumps(alts, ensure_ascii=False), term_id))


def _seed_one(conn, canonical_en: str, cz: str, type_: str,
              aliases: list, note: str):
    """Vrací dict konfliktu, nebo None. Řádek nalezený JEN přes alias se
    nepřepíše, liší-li se příchozí canonical_en - jinak by seed položky `Billy`
    přepsal kanonický tvar řádku `Billy Borden`, který ji má mezi aliasy."""
    existing, matched_by_canonical = None, False
    # textnorm.normalize_key (NFC + casefold), ne .strip().lower() - identita
    # v celém plánu (Task 9 merge, Task 4 hledání) stojí na normalize_key;
    # `.lower()` samotné nesloučí kanonicky stejný, ale jinak zapsaný Unicode
    # text (NFC vs. NFD), takže by guard vyrobil duplicitní řádek místo toho,
    # aby kolizi odhalil.
    needle = textnorm.normalize_key(canonical_en)
    rows = conn.execute("SELECT term_id,canonical_en,aliases,status FROM glossary").fetchall()
    # Dva průchody schválně: kanonická shoda má vždy přednost před aliasovou,
    # bez ohledu na pořadí řádků v tabulce. Jeden průchod s `break` na první
    # shodě by mohl narazit na aliasovou shodu dřív, než na kanonickou o pár
    # řádků dál, a nesprávně tvrdit "nalezeno jen přes alias".
    for r in rows:
        if textnorm.normalize_key(r["canonical_en"] or "") == needle:
            existing, matched_by_canonical = r, True
            break
    if existing is None:
        for r in rows:
            if needle in [textnorm.normalize_key(a or "")
                          for a in json.loads(r["aliases"] or "[]")]:
                existing = r
                break

    if existing is None:
        tid = _free_term_id(conn, "term_" + slugify(canonical_en))
        conn.execute(
            "INSERT INTO glossary (term_id,canonical_en,aliases,cz,accepted_alt,"
            "note,type,status) VALUES (?,?,?,?,'[]',?,?,'seeded')",
            (tid, canonical_en, json.dumps(aliases, ensure_ascii=False), cz, note, type_))
        return None

    if not matched_by_canonical and \
            textnorm.normalize_key(existing["canonical_en"] or "") != needle:
        return {"incoming": canonical_en,
                "existing_term_id": existing["term_id"],
                "existing_canonical": existing["canonical_en"]}

    merged = json.loads(existing["aliases"] or "[]")
    for a in aliases:
        if a not in merged:
            merged.append(a)
    if existing["status"] == "approved":
        # Lidské rozhodnutí přes `answer` vyhrává - měníme jen aliasy.
        conn.execute("UPDATE glossary SET aliases=? WHERE term_id=?",
                     (json.dumps(merged, ensure_ascii=False), existing["term_id"]))
        return None
    conn.execute(
        "UPDATE glossary SET canonical_en=?, aliases=?, cz=?, note=?, type=?, "
        "status='seeded', updated_at=CURRENT_TIMESTAMP WHERE term_id=?",
        (canonical_en, json.dumps(merged, ensure_ascii=False), cz, note, type_,
         existing["term_id"]))
    return None


def seed_from_guide(db_path: str, guide: dict) -> list:
    """Naseeduje glosář z potvrzeného návodu. Vrací seznam konfliktů, které
    CLI vypíše - nic se přitom nepřepíše."""
    conflicts = []
    with state.connect(db_path) as conn:
        for ch in guide.get("characters", []) or []:
            name = ch.get("name_en") or ""
            if not name:
                continue
            cz = name if ch.get("render", "keep") == "keep" else (ch.get("cz") or name)
            c = _seed_one(conn, name, cz, "name", list(ch.get("aliases") or []),
                          ch.get("note") or "")
            if c:
                conflicts.append(c)
        for pl in guide.get("places", []) or []:
            name = pl.get("name_en") or ""
            if not name:
                continue
            c = _seed_one(conn, name, pl.get("cz") or name, "place",
                          list(pl.get("aliases") or []), pl.get("note") or "")
            if c:
                conflicts.append(c)
        for t in guide.get("terms", []) or []:
            name = t.get("term_en") or ""
            if not name:
                continue
            c = _seed_one(conn, name, t.get("cz") or name, "term",
                          list(t.get("aliases") or []), t.get("note") or "")
            if c:
                conflicts.append(c)
    return conflicts


def as_prompt_block(db_path: str) -> str:
    """Glosář pro prompt translatora. Uvádí term_id - translator jím odkazuje
    známé termíny, `term_en` používá jen pro nové povrchy."""
    binding, candidates = [], []
    for t in all_terms(db_path):
        alias_txt = f"  (aliasy: {', '.join(t['aliases'])})" if t["aliases"] else ""
        line = f"[{t['term_id']}] {t['canonical_en']} → {t['cz']}{alias_txt}"
        (candidates if t["status"] == "candidate" else binding).append(line)
    parts = []
    if binding:
        parts.append("ZÁVAZNÉ termíny:\n" + "\n".join(binding))
    else:
        parts.append("ZÁVAZNÉ termíny: (zatím žádné)")
    if candidates:
        parts.append("NÁVRHY (mohou se změnit):\n" + "\n".join(candidates))
    return "\n\n".join(parts)
