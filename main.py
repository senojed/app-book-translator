"""CLI překladače knih. Tenká vrstva: rozparsuj argumenty, zavolej modul, vypiš.

Fáze běhu:
    init kniha.epub    kniha → kapitoly do DB
    scan [--chunked]   scout projede knihu → guide.draft.json
    review             web UI: potvrdíš návod → guide.json (+ reseed glosáře)
    run [--retry-flagged [IDX...]]   překladová smyčka
    polish [--only IDX...] [--force]   stylistický průchod přes Codex (status=="done", volitelné, za STYLIST_ACCEPT_FS_RISK)
    polish-review      web UI: ruční review draftu z `polish`, apply/revert per kapitola
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
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from src import concordance, glossary
from src import guide as guide_mod
from src import findings as findings_mod
from src import ingest, pipeline, polish_store, requeue, state
from src import reference as reference_mod
from src import reference_mine, textnorm
from src.agents import scout, stylist
from src.llm.client import (AnthropicClient, FatalRunError, LockLostError,
                           OutputTruncated, PipelineLLMClient)

_MUTATING = {"init", "scan", "run", "answer", "review", "reference", "polish",
            "polish-review"}

_MARKERS = {"done": "OK", "pending": "..", "flagged": "!!", "needs_human": "??",
            "error": "XX", "processing": "~~"}


def _bootstrap_stdout() -> None:
    """Windows konzole je často cp1252 a český výstup by ji shodil."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def _client_factory(run_id: int, *, interactive: bool, require_lock=None):
    """Klienta staví až při volání - `run` s fake pipeline nikdy nesáhne na API."""
    def factory(agent: str):
        return PipelineLLMClient(AnthropicClient(), run_id=run_id, agent=agent,
                                 db_path=config.DB_PATH, config_mod=config,
                                 interactive=interactive, require_lock=require_lock)
    return factory


def _lock_still_owned(lock_path: str) -> bool:
    """`require_lock`-styl helper pro CLI (`_cmd_polish`) - server má
    vlastní `_require_lock` v `polish_server.py` (plus heartbeat vlákno
    na pozadí), CLI žádné takové vlákno nemá - AKTIVNĚ obnovuje zámek
    při KAŽDÉM volání (`state.refresh_lock`, ne jen pasivní kontrola),
    ať se staleness okno vůbec neotvírá mezi dvěma po sobě jdoucími
    LLM voláními uvnitř JEDNÉ kapitoly."""
    try:
        state.refresh_lock(lock_path)
        return True
    except state.LockError:
        return False


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
    """`type` je `"polish"` (skutečně přestylizováno) NEBO `"unchanged"`
    (kolo 9 - Codex zkontroloval, nic neměnil, ale marker pořád znamená
    "už řešeno, nezkoušej znovu bez --force"). Revert marker a
    "kept_original" marker mají STEJNÝ source, ale JINÝ type, aby po
    revertu / potvrzení originálu bylo možné `polish` znovu nabídnout
    bez `--force`."""
    return any(f.get("source") == "stylist" and f.get("type") in ("polish", "unchanged")
              for f in _parse_findings(notes_json))


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
                    f"délka {len(cz_before)} znaků, hash "
                    f"{hashlib.sha256(cz_before.encode('utf-8')).hexdigest()}.",
            "suggestion": None}


def _kept_original_marker(text: str, model: str, draft_id: str) -> dict:
    """Apply BEZ věcné změny (text == cz_before) - kolo 7: `type` musí
    LIŠIT od `_stylist_marker`, jinak by `_already_styled` nepravdivě
    tvrdilo, že kapitola byla stylizována, i když zůstala nezměněná.
    `draft_id` je VLASTNÍ pole, NE součást `issue` textu (kolo 10
    plán-ping-pongu BLOCKING) - `_stale_info`/`post_apply`'s idempotence
    (kolo 6/9) musí porovnávat KONKRÉTNÍ draft, ne hash obsahu textu,
    protože STEJNÝ `cz_before` se může legitimně opakovat napříč VÍCE
    nezávislými `polish` běhy na kapitole, co zůstává nestylizovaná."""
    return {"source": "stylist", "type": "kept_original", "severity": "info",
            "action": "note", "term_id": None, "expected": None,
            "actual": None, "cz_excerpt": None, "draft_id": draft_id,
            "issue": f"potvrzeno ponechání originálu přes polish-review "
                    f"(model={model}), délka {len(text)} znaků, hash "
                    f"{hashlib.sha256(text.encode('utf-8')).hexdigest()}.",
            "suggestion": None}


def _unchanged_marker(model: str) -> dict:
    """Kolo 9 IMPORTANT: `_polish_one_chapter` vrátí `outcome=="unchanged"`,
    když Codex nenavrhl žádnou úpravu - beze zápisu markeru by
    `_already_styled` zůstalo `False` a příští `polish` (i bez `--force`)
    by kapitolu znovu poslal (a zaplatil) Codexu, donekonečna. Vlastní
    `type` (ne `"polish"` jako `_stylist_marker`) - kapitola NENÍ
    přepsaná, jen zkontrolovaná, report/UI to musí umět rozlišit, ale
    `_already_styled` (main.py:100) obě hodnoty uznává stejně."""
    return {"source": "stylist", "type": "unchanged", "severity": "info",
            "action": "note", "term_id": None, "expected": None,
            "actual": None, "cz_excerpt": None,
            "issue": f"Codex zkontroloval (model={model}), žádná úprava "
                    "nenavržena.",
            "suggestion": None}


