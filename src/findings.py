"""Stabilní identita nálezů (concordance/kritik/strukturální kontrola)
napříč `run`/`polish` běhy. Bez tohodle nejde uživateli dovolit ručně
"odškrtnout vyřešeno" - nálezy se dnes přegenerují od nuly při každém
běhu a nemají žádnou trvalou identitu."""
import uuid

_MARKER_TYPES = {("stylist", "polish"), ("stylist", "kept_original"),
                 ("stylist", "revert"), ("stylist", "unchanged")}   # "unchanged"
                 # kolo 9 IMPORTANT - main._unchanged_marker (Task 5), viz tamní
                 # docstring proč musí být marker, ne obyčejný nález


_STR_FIELDS = ("source", "type", "issue", "severity", "cz_excerpt", "suggestion")


def assign_ids(findings: list) -> list:
    """Doplní `id`/`resolved` KAŽDÉMU nálezu, co je ještě nemá - nikdy
    nepřepíše existující PLATNOU (str, neprázdnou, v týhle dávce
    UNIKÁTNÍ) hodnotu (idempotentní, bezpečné volat opakovaně na stejný
    seznam). Mutuje v místě a vrací stejný seznam.

    `f.get("id")` (ne `"id" in f`/`setdefault`) - kolo 3 IMPORTANT oprava:
    klient (Task 9 save endpoint) MŮŽE poslat `{"id": null, ...}`
    (validace v `_valid_finding_shape` `None` u `id` propouští, viz
    tamní docstring). `setdefault` by tenhle PŘÍTOMNÝ, ale prázdný klíč
    nepřepsalo - nález by zůstal s `id: None` navždy, nešel by nikdy
    znovu najít podle `id` (`set_resolved` by ho nikdy nenašlo, víc
    takových nálezů by si navzájem "kolidovalo" na stejné `None`).

    Kolo 23 IMPORTANT - `id` musí být PLATNÝ, ne jen PŘÍTOMNÝ. Dřívější
    `if not f.get("id"):` nechávalo TRUTHY, ale NE-STRING `id` (např.
    `id: 123`, celé číslo) beze změny - zdroj: `_valid_entries` (Task 13
    Step 8 migrace) filtruje jen NE-DICT položky, ne SHAPE `id` uvnitř
    dict. Takový nález by GET vrátil klientovi s `id: 123`, ale `POST
    /api/findings/resolve`/`save`'s vlastní validace (`isinstance(...,
    str)`) by ho pak NAVŽDY odmítla - trvalý, neopravitelný "mrtvý"
    nález v UI. Duplicitní `id` (dvě položky se STEJNÝM, jinak platným
    `id` v JEDNÉ dávce - taky možné z pre-Task-2 dat) měly STEJNÝ
    problém jiným směrem - `set_resolved`/`_merge_findings_by_id`
    předpokládají unikátnost, ale nic ji dřív nevynucovalo. Fix -
    `seen_ids` (lokální jen pro TUHLE dávku, NE globální napříč
    voláními - uniknost se vynucuje jen v rámci JEDNOHO seznamu nálezů,
    stejný rozsah jako `_no_duplicate_ids`) sleduje, co UŽ bylo v týhle
    dávce přiděleno - `id` je platné a ZACHOVÁ SE jen když je `str`,
    neprázdné, A ještě NEVIDĚNÉ v týhle dávce; jinak dostane nové `uuid4
    ().hex`.

    NORMALIZUJE i `source`/`type`/`issue`/`severity`/`cz_excerpt`/
    `suggestion` na `str` (kolo 5 IMPORTANT - `assign_ids` je JEDINÝ
    společný choke-point, přes který projdou VŠECHNY nálezy, ať z `run`u
    (kritik/concordance), `polish`u, nebo klientského save requestu.
    `critic._to_finding` (`src/agents/critic.py:45`) čte `issue` PŘÍMO
    z LLM JSON odpovědi (`raw.get("issue") or ""`) bez kontroly typu -
    model teoreticky MŮŽE vrátit `"issue": 123` (číslo). Bez normalizace
    TADY by takový nález prošel `assign_ids`/GET/reportem v pořádku
    (display-time `str()` coerce v `render_findings_html` by ho
    ustála), ale `POST /api/chapter/{idx}/save`'s `_valid_finding_shape`
    by ho odmítlo 400 - JAKMILE by editor GET kapitolu s tímhle nálezem
    a poslal ho zpátky (i beze změny), uživatel by NEMOHL uložit VŮBEC
    NIC na tý kapitole, dokud by se nálezu nezbavil. Normalizace TADY,
    hned při vzniku, zaručuje, že klient NIKDY nedostane nález v tvaru,
    co by sám neuměl zpátky uložit."""
    seen_ids = set()
    for f in findings:
        fid = f.get("id")
        if not isinstance(fid, str) or not fid or fid in seen_ids:
            fid = uuid.uuid4().hex
            f["id"] = fid
        seen_ids.add(fid)
        if "resolved" not in f or f["resolved"] is None:
            f["resolved"] = False
        for key in _STR_FIELDS:
            if key in f and f[key] is not None and not isinstance(f[key], str):
                f[key] = str(f[key])
    return findings


def set_resolved(findings: list, finding_id: str, resolved: bool) -> bool:
    """Najde nález podle `id` a přepíše `resolved`. Vrací, jestli se
    nález našel - volající (server endpoint) na `False` odpoví 404."""
    for f in findings:
        if f.get("id") == finding_id:
            f["resolved"] = resolved
            return True
    return False


def is_marker(finding: dict) -> bool:
    """Audit marker (`main._stylist_marker`/`_revert_marker`/
    `_unchanged_marker`, a historický `"kept_original"` typ ze staré,
    už odstraněné draft-fronty - viz `_MARKER_TYPES`) NENÍ nález k
    vyřešení - je to jen záznam "kdy/jak se text změnil", uživatel ho
    nemá zaškrtávat.

    Obranné `isinstance` (kolo 4 IMPORTANT) - `source`/`type` u nálezů z
    `_run_critic`/`concordance` nejsou nikde vynuceně `str` (jen `Task 9`
    save endpoint tohle validuje pro KLIENTSKÝ vstup, ne producenty jako
    kritik). Netypovaná hodnota (např. `source: []`) by jako prvek
    tuplu byla NEHASHOVATELNÁ - `in` na množině tuplů by spadlo na
    `TypeError` místo vrácení `False`."""
    source, type_ = finding.get("source"), finding.get("type")
    if not isinstance(source, str) or not isinstance(type_, str):
        return False
    return (source, type_) in _MARKER_TYPES


def count_unresolved(findings: list) -> int:
    return sum(1 for f in findings if not is_marker(f) and not f.get("resolved"))
