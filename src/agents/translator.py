"""Translator - dva režimy, jedna rodina promptů.

- čerstvý: scéna EN + návod + glosář → český překlad scény
- revizní: celá kapitola EN + předchozí CZ + nálezy → opravená kapitola
  (revizor není samostatný agent, je to translator s jiným promptem; EN originál
  je povinný, jinak nemůže opravit věrnost ani vynechávky)

PRÓZA NIKDY NEJDE V JSON. Překlad se vrací jako čistý text mezi markery,
metadata jako malý JSON za druhým markerem. JSON escapování dlouhé prózy je
zdroj rozbitých výstupů.
"""
import re
from dataclasses import dataclass, field

import config
from src.llm.client import OutputTruncated
from src.llm.parsing import extract_json

MARK_TRANSLATION = "===PREKLAD==="
MARK_METADATA = "===METADATA==="
MARK_END = "===KONEC==="

_FORMAT_RULES = f"""Výstup má PŘESNĚ tento tvar:

{MARK_TRANSLATION}
<čistý český překlad, žádné komentáře, žádné značky>
{MARK_METADATA}
{{"new_terms": [{{"term_en": "...", "cz": "...", "note": "...", "type": "name|place|term"}}],
 "rendered_terms": [{{"term_id": "...", "cz_as_used": "..."}}],
 "questions": [{{"kind": "term|name|relationship|style|other", "scope_key": "...",
                "guess_answer": "...", "text": "...", "severity": "guess|blocking"}}]}}
{MARK_END}

Pravidla metadat:
- "new_terms": jen povrchy, které v dodaném glosáři NEJSOU.
- "rendered_terms": pro každý termín z DODANÉHO glosáře, kterého ses dotkl,
  jeden řádek s jeho term_id a tvarem, jak jsi ho v překladu použil (i skloňovaným).
  Netextuj sem termíny, které v glosáři nejsou.
- "questions": "guess" = přeložil jsi to odhadem (vyplň guess_answer);
  "blocking" = fakt nevíš a překlad by mohl být špatně (guess_answer nech null).
- scope_key: u známého termínu jeho term_id z glosáře; u neznámého povrchu
  ten povrch přesně jak je v anglickém textu (včetně velkých písmen);
  u vztahu "JménoA|JménoB"; u style/other nech prázdné.

{MARK_END} MUSÍ být úplně poslední řádek výstupu - žádný text po něm.
Bez něj je výstup považovaný za useknutý/neúplný a celý zahozený, i
kdyby zbytek vypadal kompletně."""

SYSTEM_PROMPT_FRESH = f"""Jsi literární překladatel z angličtiny do češtiny.
Překládáš román pro čtenáře, ne doslovně - česky to musí znít přirozeně, ale
nesmíš nic vynechat ani přidat. Drž se dodaného návodu a glosáře; glosář je
závazný.

{_FORMAT_RULES}"""

SYSTEM_PROMPT_REVISE = f"""Jsi literární redaktor a překladatel. Dostaneš
anglický originál kapitoly, její dosavadní český překlad a seznam nálezů.
Oprav nálezy a vrať CELOU kapitolu znovu - ne jen opravené kusy. Co nález
nezmiňuje, neměň zbytečně.

{_FORMAT_RULES}"""


@dataclass
class TranslationResult:
    translation: str
    new_terms: list = field(default_factory=list)
    rendered_terms: list = field(default_factory=list)
    questions: list = field(default_factory=list)


class InvalidTranslationOutput(ValueError):
    """Výstup translatora neodpovídá očekávanému formátu (chybějící/
    duplicitní/špatně umístěný marker, prázdný překlad, rozbité JSON
    metadata) - podtřída ValueError, takže existující `except ValueError`
    volající kód funguje beze změny. `--translator codex` cestu (main.py
    `_cmd_run`, Task 5) zajímá zvlášť - signalizuje systémový drift
    formátu (Codex přestal dodržovat kontrakt), ne náhodnou chybu jedné
    kapitoly, viz Task 5 "Kolo 6 IMPORTANT"."""


def _marker_line_positions(raw: str, marker: str) -> list:
    """Pozice (offsety) řádků, co PŘESNĚ odpovídají markeru (celý
    řádek, nic jiného) - substring `in`/`count`/`index` by chytlo
    marker i UPROSTŘED přeloženého textu nebo JSON hodnoty (citace
    formátování zdrojového textu, popis nápisu v knize - kolo 9
    IMPORTANT, plan-consensus). `_FORMAT_RULES` už vyžaduje marker na
    VLASTNÍM řádku - tahle kontrola to VYNUTÍ, místo aby jen hledala
    podřetězec kdekoli."""
    pattern = re.compile(rf"^{re.escape(marker)}$", re.MULTILINE)
    return [m.start() for m in pattern.finditer(raw)]


