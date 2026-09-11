"""CLI překladače knih. Tenká vrstva: rozparsuj argumenty, zavolej modul, vypiš.

Fáze běhu:
    init kniha.epub    kniha → kapitoly do DB
    scan [--chunked]   scout projede knihu → guide.draft.json
    review             web UI: potvrdíš návod → guide.json (+ reseed glosáře)
    run [--retry-flagged [IDX...]]   překladová smyčka
    questions / answer QID "text"    dávkové otázky
    status / export [--only-done]

Mutující příkazy drží zámek v data/ - druhý běh se nespustí a nerozbije stav.
"""
import argparse
import datetime as _dt
import hashlib
import json
import os
import sqlite3
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from src import concordance, glossary
from src import guide as guide_mod
from src import ingest, pipeline, requeue, state
from src import reference as reference_mod
from src import reference_mine, textnorm
from src.agents import scout, stylist
from src.llm.client import AnthropicClient, FatalRunError, OutputTruncated, PipelineLLMClient

_MUTATING = {"init", "scan", "run", "answer", "review", "reference"}

_MARKERS = {"done": "OK", "pending": "..", "flagged": "!!", "needs_human": "??",
            "error": "XX", "processing": "~~"}


def _bootstrap_stdout() -> None:
    """Windows konzole je často cp1252 a český výstup by ji shodil."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def _client_factory(run_id: int, *, interactive: bool):
    """Klienta staví až při volání - `run` s fake pipeline nikdy nesáhne na API."""
    def factory(agent: str):
        return PipelineLLMClient(AnthropicClient(), run_id=run_id, agent=agent,
                                 db_path=config.DB_PATH, config_mod=config,
                                 interactive=interactive)
    return factory


def _print_usage(db_path: str, run_id: int) -> None:
    with state.connect(db_path) as conn:
        r = conn.execute(
            "SELECT COUNT(*) n, COALESCE(SUM(input_tokens),0) it, "
            "COALESCE(SUM(output_tokens),0) ot, COALESCE(SUM(cost_usd),0) c "
            "FROM llm_calls WHERE run_id = ?", (run_id,)).fetchone()
    _say(f"LLM volání: {r['n']}, vstup {r['it']} tok, výstup {r['ot']} tok, "
         f"cena ~${r['c']:.4f}")


def _say(msg: str) -> None:
    """Best-effort diagnostický výpis (kolo 35 IMPORTANT). Používá se
    pro VŠECHNY per-kapitolové hlášky v `_polish_one_chapter` i
    `_cmd_polish` smyčce - `print()` může vyhodit (`BrokenPipeError`,
    zavřený stdout), a to NESMÍ změnit `outcome` kapitoly ani stav běhu
    (zvlášť po úspěšném commitu). Výsledek běhu se řídí stavem DB a
    kontrolami, ne tím, jestli hláška dorazila na terminál."""
    try:
        print(msg)
    except Exception:
        pass


def _parse_findings(notes_json: str | None) -> list:
    """Bezpečné čtení `notes` jako seznamu nálezů - platný JSON, co NENÍ
    seznam (starší/cizí tvar `notes`), nebo úplně rozbitý JSON, dá prázdný
    seznam, ne pád (kolo 2 nález). Používá `_already_styled` (hledá stylist
    marker). Konkordanční baseline pro `_polish_rejected` se NEčte odsud -
    ta se počítá čerstvě přes `concordance.check_chapter` (kolo 4 IMPORTANT,
    viz `_polish_one_chapter`), aby neuvízla na starším glosáři."""
    try:
        findings = json.loads(notes_json or "[]")
    except ValueError:
        return []
    if not isinstance(findings, list):
        return []
    return [f for f in findings if isinstance(f, dict)]


def _already_styled(notes_json: str | None) -> bool:
    return any(f.get("source") == "stylist" for f in _parse_findings(notes_json))


def _stylist_marker(cz_before: str, model: str) -> dict:
    """Stejný tvar jako ostatní nálezy (concordance._finding) - kód, co
    `notes` čte jinde (review UI, budoucí nástroje), nesmí na neznámý tvar
    spadnout. `cz_before` se ukládá jen jako hash+délka, ne celý text -
    plná historie je záměrně mimo rozsah (viz spec výše). Celý SHA-256
    (ne zkrácený SHA-1), ne kvůli bezpečnosti proti útoku, ale prostě
    nemá to praktickou cenu zkracovat/slabší algoritmus (kolo 6 NIT)."""
    return {"source": "stylist", "type": "polish", "severity": "info",
            "action": "note", "term_id": None, "expected": None,
            "actual": None, "cz_excerpt": None,
            "issue": f"stylizováno přes Codex (model={model}), "
                    f"původní délka {len(cz_before)} znaků, hash "
                    f"{hashlib.sha256(cz_before.encode('utf-8')).hexdigest()}.",
            "suggestion": None}


def _finding_key(f: dict) -> tuple:
    """Klíč pro srovnání PŘED/PO u konkordančních nálezů - kolo 4 IMPORTANT:
    JEN `(type, term_id)` by netvrdilo, že se KONKRÉTNÍ špatná hodnota
    nezměnila na JINOU špatnou hodnotu (pořád "stejný" nález podle typu a
    termínu, ale fakticky jiný problém). `actual` je součástí klíče."""
    return (f.get("type"), f.get("term_id"), f.get("actual"))


def _rejection_reasons(baseline_concordance: list, after_findings: list,
                       cz_before: str, cz_after: str, glossary_rows: list) -> list:
    """Vrací SEZNAM nálezů, co odůvodňují zamítnutí stylizace (prázdný
    seznam = nezamítat). `_polish_rejected` je tenký bool wrapper nad
    tímhle - rozhodovací logika je JEDNA, tady. Volající
    (`_polish_one_chapter`) tenhle seznam LOGUJE do report souboru
    (kolo 27 - viz `_write_polish_report`), ať jde po v1 změřit nejen
    reject RATE, ale i DŮVODY (který ze tří kontrol, jaký typ nálezu).

    Srovnává konkordanci PROTI ČERSTVĚ PŘEPOČÍTANÉMU stavu PŘED stylizací
    (kolo 4 IMPORTANT - ne proti uloženým `notes`, které mohly zastarat
    vůči AKTUÁLNÍMU glosáři; volající spočítá `baseline_concordance` přes
    `concordance.check_chapter(en, cz, glossary_rows, rendered_terms)`
    těsně předtím, se STEJNÝM `glossary_rows` i `rendered_terms` jako pro
    `after_findings` - obě strany tak vždy měří proti stejným pravidlům.
    `rendered_terms` NENÍ prázdný seznam - kolo 10 IMPORTANT, opravuje
    zastaralý docstring: prázdný seznam by byl přesně ta slepá skvrna,
    co kolo 5 BLOCKING opravilo přes `state.chapter_mentions`, viz níže).
    Absolutní odmítání (bez baseline)
    by kapitolu s jakýmkoli, byť neškodným, pre-existujícím nálezem nikdy
    nešlo stylizovat (kolo 3 IMPORTANT).

    Tři pravidla, každé pro jiný zdroj nálezu:
    1. `meaning_drift`/`register_drift` (zdroj `stylist_check`) - odmítá
       VŽDY, když se objeví. `register_drift` přidán v kole 7 (tykání/
       vykání, hlas vypravěče) - deterministicky nové signály, PŘED
       stylizací nemohly existovat (ta kontrola PŘED tímhle během vůbec
       neexistovala).
    2. Kritikův nález s `action == "revise"` (`severity == "critical"`) -
       odmítá VŽDY. Kapitola má `status == "done"`, což už samo o sobě
       znamená, že v PŮVODNÍM stavu žádný takový nález neměla (jinak by
       `done` nebyla) - cokoli nové je tedy vždy NOVÉ zhoršení. Kritikovy
       `minor` nálezy (action=='note') se ignorují - subjektivní/stylové,
       to je přesně doména stylisty, ne důvod k zamítnutí.
    3. Konkordance (`leak`/`omission`/`inconsistency`) - deterministické,
       klíčované přes `_finding_key` (type, term_id, actual). Srovná se
       MNOŽINA těchto klíčů PŘED a PO - odmítá se jen kapitola, kde se
       objevil klíč, co v PŮVODNÍM stavu nebyl (skutečně NOVÝ nebo JINAK
       špatný problém), ne kapitola, která identický konkordanční nález
       měla furt.

       Kolo 16 navrhlo `Counter`-based srovnání POČTŮ nálezů, kolo 17-18
       ho vrátilo na množinu (`check_chapter()` sama dedupuje). Kolo 20-22
       ale ukázalo, že množina ani Counter-na-nálezech nezachytí regresi,
       kde stylista PŘIDÁ výskyt problému, co v baseline UŽ byl (stejný
       klíč). Proto DRUHÁ kontrola nad TEXTEM: pro každý PRE-EXISTUJÍCÍ
       `leak`/`inconsistency` nález se počítá výskyt zakázaných povrchů v
       `cz_before` vs. `cz_after` přes `find_form_occurrences`:
       - `inconsistency`: konkrétní chybný CZ tvar (`actual`);
       - `leak`: VŠECHNY zakázané EN povrchy termínu (canonical + aliasy,
         kolo 22 - ne jen `actual`=`leaked[0]`, jinak by nový leak JINÉHO
         aliasu prošel), ale JEN u termínů, co se mají překládat (keep-
         untranslated termín má EN povrch správně).
       Nárůst kteréhokoli → odmítnuto. `omission` (actual None, termín v
       textu vůbec chybí) tudy neprochází.

       VĚDOMĚ NEPŘIJATO (kolo 22 druhá půlka návrhu): "pokles počtu
       SCHVÁLENÝCH CZ forem → odmítnout". Pokles je nejednoznačný -
       legitimní stylistické sloučení dvou vět s opakovaným termínem
       ("Bílá rada rozhodla. Bílá rada pak..." → "Bílá rada rozhodla a
       pak...") sníží počet z 2 na 1 bez jakékoli regrese. Odmítat to by
       falešně blokovalo běžnou práci stylisty. Skutečná regrese
       "správný tvar → JINÝ CHYBNÝ CZ tvar" je pokrytá jinak: `check_
       chapter()` ten nový chybný tvar ohlásí jako NOVOU inconsistency
       (nový `cz_form` klíč → množinová kontrola výš), a pokud kolize s
       existujícím klíčem, chytne to `inconsistency`-větev počtu `actual`
       výš. Zbytkovou skulinu (nový chybný CZ tvar kolidující s
       existujícím klíčem A lišící se od `actual` A neviditelný pro
       kritika i meaning-check) hodnotím jako přijatelně úzkou proti ceně
       falešných zamítnutí.
    """
    reasons = []
    reasons += [f for f in after_findings
                if f.get("type") in ("meaning_drift", "register_drift")]
    reasons += [f for f in after_findings
                if f.get("source") == "critic" and f.get("action") == "revise"]
    baseline_keys = {_finding_key(f) for f in baseline_concordance}
    reasons += [f for f in after_findings
                if f.get("source") == "concordance"
                and _finding_key(f) not in baseline_keys]
    # Pre-existující leak/inconsistency, co PO stylizaci v textu PŘIBYL
    # (stejný klíč, `check_chapter()` ho dedupuje na jeden nález, takže
    # množina výš to nevidí). Kolo 20-22 IMPORTANT - výskyty se počítají
    # PŘES `concordance.find_form_occurrences` (ne `str.count` - kolo 21;
    # `find_form_occurrences` stemuje + lowercasuje obě strany STEJNĚ,
    # takže přidaný výskyt s jinou velikostí písmen / v jiném pádu se
    # zachytí; absolutní nepřesnost počtu nevadí, porovnává se relativní
    # rozdíl touž funkcí). Kolo 22 IMPORTANT rozšiřuje z "počet `actual`"
    # na "počet KTERÉHOKOLI zakázaného EN povrchu termínu" - nový leak
    # JINÉHO aliasu, když `actual` (= `leaked[0]`) zůstane stejný, by
    # jinak prošel.
    by_id = {t.get("term_id"): t for t in glossary_rows}
    # Dedup pro případ z kola 28 IMPORTANT: týž problém se může objevit
    # v NOVÝ-klíč větvi výš I v počet-výskytů větvi níž - report by pak
    # tutéž regresi započetl dvakrát. Kolo 31 IMPORTANT: dedup je
    # NA ÚROVNI KONKRÉTNÍHO POVRCHU (`_finding_key` = `(type, term_id,
    # actual)`), NE celého termínu - jinak by nový chybný povrch B
    # zamaskoval, že SOUČASNĚ narostl i výskyt povrchu A (report by ztratil
    # jednu ze skutečných příčin). Nekonkordanční důvody
    # (meaning/register drift, kritik) se NEdedupují - dva kritikovy
    # `fidelity` nálezy jsou dvě informace.
    seen_keys = {_finding_key(r) for r in reasons
                 if r.get("source") == "concordance"}
    for f in after_findings:
        if f.get("source") != "concordance":
            continue
        ftype = f.get("type")
        if ftype not in ("leak", "inconsistency"):
            continue
        tid = f.get("term_id")
        # inconsistency: sleduj konkrétní chybný CZ tvar (`actual`).
        surfaces = []
        if f.get("actual"):
            surfaces.append(f["actual"])
        # leak: sleduj VŠECHNY zakázané EN povrchy termínu (canonical +
        # aliasy), ne jen ohlášený `actual` - ale JEN u termínů, co se
        # SKUTEČNĚ mají překládat (keep-untranslated termín má EN povrch
        # SPRÁVNĚ, jeho přibývání není leak).
        if ftype == "leak":
            term = by_id.get(tid) or {}
            canonical = (term.get("canonical_en") or "").strip().lower()
            cz = (term.get("cz") or "").strip().lower()
            if canonical and cz != canonical:
                surfaces += [s for s in ([term.get("canonical_en", "")]
                             + list(term.get("aliases") or [])) if s]
        for s in set(surfaces):
            if (ftype, tid, s) in seen_keys:
                continue   # týž povrch už nahlášen (nový klíč / dřív tady)
            before_n = len(concordance.find_form_occurrences(cz_before, s))
            after_n = len(concordance.find_form_occurrences(cz_after, s))
            if after_n > before_n:
                reasons.append({
                    "source": "concordance", "type": ftype,
                    "severity": "critical", "action": "revise",
                    "term_id": tid, "expected": None,
                    "actual": s, "cz_excerpt": None, "suggestion": None,
                    "issue": (f"po stylizaci PŘIBYL výskyt zakázaného "
                              f"povrchu {s!r} ({before_n} -> {after_n})")})
                seen_keys.add((ftype, tid, s))
    return reasons


def _polish_rejected(baseline_concordance: list, after_findings: list,
                     cz_before: str, cz_after: str, glossary_rows: list) -> bool:
    """Tenký bool wrapper nad `_rejection_reasons` (kolo 27) - zpětně
    kompatibilní rozhodovací brána, aby existující volání/testy
    (`if _polish_rejected(...)`, "vrátí `True`/`False`") platily beze
    změny. Rozhodovací logika i její zdůvodnění jsou v `_rejection_
    reasons` výš."""
    return bool(_rejection_reasons(baseline_concordance, after_findings,
                                   cz_before, cz_after, glossary_rows))


def _snapshot_db(db: str, snapshot_path: str, *, timeout: float = 30.0) -> None:
    """Zapíše KONZISTENTNÍ snapshot DB do `snapshot_path` přes SQLite
    vlastní `Connection.backup()` API (kolo 14 IMPORTANT), NE `shutil.
    copy2` - prostý souborový copy může zachytit DB uprostřed cizího
    zápisu (nekonzistentní stav) a nezná WAL/SHM sidecar soubory, kdyby
    se žurnálovací režim někdy změnil (dnešní `state.connect()` žádný
    explicitní `journal_mode` nenastavuje, takže je to teoretická, ne
    aktuální hrozba - `backup()` ji ale řeší úplně obecně, bez ohledu na
    to). `PRAGMA integrity_check` na výsledku navíc ověří, že samotný
    backup proběhl kompletně (přerušení uprostřed by jinak dalo tiše
    existující, ale poškozený soubor).

    `timeout` (kolo 15 IMPORTANT) - `backup()` samo o sobě NEMÁ žádný
    časový limit; při dlouhodobě zamčené DB (jiný proces drží zámek,
    extrémně pomalý disk - síťové úložiště, antivirus) by mohlo viset
    NEOMEZENĚ. `progress` callback (SQLite ho volá po každé zkopírované
    dávce stránek) hlídá uplynulý čas a po `timeout` sekundách vyhodí
    `TimeoutError`, kterou `backup()` propaguje ven místo dalšího čekání.

    `pages=100` (kolo 16 IMPORTANT, opravuje kolo 15) - BEZ tohohle by
    `backup()` použilo výchozí `pages=-1`, co zkopíruje CELOU DB v JEDNOM
    kroku - `progress` callback by se zavolal nejvýš JEDNOU, těsně před
    návratem, tedy AŽ PO dokončení kopírování. Deadline kontrola uvnitř
    by tak nikdy nestihla zasáhnout UPROSTŘED pomalého/zaseknutého
    kopírování - byla by čistě kosmetická, ne skutečný časový limit.
    S omezeným `pages` proběhne VÍC kroků, `progress` se zavolá mezi
    každým z nich, a deadline tak má reálnou šanci kopírování přerušit."""
    deadline = time.monotonic() + timeout

    def _check_deadline(status, remaining, total):
        if time.monotonic() > deadline:
            raise TimeoutError(
                f"Snapshot DB přesáhl časový limit ({timeout}s) - "
                f"zbývá {remaining}/{total} stránek, DB je pravděpodobně "
                "dlouhodobě zamčená jiným procesem.")

    src = sqlite3.connect(db)
    try:
        dst = sqlite3.connect(snapshot_path)
        try:
            src.backup(dst, pages=100, progress=_check_deadline)
        finally:
            dst.close()
    finally:
        src.close()
    check = sqlite3.connect(snapshot_path)
    try:
        row = check.execute("PRAGMA integrity_check").fetchone()
        if row is None or row[0] != "ok":
            raise OSError(f"Snapshot DB neprošel integrity_check: {row}")
    finally:
        check.close()


def _backup_db_once(db: str, backup_state: dict) -> None:
    """Promuje PŘEDEM pořízený snapshot (viz `_cmd_polish` - vzniká PŘED
    `state.create_run`) na kanonickou zálohu `db + ".pre-polish-backup"`,
    ale jen JEDNOU za běh, těsně PŘED prvním skutečným zápisem výsledku
    (kolo 8 IMPORTANT, časování zpřesněné kolo 9 BLOCKING).

    Kolo 9 BLOCKING: `state.create_run` zapisuje řádek do `runs` a
    kritik/`check_meaning_preserved` volané uvnitř `_polish_one_chapter`
    logují přes `record_llm_call` I PRO KAPITOLY, co skončí
    'rejected'/'failed' - tedy PŘED prvním `commit_chapter_result`. Kdyby
    se DB kopírovala až TADY (jak to dělalo kolo 8), "záloha" by už nesla
    tohohle běhu vlastní bookkeeping (řádek `runs` + `llm_calls` z
    zamítnutých pokusů), ne skutečný stav PŘED spuštěním `polish`. Proto
    se skutečná kopie dat dělá dřív (snapshot v `_cmd_polish`, PŘED
    `create_run`) a tahle funkce jen PROMUJE už hotový snapshot na
    kanonickou cestu - `os.replace` je atomické přejmenování na úrovni
    souborového systému, ne stream kopie, takže staré `.pre-polish-backup`
    (pokud existovalo) zmizí v okamžiku přejmenování a nikdy není vidět
    částečně přepsané (kolo 9 IMPORTANT - `shutil.copy2` by ho přepisoval
    postupně, pád/plný disk uprostřed by starou zálohu poškodil).

    Obnova (mimo běžící `main.py` - DB nesmí mít otevřené spojení, což
    zaručí zastavený `main.py`; ruční zásah do DAT, žádoucí kandidát na
    vlastní zamykání/testovanou příkazovou obálku je mimo rozsah týhle
    spec, viz "Mimo rozsah" výš): NE přímý `shutil.copy2(db +
    ".pre-polish-backup", db)` na AKTIVNÍ cestu (kolo 11 IMPORTANT) -
    stejné riziko částečného zápisu jako u vytváření zálohy výš, jen by
    teď poškodilo přímo `db`, ne zálohu. Bezpečný postup: zkopírovat
    zálohu do DOČASNÉHO souboru ve STEJNÉM adresáři jako `db` (`shutil.
    copy2(backup_path, db + ".restore-tmp")`), ověřit integritu
    (`sqlite3.connect(tmp_path).execute("PRAGMA integrity_check").
    fetchone() == ("ok",)`), a teprve pak `os.replace(tmp_path, db)` -
    atomické přejmenování, stejný princip jako promoce zálohy výš.
    Sidecar soubory (`db + "-wal"`, `db + "-shm"`, `db + "-journal"`) se
    mažou AŽ PO úspěšném `os.replace`, ne před ním (kolo 16 IMPORTANT,
    opravuje kolo 15 - mazání PŘED přejmenováním otvíralo okno, kdy by
    pád uprostřed mohl připravit AKTUÁLNÍ (ještě nenahrazenou) `db` o
    její VLASTNÍ potřebný `-journal`). Po `os.replace` je smazání
    sidecarů BEZPEČNOSTNĚ NUTNÝ krok (kolo 22 NIT - ne "kosmetický"):
    starý `-journal`/`-wal` vázaný ke jménu `db` by SQLite při příštím
    otevření mohl aplikovat na ČERSTVĚ obnovený soubor a změnit nebo
    poškodit ho (viz "ZBÝVAJÍCÍ NEVYŘEŠENÉ RIZIKO" níž - právě proto
    recept žádá i druhý `integrity_check` na finálním `db`). Dnešní `state.connect()` WAL nepoužívá
    (viz `_snapshot_db` docstring), ale ROLLBACK journal (`-journal`)
    ano - tenhle recept je vědomě jen dokumentovaný ruční postup pro
    disaster recovery (main.py musí být zastavené), ne testovaná,
    zamykaná příkazová obálka - plná automatizace obnovy je mimo rozsah
    týhle spec o stylistickém průchodu.

    ZBÝVAJÍCÍ NEVYŘEŠENÉ RIZIKO (kolo 17 IMPORTANT, přijato jako
    zdokumentovaná mezera, ne dořešeno): i "po `os.replace`" pořadí má
    svoje vlastní úzké okno - pád PO úspěšném `os.replace`, ale PŘED
    smazáním starého sidecaru, nechá STARÝ (ke jménu `db`, ne k jeho
    novému OBSAHU patřící) `-journal`/`-wal` ležet vedle ČERSTVĚ
    obnoveného souboru. SQLite si sice hot journal ověřuje proti
    change-counteru hlavního souboru před tím, než by ho aplikovalo (v
    téhle relaci NEOVĚŘENO s jistotou přes dokumentaci - jen obecně
    známá vlastnost formátu), takže nesedící journal by měl být
    rozpoznán jako neplatný a zahozen, ne slepě aplikovaný - ale bez
    přímého ověření tuhle záruku nelze brát jako jistotu. Praktická
    obrana, co recept PŘIDÁVÁ (žádný nový kód, jen další krok ručního
    postupu): PO dokončení `os.replace` i úklidu sidecarů otevřít
    obnovenou `db` ČERSTVÝM spojením a spustit `PRAGMA integrity_check`
    znovu (ne jen na `tmp_path` PŘED přejmenováním, ale i na FINÁLNÍM
    `db` PO něm) - odhalí případné poškození z tohohle okna dřív, než se
    člověk spolehne na "obnova proběhla"."""
    if backup_state["done"]:
        return
    backup_path = db + ".pre-polish-backup"
    os.replace(backup_state["snapshot_path"], backup_path)
    # `done = True` HNED po `os.replace` (kolo 36 IMPORTANT), PŘED
    # diagnostickým výpisem - jinak by `BrokenPipeError` z `print`
    # udělal z úspěšné promoce `FatalRunError` a `_polish_one_chapter` by
    # commit vůbec nezkusil. `_say` je navíc nevyhazující.
    backup_state["done"] = True
    _say(f"Záloha DB (stav před tímto během `polish`): {backup_path}")


_REPORT_SCHEMA_VERSION = 1


_REPORT_OUTCOMES = ("polished", "unchanged", "rejected", "failed", "fatal",
                    "interrupted")


def _write_polish_report(db: str, rid: int, report: list, *, codex_model: str,
                         planned_count: int, batch_completed: bool,
                         run_status: str, run_error: "str | None" = None,
                         finalization_error: "str | None" = None) -> None:
    """JSON report běhu `polish` - VEDLE DB (soubor), NE do DB (žádná
    změna schématu). Kolo 27-28: vědomá revize kola-1 "jen konzole".
    Smysl v1 je ZMĚŘIT, jestli stylista funguje.

    Volá se z `finally` v `_cmd_polish` VŽDY, když existuje `rid` (kolo
    28 - i běh, co po `create_run` spadl PŘED první kapitolou, je data:
    "spustil se, neudělal nic"). `if not report` se NEkontroluje.

    Kontrakt záznamu kapitoly - viz `_polish_one_chapter` docstring.
    Klíčové: `rejected` nese `reason_types` VŽDY (deduplikované
    `"src/type"` řetězce, bezpečná agregační metrika); `reasons`/
    `findings`/`styled` jen za `config.STYLIST_REPORT_REJECTED_TEXT`.
    `failed` nese jen `error`.

    Hlavička (kompletní výčet):
      - `schema_version`, `run_id`, `generated_at` (ISO čas zápisu)
      - `codex_model` - SKUTEČNĚ použitý model (kolo 30: předává ho
        `_cmd_polish` jako `codex_model=model`, ne re-read `config.
        CODEX_MODEL` - auditní údaj svázaný s během). Codex volání NENÍ v
        `llm_calls`, bez modelu nejde reject rate porovnat mezi
        konfiguracemi.
      - `planned_count` (kolik kapitol se mělo zpracovat),
        `attempted_count` (= `len(report)`), `batch_completed` (smyčka
        prošla VŠECHNY kapitoly - kolo 28 IMPORTANT: samostatný příznak,
        NE odvozený z `run_status`; dávka, kde všechny kapitoly `failed`,
        DOběhla celá, i když `run_status="fatal"`)
      - `run_status` ("ok"/"fatal"/"interrupted"), `run_error` (hláška
        top-level výjimky, když běh spadl mimo per-kapitolovou smyčku),
        `finalization_error` (když `state.finish_run` selhal - kolo 28:
        report se píše AŽ PO `finish_run`, aby tohle mohl zaznamenat)
      - `summary` - dict s počty pro každý outcome v `_REPORT_OUTCOMES`
        (polished/unchanged/rejected/failed/fatal/interrupted)

    `polish-reports/run-<rid>-<timestamp>-<8 hex>.json` - jeden soubor za běh,
    historie zůstává. Atomický zápis (tmp + `os.replace`).

    Best-effort: CELÉ sestavení i zápis v `except Exception` (ne jen
    `OSError` - `json.dump` neserializovatelné hodnoty hodí `TypeError`;
    volá se z `finally`, nová výjimka by přebila skutečný výsledek).
    Selhání jen VYPÍŠE a uklidí `.tmp`.

    BEZPEČNOST (kolo 27-32): s `config.STYLIST_REPORT_REJECTED_TEXT is
    True` report u `rejected` PERZISTENTNĚ ukládá zamítnutý text od
    Codexu + volná pole nálezů (`issue`, `cz_excerpt`, ...), co můžou
    nést exfiltrovaný obsah (dřív se po zamítnutí zahodilo). To je
    SAMOSTATNÉ riziko (trvalá perzistence potenciálně exfiltrovaného
    obsahu, navíc do často synchronizované složky) - NENÍ pokryté
    přijetím `STYLIST_ACCEPT_FS_RISK` (to je jen o čtení disku BĚHEM
    běhu), proto SAMOSTATNÝ explicitní opt-in (kolo 31 IMPORTANT). DEFAULT
    je `False` → záznam `rejected` nese JEN `reason_types` (normalizované
    kategorie, žádný volný text), per-kapitolový konzolový výpis vynechá
    `issue` řádky, a `polish()` nepřipojí Codex stderr do `StylistError`.
    Kontrola `is True` (kolo 32) - `1`/`"False"`/`None` plný detail
    NEaktivují. Retence/práva souborů `polish-reports/` jsou na uživateli."""
    tmp = None
    try:
        now = _dt.datetime.now(_dt.timezone.utc).astimezone()
        payload = {
            "schema_version": _REPORT_SCHEMA_VERSION,
            "run_id": rid,
            "codex_model": codex_model,
            "generated_at": now.isoformat(),   # timezone-aware ISO 8601 (kolo 34)
            "planned_count": planned_count,
            "attempted_count": len(report),
            "batch_completed": batch_completed,
            "run_status": run_status,
            "run_error": run_error,
            "finalization_error": finalization_error,
            "summary": {k: sum(1 for rec in report if rec.get("outcome") == k)
                        for k in _REPORT_OUTCOMES},
            "chapters": report,
        }
        out_dir = os.path.join(os.path.dirname(db) or ".", "polish-reports")
        os.makedirs(out_dir, exist_ok=True)
        # `run-<rid>-<čas>-<8 hex>.json` - `rid` je unikátní sám o sobě
        # (autoincrement), časové razítko a náhodný suffix (kolo 34 NIT)
        # jen kdyby se `_write_polish_report` volalo pro týž run vícekrát.
        stamp = now.strftime("%Y%m%d-%H%M%S")
        path = os.path.join(out_dir,
                            f"run-{rid}-{stamp}-{os.urandom(4).hex()}.json")
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
        _say(f"Report běhu: {path}")
    except Exception as e:
        # `_say` (nevyhazující, kolo 36 IMPORTANT) - `_write_polish_
        # report` se volá z `finally`, výjimka z `print` v tomhle
        # `except` by unikla ven a přebila skutečný výsledek běhu.
        _say(f"POZOR: zápis reportu selhal ({type(e).__name__}: {e}) - "
             "výsledek běhu výš je platný, chybí jen diagnostický soubor.")
        if tmp:
            try:
                os.remove(tmp)
            except OSError:
                pass


def _polish_one_chapter(c, glossary_rows, cf, db, model: str, guide_block: str,
                        codex_cmd: list, backup_state: dict) -> dict:
    """Vrací JEDEN report `dict` za kapitolu. Výjimky
    NEchytá (kromě `stylist.StylistError` → `"failed"` a záloha/DB zápisu
    → `FatalRunError`, viz níže) - volající (_cmd_polish) rozhoduje, co je
    per-kapitolové (chytit, pokračovat) a co ukončuje celý běh
    (FatalRunError).

    NÁVRATOVÁ HODNOTA (kolo 34 IMPORTANT - dřív funkce mutovala sdílený
    `report`, což vedlo k dvojím/chybějícím záznamům při výjimce z
    `print()` apod.): vrací PRÁVĚ JEDEN `dict` záznam za kapitolu.
    NEMUTUJE `report` - `_cmd_polish` appendne PRÁVĚ JEDNOU ZA ITERACI
    smyčky (JEDEN `try/except/finally`, append ve `finally` - `rec` se
    tam dopočítá z DB, když ho žádná větev nesestavila; invariant je
    STRUKTURNÍ, ne dohlídaný dedupem). Tvary:
      - `{"idx", "outcome": "polished"|"unchanged"}`
      - `{"idx", "outcome": "failed", "error": <hláška>}` - `error` z
        `stylist.StylistError` je už u zdroje (`polish()`) zbavená
        Codexem-řízených hodnot, když `STYLIST_REPORT_REJECTED_TEXT`
        není `True` (kolo 29-33).
      - `{"idx", "outcome": "rejected", "reason_types": [...]}` +
        (za `STYLIST_REPORT_REJECTED_TEXT is True`) `reasons`/`findings`/
        `styled`.
    `FatalRunError` (selhání commitu, NEBO fatální chyba klienta z kritika
    / meaning-checku - kolo 37) se NEobaluje do záznamu tady - propaguje
    ven a `_cmd_polish` si `fatal` záznam postaví sám (zná `c`). Hláška
    je VŽDY REDIGOVANÁ U ZDROJE (`stylist._redact_detail`, kolo 35/37).
    `KeyboardInterrupt` taky propaguje - `_cmd_polish` po něm porovná
    `translated_text` kapitoly v DB se vstupním `c` (kolo 35 - NE marker,
    ten je u `--force` z dřívějšího běhu) a zapíše `polished` nebo
    `interrupted`.

    `codex_cmd` je JIŽ rozřešený (`_cmd_polish` ho spočítal jednou v
    preflightu) - `stylist.polish` ho díky tomu nemusí znovu hledat přes
    `shutil.which` na každou kapitolu (kolo 8 NIT)."""
    idx, en, cz = c["idx"], c["raw_text"], c["translated_text"]
    try:
        styled = stylist.polish(en, cz, codex_cmd=codex_cmd, codex_model=model,
                                guide_block=guide_block,
                                timeout=config.STYLIST_TIMEOUT_SECONDS)
    except stylist.StylistError as e:
        _say(f"Kapitola {idx}: stylista selhal ({e}), ponechávám původní.")
        return {"idx": idx, "outcome": "failed", "error": str(e)}

    if styled == cz:
        _say(f"Kapitola {idx}: beze změny (Codex nenavrhl žádnou úpravu).")
        return {"idx": idx, "outcome": "unchanged"}

    # Předchozí mentions JAKO rendered_terms (kolo 5 BLOCKING) - termín
    # zachycený translatorem VÝHRADNĚ přes vlastní hlášení (žádná přesná EN
    # shoda povrchu) by se s rendered_terms=[] vůbec neprozkoumal, ani v
    # baseline, ani v `after` - úplná slepá skvrna, ne jen ztráta metadat
    # (viz "Oprava mimo nový modul: src/state.py" výše). `_term_mentions`
    # ověřuje `form in cz_text`/`form in styled` samo - stará forma, co ve
    # stylizovaném textu už není, se prostě neuplatní (correctly).
    #
    # JEN `source == "rendered"` (kolo 20 IMPORTANT) - `concordance._term_
    # mentions` označí VŠECHNO z `rendered_terms` jako "rendered". Kdyby
    # sem prošla i původně "detected" mention (zachycená kódem, ne
    # hlášená translatorem), po úspěšném průchodu by se uložila jako
    # "rendered" - falešná provenience. "detected" termíny concordance
    # najde sama z EN/glosáře, forwardovat je netřeba - forwarduje se jen
    # to, co concordance sama z povrchu NEDOHLEDÁ (skutečné translatorovo
    # hlášení).
    prior = state.chapter_mentions(db, idx)
    rendered_terms = [{"term_id": m["term_id"], "cz_as_used": m["cz_form"],
                       "scene_idx": m["scene_idx"]}
                      for m in prior
                      if m.get("cz_form") and m.get("source") == "rendered"]

    # Baseline se počítá ČERSTVĚ nad PŮVODNÍM cz, se STEJNÝM (aktuálním)
    # glossary_rows jako `findings` níže - ne z uložených `notes`, které
    # mohly vzniknout pod STARŠÍM glosářem (kolo 4 IMPORTANT). Zdarma
    # (žádné LLM volání), takže dvojí přepočet nic nestojí navíc.
    baseline_concordance = concordance.check_chapter(en, cz, glossary_rows, rendered_terms)
    findings = concordance.check_chapter(en, styled, glossary_rows, rendered_terms)
    # Kolo 9 NIT: `check_meaning_preserved` je DALŠÍ placené volání
    # (Anthropic request) - když konkordance nebo kritik SAMY o sobě
    # zamítnutí už zaručují, nemá smysl za něj platit. `_rejection_
    # reasons` se volá DVAKRÁT (žádná duplicitní rozhodovací logika, jen
    # fail-fast dřív). Kolo 27: bereme SEZNAM důvodů (ne jen bool).
    #
    # Kolo 37 IMPORTANT: `pipeline._run_critic` i `check_meaning_
    # preserved` volají Anthropic klienta S TEXTEM `styled`; klientův
    # `FatalRunError` (400, cost guard) může do hlášky pojmout část
    # requestu = obsah `styled`. Proto se `FatalRunError` z týhle sekce
    # zabalí s hláškou REDIGOVANOU U ZDROJE (`stylist._redact_detail`) -
    # `str(fe)` je pak bezpečné v `fatal` záznamu, `run_error` i výpisu
    # (stejný princip jako commitová `FatalRunError`, kolo 35).
    try:
        critic_findings, critic_failed = pipeline._run_critic(en, styled, cf("critic"))
        findings += critic_findings
        reasons = _rejection_reasons(baseline_concordance, findings, cz, styled, glossary_rows)
        if critic_failed:
            reasons = [{"source": "critic", "type": "critic_failed",
                        "severity": "critical", "action": "revise", "term_id": None,
                        "expected": None, "actual": None, "cz_excerpt": None,
                        "suggestion": None,
                        "issue": "kritik nevrátil platnou odpověď ani po retry "
                                 "- bereme jako selhání kontroly"}] + reasons
        if not reasons:
            findings += stylist.check_meaning_preserved(cz, styled, cf("stylist_check"))
            reasons = _rejection_reasons(baseline_concordance, findings, cz, styled, glossary_rows)
    except FatalRunError as fe:
        raise FatalRunError(
            f"Kontrola stylizace kapitoly {idx} selhala fatálně "
            f"({stylist._redact_detail(str(fe))}) - cost guard / chyba LLM "
            "klienta, celý běh `polish` se zastavuje.") from fe
    if reasons:
        # `reason_types` = deduplikovaný seznam `"source/type"` řetězců.
        # Tohle je BEZPEČNÁ agregační metrika (kolo 28 IMPORTANT) - žádný
        # volný text, jde do reportu VŽDY. Volná pole (`issue`,
        # `cz_excerpt`, celý `styled`) jdou jen za `STYLIST_REPORT_
        # REJECTED_TEXT` (kolo 28 - i `issue`/`cz_excerpt` můžou
        # zopakovat exfiltrovaný úryvek, ne jen `styled`).
        reason_types = sorted({f"{r.get('source', '?')}/{r.get('type', '?')}"
                               for r in reasons})
        # `is True` (kolo 32) - `1`/`"False"`/`None` NEsmí plný detail
        # (perzistence potenciálně exfiltrovaného textu) aktivovat.
        full = config.STYLIST_REPORT_REJECTED_TEXT is True
        _say(f"Kapitola {idx}: stylizace zamítnuta kontrolou "
             f"({', '.join(reason_types)}), ponechávám původní.")
        if full:
            for r in reasons:
                _say(f"    - [{r.get('source', '?')}/{r.get('type', '?')}] "
                     f"{r.get('issue') or '(bez popisu)'}")
        rec = {"idx": idx, "outcome": "rejected", "reason_types": reason_types}
        if full:
            rec["reasons"] = reasons
            rec["findings"] = findings
            rec["styled"] = styled
        return rec

    findings.append(_stylist_marker(cz, model))
    # Mentions se přepočítají se STEJNÝM rendered_terms jako `findings`
    # výš - termín rozpoznaný translatorem se tak dál vede jako "rendered"
    # (ne "detected"), pokud jeho hlášená forma ve stylizovaném textu pořád
    # je (kolo 5 BLOCKING, opravuje dřívější `rendered_terms=[]`).
    mentions = concordance.build_mentions(en, styled, glossary_rows, rendered_terms)
    # Kolo 12 IMPORTANT: záloha/DB zápis NENÍ per-kapitolová chyba, je to
    # INFRASTRUKTURNÍ selhání (plný disk, poškozená DB, ztráta práv) - může
    # ohrozit CELÝ běh, ne jen tuhle kapitolu. Bez tohohle zabalení by ho
    # vnější `except Exception` v `_cmd_polish` spolykal jako obyčejné
    # `outcome="failed"` téhle jedné kapitoly, a pokud by JINÁ kapitola v
    # téže dávce dopadla "unchanged"/"rejected" (žádná další nedopadla
    # `failed`), celý běh by mohl skončit `status="ok"` navzdory reálně
    # rozbité DB/disku - přesně tenhle rozpor `_cmd_polish` už jednou řešil
    # pro "všechno selhalo" (kolo 5), tady jde o STEJNÝ princip na jiném
    # místě. `FatalRunError` `_cmd_polish` NEchytá per-kapitolově (`except
    # FatalRunError: raise` stojí NAD obecným `except Exception`).
    try:
        _backup_db_once(db, backup_state)   # PŘED prvním skutečným zápisem - viz _backup_db_once
        state.commit_chapter_result(
            db, idx, translated_text=styled, revision_rounds=c["revision_rounds"],
            notes_json=json.dumps(findings, ensure_ascii=False), status="done",
            new_candidates=[], mentions=mentions, questions=[])
    except Exception as e:
        # `FatalRunError` propaguje ven, `_cmd_polish` si `fatal` záznam
        # postaví sám (kolo 34). Hláška je REDIGOVANÁ U ZDROJE (kolo 35
        # IMPORTANT) přes `stylist._redact_detail` - `str(e)` commitové
        # výjimky může nést data; `str(fe)` pak jde do `fatal` záznamu,
        # `run_error` I `_say(e)` výpisu bez dalšího řešení.
        raise FatalRunError(
            f"Zápis výsledku kapitoly {idx} selhal "
            f"({stylist._redact_detail(f'{type(e).__name__}: {e}')}) - "
            "záloha/DB zápis je infrastrukturní selhání, ne per-kapitolová "
            "chyba, celý běh `polish` se zastavuje.") from e
    _say(f"Kapitola {idx}: vylepšeno.")
    return {"idx": idx, "outcome": "polished"}


# --- příkazy ----------------------------------------------------------------

def _cmd_init(args) -> int:
    db = config.DB_PATH
    if not state.is_db_empty(db) and not args.reset:
        print("DB už obsahuje knihu. Použij `init --reset` pro nahrazení.")
        return 1
    if args.reset:
        state.reset_book(db)
    chapters = ingest.load_book(args.path)
    state.seed_chapters(db, chapters)
    print(f"Načteno kapitol: {len(chapters)}")
    return 0


def _cmd_scan(args) -> int:
    db = config.DB_PATH
    state.recover_processing(db)
    rid = state.create_run(db, "scan")
    status = "fatal"
    try:
        chs = state.chapters_by_status(
            db, ("pending", "processing", "done", "flagged", "needs_human", "error"))
        if not chs:
            raise FatalRunError("Žádné kapitoly - nejdřív `init`.")
        # scan je neinteraktivní: jedno velké volání, cost guard tvrdě zastaví
        cf = _client_factory(rid, interactive=False)
        try:
            if args.chunked:
                chunks = scout.chunk_chapters(chs, config.SCOUT_CHUNK_WORD_LIMIT)
                result = scout.scan_chunks(chunks, cf("scout"))
            else:
                text = "\n\n".join(c["raw_text"] for c in chs)
                result = scout.scan_book(text, cf("scout"))
        except (OutputTruncated, ValueError) as e:
            raw = getattr(e, "raw", "")
            if raw:
                # Bez surového výstupu je další pokus slepý; do gitu se nedostane.
                dump = os.path.join(config.DATA_DIR, "scout_raw_last.txt")
                with open(dump, "w", encoding="utf-8") as f:
                    f.write(raw)
                print(f"Surový výstup scouta uložen: {dump}")
            raise FatalRunError(
                f"Scout výstup je neúplný/rozbitý ({e}). Zkus `scan --chunked` "
                "nebo zvyš MAX_TOKENS_SCOUT v config.py.")
        guide_mod.save_draft(config.GUIDE_DRAFT_PATH, result)
        print(f"Draft návodu uložen: {config.GUIDE_DRAFT_PATH}")
        print("Dál: `python main.py review`")
        status = "ok"
        return 0
    except FatalRunError as e:
        print(e)
        return 1
    except KeyboardInterrupt:
        status = "interrupted"
        raise
    finally:
        state.finish_run(db, rid, status)


def _cmd_reference(args) -> int:
    db = config.DB_PATH
    root = args.dir or config.REFERENCE_DIR
    rid = state.create_run(db, "reference")
    status = "fatal"
    try:
        if not root:
            raise FatalRunError("Chybí cesta k referencím - použij `--dir CESTA` "
                                "nebo nastav REFERENCE_DIR v config.py.")
        if not os.path.exists(config.GUIDE_DRAFT_PATH):
            raise FatalRunError(
                f"Chybí {config.GUIDE_DRAFT_PATH} - nejdřív spusť `scan`.")
        try:
            draft = guide_mod.load_draft(config.GUIDE_DRAFT_PATH)
        except (OSError, ValueError) as e:
            raise FatalRunError(
                f"{config.GUIDE_DRAFT_PATH} se nepodařilo načíst ({type(e).__name__}: {e}).")

        corpus = None if args.refresh_cache else reference_mod.load_cache(
            config.REFERENCE_CACHE_PATH, root)
        if corpus is None:
            print("Načítám referenční korpus (~30 s)...")
            try:
                corpus = reference_mod.load_corpus(root)
            except ValueError as e:
                raise FatalRunError(str(e))
            except OSError as e:
                raise FatalRunError(f"Referenční korpus se nepodařilo načíst: {e}")
            try:
                reference_mod.save_cache(corpus, config.REFERENCE_CACHE_PATH)
            except OSError as e:
                # Cache je jen zrychlení příštího běhu - selhání zápisu
                # nesmí shodit těžbu, která už proběhla.
                print(f"reference: cache se nepodařilo uložit ({e}), pokračuji bez ní")

        items = []
        for section, key in (("characters", "name_en"), ("places", "name_en"),
                             ("terms", "term_en")):
            for it in draft.get(section) or []:
                surface = (it.get(key) or "").strip()
                if not surface:
                    continue
                items.append({"id": f"{section}/{textnorm.normalize_key(surface)}",
                              "section": section, "surface": surface,
                              "aliases": list(it.get("aliases") or []),
                              "note": it.get("note") or ""})

        cf = _client_factory(rid, interactive=False)
        try:
            # resolve() i write_reference() jsou v JEDNOM try/except: selže-li
            # cokoli mezi voláním modelu a dokončením zápisu (i samotný zápis,
            # např. disk plný), jde o stejnou situaci - těžba neproběhla a
            # předchozí reference.json (write_reference ho nahrazuje jen na
            # úplný konec přes os.replace) zůstává nedotčený.
            findings = reference_mine.resolve(corpus, items, cf, config)
            # manifest_fingerprint(corpus.manifest), NE corpus_fingerprint(root) -
            # to druhé by po těžbě (může trvat minuty kvůli modelu) přečetlo
            # AKTUÁLNÍ stav disku, ne ten, ze kterého nálezy skutečně vzešly.
            fingerprint = {
                "draft": reference_mine.draft_fingerprint(draft),
                "corpus": reference_mine.manifest_fingerprint(corpus.manifest),
                "thresholds": reference_mine.thresholds_fingerprint(config)}
            reference_mine.write_reference(findings, config.REFERENCE_PATH, rid,
                                           fingerprint, corpus.source_root)
        except FatalRunError:
            raise
        except Exception as e:
            raise FatalRunError(
                f"Těžba selhala ({type(e).__name__}: {e}). Předchozí "
                f"{config.REFERENCE_PATH} zůstal beze změny, spusť znovu.")

        counts = {}
        for f in findings:
            counts[f["classification"]] = counts.get(f["classification"], 0) + 1
        print(f"Vytěženo do {config.REFERENCE_PATH}:")
        for name in ("confirmed", "weak", "evidence_only", "proposed",
                     "not_attested", "unresolved"):
            print(f"   {name:<15} {counts.get(name, 0)}")
        _print_usage(db, rid)
        print("Dál: `python main.py review`")
        status = "ok"
        return 0
    except FatalRunError as e:
        print(e)
        return 1
    except KeyboardInterrupt:
        status = "interrupted"
        raise
    finally:
        state.finish_run(db, rid, status)


def _cmd_review(args) -> int:
    from src import glossary
    from src.review_ui import server
    rc = server.run_review_server(config.GUIDE_DRAFT_PATH, config.GUIDE_PATH,
                                  reference_path=config.REFERENCE_PATH)
    if rc != 0:
        print("Návod nebyl uložen - glosář zůstává beze změny.")
        return rc
    # Reseed dělá CLI, ne UI - UI o DB nic neví (izolace modulů).
    conflicts = glossary.seed_from_guide(config.DB_PATH,
                                         guide_mod.load_guide(config.GUIDE_PATH))
    for c in conflicts:
        print(f"KONFLIKT: {c['incoming']!r} je alias položky "
              f"{c['existing_canonical']!r} - nic jsem nepřepsal, rozhodni ručně.")
    print("Návod uložen, glosář naseedován. Dál: `python main.py run`")
    return 0


def _cmd_run(args) -> int:
    db = config.DB_PATH
    state.recover_processing(db)
    if args.retry_flagged is not None:
        n = state.retry_flagged(db, args.retry_flagged or None)
        print(f"Vráceno do fronty (flagged → pending): {n}")
    rid = state.create_run(db, "run")
    status = "fatal"
    try:
        g = guide_mod.load_guide(config.GUIDE_PATH)
        cf = _client_factory(rid, interactive=True)
        queue = state.queue_for_run(db)
        if args.only:
            # Pilot: přelož jen vyjmenované kapitoly, zbytek nech ve frontě.
            wanted = set(args.only)
            queue = [c for c in queue if c["idx"] in wanted]
            chybi = sorted(wanted - {c["idx"] for c in queue})
            if chybi:
                print("Přeskočeno (nejsou ve frontě - už hotové, flagged nebo "
                      "needs_human): " + ", ".join(str(i) for i in chybi))
        for ch in queue:
            try:
                summary = pipeline.process_chapter(db, ch, client_factory=cf, guide=g)
            except FatalRunError:
                raise                      # celý běh končí, kapitola zůstane rozpracovaná
            except Exception as e:         # OutputTruncated i ValueError sem patří
                state.update_chapter(db, ch["idx"], status="error",
                                     notes=json.dumps(
                                         {"error": f"{type(e).__name__}: {e}"},
                                         ensure_ascii=False))
                print(f"Kapitola {ch['idx']}: chyba ({type(e).__name__}), pokračuji.")
                continue
            print(f"Kapitola {summary['idx']}: {summary['status']} "
                  f"(revizí: {summary.get('revision_rounds', 0)})")
            if summary["status"] in ("done", "flagged"):
                counts = state.counts_by_status(db)
                n = counts.get("done", 0) + counts.get("flagged", 0)
                if n > 0 and n % config.CROSS_REF_EVERY_N == 0:
                    drifts = pipeline.run_drift_check(db, ch["idx"])
                    if drifts:
                        print(f"Drift check: {len(drifts)} termínů s rozjetými tvary "
                              "→ nové otázky.")
        _report(db)
        _print_usage(db, rid)
        status = "ok"
        return 0
    except FatalRunError as e:
        print(f"Fatální chyba běhu: {e}")
        return 1
    except KeyboardInterrupt:
        status = "interrupted"
        raise
    finally:
        state.finish_run(db, rid, status)


def _report(db: str) -> None:
    counts = state.counts_by_status(db)
    parts = [f"{k}: {v}" for k, v in sorted(counts.items())]
    print("Stav kapitol - " + ", ".join(parts) if parts else "Žádné kapitoly.")
    open_q = state.unanswered_questions(db)
    if open_q:
        print(f"Nezodpovězených otázek: {len(open_q)} (`python main.py questions`)")


def _cmd_status(args) -> int:
    db = config.DB_PATH
    _report(db)
    for ch in state.chapters_by_status(
            db, ("pending", "processing", "done", "flagged", "needs_human", "error")):
        mark = _MARKERS.get(ch["status"], "??")
        print(f"  [{mark}] {ch['idx']:>3}  {ch['title']}")
    return 0


def _cmd_questions(args) -> int:
    rows = state.unanswered_questions(config.DB_PATH)
    if not rows:
        print("Žádné otevřené otázky.")
        return 0
    for q in rows:
        scope = f"kapitola {q['chapter_idx']}" if q["chapter_idx"] is not None else "globální"
        guess = f" (odhad: {q['guess_answer']})" if q["guess_answer"] else ""
        print(f"#{q['id']} [{q['severity']}] {q['kind']} / {scope}{guess}\n"
              f"    {q['text']}")
    print("\nOdpověz: python main.py answer <ID> \"text\"  "
          "(víc tvarů odděl svislítkem: \"Rada | Radě\")")
    return 0


def _cmd_answer(args) -> int:
    try:
        out = requeue.apply_answer(config.DB_PATH, config.GUIDE_PATH,
                                   args.qid, args.text)
    except ValueError as e:
        print(e)
        return 1
    if out["requeued"]:
        print("Přepočítat kapitoly: " +
              ", ".join(str(i) for i in out["requeued"]) + " (spusť `run`)")
    elif out["chapter_status_changed"]:
        print("Kapitola uvolněna k překladu (spusť `run`).")
    else:
        print("Zapsáno. Žádná kapitola se přepočítávat nemusí.")
    return 0


def _finding_summary(notes: str) -> str:
    try:
        data = json.loads(notes or "[]")
    except (ValueError, TypeError):
        return "neznámý nález"
    if isinstance(data, dict):
        return str(data.get("error") or "neznámý nález")
    for f in data:
        if f.get("issue"):
            return f["issue"]
    return "neznámý nález"


def _cmd_export(args) -> int:
    db = config.DB_PATH
    chapters = state.chapters_by_status(
        db, ("pending", "processing", "done", "flagged", "needs_human", "error"))
    out_lines, skipped = [], []
    for ch in chapters:
        idx, st = ch["idx"], ch["status"]
        if st == "done":
            out_lines.append(f"\n\n{ch['title']}\n\n{ch['translated_text'] or ''}")
        elif st == "flagged" and not args.only_done:
            out_lines.append(
                f"\n\n[!! REVIDOVAT: {_finding_summary(ch['notes'])}]\n"
                f"{ch['title']}\n\n{ch['translated_text'] or ''}")
        elif st == "flagged":
            skipped.append(idx)
        else:
            skipped.append(idx)
            if not args.only_done:
                # Kniha nesmí tiše přijít o kapitolu.
                out_lines.append(f"\n\n[!! CHYBÍ KAPITOLA {idx} - stav {st}]")
    os.makedirs(os.path.dirname(config.OUTPUT_TXT) or ".", exist_ok=True)
    with open(config.OUTPUT_TXT, "w", encoding="utf-8") as f:
        f.write("\n".join(out_lines).strip() + "\n")
    print(f"Export: {config.OUTPUT_TXT}")
    if skipped:
        print("Vynechané kapitoly: " + ", ".join(str(i) for i in skipped))
    return 0


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="book-translator",
                                description="Multiagentní překladač knih EN→CZ")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init", help="načti knihu do DB")
    p_init.add_argument("path")
    p_init.add_argument("--reset", action="store_true",
                        help="smaž dosavadní stav knihy a nahraď novou")
    p_init.set_defaults(func=_cmd_init)

    p_scan = sub.add_parser("scan", help="scout → guide.draft.json")
    p_scan.add_argument("--chunked", action="store_true",
                        help="po částech, když se kniha nevejde do kontextu")
    p_scan.set_defaults(func=_cmd_scan)

    p_ref = sub.add_parser("reference", help="vytěž terminologii z profesionálních překladů")
    p_ref.add_argument("--dir", default=None, help="kořen se složkami EN/ a CZ/")
    p_ref.add_argument("--refresh-cache", action="store_true", dest="refresh_cache",
                       help="postav korpus znovu bez ohledu na cache")
    p_ref.set_defaults(func=_cmd_reference)

    sub.add_parser("review", help="web UI: potvrď návod → guide.json"
                   ).set_defaults(func=_cmd_review)

    p_run = sub.add_parser("run", help="překladová smyčka")
    p_run.add_argument("--retry-flagged", nargs="*", type=int, default=None,
                       dest="retry_flagged",
                       help="vrať flagged kapitoly do fronty (bez IDX = všechny)")
    p_run.add_argument("--only", nargs="+", type=int, default=None,
                       help="přelož jen tyhle kapitoly (pilot); zbytek zůstane ve frontě")
    p_run.set_defaults(func=_cmd_run)

    sub.add_parser("status", help="přehled kapitol").set_defaults(func=_cmd_status)
    sub.add_parser("questions", help="otevřené otázky").set_defaults(func=_cmd_questions)

    p_ans = sub.add_parser("answer", help="odpověz na otázku")
    p_ans.add_argument("qid", type=int)
    p_ans.add_argument("text")
    p_ans.set_defaults(func=_cmd_answer)

    p_exp = sub.add_parser("export", help="hotové kapitoly do TXT")
    p_exp.add_argument("--only-done", action="store_true", dest="only_done",
                       help="jen čisté kapitoly, bez flagged")
    p_exp.set_defaults(func=_cmd_export)

    return p


def main(argv=None) -> int:
    _bootstrap_stdout()
    os.makedirs(config.DATA_DIR, exist_ok=True)
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    state.init_db(config.DB_PATH)

    args = _build_parser().parse_args(argv)
    if args.cmd in _MUTATING:
        try:
            with state.run_lock(config.LOCK_PATH):
                return args.func(args)
        except state.LockError as e:
            print(e)
            return 1
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
