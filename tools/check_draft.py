"""Report-only kontrola draftu od scouta před těžbou referencí.

Scoutův draft obsahuje vady, které by těžbu a formulář rozbily: výčty místo
jednoho povrchu, duplicitní entity, otázky odkazující nikam. Tenhle skript je
NAJDE A VYPÍŠE, ale nic nemění - opravu dělá člověk ručně v `guide.draft.json`.

Proč report-only: rozhodnutí "je `White Court / Red Court` jedna entita se
synonymy, nebo tři různé?" automat neudělá. Je to jednorázová práce na ~39
řádcích, takže interaktivní nástroj by se nevyplatil.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from src import guide, textnorm

# Aliasy, které jako dotaz do korpusu nic neurčují - rozšířily by důkaz o šum.
ROLE_ALIASES = {"sir", "captain", "kid", "apprentice", "boss", "boy", "girl",
                "master", "mister", "miss"}

_OR_SEPARATOR = re.compile(r"\bor\b", re.IGNORECASE)
SECTIONS = (("characters", "name_en"), ("places", "name_en"), ("terms", "term_en"))
KIND_TO_SECTION = {"name": "characters", "place": "places", "term": "terms"}


def _items(draft):
    """Vrací (sekce, klíčové_pole, položka) pro všechny tři sekce."""
    for section, field in SECTIONS:
        for item in draft.get(section) or []:
            yield section, field, item


def _issue(section, surface, detail):
    return {"section": section, "surface": surface, "detail": detail}


def find_issues(draft: dict) -> dict:
    issues = {k: [] for k in ("compound", "alias_collision", "duplicate_key",
                              "bad_scope_key", "bad_relationship",
                              "duplicate_relationship", "parenthesized",
                              "cross_section", "weak_alias",
                              "short_relationship")}

    # mapa normalizovaný klíč -> sekce (pro homonyma) a alias -> vlastník
    key_sections, alias_owner, key_counts = {}, {}, {}
    for section, field, item in _items(draft):
        surface = item.get(field) or ""
        key = textnorm.normalize_key(surface)
        if key:
            key_sections.setdefault(key, set()).add(section)
            key_counts[(section, key)] = key_counts.get((section, key), 0) + 1
        for alias in item.get("aliases") or []:
            alias_owner.setdefault(textnorm.normalize_key(alias), []).append(surface)

    # Duplicitní kanonické jméno v jedné sekci: scout stejnou entitu vede
    # dvakrát pod stejným (case/whitespace-insensitive) klíčem. Bez tohohle by
    # `reference_mine.resolve` vytvořilo dvě položky se stejným `id`.
    for (section, key), count in key_counts.items():
        if count > 1:
            issues["duplicate_key"].append(
                _issue(section, key, f"{count}x stejný kanonický klíč v sekci"))

    for section, field, item in _items(draft):
        surface = item.get(field) or ""
        if "/" in surface or _OR_SEPARATOR.search(surface):
            issues["compound"].append(_issue(section, surface, "výčet variant"))
        if "(" in surface or ")" in surface:
            issues["parenthesized"].append(
                _issue(section, surface, "poznámka v závorce - přesné hledání ji nenajde"))
        owners = [o for o in alias_owner.get(textnorm.normalize_key(surface), [])
                  if textnorm.normalize_key(o) != textnorm.normalize_key(surface)]
        if owners:
            issues["alias_collision"].append(
                _issue(section, surface, "je aliasem u: " + ", ".join(owners)))
        for alias in item.get("aliases") or []:
            stripped = alias.strip()
            a = textnorm.normalize_key(alias)
            if a in ROLE_ALIASES or len(stripped) <= 3 \
                    or (stripped[:1].islower() if stripped else False):
                issues["weak_alias"].append(_issue(section, surface, alias))

    for key, sections in key_sections.items():
        if len(sections) > 1:
            issues["cross_section"].append(
                _issue("/".join(sorted(sections)), key, "homonymum napříč sekcemi"))

    # kanonická jména postav - pro kontrolu konců vztahů
    char_keys = {textnorm.normalize_key(c.get("name_en") or "")
                 for c in draft.get("characters") or []}
    rel_counts = {}
    for rel in draft.get("relationships") or []:
        a, b = rel.get("a") or "", rel.get("b") or ""
        for end in (a, b):
            if "/" in end:
                issues["bad_relationship"].append(
                    _issue("relationships", end, "lomítko ve jméně"))
            elif textnorm.normalize_key(end) not in char_keys:
                issues["short_relationship"].append(
                    _issue("relationships", end, "není kanonické jméno postavy"))
        # dvojice se počítá bez ohledu na pořadí a velikost písmen, stejně
        # jako to dělá guide.relationship_key - jinak by duplicita neprojevila
        rk = guide.relationship_key(a, b)
        rel_counts[rk] = rel_counts.get(rk, 0) + 1
    for rk, count in rel_counts.items():
        if count > 1:
            issues["duplicate_relationship"].append(
                _issue("relationships", rk, f"{count}x stejná dvojice"))

    for md in draft.get("must_decide") or []:
        kind = md.get("kind")
        scope = md.get("scope_key") or ""
        if kind == "style":
            continue          # styl nemá klíčované položky, odpověď jde do rules
        if kind == "relationship":
            a, _, b = scope.partition("|")
            # scope_key musí být přesně tvar, jaký apply_must_decide hledá -
            # guide.relationship_key(a, b). Jiné pořadí nebo velikost písmen
            # (`Murphy|Harry` místo `harry|murphy`) by odpověď nenašla svůj cíl.
            expected = guide.relationship_key(a, b) if b else None
            if not b or textnorm.normalize_key(a) not in char_keys \
                    or textnorm.normalize_key(b) not in char_keys \
                    or scope != expected:
                issues["bad_scope_key"].append(
                    _issue("must_decide", scope,
                           "vztah: čekej tvar odpovídající guide.relationship_key(a, b)"))
            continue
        section = KIND_TO_SECTION.get(kind)
        if section is None:
            issues["bad_scope_key"].append(_issue("must_decide", scope, f"neznámý kind {kind!r}"))
            continue
        if textnorm.normalize_key(scope) not in {
                textnorm.normalize_key(i.get(f) or "")
                for s, f, i in _items(draft) if s == section}:
            issues["bad_scope_key"].append(
                _issue("must_decide", scope, f"neukazuje na položku v sekci {section}"))

    return issues


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    path = (argv or sys.argv[1:] or [config.GUIDE_DRAFT_PATH])[0]
    draft = guide.load_draft(path)
    issues = find_issues(draft)
    total = sum(len(v) for v in issues.values())
    if not total:
        print(f"{path}: čistý, všech šest postpodmínek splněno.")
        return 0
    print(f"{path}: {total} věcí k ruční opravě\n")
    for name, rows in issues.items():
        if not rows:
            continue
        print(f"== {name} ({len(rows)}) ==")
        for r in rows:
            print(f"   [{r['section']}] {r['surface']!r} - {r['detail']}")
        print()
    print("Skript nic nemění. Oprav guide.draft.json ručně a spusť znovu.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