def _revert_marker(note: str) -> dict:
    """Kolo 5: `type` odlišný od `_stylist_marker`, ať `_already_styled`
    po revertu vrátí `False` (kapitola se má chovat, jako by ještě
    nebyla stylizována)."""
    return {"source": "stylist", "type": "revert", "severity": "info",
            "action": "note", "term_id": None, "expected": None,
            "actual": None, "cz_excerpt": None, "issue": note,
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
    1. `meaning_drift`/`register_drift`/`structure_drift`/`length_drift`/
       `number_drift` (zdroj `stylist_check`) - odmítá VŽDY, když se
       objeví. `register_drift` přidán v kole 7 (tykání/vykání, hlas
       vypravěče); `structure_drift`/`length_drift`/`number_drift`
       přidány 2026-09-13 v2 (`stylist.structural_findings` - dřív to
       samo `stylist.polish()` řešilo tvrdým `StylistError`, teď je to
       nález jako kterýkoli jiný, viz `stylist.py` docstring proč) -
       všechny deterministicky nové signály, PŘED stylizací nemohly
       existovat (ta kontrola PŘED tímhle během vůbec neexistovala).
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
                if f.get("type") in ("meaning_drift", "register_drift",
                                     "structure_drift", "length_drift", "number_drift")]
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