def _parse(raw: str) -> TranslationResult:
    # Kolo 11 IMPORTANT (plan-consensus) - normalizace CRLF/CR na LF
    # JAKO PRVNÍ krok, PŘED řádkovou validací - `^marker$` (re.MULTILINE)
    # by na řádku končícím "\r\n" NEPROŠLO (`\r` zůstane MEZI markerem a
    # `$` pozicí, `$` v Pythonu matchuje těsně PŘED `\n`, ne za `\r\n`
    # dohromady). Windows-primární projekt - `subprocess`/`open()`'s
    # textový mód univerzální newlines obvykle řeší samy, ale tenhle
    # parser je backend-agnostický (obrana do hloubky i pro Claude
    # cestu, viz kolo 3), takže se na to nespoléhá.
    raw = raw.replace("\r\n", "\n").replace("\r", "\n")
    # Kolo 4 BLOCKING (plan-consensus) - pouhé "marker je NĚKDE v textu"
    # (kolo 3's `MARK_END in raw`) nestačí: marker uprostřed/duplicitní,
    # text po markeru, nebo (nejhorší) chybějící ===METADATA=== se
    # zachovaným ===KONEC=== by nechalo marker zapečený JAKO SOUČÁST
    # přeloženého textu (split_sections by "PREKLAD" sekci nezkrátilo,
    # protože by nenašlo svůj `nxt` marker). Vyžaduje se PŘESNÁ
    # struktura: každý marker právě jednou (na VLASTNÍM řádku, kolo 9
    # IMPORTANT - viz `_marker_line_positions` výš), ve správném pořadí,
    # a `===KONEC===` je opravdu POSLEDNÍ neprázdný obsah.
    # Kolo 6 IMPORTANT (plan-consensus) - `InvalidTranslationOutput`
    # (podtřída ValueError), ne holý `ValueError` - `--translator codex`
    # (main.py `_cmd_run`, Task 5) ji rozlišuje zvlášť a dělá z ní
    # `FatalRunError`, protože jde o STEJNOU třídu rizika jako kolo 2's
    # `StylistError`→`FatalRunError` (`state.queue_for_run`'s automatický
    # retry `error` kapitol), jen pro selhání PARSOVÁNÍ (formát driftl),
    # ne selhání CLI exekuce.
    trans_pos = _marker_line_positions(raw, MARK_TRANSLATION)
    meta_pos = _marker_line_positions(raw, MARK_METADATA)
    end_pos = _marker_line_positions(raw, MARK_END)
    if len(trans_pos) != 1 or len(meta_pos) != 1 or len(end_pos) != 1:
        raise InvalidTranslationOutput(
            "Výstup nemá přesně jeden ŘÁDEK s každým markerem "
            f"({MARK_TRANSLATION}/{MARK_METADATA}/{MARK_END}) - "
            "useknutý nebo jinak poškozený výstup.")
    if not (trans_pos[0] < meta_pos[0] < end_pos[0]):
        raise InvalidTranslationOutput(
            "Markery nejsou ve správném pořadí "
            f"({MARK_TRANSLATION} → {MARK_METADATA} → {MARK_END}).")
    if not raw.rstrip().endswith(MARK_END):
        raise InvalidTranslationOutput(
            f"Výstup nekončí markerem {MARK_END} - useknutý nebo jinak "
            "neúplný výstup, odmítám ho tiše přijmout jako hotový.")
    # Kolo 10 BLOCKING (plan-consensus) - `split_sections()` (src/llm/
    # parsing.py) NEPOUŽÍVÁME - i po kontrolách výš by její VLASTNÍ
    # substring `.split(marker, 1)` hledání znovu narazilo na STEJNÝ
    # problém: marker-podobný text UPROSTŘED METADATA JSON hodnoty (ne
    # na vlastním řádku, takže validaci výš neprojde jako SKUTEČNÝ
    # marker) by `split_sections()` přesto našla jako PRVNÍ výskyt
    # podřetězce a sekci tam předčasně uřízla - `_marker_line_positions()`
    # výš zná PŘESNÉ, OVĚŘENÉ offsety, takže sekce řežeme PŘÍMO slicingem
    # podle nich, ne přes samostatné substring hledání.
    translation = raw[trans_pos[0] + len(MARK_TRANSLATION):meta_pos[0]].strip()
    if not translation:
        raise InvalidTranslationOutput(
            "Translator nevrátil žádný text mezi markery "
            f"{MARK_TRANSLATION} / {MARK_METADATA}.")
    metadata_text = raw[meta_pos[0] + len(MARK_METADATA):end_pos[0]].strip()
    # `extract_json()`'s `ValueError` se přebalí na `InvalidTranslationOutput`
    # taky - rozbité JSON je STEJNÁ třída "formát driftl", ne jiná.
    try:
        meta = extract_json(metadata_text)
    except ValueError as e:
        raise InvalidTranslationOutput(str(e)) from e
    # Kolo 12 IMPORTANT (plan-consensus) - `extract_json()` validuje jen
    # SYNTAXI JSON, ne jeho TVAR - `[]`/`null`/`{"new_terms": "x"}` je
    # validní JSON, ale `meta.get(...)` na ne-dict spadne na
    # `AttributeError`, a `list("x")` (string místo seznamu) by tiše
    # rozsekal řetězec na znaky. Obojí je STEJNÁ třída "formát driftl"
    # jako rozbité JSON výš - musí projít přes `InvalidTranslationOutput`,
    # ne uniknout jako obyčejná `AttributeError` (necháno neklasifikované
    # by to Codex cestu nechalo auto-retryovat jako běžnou kapitolu).
    if not isinstance(meta, dict):
        raise InvalidTranslationOutput(
            f"Metadata JSON musí být objekt, ne {type(meta).__name__}.")
    for key in ("new_terms", "rendered_terms", "questions"):
        value = meta.get(key)
        if value is not None and (not isinstance(value, list)
                                  or not all(isinstance(item, dict) for item in value)):
            raise InvalidTranslationOutput(
                f"Metadata pole '{key}' musí být seznam objektů, "
                f"ne {type(value).__name__}.")
    # Kolo 14 IMPORTANT (plan-consensus) - "seznam objektů" (výš) samo
    # nestačí - `{"new_terms": [{"term_en": 1}]}` projde touhle kontrolou
    # (je to seznam, položka JE dict), ale `pipeline.py`'s `(nt.get(
    # "term_en") or "").strip()` na INTU spadne na `AttributeError`
    # (`1` je truthy, `or ""` fallback se nepoužije). Validuj typ
    # OČEKÁVANÝCH textových polí uvnitř každé položky - musí být string
    # nebo `None`/chybí, jinak STEJNÁ třída "formát driftl".
    _STRING_FIELDS = {
        "new_terms": ("term_en", "cz", "note", "type"),
        "rendered_terms": ("term_id", "cz_as_used"),
        "questions": ("kind", "scope_key", "guess_answer", "text", "severity"),
    }
    for key, fields in _STRING_FIELDS.items():
        for item in meta.get(key) or []:
            for field in fields:
                value = item.get(field)
                if value is not None and not isinstance(value, str):
                    raise InvalidTranslationOutput(
                        f"Metadata '{key}' pole '{field}' musí být řetězec "
                        f"nebo null, ne {type(value).__name__}.")
    return TranslationResult(
        translation=translation,
        new_terms=list(meta.get("new_terms") or []),
        rendered_terms=list(meta.get("rendered_terms") or []),
        questions=list(meta.get("questions") or []))


