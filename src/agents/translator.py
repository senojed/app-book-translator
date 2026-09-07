"""Translator - dva režimy, jedna rodina promptů.

- čerstvý: scéna EN + návod + glosář → český překlad scény
- revizní: celá kapitola EN + předchozí CZ + nálezy → opravená kapitola
  (revizor není samostatný agent, je to translator s jiným promptem; EN originál
  je povinný, jinak nemůže opravit věrnost ani vynechávky)

PRÓZA NIKDY NEJDE V JSON. Překlad se vrací jako čistý text mezi markery,
metadata jako malý JSON za druhým markerem. JSON escapování dlouhé prózy je
zdroj rozbitých výstupů.
"""
from dataclasses import dataclass, field

import config
from src.llm.client import OutputTruncated
from src.llm.parsing import extract_json, split_sections

MARK_TRANSLATION = "===PREKLAD==="
MARK_METADATA = "===METADATA==="

_FORMAT_RULES = f"""Výstup má PŘESNĚ tento tvar:

{MARK_TRANSLATION}
<čistý český překlad, žádné komentáře, žádné značky>
{MARK_METADATA}
{{"new_terms": [{{"term_en": "...", "cz": "...", "note": "...", "type": "name|place|term"}}],
 "rendered_terms": [{{"term_id": "...", "cz_as_used": "..."}}],
 "questions": [{{"kind": "term|name|relationship|style|other", "scope_key": "...",
                "guess_answer": "...", "text": "...", "severity": "guess|blocking"}}]}}

Pravidla metadat:
- "new_terms": jen povrchy, které v dodaném glosáři NEJSOU.
- "rendered_terms": pro každý termín z DODANÉHO glosáře, kterého ses dotkl,
  jeden řádek s jeho term_id a tvarem, jak jsi ho v překladu použil (i skloňovaným).
  Netextuj sem termíny, které v glosáři nejsou.
- "questions": "guess" = přeložil jsi to odhadem (vyplň guess_answer);
  "blocking" = fakt nevíš a překlad by mohl být špatně (guess_answer nech null).
- scope_key: u známého termínu jeho term_id z glosáře; u neznámého povrchu
  ten povrch přesně jak je v anglickém textu (včetně velkých písmen);
  u vztahu "JménoA|JménoB"; u style/other nech prázdné."""

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


def _parse(raw: str) -> TranslationResult:
    sections = split_sections(raw, [MARK_TRANSLATION, MARK_METADATA])
    translation = (sections.get("PREKLAD") or "").strip()
    if not translation:
        raise ValueError("Translator nevrátil žádný text mezi markery "
                         f"{MARK_TRANSLATION} / {MARK_METADATA}.")
    meta: dict = {}
    if MARK_METADATA in raw:
        # Marker je tam, ale JSON nedává smysl → rozbitý výstup agenta.
        # Tiše polykat by znamenalo ztratit otázky a nové termíny.
        meta = extract_json(sections.get("METADATA") or "")
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