_REPORT_OUTCOMES = ("applied", "unchanged", "failed", "fatal", "interrupted")


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
    Klíčové: `drafted` nese `reason_types` VŽDY (deduplikované
    `"src/type"` řetězce, bezpečná agregační metrika); `findings`/
    `styled` jen za `config.STYLIST_REPORT_REJECTED_TEXT`.
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
        (drafted/unchanged/failed/fatal/interrupted)

    `polish-reports/run-<rid>-<timestamp>-<8 hex>.json` - jeden soubor za běh,
    historie zůstává. Atomický zápis (tmp + `os.replace`).

    Best-effort: CELÉ sestavení i zápis v `except Exception` (ne jen
    `OSError` - `json.dump` neserializovatelné hodnoty hodí `TypeError`;
    volá se z `finally`, nová výjimka by přebila skutečný výsledek).
    Selhání jen VYPÍŠE a uklidí `.tmp`.

    BEZPEČNOST (kolo 27-32, aktualizováno po zavedení `polish-review`):
    s `config.STYLIST_REPORT_REJECTED_TEXT is True` report u `drafted`
    PERZISTENTNĚ ukládá stylizovaný text od Codexu + volná pole nálezů
    (`issue`, `cz_excerpt`, ...), co můžou nést exfiltrovaný obsah (dřív
    se po zamítnutí zahodilo, dnes jde vždy k ručnímu review přes
    `polish-review`). To je SAMOSTATNÉ riziko (trvalá perzistence
    potenciálně exfiltrovaného obsahu, navíc do často synchronizované
    složky) - NENÍ pokryté přijetím `STYLIST_ACCEPT_FS_RISK` (to je jen o
    čtení disku BĚHEM běhu), proto SAMOSTATNÝ explicitní opt-in (kolo 31
    IMPORTANT). DEFAULT je `False` → záznam `drafted` nese JEN
    `reason_types` (normalizované kategorie, žádný volný text),
    per-kapitolový konzolový výpis vynechá `issue` řádky, a `polish()`
    nepřipojí Codex stderr do `StylistError`. Kontrola `is True` (kolo
    32) - `1`/`"False"`/`None` plný detail NEaktivují. Retence/práva
    souborů `polish-reports/` jsou na uživateli."""
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


def _rendered_terms_for_chapter(db: str, idx: int) -> list:
    """Translatorem HLÁŠENÉ (ne jen detekované) formy termínů pro danou
    kapitolu - vstup pro `concordance.build_mentions`/`check_chapter`,
    sdíleno `_polish_one_chapter` (dávka) i editor "Uložit" endpointem
    (Task 9, kapitola bez živého draftu potřebuje stejnou hodnotu)."""
    prior = state.chapter_mentions(db, idx)
    return [{"term_id": m["term_id"], "cz_as_used": m["cz_form"],
            "scene_idx": m["scene_idx"]}
           for m in prior
           if m.get("cz_form") and m.get("source") == "rendered"]


def _preferred_rendered_terms(db: str, idx: int, current_text: str,
                              history_entries: list) -> list:
    """Historie MÁ přednost před živou `term_mentions` (ta se PŘEPISUJE
    při každém `commit_chapter_result` na základě `concordance.build_
    mentions`, co může být UŽŠÍ množina, než co translator PŮVODNĚ
    nahlásil při `run`u - opakované úpravy by jinak postupně "zapomínaly"
    původně nahlášené tvary) - ALE JEN pokud poslední historie záznam
    popisuje PRÁVĚ `current_text` (`cz_after == current_text`). Jinak
    (žádná historie, nebo text mezitím prošel `run`/`answer` mimo
    polish/editor) je živá DB jediný platný zdroj - stará historie by
    patřila jiné verzi textu. `polish_store` už je importovaný na úrovni
    modulu (main.py's existující `from src import ..., polish_store,
    ...`), žádný nový import netřeba."""
    latest = polish_store.find_latest(history_entries, idx)
    if latest is not None and latest["cz_after"] == current_text:
        return latest["rendered_terms"]
    return _rendered_terms_for_chapter(db, idx)


def _polish_one_chapter(c, glossary_rows, cf, db, model: str,
                        codex_cmd: list, rendered_terms: "list | None" = None) -> dict:
    """Vrací JEDEN záznam za kapitolu - NEcommituje nic do DB (spec
    2026-09-11-polish-review-design.md - `_cmd_polish`/`polish-review`
    apply endpoint dělají commit/zálohu teď, ne tahle funkce). Tvary:
      - `{"idx", "outcome": "unchanged"}` / `{"idx", "outcome": "failed", "error"}`
        - beze změny oproti dřívějšku.
      - draft dict BEZ klíče `"outcome"` (`idx`, `title`, `cz_before`,
        `styled`, `revision_rounds`, `reason_types`, `findings`,
        `rendered_terms`, `draft_id`) - volající (`_cmd_polish`) ho pozná podle
        CHYBĚJÍCÍHO `"outcome"` a zapíše do `polish.draft.json`.
        `reason_types` je JEN kontext pro člověka (prázdné = nic
        nenamítáno, neprázdné = kritik/konkordance/meaning-check něco
        našly) - nikdy negate ROZHODNUTÍ, to dělá teď `polish-review`.
    `FatalRunError` z kritika/meaning-checku pořád propaguje (kolo 37) -
    žádná DB zápisová `FatalRunError` už neexistuje, funkce nic
    nezapisuje. Žádný `guide_block` (odstraněn 2026-09-13, pilotní nález -
    `stylist.polish()` prompt bez omezení funguje lépe, `guide_block` šel
    pryč spolu se seznamem zákazů, viz `stylist.py` komentář nad
    `POLISH_PROMPT_TEMPLATE`)."""
    idx, en, cz = c["idx"], c["raw_text"], c["translated_text"]
    try:
        styled = stylist.polish(en, cz, codex_cmd=codex_cmd, codex_model=model,
                                timeout=config.STYLIST_TIMEOUT_SECONDS)
    except stylist.StylistError as e:
        _say(f"Kapitola {idx}: stylista selhal ({e}), ponechávám původní.")
        return {"idx": idx, "outcome": "failed", "error": str(e)}

    if styled == cz:
        _say(f"Kapitola {idx}: beze změny (Codex nenavrhl žádnou úpravu).")
        return {"idx": idx, "outcome": "unchanged"}

    if rendered_terms is None:
        rendered_terms = _rendered_terms_for_chapter(db, idx)

    baseline_concordance = concordance.check_chapter(en, cz, glossary_rows, rendered_terms)
    findings = concordance.check_chapter(en, styled, glossary_rows, rendered_terms)
    # Strukturální nálezy (odstavce/délka/čísla) - deterministické, žádné
    # LLM volání, PŘED kritikem (2026-09-13 v2 - dřív uvnitř `stylist.
    # polish()` jako tvrdé zamítnutí, viz `structural_findings` docstring
    # proč se to přestavělo na nález jako kterýkoli jiný).
    findings += stylist.structural_findings(cz, styled)
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
    except LockLostError:
        raise   # zachovej typ, NEPŘEBALUJ (server potřebuje rozlišit
        # LockLostError od obecné FatalRunError, viz Task 10)
    except FatalRunError as fe:
        raise FatalRunError(
            f"Kontrola stylizace kapitoly {idx} selhala fatálně "
            f"({stylist._redact_detail(str(fe))}) - cost guard / chyba LLM "
            "klienta, celý běh `polish` se zastavuje.") from fe

    reason_types = sorted({f"{r.get('source', '?')}/{r.get('type', '?')}"
                           for r in reasons}) if reasons else []
    if reasons:
        _say(f"Kapitola {idx}: kontrola má výhrady ({', '.join(reason_types)}).")
        full = config.STYLIST_REPORT_REJECTED_TEXT is True
        if full:
            for r in reasons:
                _say(f"    - [{r.get('source', '?')}/{r.get('type', '?')}] "
                     f"{r.get('issue') or '(bez popisu)'}")
            context = [f for f in findings
                      if f.get("source") == "critic" and f not in reasons]
            if context:
                _say("    (kontext od kritika - samo o sobě nezpůsobilo "
                     "výhradu, ale vysvětluje rozpor výš):")
                for f in context:
                    _say(f"      - [{f.get('severity', '?')}] "
                         f"{f.get('issue') or '(bez popisu)'}")
    else:
        _say(f"Kapitola {idx}: návrh připraven, žádné výhrady.")

    # `draft_id` identifikuje TOHLE KONKRÉTNÍ rozhodnutí, NIKDY se
    # neodvozuje z obsahu textu (kolo 10 plán-ping-pongu BLOCKING - dřív
    # `_stale_info`/`post_apply`'s no-op idempotence (kolo 6/9) klíčovaly
    # podle hashe `cz_before`/`text`; kapitola co zůstává nestylizovaná
    # může mít STEJNÝ `cz_before` napříč VÍCE nezávislými `polish` běhy -
    # starý `kept_original` marker by pak falešně označil ÚPLNĚ NOVÝ,
    # nevyřízený draft jako už vyřízený).
    findings = findings_mod.assign_ids(findings)
    return {"idx": idx, "title": c["title"], "cz_before": cz, "styled": styled,
            "revision_rounds": c["revision_rounds"], "reason_types": reason_types,
            "findings": findings, "rendered_terms": rendered_terms,
            "draft_id": uuid.uuid4().hex}


# --- příkazy ----------------------------------------------------------------

def _archive_polish_file(path: str) -> "str | None":
    """Přejmenuje `path` na timestampovanou archivní kopii (MIKROsekundová
    přesnost - kolo 6, dva resety ve stejné sekundě by jinak dostaly
    STEJNÝ název a `os.rename` by na Windows selhal na kolizi, což je
    žádoucí - NIKDY tiché přepsání). Timestamp jde PŘED příponu
    (`polish.draft.<stamp>.json`, spec kolo 6 - NE za ni
    `polish.draft.json.<stamp>`, kolo 1 plán-ping-pongu BLOCKING).
    Vrátí novou cestu, nebo `None`, když `path` neexistuje (nic k
    archivaci)."""
    if not os.path.exists(path):
        return None
    stamp = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    base, ext = os.path.splitext(path)
    archived = f"{base}.{stamp}{ext}"
    os.rename(path, archived)
    return archived


def _safe_rollback_rename(archived: "str | None", original: str) -> bool:
    """Best-effort vrácení archivace zpět - vrátí `True` při úspěchu NEBO
    když nebylo co vracet (`archived is None`). Kolo 2 plán-ping-pongu
    IMPORTANT - SAMOTNÝ rollback `os.rename` může taky selhat (disk
    skutečně rozbitý); bez tyhle ochrany by to spadlo jako nezachycený
    traceback místo slíbeného "vypíše přesný stav". Při selhání vypíše,
    KTERÁ cesta SKUTEČNĚ existuje (archivní i původní), ať se dá stav
    opravit ručně."""
    if archived is None:
        return True
    try:
        os.rename(archived, original)
        return True
    except OSError as e:
        _say(f"POZOR: rollback {archived} -> {original} selhal ({e}) - "
             f"zkontroluj ručně: archivní cesta existuje = "
             f"{os.path.exists(archived)}, původní cesta existuje = "
             f"{os.path.exists(original)}.")
        return False


def _cmd_init(args) -> int:
    db = config.DB_PATH
    if not state.is_db_empty(db) and not args.reset:
        print("DB už obsahuje knihu. Použij `init --reset` pro nahrazení.")
        return 1
    # Kniha se NAČTE (a tím validuje) JAKO ÚPLNĚ PRVNÍ krok (kolo 5
    # plán-ping-pongu BLOCKING) - PŘED archivací i resetem. Dřív se
    # `ingest.load_book`/`state.seed_chapters` volaly AŽ PO úspěšném
    # resetu, BEZE ZMĚNY z existujícího main.py a BEZ ochrany - selhání
    # (špatný vstupní soubor, poškozený EPUB) by nechalo uživatele BEZ
    # staré knihy (DB resetnutá) I BEZ nové (načtení selhalo) I BEZ
    # aktivní review fronty (archivovaná, ne smazaná, ale nedostupná z
    # běžných cest). Validace na začátku eliminuje "špatný vstupní
    # soubor" jako spouštěč úplně - archivace/reset se vůbec nezačnou,
    # dokud nevíme, že nová kniha JDE načíst.
    try:
        chapters = ingest.load_book(args.path)
    except Exception as e:
        print(f"Kniha se nepodařilo načíst ({type(e).__name__}: {e}) - "
              "nic se nezměnilo, DB i polish soubory beze změny.")
        return 1
    if args.reset:
        # Úklid PŘED `state.reset_book` (kolo 2/9/10) - obě přejmenování
        # musí uspět DOHROMADY (vše nebo nic), jinak by nezkontrolovaný
        # draft zmizel z aktivních cest, aniž by o něm cokoli vědělo
        # (spec "init --reset a draft/historie").
        archived_history = None
        archived_draft = None
        try:
            archived_history = _archive_polish_file(config.POLISH_HISTORY_PATH)
            archived_draft = _archive_polish_file(config.POLISH_DRAFT_PATH)
        except OSError as e:
            ok = _safe_rollback_rename(archived_history, config.POLISH_HISTORY_PATH)
            print(f"init --reset selhal (archivace polish souborů: {e}) - "
                  "DB nedotčená." + ("" if ok else " Rollback SAMOTNÝ selhal, "
                  "viz hláška výš - zkontroluj stav ručně."))
            return 1
        try:
            state.reset_book(db)
        except Exception as e:
            ok_draft = _safe_rollback_rename(archived_draft, config.POLISH_DRAFT_PATH)
            ok_history = _safe_rollback_rename(archived_history, config.POLISH_HISTORY_PATH)
            print(f"init --reset selhal ({type(e).__name__}: {e}) - "
                  "DB nedotčená." + ("" if ok_draft and ok_history else
                  " Rollback SAMOTNÝ částečně selhal, viz hlášky výš - "
                  "zkontroluj stav souborů ručně."))
            return 1
    # `state.seed_chapters` po `reset_book` zůstává BEZ dalšího rollbacku
    # (kolo 5 IMPORTANT - vědomě přijaté zbytkové riziko, ne dořešeno):
    # `reset_book` samo o sobě NENÍ vratné (žádný snapshot dat CHAPTERS
    # tahle spec nikdy nedělala - to je mimo její rozsah, viz "Mimo
    # rozsah" v designové spec). Kniha už je ale VALIDOVANÁ výš (selže-li
    # TADY, je to infrastrukturní chyba - plný disk apod., ne špatný
    # vstup) - DB v tom případě zůstává PRÁZDNÁ (`reset_book` proběhlo),
    # ale ne poškozená - obyčejný `init <path>` (bez --reset) na
    # prázdnou DB bezpečně doběhne, což je jasná a jednoduchá cesta ven.
    try:
        state.seed_chapters(db, chapters)
    except Exception as e:
        print(f"Načtení kapitol do DB selhalo ({type(e).__name__}: {e}) - "
              "DB je teď PRÁZDNÁ (reset proběhl, načtení ne). Zkus "
              "`python main.py init <cesta>` znovu (BEZ --reset, DB je "
              "prázdná) - polish soubory zůstávají archivované beze změny.")
        return 1
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


def _cmd_polish_review(args) -> int:
    from src.review_ui import polish_server
    # `run_polish_review_server` volá `build_app` PŘED svým vlastním
    # try/finally - poškozená `polish.history.json` (`PolishStoreError`)
    # nebo selhání startovního `_snapshot_db` (`TimeoutError` u dlouho
    # zamčené DB, `OSError` u neprošlého integrity_check) by jinak
    # propadly jako nezachycený traceback až sem - `main()`'s `except
    # state.LockError` tyhle výjimky nechytá. Čitelná hláška + `return 1`,
    # ne holý traceback.
    try:
        return polish_server.run_polish_review_server(
            config.DB_PATH, config.POLISH_HISTORY_PATH, config.LOCK_PATH)
    except (polish_store.PolishStoreError, OSError, TimeoutError) as e:
        _say(f"polish-review se nepodařilo spustit ({type(e).__name__}: {e}) - "
             f"zkontroluj {config.POLISH_HISTORY_PATH} a DB ({config.DB_PATH}), "
             "případně poškozený soubor oprav nebo smaž.")
        return 1


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
    for f in _parse_findings(notes):   # bezpečné, jen dict prvky - main.py:84
        if f.get("issue"):
            return str(f["issue"])
    return "neznámý nález"


def export_book(db_path: str, only_done: bool) -> tuple:
    """Čistá funkce (žádný I/O na argparse `args`, žádný `print`) - sdíleno
    CLI `_cmd_export` a novým `POST /api/export` (Task 12, tlačítko v UI).
    Vrací `(cesta_k_výslednému_souboru, seznam_vynechaných_idx)`."""
    chapters = state.chapters_by_status(
        db_path, ("pending", "processing", "done", "flagged", "needs_human", "error"))
    out_lines, skipped = [], []
    for ch in chapters:
        idx, st = ch["idx"], ch["status"]
        if st == "done":
            out_lines.append(f"\n\n{ch['title']}\n\n{ch['translated_text'] or ''}")
        elif st == "flagged" and not only_done:
            out_lines.append(
                f"\n\n[!! REVIDOVAT: {_finding_summary(ch['notes'])}]\n"
                f"{ch['title']}\n\n{ch['translated_text'] or ''}")
        elif st == "flagged":
            skipped.append(idx)
        else:
            skipped.append(idx)
            if not only_done:
                out_lines.append(f"\n\n[!! CHYBÍ KAPITOLA {idx} - stav {st}]")
    os.makedirs(os.path.dirname(config.OUTPUT_TXT) or ".", exist_ok=True)
    with open(config.OUTPUT_TXT, "w", encoding="utf-8") as f:
        f.write("\n".join(out_lines).strip() + "\n")
    return config.OUTPUT_TXT, skipped


def _cmd_export(args) -> int:
    path, skipped = export_book(config.DB_PATH, args.only_done)
    print(f"Export: {path}")
    if skipped:
        print("Vynechané kapitoly: " + ", ".join(str(i) for i in skipped))
    return 0


def _polish_preflight() -> tuple:
    """Bezpečnostní + config kontroly sdílené `_cmd_polish` (dávka) a
    `POST /api/polish/regenerate` (server, Task 10) - OBĚ cesty volají
    Codex, obě musí projít STEJNOU bránou. Vrací `(model, codex_cmd, None)`
    při úspěchu, `(None, None, chybová_hláška)` při selhání."""
    if config.STYLIST_ACCEPT_FS_RISK is not True:
        return None, None, (
            "polish je vypnutý: spouští agentní `codex exec`, který má "
            "ČTECÍ přístup k CELÉMU disku (ověřeno). Prompt injection z "
            "textu knihy tak MŮŽE exfiltrovat citlivý soubor jako součást "
            "stylizovaného textu, dřív než guardraily proběhnou.\n"
            "Chceš-li to i tak spustit, nastav v config.py "
            "`STYLIST_ACCEPT_FS_RISK = True`.")
    model = (config.CODEX_MODEL or "").strip()
    if not model:
        return None, None, ("Chybí config.CODEX_MODEL - nastav ho (audit "
                            "stylizace musí vědět, jaký model se skutečně použil).")
    try:
        codex_cmd = stylist._resolve_codex_cmd(["codex"])
    except stylist.StylistError as e:
        return None, None, f"Codex CLI není použitelné: {e}"
    return model, codex_cmd, None


class HistoryWriteFailedAfterCommit(Exception):
    """DB commit UŽ proběhl (nevratně), tohle selhání je z JINÉ třídy
    než selhání PŘED commitem - volající to MUSÍ hlásit jinak (stejný
    princip jako `2026-09-11` spec's `apply`/`revert` "text SE uložil,
    ale historie ne" rozlišení). BLOCKING oprava kola 2 - `_commit_
    polish_result` dřív načítala/validovala historii AŽ PO DB commitu,
    takže poškozený `polish.history.json` by nechal DB už změněnou, ale
    volající by to nesprávně hlásil jako "text NEBYL uložen"."""


def _commit_polish_result(db: str, history_path: str, idx: int, *, en: str,
                          cz_before: str, final_text: str, findings: list,
                          glossary_rows: list, revision_rounds: int, source: str,
                          model_label: str, styled_by_codex: str,
                          backup_state: dict, rendered_terms: "list | None" = None) -> None:
    """Sdílený zápis "text se STÁVÁ finálním" - volá dávkový `_cmd_polish`
    (`source="polish-batch"`) i editor "Uložit" endpoint (`polish_server.py`
    Task 9, `source="polish-review"`). JEDNO místo pro DB commit +
    historii, ať obě cesty zůstanou navždy v souladu (stejný vzor jako
    dnešní `POST /api/polish/apply`, jen extrahovaný a sdílený). PŘEPISUJE
    `chapters.notes` (nenačítá/nemergeuje předchozí obsah) - stejné chování
    jako dnešní `apply` endpoint už dělá; report nálezů (Task 7/8) proto
    čte JEN `chapters.notes` jako aktuální stav, ne merge s historií (viz
    tamní poznámka o duplicitě).

    Historie se NAČTE/OVĚŘÍ JAKO PRVNÍ krok, PŘED jakýmkoli zápisem do DB
    (kolo 2 BLOCKING oprava) - poškozený `polish.history.json` tak zastaví
    CELOU operaci dřív, než se text vůbec změní. Selhání SAMOTNÉHO zápisu
    historie (`save_history` na konci, PO úspěšném DB commitu) je jiná
    třída chyby - `HistoryWriteFailedAfterCommit` výš, volající ji MUSÍ
    zachytit zvlášť.

    `rendered_terms` je VOLITELNÝ (kolo 5 IMPORTANT, revize kola 2) -
    když volající NEPŘEDÁ nic (`None`, Task 9 save endpoint - žádná
    předchozí `_polish_one_chapter` analýza, se kterou by se muselo
    shodovat), spočítá se TADY přes `_preferred_rendered_terms(db, idx,
    cz_before, history["entries"])` (Task 4). Když volající HODNOTU
    předá (dávka Task 5, `_polish_one_chapter` ji dostala STEJNOU - viz
    Task 3), použije se BEZE ZMĚNY - analýza (concordance kontrola
    uvnitř `_polish_one_chapter`) a zápis (`concordance.build_mentions`
    tady) musí vidět STEJNOU množinu, jinak může kontrola podhodnotit
    závažnost nálezu (`omission/minor` místo `inconsistency/critical`),
    protože zápis mezitím do `term_mentions` prosadí JINOU sadu, než
    jakou kontrola viděla (konkrétní reprodukce v plán-consensus logu,
    kolo 5)."""
    findings_to_store = findings_mod.assign_ids(
        list(findings) + [_stylist_marker(final_text, model_label)])
    history = polish_store.load_history(history_path)   # PŘED DB zápisem
    if rendered_terms is None:
        rendered_terms = _preferred_rendered_terms(db, idx, cz_before, history["entries"])
    mentions = concordance.build_mentions(en, final_text, glossary_rows, rendered_terms)
    _backup_db_once(db, backup_state)
    row_before = state.get_chapter(db, idx)
    title = row_before["title"] if row_before else f"Chapter {idx}"
    state.commit_chapter_result(
        db, idx, translated_text=final_text, revision_rounds=revision_rounds,
        notes_json=json.dumps(findings_to_store, ensure_ascii=False), status="done",
        new_candidates=[], mentions=mentions, questions=[])
    # DB commit VÝŠ už proběhl a je NEODVOLATELNÝ - selhání NÍŽE je JINÁ
    # třída chyby (kolo 2 BLOCKING), zabalená do `HistoryWriteFailedAfterCommit`.
    history["entries"].append({
        "idx": idx, "applied_at": polish_store.utc_now_z(),
        "cz_before": cz_before, "cz_after": final_text,
        "styled_by_codex": styled_by_codex, "title": title,
        "findings": findings_to_store, "rendered_terms": rendered_terms,
        "source": source, "draft_id": uuid.uuid4().hex})
    try:
        polish_store.save_history(history_path, history)
    except Exception as e:
        raise HistoryWriteFailedAfterCommit(str(e)) from e


def _cmd_polish(args) -> int:
    db = config.DB_PATH
    model, codex_cmd, preflight_err = _polish_preflight()
    if preflight_err:
        _say(preflight_err)
        return 1

    rid = None
    status = "fatal"
    report = []
    planned_count = 0
    batch_completed = False
    run_error = None
    backup_state = {"done": False, "snapshot_path": db + ".pre-polish-snapshot"}
    # `_snapshot_db` selhání (`OSError`/`TimeoutError`) MUSÍ dostat
    # ŘÍZENÉ ošetření - VLASTNÍ `try/except`, ne propad do hlavního
    # `try:` bloku (ten se ještě nezačal). `main()` zachytává VÝHRADNĚ
    # `state.LockError`, žádnou jinou výjimku.
    try:
        _snapshot_db(db, backup_state["snapshot_path"])
    except (OSError, TimeoutError) as e:
        _say(f"Záloha DB před polishem selhala ({type(e).__name__}: {e}) - "
             "běh se nespouští, dokud se nedá udělat bezpečná záloha.")
        return 1
    try:
        all_done = state.chapters_by_status(db, ("done",))
        chapters = all_done
        if args.only:
            wanted = set(args.only)
            chapters = [c for c in all_done if c["idx"] in wanted]
            chybi = sorted(wanted - {c["idx"] for c in chapters})
            if chybi:
                _say("Přeskočeno (nejsou 'done', nebo neexistují): "
                     + ", ".join(str(i) for i in chybi))
        if not args.force:
            pred_force = len(chapters)
            chapters = [c for c in chapters if not _already_styled(c["notes"])]
            preskoceno_stylizovane = pred_force - len(chapters)
            if preskoceno_stylizovane:
                _say(f"Přeskočeno (už stylizováno, zkus --force): "
                     f"{preskoceno_stylizovane}")
        if not chapters:
            _say("Žádné kapitoly ke stylizaci.")
            status = "ok"
            return 0
        planned_count = len(chapters)

        glossary_rows = glossary.all_terms(db)
        rid = state.create_run(db, "polish")
        cf = _client_factory(rid, interactive=True,
                             require_lock=lambda: _lock_still_owned(config.LOCK_PATH))
        for c in chapters:
            rec = None
            try:
                history_for_rt = polish_store.load_history(config.POLISH_HISTORY_PATH)
                rt = _preferred_rendered_terms(
                    db, c["idx"], c["translated_text"], history_for_rt["entries"])
                rec = _polish_one_chapter(c, glossary_rows, cf, db, model, codex_cmd,
                                          rendered_terms=rt)
            except FatalRunError as fe:
                rec = {"idx": c["idx"], "outcome": "fatal", "error": str(fe)}
                raise
            except Exception as e:
                rec = {"idx": c["idx"], "outcome": "failed",
                       "error": f"{type(e).__name__}: "
                                f"{stylist._redact_detail(str(e))}"}
                _say(f"Kapitola {c['idx']}: neočekávaná chyba "
                     f"({type(e).__name__}), ponechávám původní.")
            finally:
                if rec is None:
                    # KeyboardInterrupt/BaseException propadla dřív, než
                    # `_polish_one_chapter` vrátila výsledek - funkce nic
                    # nekomituje, takže žádná DB kontrola není potřeba
                    # (kolo 5 refaktoru main.py - dřív se tu srovnával
                    # DB stav, protože commit mohl proběhnout uprostřed).
                    rec = {"idx": c["idx"], "outcome": "interrupted"}
                if "outcome" not in rec:
                    # Codex navrhl jinou stylizaci - ROVNOU zapiš jako
                    # finální text (spec "Architektura" - žádná čekající
                    # fronta). Obnov zámek PŘED KAŽDÝM zápisem - dlouhá
                    # dávka (desítky kapitol, minuty Codex volání na
                    # kapitolu) jinak riskuje překročení stálosti zámku
                    # uprostřed běhu.
                    try:
                        state.refresh_lock(config.LOCK_PATH)
                    except state.LockError as e:
                        report.append({"idx": rec["idx"], "outcome": "fatal",
                                       "error": f"Zámek ztracen: {e}"})
                        raise FatalRunError(
                            f"Zámek ztracen uprostřed dávky ({e}) - jiný "
                            "proces teď píše do DB, běh se zastavuje.") from e
                    # CAS - `en`/`cz_before` musí přijít ze STEJNÉHO `c`
                    # objektu, ale DB se od zahájení smyčky mohla změnit
                    # (i v rámci JEDNOHO zámku - obranná kontrola, ne jen
                    # cross-proces). Neshoda → přeskoč TUHLE kapitolu,
                    # nezastavuj celou dávku.
                    row_now = state.get_chapter(db, c["idx"])
                    if (row_now is None
                            or row_now["translated_text"] != c["translated_text"]
                            or row_now["status"] != "done"):
                        rec = {"idx": c["idx"], "outcome": "failed",
                               "error": "kapitola se mezitím změnila mimo "
                                       "tenhle běh, přeskočeno"}
                    else:
                        findings_final = rec["findings"]
                        try:
                            _commit_polish_result(
                                db, config.POLISH_HISTORY_PATH, c["idx"],
                                en=c["raw_text"], cz_before=c["translated_text"],
                                final_text=rec["styled"], findings=findings_final,
                                glossary_rows=glossary_rows,
                                revision_rounds=rec["revision_rounds"],
                                source="polish-batch", model_label=model,
                                styled_by_codex=rec["styled"],
                                backup_state=backup_state,
                                rendered_terms=rt)   # STEJNÁ hodnota jako
                                # analýza výš (`_polish_one_chapter`
                                # volání) - kolo 5 IMPORTANT konzistence.
                        except HistoryWriteFailedAfterCommit as e:
                            # Text UŽ JE v DB (kolo 2 BLOCKING rozlišení) -
                            # jiná hláška než "nezapsáno", i když se běh
                            # pořád zastavuje (historie je z tohohle místa
                            # dál nekonzistentní, bezpečnější nepokračovat).
                            report.append({"idx": rec["idx"], "outcome": "fatal",
                                           "error": stylist._redact_detail(
                                               f"HistoryWriteFailedAfterCommit: {e}")})
                            raise FatalRunError(
                                f"Kapitola {c['idx']}: text SE zapsal do knihy, ale "
                                f"zápis do historie selhal ({stylist._redact_detail(str(e))}) "
                                "- celý běh `polish` se zastavuje, zkontroluj "
                                f"{config.POLISH_HISTORY_PATH} ručně.") from e
                        except Exception as e:
                            report.append({"idx": rec["idx"], "outcome": "fatal",
                                           "error": stylist._redact_detail(
                                               f"{type(e).__name__}: {e}")})
                            raise FatalRunError(
                                f"Zápis výsledku selhal ({stylist._redact_detail(f'{type(e).__name__}: {e}')}) "
                                "- infrastrukturní chyba, celý běh `polish` se "
                                "zastavuje.") from e
                        _say(f"Kapitola {c['idx']}: stylizováno a zapsáno "
                             f"({len(findings_final)} nálezů).")
                        full = config.STYLIST_REPORT_REJECTED_TEXT is True
                        report_rec = {"idx": rec["idx"], "outcome": "applied",
                                     "reason_types": rec["reason_types"]}
                        if full:
                            report_rec["findings"] = rec["findings"]
                            report_rec["styled"] = rec["styled"]
                        rec = report_rec
                elif rec.get("outcome") == "unchanged":
                    # Marker zapiš i BEZE ZMĚNY textu (viz "_unchanged_
                    # marker" docstring) - jinak `_already_styled` zůstane
                    # `False` a příští `polish` bez `--force` kapitolu
                    # znovu (a zbytečně) pošle Codexu. `_commit_polish_
                    # result` se tu NEPOUŽÍVÁ (žádná VĚCNÁ změna textu,
                    # historie by dostala zavádějící `cz_before ==
                    # cz_after` záznam) - stejný lehký zápis jako Task 9's
                    # notes-only větev.
                    try:
                        state.refresh_lock(config.LOCK_PATH)
                    except state.LockError as e:
                        report.append({"idx": rec["idx"], "outcome": "fatal",
                                       "error": f"Zámek ztracen: {e}"})
                        raise FatalRunError(
                            f"Zámek ztracen uprostřed dávky ({e}) - jiný "
                            "proces teď píše do DB, běh se zastavuje.") from e
                    row_now = state.get_chapter(db, c["idx"])
                    if (row_now is None
                            or row_now["translated_text"] != c["translated_text"]
                            or row_now["status"] != "done"):
                        # Kapitola se mezitím změnila mimo tenhle běh -
                        # na rozdíl od "applied" větve NENÍ text co
                        # zahodit (nic se nezměnilo), marker jen zůstane
                        # nezapsaný - příští `polish` to zkusí znovu na
                        # AKTUÁLNÍM stavu kapitoly.
                        pass
                    else:
                        marker = findings_mod.assign_ids([_unchanged_marker(model)])[0]
                        current_notes = _parse_findings(row_now["notes"])
                        try:
                            _backup_db_once(db, backup_state)
                            with state.connect(db) as conn:
                                conn.execute(
                                    "UPDATE chapters SET notes=?, "
                                    "updated_at=CURRENT_TIMESTAMP WHERE idx=?",
                                    (json.dumps(current_notes + [marker], ensure_ascii=False),
                                     c["idx"]))
                        except Exception as e:
                            report.append({"idx": rec["idx"], "outcome": "fatal",
                                           "error": stylist._redact_detail(
                                               f"{type(e).__name__}: {e}")})
                            raise FatalRunError(
                                f"Zápis markeru selhal ({stylist._redact_detail(f'{type(e).__name__}: {e}')}) "
                                "- infrastrukturní chyba, celý běh `polish` se "
                                "zastavuje.") from e
                report.append(rec)
        batch_completed = True

        tally = {k: sum(1 for rec in report if rec.get("outcome") == k)
                 for k in _REPORT_OUTCOMES}
        _say(f"Stylizováno a zapsáno: {tally['applied']}, beze změny: "
             f"{tally['unchanged']}, selhalo: {tally['failed']}")
        _print_usage(db, rid)
        if tally["failed"] == len(chapters) and tally["failed"] > 0:
            _say("POZOR: všechny kapitoly selhaly - zkontroluj Codex CLI "
                  "(přihlášení, config.CODEX_MODEL, síť).")
            status = "fatal"
            return 1
        status = "ok"
        return 0
    except FatalRunError as e:
        run_error = str(e)
        _say(str(e))
        return 1
    except KeyboardInterrupt:
        status = "interrupted"
        run_error = "KeyboardInterrupt"
        raise
    except Exception as e:
        run_error = f"{type(e).__name__}: {e}"
        _say(f"Neočekávaná chyba: {type(e).__name__}: {e}")
        return 1
    finally:
        if not backup_state["done"]:
            try:
                os.remove(backup_state["snapshot_path"])
            except OSError:
                pass
        if rid is not None:
            finalization_error = None
            try:
                state.finish_run(db, rid, status)
            except Exception as e:
                finalization_error = f"{type(e).__name__}: {e}"
                _say(f"POZOR: zápis konečného stavu běhu selhal "
                     f"({finalization_error}) - run zůstává nedokončený "
                     "v DB, ale výsledek/chyba výš je platná.")
            _write_polish_report(db, rid, report, codex_model=model,
                                 planned_count=planned_count,
                                 batch_completed=batch_completed, run_status=status,
                                 run_error=run_error,
                                 finalization_error=finalization_error)


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

    p_pol = sub.add_parser("polish", help="stylistický průchod přes Codex (nad hotovými kapitolami)")
    p_pol.add_argument("--only", nargs="+", type=int, default=None,
                       help="jen tyhle kapitoly (musí být status=='done')")
    p_pol.add_argument("--force", action="store_true",
                       help="stylizuj i kapitoly, co už prošly (přepíše dřívější stylizaci)")
    p_pol.set_defaults(func=_cmd_polish)

    sub.add_parser("polish-review", help="web UI: ruční review stylistického "
                   "průchodu, apply/revert per kapitola").set_defaults(
                       func=_cmd_polish_review)

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