def _complete(client, system: str, user: str, model, max_tokens) -> str:
    comp = client.complete(system=system, user=user,
                           max_tokens=max_tokens or config.MAX_TOKENS_TRANSLATOR,
                           model=model or config.MODEL_TRANSLATOR)
    if comp.truncated:
        raise OutputTruncated("Překlad byl useknutý na max_tokens - "
                              "neúplný překlad je ztráta dat.")
    return comp.text


def translate_scene(scene_en: str, guide_block: str, glossary_block: str, client,
                    *, model=None, max_tokens=None) -> TranslationResult:
    user = (f"NÁVOD:\n{guide_block}\n\nGLOSÁŘ:\n{glossary_block}\n\n"
            f"ANGLICKÝ TEXT K PŘEKLADU:\n{scene_en}")
    return _parse(_complete(client, SYSTEM_PROMPT_FRESH, user, model, max_tokens))


def _format_findings(findings: list) -> str:
    lines = []
    for i, f in enumerate(findings or [], 1):
        issue = f.get("issue") or ""
        suggestion = f.get("suggestion") or ""
        excerpt = f.get("cz_excerpt") or ""
        line = f"{i}. {issue}"
        if excerpt:
            line += f"\n   místo v překladu: {excerpt}"
        if suggestion:
            line += f"\n   návrh: {suggestion}"
        lines.append(line)
    return "\n".join(lines) if lines else "(žádné)"


def revise_chapter(en_chapter: str, prev_cz: str, findings: list,
                   guide_block: str, glossary_block: str, client,
                   *, model=None, max_tokens=None) -> TranslationResult:
    user = (f"NÁVOD:\n{guide_block}\n\nGLOSÁŘ:\n{glossary_block}\n\n"
            f"NÁLEZY K OPRAVĚ:\n{_format_findings(findings)}\n\n"
            f"ANGLICKÝ ORIGINÁL KAPITOLY:\n{en_chapter}\n\n"
            f"DOSAVADNÍ ČESKÝ PŘEKLAD:\n{prev_cz}")
    return _parse(_complete(client, SYSTEM_PROMPT_REVISE, user, model, max_tokens))
