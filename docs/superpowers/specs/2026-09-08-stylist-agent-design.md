# Stylistický průchod přes Codex - design

## Kontext a cíl

Pilotní běh (Turn Coat, kap. 1-3) ukázal: překlad je věcně správný a
konzistentní (glosář, konkordance, kritik to hlídají), ale čeština je místy
neobratná/krkolomná. Uživatel má zkušenost, že OpenAI modely (Codex) píší
plynulejší českou prózu než současný translator (Claude). Cíl: přidat
volitelný krok, který HOTOVÝ, už schválený překlad kapitoly stylisticky
učeše - beze změny faktů, jmen, termínů nebo struktury děje.

Riziko, které to musí zvládnout: Codex jako obecný kódovací agent má sklon
"halucinovat" - přidávat, měnit nebo mazat obsah, když dostane volnou ruku.
Řešení: stylizace se nikdy nepřijme naslepo, vždy prochází stejnou
kontrolou (konkordance + kritik), jakou prochází původní překlad. Neprojde-li,
zahodí se a použije se původní text.

## Mimo rozsah

- Žádná změna translator/critic/revizní smyčky - stylista běží AŽ PO ní, na
  kapitolách se `status == "done"`.
- Žádné opakování/retry stylisty samotného v rámci jednoho volání - jeden
  pokus na kapitolu za běh `polish`, selže-li (timeout, prázdný výstup,
  zamítnutí kontrolou), kapitola zůstává beze změny a lze to zkusit znovu
  příštím spuštěním `polish`.
- Žádné dělení kapitoly na scény pro stylistu - jede na celou kapitolu
  najednou (na rozdíl od translatoru, který pracuje po scénách).
  `config.STYLIST_MAX_CHARS` (kolo 17 IMPORTANT) tohle NEMĚNÍ - je to jen
  RYCHLÉ odmítnutí extrémně dlouhé kapitoly s jasnou zprávou (mimo
  timeout), ne dělení/slučování po částech.
- Žádná migrace DB schématu (žádný nový sloupec) - idempotence a audit
  (viz níže) jdou přes existující `notes` sloupec jako strukturovaný
  záznam, ne přes nový sloupec.
- Žádná plná verze/historie překladu (uchování VŠECH předchozích tvarů
  KAŽDÉ kapitoly zvlášť) - konzistentní s tím, že to nedělá ani revizní
  smyčka dnes (`translator.revise_chapter` taky přepisuje `translated_text`
  bez historie). Místo toho `_cmd_polish` zálohuje CELOU DB (kolo 7
  IMPORTANT - viz `_cmd_polish`/`_backup_db_once` níže) - NEJVÝŠ jedna
  záloha za běh, a jen když se skutečně něco přijme (promuje se těsně
  před PRVNÍM přijatým zápisem; běh bez přijaté změny zálohu nevytvoří
  ani nepřepíše, kolo 24 NIT). Ne rostoucí historie, ale SKUTEČNĚ
  obnovitelná (ne jen hash pro detekci, jako `_stylist_marker` sám o
  sobě).
- Žádná AUTOMATIZOVANÁ/testovaná obnova DB ze zálohy (vlastní CLI
  příkaz, zamykání přes `state.run_lock`) - kolo 16 IMPORTANT navrhlo
  tohle jako opravu, ale obnova zůstává DOKUMENTOVANÝ ruční postup pro
  disaster recovery (`main.py` musí být zastavený, viz `_backup_db_once`
  docstring "Obnova"), stejná úroveň jako zbytek zálohovacího
  mechanismu - plná automatizace by byla nová netriviální schopnost
  (vlastní příkaz, vlastní testy, vlastní zamykání), ne oprava
  existujícího kódu.
- Žádná OS/kontejnerová sandboxizace `codex exec` ani přechod na
  neagentní API bez nástrojů V TÉHLE ITERACI (kolo 18-19 IMPORTANT/
  BLOCKING). Ověřený nález: `--sandbox read-only` dovoluje číst
  LIBOVOLNOU cestu na disku. Rozhodnutí (kolo 19): varianta 1 - povinný
  opt-in `config.STYLIST_ACCEPT_FS_RISK` (default `False`), `polish` bez
  něj NEBĚŽÍ (závazná kontrola PŘÍMO v `stylist.polish()`, kolo 20). Plná
  izolace (varianta 2/3) je zdokumentovaná migrační cesta, ne součást
  téhle spec - viz SAMOSTATNÁ sekce "Bezpečnostní rozhodnutí (kolo 19)"
  hned NÍŽE, kde je i proč jde bezpečně odložit (celý risk je
  soustředěný do `stylist.polish()`, zbytek systému je provider-
  agnostický).
- Codex volání samo o sobě se NEpočítá do `MAX_SPEND_USD`/`llm_calls` -
  jiný poskytovatel, jiné účtování (uživatelův vlastní Codex plán/kvóta).
  **Pozor:** to platí jen pro samotné volání Codexu. Guardrail (kritik,
  viz níže) je normální Anthropic volání přes `_client_factory`/
  `PipelineLLMClient` a DO `llm_calls`/`MAX_SPEND_USD` se počítá stejně
  jako u `run` - `polish` na to musí být interaktivní stejně jako `run`
  (viz `_cmd_polish` níže), ne "jedno velké volání" styl jako `scan`/
  `reference`.

## Bezpečnostní rozhodnutí (kolo 19)

**Ověřený nález (kolo 18, živý test):** `codex exec --sandbox read-only`
omezuje jen ZÁPISY (na `-C` adresář), NE ČTENÍ - agent přečte libovolnou
cestu na disku. `-C` tedy NENÍ bezpečnostní hranice. Prompt injection z
textu knihy (EPUB/zdrojový text je EXTERNÍ data, "legitimně nabytá kniha"
není záruka nezávadnosti obsahu) může nechat Codex přečíst citlivý soubor
(klíče, config, cokoli čitelného) a "vrátit" jeho obsah jako součást
stylizovaného textu. Guardraily (konkordance, kritik, kontrola významu)
běží AŽ POTOM - exfiltrace nastane dřív, uvnitř Codexova běhu.

**Rozhodnutí (uživatel/vlastník projektu, kolo 19):** varianta 1 -
`polish` je za povinným opt-inem (`config.STYLIST_ACCEPT_FS_RISK = True`,
default `False`), s jasnou hláškou při vypnutém stavu. Není default
dostupný. Codex tohle bere jako přijatelné minimum, když funkce není
standardně zapnutá.

**Migrační cesta na bezpečnější variantu (proč jde odložit):** design od
začátku izoluje `stylist.polish()` jako JEDINÉ místo, co mluví s Codexem
- guardraily, orchestrace (`_cmd_polish`), DB záloha, idempotence,
`notes` audit jsou provider-agnostické a žijí MIMO tu funkci. Přechod:
- **→ neagentní OpenAI API bez nástrojů:** FS riziko zmizí úplně →
  `STYLIST_ACCEPT_FS_RISK` gate se ODSTRANÍ. Mění se jen vnitřek
  `polish()` (Popen+stdin+`-o` → API klient, `_codex_argv`/`_resolve_
  codex_cmd`/`_kill_process_tree` odpadnou). Nový OpenAI API klíč +
  billing (zvlášť od Codex CLI subscription); ověřit, že cílový model
  jde přes plain completions API.
- **→ OS/kontejnerová izolace:** `_codex_argv` výstup se obalí
  kontejnerovým voláním (Windows Sandbox / Docker / WSL s přístupem jen
  k nutným datům). Gate se nechá nebo ne podle těsnosti izolace. Velká
  latence na volání, těžké plumbing.
Obě varianty se dotknou HLAVNĚ `stylist.polish()` + konfigurace, ne
zbytku systému.

## Oprava mimo nový modul: `src/agents/critic.py` (kolo 3 nález)

`critic.review()` čte z Codexovy... ne, z Anthropic odpovědi jen
`data.get("findings")` - pole `verdict` se ZAHAZUJE, nikde se nekontroluje
proti `findings`. Odpověď `{"verdict": "revise", "findings": []}` (model
řekl "over pil to znovu", ale nedal žádný nález, který by revizi vynutil)
by tak prošla jako by byla `"pass"` - `has_revise_triggers` i `_polish_rejected`
o ní nemají jak vědět. Tohle je PŘEDEXISTUJÍCÍ mezera v jádru pipeline
(postihuje `run` úplně stejně jako `polish`), ne něco, co zavádí tenhle
plán - ale `polish` staví svou "stejná kontrola jako originál" záruku
přímo na `critic.review()`, takže díra se sem promítá 1:1. Oprava PATŘÍ
do `critic.py`, ne do `stylist.py`/`_cmd_polish` (prospěje oběma
příkazům, ne jen novému):

```python
def review(en_chapter: str, cz_chapter: str, client, *, model=None,
           max_tokens=None) -> list:
    """Vrátí nálezy. Useknutý i rozbitý výstup zkusí jednou znovu, pak vyhodí
    výjimku - `pipeline._run_critic` ji zachytí a podle VOLAJÍCÍHO kontextu
    z toho udělá RŮZNÝ výsledek (kolo 15 NIT - upřesňuje starší tvrzení,
    co počítalo jen s `run`): u `run` (`_cmd_run`) kapitola skončí
    `flagged` (nepředpokládat pass); u `polish` (`_polish_one_chapter`,
    volá se tu STEJNÁ `pipeline._run_critic`) `critic_failed=True` vede
    k `outcome="rejected"` BEZ jakékoli změny statusu kapitoly v DB -
    kapitola zůstává přesně tak, jak byla PŘED stylizací."""
    model = model or config.MODEL_CRITIC
    tokens = max_tokens or config.MAX_TOKENS_CRITIC
    user = (f"ANGLICKÝ ORIGINÁL:\n{en_chapter}\n\n"
            f"ČESKÝ PŘEKLAD:\n{cz_chapter}")

    last_error = None
    for attempt in range(2):
        comp = client.complete(system=SYSTEM_PROMPT, user=user,
                               max_tokens=tokens, model=model)
        if comp.truncated:
            last_error = OutputTruncated(
                "Kritik vrátil useknutý výstup i po zvýšení max_tokens.")
            tokens = tokens * 2      # druhý pokus s větším prostorem
            continue
        try:
            data = extract_json(comp.text)
        except ValueError as e:
            last_error = e
            continue
        # Kolo 7 BLOCKING: `extract_json` slibuje "-> dict", ale za běhu
        # vrátí cokoli platné JSON - top-level pole/string/číslo by na
        # `data.get(...)` spadlo na AttributeError MIMO tenhle retry cyklus
        # (žádný z předchozích `except` bloků ho nechytá).
        if not isinstance(data, dict):
            last_error = ValueError(
                f"Kritik vrátil {type(data).__name__} na nejvyšší úrovni, ne objekt.")
            continue
        raw_findings = data.get("findings")
        # Kolo 4 nález: `data.get("findings")` může být cokoli platné JSON
        # (string, číslo, ...), ne jen seznam/None. `for f in "text"` by
        # iterovalo PO ZNACÍCH a `_to_finding` by na jednom znaku spadlo na
        # AttributeError místo srozumitelné chyby - vynutit typ explicitně.
        if raw_findings is not None and not isinstance(raw_findings, list):
            last_error = ValueError(
                f"Kritik vrátil 'findings' jako {type(raw_findings).__name__}, ne seznam.")
            continue
        # Kolo 7 BLOCKING: TICHÉ přeskočení nedict položek (`isinstance`
        # filtr) by nechalo `{"verdict": "pass", "findings": [1]}` projít
        # jako čistý výsledek (findings=[1] → po filtru prázdné, verdikt
        # "pass" sedí) - ale [1] je zjevně poškozená odpověď, ne "žádný
        # nález". Jakákoli nedict položka = celá odpověď je nedůvěryhodná.
        if raw_findings and any(not isinstance(f, dict) for f in raw_findings):
            last_error = ValueError(
                "Kritik vrátil 'findings' s položkou, co není objekt.")
            continue
        # Kolo 9 IMPORTANT: existující `_to_finding` (v `critic.py`, mimo
        # tenhle plán) tiše DOMÝŠLÍ chybějící/neplatné `severity`/`type` na
        # bezpečné "minor"/"fidelity" - `{"severity": 0}` by tak prošlo jako
        # neškodný "minor" nález (0 je falsy → `0 or "minor"` = "minor"),
        # i když jde o zjevně poškozenou položku, ne o "žádná závažnost
        # neuvedena". Stejná filozofie jako o pár řádků výš (nedict položka
        # = celá odpověď nedůvěryhodná) - položka se špatným enum polem
        # celou odpověď zneplatní, místo aby se tiše "opravila" na bezpečnou
        # hodnotu, kterou `_to_finding` samo nabízí jako fallback (ten
        # zůstává, ale díky týhle kontrole ho `review()` už reálně
        # nevyužije).
        if raw_findings and any(
                f.get("severity") not in ("critical", "minor")
                or f.get("type") not in ("fidelity", "fluency", "register")
                for f in raw_findings):
            last_error = ValueError(
                "Kritik vrátil 'findings' s položkou s neplatným "
                "'severity'/'type'.")
            continue
        # Kolo 5 IMPORTANT: `verdict` mimo "pass"/"revise" (chybí, jiný typ,
        # nesmyslná hodnota) se dřív tiše bralo jako "ne revise", takže
        # prázdné/poškozené `findings` + neplatný verdikt vyšly jako klidné
        # "pass". Modul sám tvrdí "rozbitý výstup vede k retry a výjimce" -
        # tohle je přesně ten rozbitý případ, který tvrzení nesplňovalo.
        if data.get("verdict") not in ("pass", "revise"):
            last_error = ValueError(
                f"Kritik vrátil neplatný verdikt: {data.get('verdict')!r}.")
            continue
        findings = [_to_finding(f) for f in (raw_findings or [])]
        # Rozpor verdikt vs. findings (kolo 3 plan-consensus nález): model
        # řekl "revise", ale nedal nález, co by to samo vynutilo -
        # `has_revise_triggers`/`_polish_rejected` by o tom nevěděly a
        # nekonzistentní odpověď by tiše prošla jako čistá. Radši synteticky
        # vynutit revizi, než nechat nesoulad projít.
        if data.get("verdict") == "revise" and not any(
                f["action"] == "revise" for f in findings):
            findings.append({
                "source": "critic", "type": "fidelity", "severity": "critical",
                "action": "revise", "term_id": None, "expected": None,
                "actual": None, "cz_excerpt": None,
                "issue": "Kritik označil verdikt jako 'revise', ale nevrátil "
                        "žádný nález odpovídající závažnosti - rozpor v "
                        "odpovědi modelu.",
                "suggestion": None})
        return findings
    raise last_error
```

Testy (do `tests/test_critic.py`):
- `verdict="revise"` + prázdné `findings` → `review()` vrátí neprázdný
  seznam s aspoň jedním `action=="revise"` nálezem.
- `findings` je string místo seznamu (`{"verdict": "pass", "findings": "ok"}`)
  → `review()` to bere jako rozbitou odpověď (retry, pak `ValueError`/
  `OutputTruncated`), ne `AttributeError` z iterace po znacích (kolo 4
  BLOCKING).
- `findings` obsahuje řádek, co NENÍ dict (např. `[1, 2]`) → CELÁ odpověď
  se bere jako rozbitá (retry, pak výjimka) - ne tiché přeskočení té
  položky (kolo 7 BLOCKING - `{"verdict": "pass", "findings": [1]}` by
  jinak prošlo jako čistý výsledek s prázdnými `findings`, ačkoli `[1]`
  je zjevně poškozená odpověď).
- `verdict` chybí, nebo je jiná hodnota než `"pass"`/`"revise"` (např.
  `"maybe"`, `null`, `42`) → bere se jako rozbitá odpověď (retry, pak
  výjimka), i kdyby `findings` bylo prázdné (kolo 5 IMPORTANT - dřív by
  tohle tiše prošlo jako "pass").
- `extract_json` vrátí NEDICT na nejvyšší úrovni (např. `[{"verdict":
  "pass"}]` - pole místo objektu) → bere se jako rozbitá odpověď (retry,
  pak výjimka), ne `AttributeError` z `data.get(...)` na poli (kolo 7
  BLOCKING).
- `findings` obsahuje položku BEZ `severity` (např. `{"type": "fidelity",
  "issue": "..."}`, klíč úplně chybí) → CELÁ odpověď se bere jako rozbitá
  (retry, pak výjimka) - `_to_finding` by chybějící `severity` tiše
  domyslelo na `"minor"`, tenhle test ověřuje, že `review()` k tomu
  vůbec NEDOJDE (kolo 9/11 IMPORTANT).
- `findings` obsahuje položku s NEPLATNOU hodnotou `severity` (např.
  `{"severity": 0, ...}` - Python `0` je falsy, `_to_finding`'s `raw.
  get("severity") or "minor"` by ho tiše nahradilo za `"minor"`) → CELÁ
  odpověď se bere jako rozbitá (kolo 9/11 IMPORTANT - přesně ten
  konkrétní gap, co motivoval opravu).
- `findings` obsahuje položku s NEPLATNOU hodnotou `type` (např.
  `{"severity": "critical", "type": "grammar", ...}` - mimo deklarovaný
  enum `fidelity`/`fluency`/`register`) → CELÁ odpověď se bere jako
  rozbitá (kolo 9/11 IMPORTANT).
- Oba pokusy (retry) vrátí findings se stejnou neplatnou `severity`/`type`
  → `review()` nakonec vyhodí `last_error` (`ValueError`), ne že by po
  druhém pokusu neplatnost tiše prošla (kolo 9/11 IMPORTANT - ověřuje, že
  validace platí na KAŽDÉM pokusu retry smyčky, ne jen na prvním).

## Oprava mimo nový modul: `src/state.py` (kolo 5 BLOCKING)

`_polish_one_chapter` volalo `concordance.check_chapter`/`build_mentions`
s `rendered_terms=[]`. To je horší, než jen ztráta provenience (jak jsem
to hodnotil v kole 1-4): `concordance.examined_terms()` zařadí termín do
kontroly JEN když je v EN textu přesná shoda povrchu, NEBO je v
`rendered_terms`. Termín, který translator zachytil VÝHRADNĚ přes vlastní
hlášení (`cz_as_used`) - typicky proto, že EN text ho zmiňuje opisně,
zájmenem, nebo v tvaru, co neodpovídá přesně `canonical_en`/`aliases` -
by se s `rendered_terms=[]` u `polish` vůbec NEZKOUMAL. Kdyby stylista
takový termín nenápadně změnil, nezachytí to ANI baseline, ANI `after`
nález - úplná slepá skvrna, ne jen chybějící metadata.

Oprava: `state.py` potřebuje malý getter (žádná nová infrastruktura -
stejný vzor jako `get_chapter`/`chapters_by_status`) pro mentions JEDNÉ
konkrétní kapitoly, co dnes chybí (`all_term_mentions`/
`chapters_mentioning_term` jsou agregátní přes VÍC kapitol):

```python
def chapter_mentions(db_path: str, chapter_idx: int) -> list:
    """Mentions JEDNÉ kapitoly - na rozdíl od `all_term_mentions`
    (agregátní, přes víc kapitol) tohle `polish` potřebuje jako VSTUP pro
    `concordance.check_chapter`/`build_mentions` (rendered_terms), aby
    nepřišel o termíny zachycené jen translatorovým vlastním hlášením."""
    with connect(db_path) as conn:
        rows = conn.execute(
            "SELECT term_id, cz_form, scene_idx, source FROM term_mentions "
            "WHERE chapter_idx=? ORDER BY id", (chapter_idx,)).fetchall()
    return [dict(r) for r in rows]
```

Test (do `tests/test_state.py`): naplnit `term_mentions` pro kapitolu 1 a
2 přes `replace_term_mentions`, ověřit že `chapter_mentions(db, 1)` vrátí
JEN řádky kapitoly 1, ve vloženém pořadí, VČETNĚ sloupce `source`.

Test provenience (do `tests/test_cli.py`, kolo 20 IMPORTANT): kapitola má
v `term_mentions` mix `source="rendered"` a `source="detected"` řádků.
Po `_polish_one_chapter` (úspěšný průchod) ověřit, že `rendered_terms`
předané do `concordance.check_chapter`/`build_mentions` obsahovalo JEN
`rendered` řádky - `detected` mention se NESMÍ po průchodu uložit jako
`rendered` (falešná provenience). `detected` termíny concordance
dohledá sama z EN/glosáře.

## Architektura

Nový modul `src/agents/stylist.py`, nový CLI příkaz `python main.py polish`.
Žádný zásah do `src/pipeline.py` ani `process_chapter` - stylista je
samostatný, po běhu `run` spustitelný krok, ne součást hlavní smyčky.

```
python main.py run       # scout → translator → kritik → revize (jako dnes)
python main.py polish    # NOVÉ: nad status=="done" kapitolami, volitelné
```

### `config.py` (nové hodnoty)

```python
# --- stylistický průchod přes Codex --------------------------------------
# Prázdné = `polish` odmítne běžet (auditní záznam potřebuje vědět, JAKÝ
# model se skutečně použil - "necháme na výchozím CLI" by časem přestalo
# být dohledatelné, viz kolo 2 plan-consensus review).
CODEX_MODEL = ""
# Timeout na jedno volání `codex exec` (kolo 17 IMPORTANT). `stylist.
# polish`'s parametr `timeout` je od kola 22 `= None` a bez explicitní
# hodnoty spadne SEM (dřív byl natvrdo `= 180`, veřejné volání config
# obcházelo). Dlouhá kapitola může legitimně potřebovat víc času -
# hodnota jde upravit BEZ zásahu do kódu.
STYLIST_TIMEOUT_SECONDS = 180
# Hrubý bezpečnostní strop na délku kapitoly pro stylistický průchod
# (kolo 17 IMPORTANT) - součet znaků EN+CZ. NENÍ přesný odhad tokenového
# limitu konkrétního modelu (ten je uživatelsky konfigurovaný přes
# CODEX_MODEL, jeho přesný kontext se odsud nedá spolehlivě zjistit) -
# je to konzervativní, ručně nastavitelná pojistka, co dá RYCHLÉ a JASNÉ
# "kapitola je moc dlouhá" hlášení MÍSTO čekání na timeout, co by u
# extrémně dlouhé kapitoly stejně nikdy neuspěl. ~60 000 znaků je hrubě
# desetitisíce slov EN+CZ dohromady - běžná kapitola bezpečně projde,
# extrémně dlouhá dostane rychlé, srozumitelné selhání.
STYLIST_MAX_CHARS = 60_000
# Bezpečnostní opt-in (kolo 19 BLOCKING) - `polish` volá agentní `codex
# exec`, který má (OVĚŘENO živě, viz bezpečnostní detail 6 v `stylist.
# polish` docstringu) NEOMEZENÉ ČTENÍ celého souborového systému. Prompt
# injection z textu knihy tak MŮŽE nechat Codex přečíst a "vrátit" obsah
# citlivého souboru dřív, než výstupní kontroly vůbec proběhnou.
# `polish` proto BĚŽÍ JEN, když je tahle hodnota výslovně `True` - není
# to default. Nastavení `True` = "rozumím, že tenhle příkaz spouští
# agenta se čtecím přístupem k celému disku nad textem knihy, a beru to
# riziko". Migrace na bezpečnější variantu (neagentní API bez nástrojů,
# nebo OS/kontejnerová izolace) tohle celé nahradí - viz sekce
# "Bezpečnostní rozhodnutí (kolo 19)" níže.
STYLIST_ACCEPT_FS_RISK = False
```

`main.py` navíc potřebuje (kolo 3 nález - `concordance`/`glossary` v
`main.py` dnes NEJSOU importované na modulové úrovni, jen lokálně uvnitř
`_cmd_review`; `_cmd_polish`/`_polish_one_chapter` je ale potřebují na
každé volání, proto na úrovni modulu):

```python
import hashlib
import sqlite3
import time
from src import concordance, glossary
```

(`sqlite3` pro `Connection.backup()` - konzistentní snapshot DB před
`polish`, viz kolo 7 IMPORTANT a kolo 14 IMPORTANT níže. Původně `shutil.
copy2` - kolo 14 ho nahradilo SQLite vlastním backup API, `import shutil`
tak v `main.py` runtime kódu už není potřeba. `time` pro `time.monotonic()`
- časový limit `_snapshot_db` proti neomezenému čekání na zamčenou DB,
viz kolo 15 IMPORTANT níže. `collections.Counter` pro `_polish_rejected`
NAVRŽEN v kole 16, ale kolo 17-18 přímým ověřením `concordance.py`
potvrdilo, že je zbytečný - `check_chapter()` sama nikdy nevrátí
duplicitní `(type, term_id, actual)` klíč v jednom volání, takže
množinové srovnání stačí - `import` se do `main.py` nakonec nedostal.)

(`json` už je v importech, `pipeline`/`state`/`FatalRunError` taky.)

### `src/agents/stylist.py`

```python
"""Stylistický průchod přes Codex CLI. Nepřekládá, nemění fakta - jen
učeše plynulost hotové, už schválené české věty.

Codex je obecný kódovací agent, ne jazykový nástroj na míru - jeho výstup
se NIKDY nebere jako důvěryhodný sám o sobě. Volající (main.py _cmd_polish)
musí výsledek znovu prohnat kontrolami: STEJNÝMI, jakými prochází
originální překlad (konkordance + kritik), PLUS DODATEČNÝMI, co originál
nepotřebuje (sekvence čísel, počet odstavců/poměr délky, a CZ-před vs.
CZ-po kontrola zachování významu a rejstříku - originál nemá "před"
verzi k porovnání). To je zde záměrně mimo tenhle modul, aby `stylist.py`
zůstal čistý (jen volání Codexu), bez závislosti na concordance/critic/DB.

Bezpečnostní detaily (kola 1-6, 17-20 a 25 plan-consensus review):
1. Vstup (prompt s EN + celou kapitolou CZ) jde přes STDIN, ne argument
   procesu ani soubor (kolo 4 - ověřeno přímo `codex exec --help`:
   `[PROMPT]` čte ze stdin, když je pozicionální argument `-`) -
   `subprocess.run`/`Popen` s dlouhým textem v argv naráží na limit délky
   příkazové řádky (na Windows ~32 KiB), navíc by byl vidět v seznamu
   procesů. Stdin nemá žádný z těchhle limitů a PŮVODNÍ text kapitoly se
   navíc nezapisuje jako samostatný čitelný soubor (drobný bonus k bodu 5;
   pozor - STYLIZOVANÁ verze se stejně zapíše přes `-o`, viz bod 2, jen
   dočasně a bez záruky bezpečného vymazání).
2. VÝSTUP jde přes `-o out_path`/`--output-last-message` - `codex exec`
   samo zachytí POSLEDNÍ ZPRÁVU agenta a zapíše ji do souboru (capture na
   úrovni CLI, ne akce sandboxovaného procesu - `--sandbox read-only` by
   zápis SAMOTNÉHO agenta blokoval, proto se ho nikdy nežádá, aby cokoli
   zapisoval - kolo 2 nález). Přesně stejný mechanismus jako u
   plan-consensus skillu, ověřeno přímo v tomhle běhu
   (`round-1-codex.md`-`round-4-codex.md` vznikly touhle cestou).
3. `-C` (pracovní adresář) míří na IZOLOVANÝ prázdný dočasný adresář, ne
   na kořen book-translator repa - i v read-only sandboxu čte `codex exec`
   soubory daného adresáře a mohl by sebrat projektové instrukce
   (AGENTS.md apod.), které by ho zmátly o vlastní roli. Se stdin-vstupem
   (bod 1) už tenhle adresář neslouží ke čtení ničeho - jen jako izolovaný
   `-C` kořen a cíl pro `-o`.
4. Executable se hledá přes `shutil.which` - na Windows je Codex CLI
   typicky `codex.cmd`, holé `"codex"` v `subprocess.run(shell=False)`
   často neuspěje (kolo 2 nález).
5. `--ephemeral` (kolo 4 IMPORTANT, ověřeno `codex exec --help`: "Run
   without persisting session files to disk") - Codex CLI si ukládá
   historii relací nezávisle na tom, co uklidí `TemporaryDirectory`. Bez
   `--ephemeral` by text knihy mohl přežít v Codexově vlastní session
   historii i po smazání dočasného adresáře - `--ephemeral` tomu
   předchází přímo u zdroje.
6. `--ignore-user-config` (kolo 17 IMPORTANT, ověřeno přímo `codex exec
   --help`: "Do not load `$CODEX_HOME/config.toml`; auth still uses
   `CODEX_HOME`") - `-C work_dir` izoluje jen PRACOVNÍ ADRESÁŘ, ne
   uživatelův GLOBÁLNÍ Codex config (`~/.codex/config.toml`), který může
   nést libovolné MCP servery a pluginy - ty se BEZ týhle vlajky načtou
   při každém spuštění bez ohledu na `-C`. Dvojí důvod: (a) SPOLEHLIVOST -
   tenhle samotný plan-consensus proces opakovaně narazil na `codex exec`
   viset na startu kvůli MCP serveru v uživatelově globálním configu bez
   vlastního timeoutu (síťový handshake, auth) - stejné riziko by
   `polish` v PRODUKCI zdědilo při KAŽDÉM spuštění; (b) ÚTOČNÁ PLOCHA -
   ignorováním uživatelského configu se nenačtou žádné DALŠÍ MCP nástroje
   nad rámec toho, co `--sandbox read-only` samo povoluje, což zužuje, co
   by prompt injection z textu knihy mohlo zneužít. Autentizace (`auth
   still uses CODEX_HOME`) zůstává funkční - `polish` se dál umí
   přihlásit, jen nenačte pluginy/MCP servery z globálního configu.
   OVĚŘENO PŘÍMO (kolo 17 otevřelo otázku, kolo 18 ji uzavřelo živým
   testem, ne jen čtením `--help`): `--sandbox read-only` DOVOLUJE číst
   LIBOVOLNOU cestu na disku, ne jen `-C` adresář. Přímý test (`codex
   exec --sandbox read-only -C <izolovaný dočasný adresář>` s promptem
   "přečti soubor na <cestě MIMO -C> a vrať přesně jeho obsah") uspěl -
   Codex spustil `Get-Content` na cestě mimo pracovní adresář a vrátil
   přesný obsah souboru. `read-only` tedy omezuje ZÁPISY (na `-C`
   adresář), NE ČTENÍ (to zůstává neomezené na celý souborový systém,
   aspoň na týhle platformě/verzi). Prompt injection z textu knihy by
   TEORETICKY (a teď POTVRZENĚ TECHNICKY MOŽNÉ, ne jen teoreticky) mohla
   nechat Codex přečíst a "vrátit" obsah citlivého souboru jako součást
   stylizovaného textu. `--ignore-user-config` tohle NEŘEŠÍ (jde o rozsah
   ČTENÍ sandboxu, ne o config), jen ho zmírňuje nepřímo (méně MCP
   nástrojů, co by injected prompt mohl přimět něco takového udělat).

   ŘEŠENÍ (kolo 19 BLOCKING, rozhodnutí uživatele/vlastníka projektu):
   `polish` běží JEN za povinným opt-inem `config.STYLIST_ACCEPT_FS_RISK
   = True` (default `False`). ZÁVAZNÁ kontrola je PŘÍMO v `polish()` výš
   (kolo 20 BLOCKING - `polish()` je veřejná funkce, kontrola jen v CLI
   by šla obejít); `_cmd_polish` si nechává vlastní časnou hlášku jen
   jako hezčí UX. Plná OS/kontejnerová sandboxizace nebo přechod na
   neagentní API (kolo 18 navrhlo obojí) je ZDOKUMENTOVANÁ migrační
   cesta pro pozdější iteraci, ne součást tohohle plánu - viz spec
   sekce "Bezpečnostní rozhodnutí (kolo 19)" (v dokumentu NÍŽ), kde je
   i proč jde bezpečně odložit (celé riziko je uvnitř `stylist.polish()`,
   zbytek systému je provider-agnostický). Riziko je OVĚŘENÉ (ne
   domnělé), s povinným canary krokem v "Manuální ověření"."""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

import config
from src.llm.parsing import extract_json

SYSTEM_PROMPT_TEMPLATE = """Jsi redaktor české prózy. Dostaneš anglický
originál a jeho český překlad. Tvůj JEDINÝ úkol: uprav ČESKÝ text tak, aby
zněl plynuleji a přirozeněji - beze změny významu, faktů, jmen postav,
míst nebo termínů, beze změny počtu odstavců nebo pořadí událostí.

PŘÍSNÁ PRAVIDLA:
- Nesmíš nic přidat, co v překladu není (žádné nové věty, detaily, popisy).
- Nesmíš nic vynechat.
- Nesmíš měnit jména, tituly ani zavedené termíny - i kdyby zněly kostrbatě,
  jsou to schválené, závazné tvary.
- Nesmíš měnit tykání/vykání, hlas vypravěče ani rejstřík postav - drž se
  toho, co je v předchozím textu, i v návodu níže (je-li přiložen).
- Nesmíš měnit žádná čísla, procenta ani data.
- Zachovej přesně stejný počet odstavců jako má český text níže.
- Neupravuj žádné soubory na disku. Tvůj jediný úkol je vrátit text jako
  SVOU ODPOVĚĎ.
- Odpověz POUZE opraveným českým textem kapitoly - žádné vysvětlení,
  žádné poznámky, žádné markdown bloky (```), nic navíc kolem.
{guide_section}
--- ANGLICKÝ ORIGINÁL ---
{en_text}

--- ČESKÝ PŘEKLAD K UPRAVENÍ ---
{cz_text}

Odpověz upravenou verzí ČESKÉHO textu - a jenom jí."""


class StylistError(Exception):
    """Codex selhal, vrátil prázdno, timeoutoval, nebo výstup neprošel
    základní strukturální kontrolou. Volající to bere jako 'stylizace se
    nepovedla', ne jako fatální chybu běhu."""


_LINE_ENDING_RE = re.compile(r"\r\n|\r")


def _paragraph_count(text: str) -> int:
    # Kolo 16 NIT: holé `text.split("\n\n")` nezachytí CRLF konce řádků
    # (`\r\n\r\n` neobsahuje dva `\n` za sebou) ani prázdný řádek s jen
    # mezerami/tabulátory. Normalizace na `\n` + rozdělení regexem
    # (prázdný řádek, i s bílými znaky) je odolnější, i když v týhle
    # konkrétní cestě (LLM API text + `open(..., "r")` s výchozím
    # universal-newlines čtením) je CRLF spíš teoretické riziko.
    normalized = _LINE_ENDING_RE.sub("\n", text)
    return len([p for p in re.split(r"\n[ \t]*\n", normalized) if p.strip()])


# Kolo 6 IMPORTANT - PŘEHODNOCENO (kola 4-5 to odmítala jako "mimo rozsah,
# vlastní NLP úloha"): arabské číslice/procenta jsou levné a spolehlivé
# extrahovat, na rozdíl od plného číselného NLP extraktoru. Zachytí
# přehození číslic ("12"→"21"), které LLM kontroly (kritik i
# check_meaning_preserved) mohou přehlédnout, protože oboje zůstává
# "čitelné". Slovně vypsaná čísla ("pět") záměrně MIMO ROZSAH - detekce by
# vyžadovala jazykový slovník/NLP, přesně to draho.
#
# `[   ]?%?` (ne jen `%?`) - kolo 10 IMPORTANT: česká typografie
# píše "12 %" S MEZEROU před znakem procenta, anglická "12%" bez ní. Bez
# týhle úpravy regex mezeru před "%" vůbec nepovoloval, takže na běžném
# českém textu ("12 %") znak "%" NIKDY nezachytil jako součást čísla -
# kontrola "%" byla na reálném českém textu prakticky mrtvá (ztráta "%"
# by prošla beze změny sekvence). Kolo 11 IMPORTANT rozšířilo mezerové
# znaky ze samotné NBSP (U+00A0) i o úzkou nezalomitelnou mezeru (U+202F) -
# LLM výstup (překladač i stylista) může použít kteroukoli variantu,
# regex musí pokrýt obě, ne jen tu nejběžnější. Znaménko (`-12` → `12`)
# ZÁMĚRNĚ MIMO ROZSAH (kola 10-11) - pomlčka je v běžné próze silně
# přetížená (rozsahy stran "12-14", vsuvky s pomlčkou, spojovník ve
# složenině), takže "opravit" znaménko by riskovalo NOVÉ falešné poplachy
# přesně tam, kde dřív žádné nebyly (např. stylista přepíše "strany 12-14"
# na "strany 12 až 14" - legitimní úprava, co by s naivním "-12"→znaménko
# vyšla jako změna čísla). Stejná filozofie jako slovně vypsaná čísla o pár
# řádků výš - cena falešných poplachů na přetíženém znaku je vyšší než
# přínos zachycení řídkého případu úmyslně otočeného znaménka (to navíc
# pořád hlídá `check_meaning_preserved`, jen ne deterministicky).
_NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)?[   ]?%?")


def _number_sequence(text: str) -> list:
    """Vrácí čísla v POŘADÍ VýSKYTU, NESEŘAZENÁ (kolo 13 BLOCKING - dřív
    `_number_multiset` řadila výstup, čímž z kontroly udělala pouhé
    srovnání MNOŽIN. Přehození DVOU RŮZNÝCH čísel mezi dvěma místy v textu
    (např. "3" a "5" prohozené mezi dvěma postavami, nebo den/měsíc
    prohozené v datu - "2026-09-08" → "2026-08-09" dá STEJNOU seřazenou
    množinu {"08","09","2026"} jako originál) by tak prošlo beze
    povšimnutí, přestože jde přesně o tu třídu chyby ("přehození číslic"),
    kterou tahle kontrola má zachytit. Porovnání SEKVENCE (ne množiny)
    tuhle mezeru zavírá - a je to bezpečné, protože `SYSTEM_PROMPT_TEMPLATE`
    výše stylistovi explicitně zakazuje měnit "pořadí událostí" i čísla
    samotná, takže shodná posloupnost čísel je u DODRŽUJÍCÍHO stylisty
    očekávaná, ne jen náhodná shoda.

    DESETINNÝ ODDĚLOVAČ SE NENORMALIZUJE (kolo 14 IMPORTANT, revize kola
    13) - kolo 13 zavedlo normalizaci `,`/`.` s odůvodněním "tečka v už
    přeloženém českém textu je téměř vždy reziduální anglicismus, ne
    záměrně jiná hodnota". Codex v kole 14 dal KONKRÉTNÍ protipříklad,
    co tohle vyvrací: "Python 3.5" (verze softwaru, technický identifikátor,
    ne desetinné číslo) → "Python 3,5" by normalizace tiše PŘIJALA jako
    "jen jinou notaci", přestože jde o VIDITELNÉ poškození technického
    termínu (verzová čísla se v češtině NEpřevádí na desetinnou čárku,
    zůstávají s tečkou jako mezinárodní konvence). Regex `_NUMBER_RE`
    nemá jak rozlišit "desetinné číslo" od "identifikátoru, co vypadá
    jako desetinné číslo" - to by vyžadovalo kontextovou/sémantickou
    analýzu (jaké slovo číslo předchází), přesně tu "drahou NLP úlohu",
    co tenhle deterministický guard záměrně nedělá (viz slovně vypsaná
    čísla/data výš). U bezpečnostní brány je falešné ZAMÍTNUTÍ (stylista
    legitimně opraví "3.5 metru" na "3,5 metru", ale konkordance/
    strukturální kontrola to jednou odmítne jako "změněné číslo",
    kapitola zůstane beze změny) levnější než falešné PŘIJETÍ (skutečná
    korupce identifikátoru tiše projde jako "jen formátování") - proto
    normalizace ZRUŠENA, ne zúžena. Mezerová varianta (obyčejná, NBSP,
    úzká nezalomitelná) před "%" se ODSTRAŇUJE dál (viz komentář u
    `_NUMBER_RE`) - "12 %" a "12%" musí dát STEJNÝ token, jinak by
    legitimní přeformátování mezery prošlo jako falešný poplach; na
    rozdíl od desetinného oddělovače tu neexistuje žádný plausibilní
    identifikátor, kde by mezera před "%" nesla jiný význam."""
    out = []
    for t in _NUMBER_RE.findall(text):
        for space_char in (" ", " ", " "):
            t = t.replace(space_char, "")
        out.append(t)
    return out


def _resolve_codex_cmd(codex_cmd: list) -> list:
    """`codex_cmd[0]` se hledá přes `shutil.which`, jen když je to holé
    jméno bez cesty (testy dávají `sys.executable` - absolutní cestu, tu
    `which` nemusí hledat, stačí ji použít přímo). Chybí-li, `StylistError`
    s jasnou hláškou - ne matoucí `FileNotFoundError` z `subprocess.run`."""
    exe = codex_cmd[0]
    resolved = exe if os.path.isabs(exe) else shutil.which(exe)
    if not resolved:
        raise StylistError(
            f"příkaz {exe!r} nenalezen - je Codex CLI nainstalované a "
            "přihlášené (`codex login`)?")
    return [resolved] + codex_cmd[1:]


# Bezpečnostní přepínače (viz "Bezpečnostní detaily" v `polish` docstringu):
# read-only sandbox, izolovaný `-C`, `--ephemeral` (nepersistovat session),
# `--ignore-user-config` (nenačítat globální MCP/pluginy - kolo 17; ověřený
# důvod SPOLEHLIVOSTI - viset na startu MCP serveru - plus vedlejší zúžení
# útočné plochy). Vstup stdinem (`-`), výstup přes `-o`.
#
# `--ignore-rules` se VĚDOMĚ NEPOUŽÍVÁ (kolo 23 ho přidalo, kolo 25 vrátilo):
# ten flag NEnačte user/project execpolicy `.rules`, čímž útočnou plochu
# ROZŠIŘUJE, ne zužuje - `codex exec` je agentní a shell příkazy SPOUŠTÍ
# (canary test v `polish` docstringu bod 6 - Codex spustil `Get-Content`),
# takže případná restriktivní pravidla `forbidden`/`prompt` v uživatelových
# `.rules` můžou exfiltraci omezit. Kolo-23 zdůvodnění ("stylista nespouští
# shell příkazy, nejrestriktivnější execpolicy") bylo obrácené a věcně chybné.
_CODEX_STATIC_FLAGS = ["exec", "--sandbox", "read-only", "--skip-git-repo-check",
                       "--ephemeral", "--ignore-user-config"]


def _codex_argv(codex_cmd: list, work_dir: str, out_path: str,
                codex_model: str | None) -> list:
    """JEDINÉ místo v PRODUKCI, kde se skládá argv pro `codex exec` (kolo
    19 IMPORTANT - dřív inline v `polish`, tři místa co se rozjížděla).
    Volá to `polish()` a odkazuje "Manuální ověření" canary. Argv test
    (`test_polish_invokes_codex_with_expected_argv`) ho VĚDOMĚ NEVOLÁ -
    má ručně zapsaný oracle, aby zachytil i odstranění `--sandbox
    read-only`/`--ephemeral`/atd. z týhle funkce (kolo 20 IMPORTANT)."""
    argv = list(codex_cmd) + _CODEX_STATIC_FLAGS + ["-C", work_dir, "-o", out_path]
    if codex_model:
        argv += ["-m", codex_model]
    argv.append("-")   # prompt jde stdinem - viz `polish` docstring bod 1
    return argv


def _kill_process_tree(proc) -> None:
    """`subprocess.run(timeout=...)`/`Popen.kill()` na Windows ukončí jen
    PŘÍMÉHO potomka (cmd.exe/codex.cmd wrapper) - `codex.cmd` spouští
    `node.exe` jako DALŠÍHO potomka, který by na timeoutu běžel dál a čerpal
    Codex kvótu (kolo 5 IMPORTANT). `taskkill /T /F` ukončí celý strom
    procesů, ne jen jeden PID.

    Kolo 6 IMPORTANT: `taskkill` může SELHAT (proces mezitím sám skončil,
    nedostatečná oprávnění) - bez fallbacku by volající čekal na proces,
    co se nikdy neukončí. `proc.kill()` jako záchranná síť (ukončí aspoň
    hlavní proces, i když ne nutně celý strom) - lepší než nic.

    Kolo 7 IMPORTANT: `taskkill` sám potřebuje VLASTNÍ timeout - bez něj by
    tahle funkce (volaná právě proto, že něco viselo) mohla sama viset na
    `taskkill`, a fallback na `proc.kill()` by se nikdy nespustil. `timeout=10`
    + `except (TimeoutExpired, OSError)` řeší i tenhle vnořený případ."""
    killed_tree = False
    if sys.platform == "win32":
        try:
            result = subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                                    capture_output=True, timeout=10)
            killed_tree = result.returncode == 0
        except (subprocess.TimeoutExpired, OSError):
            killed_tree = False
    if not killed_tree:
        try:
            proc.kill()
        except OSError:
            pass


def polish(en_text: str, cz_text: str, *, timeout: int | None = None,
           codex_cmd: list[str] | None = None,
           codex_model: str | None = None,
           guide_block: str = "") -> str:
    """Vrací upravený český text. Zvedá StylistError při jakémkoli selhání
    NEBO když výstup neprojde levnou strukturální kontrolou (viz níže) -
    volající (main.py) na to reaguje ponecháním původního textu, ne pádem.

    ZÁVAZNÁ bezpečnostní brána (kolo 20 BLOCKING): bez `config.STYLIST_
    ACCEPT_FS_RISK is True` funkce rovnou vyhodí `StylistError` - `codex
    exec` má ověřený neomezený čtecí přístup k disku (bezpečnostní detail
    6 níž + spec sekce "Bezpečnostní rozhodnutí (kolo 19)"). Kontrola je
    TADY, ne jen v `_cmd_polish`, protože tohle je veřejná funkce.

    `codex_cmd` jde přepsat v testech (`[sys.executable, str(fake_script)]`)
    - produkční výchozí je `["codex"]` (přes `shutil.which`, viz
    `_resolve_codex_cmd`). Vždy seznam, ne string - string by `subprocess.run`
    vzal jako JEDEN spustitelný soubor s mezerou ve jméně, ne jako "spusť
    python se skriptem jako argumentem".

    `guide_block` (kolo 6 IMPORTANT) - stejný text jako `guide_
    as_prompt_block(guide)`, co dostává translator (`translate_scene` i
    `revise_chapter` v `pipeline.process_chapter`) - NE kritik
    (`pipeline._run_critic` volá `critic.review(en, cz, client)` bez
    návodu, kolo 17 NIT opravuje dřívější nepřesné "translator/kritik",
    ověřeno přímo v `src/pipeline.py`). Stylista bez něj NEVÍ o
    rozhodnutích tykání/vykání, hlasu vypravěče ani rejstříku (EN samo
    tuhle informaci nenese - kritik EN-vs-CZ na to nemá signál), takže by
    ho mohl nepozorovaně změnit. Prázdný string,
    když návod není k dispozici (volitelný parametr, ne tvrdý požadavek).

    Levná STRUKTURÁLNÍ kontrola (počet odstavců, poměr délky, sekvence
    čísel) běží tady, PŘED tím, než se výsledek vůbec vrátí volajícímu -
    je zadarmo (žádné LLM volání) a odchytí hrubé selhání (uťatý/zkrácený
    výstup, přehozená číslice) dřív, než se zaplatí za drahou kritikovu
    kontrolu v `_cmd_polish`. Nenahrazuje kritika (ten hlídá VÝZNAM, ne
    strukturu) - jsou to nezávislé sítě.

    `config.STYLIST_MAX_CHARS` guard (kolo 17 IMPORTANT) - běží HNED, PŘED
    `_resolve_codex_cmd`/samotným voláním Codexu. Extrémně dlouhá kapitola
    by `timeout` (i zvýšený) stejně pravděpodobně vyčerpala, nebo by
    Codex narazil na vlastní kontextový limit modelu - bez týhle kontroly
    by uživatel čekal celý `timeout` nadarmo a dostal jen obecnou
    `StylistError` o timeoutu, ne jasnou zprávu, PROČ to nešlo."""
    # Bezpečnostní opt-in VYNUCEN PŘÍMO TADY (kolo 20 BLOCKING) - ne jen v
    # `_cmd_polish`. `polish()` je veřejná funkce; kontrola jen v CLI
    # obálce by šla obejít přímým voláním. `_cmd_polish` si vlastní
    # časnou hlášku nechává (hezčí UX než N per-kapitolových StylistError),
    # ale JEDINÁ závazná brána je tahle. Testy volající `polish()` přímo
    # musí `config.STYLIST_ACCEPT_FS_RISK` nastavit (autouse fixture).
    if config.STYLIST_ACCEPT_FS_RISK is not True:
        raise StylistError(
            "stylistický průchod je vypnutý: `codex exec` má ověřený "
            "neomezený čtecí přístup k disku, prompt injection z textu "
            "knihy může exfiltrovat citlivý soubor. Nastav "
            "config.STYLIST_ACCEPT_FS_RISK = True, chceš-li to i tak "
            "spustit (viz spec 'Bezpečnostní rozhodnutí (kolo 19)').")
    combined_len = len(en_text) + len(cz_text)
    if combined_len > config.STYLIST_MAX_CHARS:
        raise StylistError(
            f"kapitola je na stylistický průchod moc dlouhá "
            f"({combined_len} znaků EN+CZ, limit "
            f"config.STYLIST_MAX_CHARS={config.STYLIST_MAX_CHARS}) - "
            "přeskakuji, aby se nečekalo na jistý timeout.")
    # Konfigurační invarianty VYNUCENÉ přímo tady (kolo 22 IMPORTANT) -
    # `polish()` je veřejná funkce, nesmí tiše obcházet `_cmd_polish`'s
    # kontroly:
    #  - `codex_cmd`: `None` = "vezmi produkční", `[]` (nebo jiný prázdný)
    #    = chyba volajícího, ne tiché spadnutí na produkční Codex (to by
    #    po opt-inu nečekaně spustilo agenta s přístupem k disku).
    #  - `codex_model`: `None` → `config.CODEX_MODEL`; prázdný = chyba
    #    (auditní záznam MUSÍ znát model, stejně jako u `_cmd_polish`).
    #  - `timeout`: `None` → `config.STYLIST_TIMEOUT_SECONDS` (ne natvrdo).
    if codex_cmd is None:
        codex_cmd = ["codex"]
    if not codex_cmd or not all(codex_cmd):
        raise StylistError("prázdný nebo neúplný codex_cmd - to je chyba "
                           "volajícího, ne důvod spustit produkční Codex.")
    codex_model = ((codex_model if codex_model is not None
                    else config.CODEX_MODEL) or "").strip()
    if not codex_model:
        raise StylistError("chybí model - předej `codex_model` nebo nastav "
                           "config.CODEX_MODEL (audit musí vědět, jaký "
                           "model se použil).")
    # kolo 23 IMPORTANT: `.strip()` se PŘIŘADÍ (ne jen použije k validaci) -
    # jinak by whitespace-padded model prošel a šel s mezerami do `-m`.
    if timeout is None:
        timeout = config.STYLIST_TIMEOUT_SECONDS
    codex_cmd = _resolve_codex_cmd(list(codex_cmd))
    guide_section = (f"\n--- NÁVOD PRO PŘEKLAD (tykání/vykání, hlas, "
                     f"rejstřík - NEPORUŠUJ) ---\n{guide_block}\n"
                     if guide_block else "")
    prompt_text = SYSTEM_PROMPT_TEMPLATE.format(
        en_text=en_text, cz_text=cz_text, guide_section=guide_section)

    # TemporaryDirectory jako context manager (kolo 3 nález) - slouží jako
    # izolovaný `-C` kořen a cíl pro `-o` (VÝSTUP se sem zapíše - vstup jde
    # stdinem, viz docstring bod 1, takže PŮVODNÍ text sem jako soubor
    # nejde; STYLIZOVANÁ verze ano, viz `out_path` níže).
    with tempfile.TemporaryDirectory(prefix="stylist-") as work_dir:
        out_path = os.path.join(work_dir, "out.txt")

        cmd = _codex_argv(codex_cmd, work_dir, out_path, codex_model)

        try:
            # Popen+communicate, ne subprocess.run (kolo 5 IMPORTANT):
            # subprocess.run(timeout=...) na Windows na timeoutu ukončí jen
            # PŘÍMÉHO potomka (cmd.exe/codex.cmd wrapper) - `codex.cmd`
            # spouští node.exe jako DALŠÍHO potomka, který by běžel dál a
            # čerpal kvótu. `Popen` dá přístup k `.pid`, aby šlo při
            # timeoutu ukončit CELÝ strom přes `_kill_process_tree`.
            #
            # `encoding="utf-8"` EXPLICITNĚ (kolo 5 BLOCKING) - bez něj
            # `text=True` použije lokální kódování OS; na Windows to bývá
            # cp1252, které český prompt (diakritika) nezakóduje a volání
            # spadne na `UnicodeEncodeError` ještě PŘED spuštěním Codexu.
            proc = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    text=True, encoding="utf-8", cwd=work_dir)
        except OSError as e:
            # Kolo 8 IMPORTANT: `FileNotFoundError` (podtřída `OSError`)
            # nestačí - `PermissionError` (soubor existuje, ale není
            # spustitelný) a další `OSError` varianty by unikly jako
            # neošetřená výjimka mimo `StylistError` kontrakt.
            raise StylistError(
                f"příkaz {codex_cmd!r} se nepodařilo spustit ({type(e).__name__}: "
                f"{e}) - je Codex CLI nainstalované a přihlášené?")
        try:
            stdout, stderr = proc.communicate(input=prompt_text, timeout=timeout)
        except subprocess.TimeoutExpired:
            _kill_process_tree(proc)
            try:
                # OMEZENÝ wait (kolo 6 IMPORTANT) - i po taskkill/kill se
                # čeká jen konečně dlouho, ne navždy, kdyby ukončení samo
                # selhalo (proces uvízlý v nepřerušitelném stavu apod.).
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                pass   # udělali jsme, co šlo - nenecháme volajícího viset
            raise StylistError(f"codex exec překročil timeout {timeout}s.")

        if proc.returncode != 0:
            raise StylistError(
                f"codex exec skončil s kódem {proc.returncode}: "
                f"{stderr[:500]}")
        if not os.path.exists(out_path):
            raise StylistError(
                "codex exec nevytvořil výstupní soubor (-o) - žádná "
                "poslední zpráva k zachycení.")
        with open(out_path, "r", encoding="utf-8") as f:
            styled = f.read().strip()

    if not styled:
        raise StylistError("codex exec vrátil prázdnou odpověď.")
    # Obrana proti tomu, že model přesto obalí odpověď do markdown bloku
    # navzdory promptu (kolo 4 NIT) - deterministická kontrola, ne spoléhání
    # jen na to, že model poslechne pokyn "žádné markdown bloky".
    if styled.startswith("```") or styled.endswith("```"):
        raise StylistError(
            "odpověď je obalená v markdown bloku (```) navzdory pokynu - "
            "podezřelý formát, radši zamítnout.")

    # Levná strukturální kontrola - viz docstring. Prahy jsou schválně
    # volné (skutečnou kontrolu obsahu dělá až kritik v _cmd_polish) -
    # cílem je odchytit JEN hrubé selhání (uťatý výstup, smazaný obsah).
    if _paragraph_count(styled) != _paragraph_count(cz_text):
        raise StylistError(
            f"počet odstavců se liší ({_paragraph_count(styled)} vs. "
            f"{_paragraph_count(cz_text)} originál) - podezření na "
            "useknutý nebo přepsaný výstup.")
    ratio = len(styled) / max(1, len(cz_text))
    if not (0.5 <= ratio <= 1.5):
        raise StylistError(
            f"délka výstupu se od originálu liší {ratio:.1f}x - "
            "podezření na useknutý nebo přepsaný výstup.")
    # Sekvence arabských číslic (kolo 6 IMPORTANT, revize kol 4-5, ŘAZENÍ
    # odstraněno kolo 13 BLOCKING - viz `_number_sequence` docstring) -
    # levné, deterministické, fail-closed. Zachytí přehození číslic
    # ("12"→"21") I přehození DVOU RŮZNÝCH čísel mezi sebou (na rozdíl od
    # dřívější seřazené verze), co LLM kontroly (kritik,
    # check_meaning_preserved) mohou přehlédnout, protože oboje zůstává
    # "čitelné". Slovně vypsaná čísla mimo rozsah.
    before_nums, after_nums = _number_sequence(cz_text), _number_sequence(styled)
    if before_nums != after_nums:
        raise StylistError(
            f"čísla v textu se změnila ({before_nums} → {after_nums}) - "
            "podezření na faktickou změnu, ne jen styl.")
    return styled


MEANING_CHECK_PROMPT = """Dostaneš dvě verze stejného českého textu - PŘED
a PO stylistické úpravě. Posuď DVĚ VĚCI zvlášť:

1. VÝZNAM - fakta, kdo co řekl/udělal, počet/pořadí událostí, jména, čísla.
   Rozdíly ve slovosledu, synonymech nebo plynulosti věty NEJSOU význam -
   ty ignoruj.
2. REJSTŘÍK - tykání/vykání mezi postavami, formálnost oslovení, hlas
   vypravěče (ironický/vážný/atd.). I drobná změna (např. "ty" → "vy" u
   jedné repliky) se počítá.

Vrať POUZE JSON:
{{"meaning_changed": true | false,
 "register_changed": true | false,
 "issue": "stručně co se změnilo (když je aspoň jedno true)"}}

--- PŘED ---
{cz_before}

--- PO ---
{cz_after}"""


def check_meaning_preserved(cz_before: str, cz_after: str, client, *,
                            model=None, max_tokens=None) -> list:
    """Třetí, nezávislá kontrolní síť (kolo 2 nález): `critic.review`
    srovnává EN vs. CZ-po, což nemusí odhalit posun, který je vůči EN
    pořád "obhajitelný", ale liší se od PŮVODNÍHO schváleného výkladu.
    Tahle funkce srovnává přímo CZ-před vs. CZ-po - jiná otázka, jiný
    nález. Od kola 7 kontroluje i REJSTŘÍK (tykání/vykání, hlas vypravěče)
    - prompt sám stylistovi říká, ať registr nemění (viz `guide_block` v
    `polish()`), ale žádná vrstva to dřív VERIFIKOVAT neuměla - kritik na
    to nemá signál (EN sám tykání/vykání nenese) a tahle funkce dřív
    kontrolovala jen VÝZNAM v užším smyslu. Vrací seznam nálezů ve stejném
    tvaru jako `concordance`/`critic` (typ `"meaning_drift"` nebo
    `"register_drift"`), prázdný seznam = beze změny.

    Anthropic volání (přes standardní `client`, ne Codex) - počítá se do
    `llm_calls`/`MAX_SPEND_USD` stejně jako kritik."""
    def _finding(type_, issue):
        return {"source": "stylist_check", "type": type_, "severity": "critical",
                "action": "revise", "term_id": None, "expected": None,
                "actual": None, "cz_excerpt": None, "issue": issue,
                "suggestion": None}

    model = model or config.MODEL_CRITIC
    max_tokens = max_tokens or config.MAX_TOKENS_CRITIC
    prompt = MEANING_CHECK_PROMPT.format(cz_before=cz_before, cz_after=cz_after)
    comp = client.complete(system="Jsi přesný, střízlivý korektor významu a rejstříku.",
                           user=prompt, max_tokens=max_tokens, model=model)
    if comp.truncated:
        return [_finding("meaning_drift",
                         "kontrola zachování významu/rejstříku useknutá - bereme jako selhání.")]
    try:
        data = extract_json(comp.text)
    except ValueError:
        return [_finding("meaning_drift",
                         "kontrola zachování významu/rejstříku vrátila nečitelnou odpověď - bereme jako selhání.")]
    # `isinstance(..., bool)`, NE `in (True, False)` (kolo 9 IMPORTANT) -
    # v Pythonu `0 == False` a `1 == True`, takže `0 in (True, False)` je
    # `True`. Odpověď `{"meaning_changed": 0}` (model vrátil číslo místo
    # JSON boolu) by tak prošla jako platné "false", i když jde o jiný typ,
    # než jaký prompt žádá - `isinstance` tenhle gap zavírá.
    if not isinstance(data, dict) or not isinstance(data.get("meaning_changed"), bool) \
            or not isinstance(data.get("register_changed"), bool):
        issue = (data.get("issue") if isinstance(data, dict) else None) or \
                "kontrola zachování významu/rejstříku vrátila neplatný tvar - bereme jako selhání."
        return [_finding("meaning_drift", issue)]
    out = []
    if data["meaning_changed"]:
        out.append(_finding("meaning_drift", data.get("issue") or "změnil se význam."))
    if data["register_changed"]:
        out.append(_finding("register_drift", data.get("issue") or "změnil se rejstřík/oslovení."))
    return out
```

**Poznámka k `MODEL_CRITIC`/`MAX_TOKENS_CRITIC`:** existující konfigurační
hodnoty (`critic.review` je používá stejně) - `check_meaning_preserved`
žádnou novou konfiguraci nepřidává, jede na stejném modelu jako kritik.

**Poznámka k `-o` a capture poslední zprávy:** stejný mechanismus jako u
plan-consensus skillu - `codex exec -o <cesta>` zapíše POSLEDNÍ ZPRÁVU
agenta do souboru, capture dělá samotné CLI, ne sandboxovaný proces. To je
DŮLEŽITÉ - `--sandbox read-only` zápis blokuje, takže návod "zapiš do
souboru" by v produkci vždy selhal (kolo 2 nález, viz bezpečnostní detail
2 v docstringu výše). Vstup jde stdinem (kolo 4 - viz bezpečnostní detail 1
v docstringu výše), ne souborem - žádný teoretický strop délky ani soubor
s textem knihy na disku.

## Guardrail: `_cmd_polish` v `main.py`

Tři vrstvy kontroly nad Codexovým výstupem, každá chytá jiný druh selhání:

1. **Strukturální** (`stylist.polish`, zdarma, bez LLM) - počet odstavců,
   poměr délky, sekvence arabských číslic/procent (kolo 6, ŘAZENÍ
   odstraněno kolo 13). Odchytí uťatý/smazaný výstup i přehozenou
   číslici (včetně přehození DVOU RŮZNÝCH čísel mezi sebou).
2. **Kritik** (`pipeline._run_critic`, EN vs. CZ-po) - stejná kontrola
   věrnosti jako u originálního překladu.
3. **Kontrola zachování významu A REJSTŘÍKU** (`stylist.check_meaning_preserved`,
   CZ-před vs. CZ-po, kolo 2) - kritik sám o sobě porovnává jen proti EN,
   což nemusí odhalit posun, který je vůči EN pořád "obhajitelný", ale liší
   se od PŮVODNÍHO schváleného výkladu, ani drift tykání/vykání/hlasu
   vypravěče (EN sám tuhle informaci nenese - kolo 7). Přímé srovnání
   před/po je nezávislá třetí síť právě na obojí.

Kola 1-3 plan-consensus review navíc opravily:

- **`finish_run`** - `try/finally` se `status` proměnnou jako u ostatních příkazů.
- **`interactive=True`** - `polish` je smyčka přes VÍC kapitol s LLM voláním
  (kritik i kontrola významu) na každou, stejně jako `run`, ne "jedno velké
  volání" jako `scan`/`reference`.
- **Pravidlo přijetí srovnává PROTI PŮVODNÍMU stavu, ne absolutně** (kolo 3
  IMPORTANT) - `done` kapitola smí mít i v PŮVODNÍM stavu drobný minor
  nález (to `done`/`has_revise_triggers` nikdy nevylučovalo). Odmítání
  KAŽDÉHO nálezu typu `fidelity`/`omission` bez ohledu na to, jestli tam
  byl už PŘED stylizací, by takové kapitoly navždy zablokovalo, i kdyby
  styl nezhoršil vůbec nic. `_polish_rejected` proto srovnává nálezy PO
  stylizaci s nálezy PŘED - PŮVODNĚ (kolo 3) počítáno z uložených `notes`,
  od kola 4 počítáno ČERSTVĚ (`concordance.check_chapter` nad PŮVODNÍM
  `cz`, se stejným aktuálním glosářem), ne z `notes` - viz kolo 4 bullet
  níže pro důvod téhle změny.
- **Atomický zápis** - `state.commit_chapter_result` (stejná transakce jako
  `process_chapter`) místo tří nezávislých kroků - `notes`/`term_mentions`
  vždy popisují AKTUÁLNÍ (přijatý) text.
- **Per-kapitolová izolace chyb, ale FatalRunError propaguje** -
  `try/except Exception` obaluje CELÉ zpracování JEDNÉ kapitoly (ne jen
  volání `stylist.polish`), ale `FatalRunError` (např. cost guard) se
  explicitně přeposílá ven a ukončí celý `polish` (kolo 2 nález - dřívější
  draft `FatalRunError` z kritika tiše "spolykal" jako `failed += 1`, což
  by cost guard udělalo bezzubým). `KeyboardInterrupt` se v `isinstance`
  kontrole NEKONTROLUJE (kolo 3 NIT) - `except Exception` ho nikdy
  nezachytí, `KeyboardInterrupt` dědí přímo z `BaseException`, takže by to
  byl mrtvý kód; vnější `except KeyboardInterrupt` na úrovni `_cmd_polish`
  stačí sám o sobě.
- **Řízený, POVINNÝ model** - `config.CODEX_MODEL` musí být nastavený
  (ne prázdný) - `_cmd_polish` to zkontroluje HNED na začátku a odmítne
  běžet bez něj. Hodnota se normalizuje (`.strip()`) JEDNOU a stejná
  normalizovaná `model` proměnná se používá všude dál (kolo 3 NIT - dřívější
  draft testoval `.strip()`, ale do CLI/markeru posílal nenormalizovanou
  hodnotu).
- **`_print_usage`** po běhu - kritik i kontrola významu jsou Anthropic
  volání, co se počítají do `llm_calls` stejně jako u `run`.
- **Preflight** (kolo 3 IMPORTANT, upřesněno kolo 22) - `_resolve_codex_
  cmd` (s `shutil.which`) se VOLÁ JEDNOU na začátku `_cmd_polish`, ne
  poprvé až v první kapitole. `polish()` sama `_resolve_codex_cmd` sice
  volá TAKY (na už rozřešené absolutní cestě), ale to je jen levný
  `os.path.isabs` check - `shutil.which` podruhé neproběhne. Chybějící
  CLI je systémový problém (ne per-kapitolové selhání) - bez preflightu
  by `polish` s N kapitolami zbytečně N-krát spustil `stylist.polish`,
  dostal N stejných `StylistError` hlášek a skončil `status="fatal"`
  (všechny kapitoly `failed`, kolo 5/6) - správný koncový stav, ale
  drahá a matoucí cesta k němu (N hlášek "Codex nenalezen" místo jedné
  jasné hlášky HNED na začátku).
- **Detekce beze změny** (kolo 3 IMPORTANT) - vrátí-li Codex text IDENTICKÝ
  s originálem (`styled == cz`), `_polish_one_chapter` to pozná HNED, bez
  volání kritika/kontroly významu (zbytečná platba za kontrolu něčeho, co
  se nezměnilo) a BEZ zápisu `stylist` markeru (jinak by se kapitola
  označila jako "stylizovaná" a `--force` by byl jediná cesta to zkusit
  znovu, přestože se fakticky nic nestylizovalo).

Navíc **idempotence**: `notes` po přijetí nese speciální záznam
`{"source": "stylist", ...}` (stejný tvar jako ostatní nálezy, takže nic
jinde v kódu, co nálezy čte, nespadne na neznámý klíč). Další `polish` bez
`--force` takové kapitoly přeskočí.

```python
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


def _polish_rejected(baseline_concordance: list, after_findings: list,
                     cz_before: str, cz_after: str, glossary_rows: list) -> bool:
    """Srovnává konkordanci PROTI ČERSTVĚ PŘEPOČÍTANÉMU stavu PŘED stylizací
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
    if any(f.get("type") in ("meaning_drift", "register_drift") for f in after_findings):
        return True
    if any(f.get("source") == "critic" and f.get("action") == "revise"
           for f in after_findings):
        return True
    baseline_keys = {_finding_key(f) for f in baseline_concordance}
    new_concordance = [f for f in after_findings
                       if f.get("source") == "concordance"
                       and _finding_key(f) not in baseline_keys]
    if new_concordance:
        return True
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
    for f in after_findings:
        if f.get("source") != "concordance":
            continue
        ftype = f.get("type")
        if ftype not in ("leak", "inconsistency"):
            continue
        # inconsistency: sleduj konkrétní chybný CZ tvar (`actual`).
        surfaces = []
        if f.get("actual"):
            surfaces.append(f["actual"])
        # leak: sleduj VŠECHNY zakázané EN povrchy termínu (canonical +
        # aliasy), ne jen ohlášený `actual` - ale JEN u termínů, co se
        # SKUTEČNĚ mají překládat (keep-untranslated termín má EN povrch
        # SPRÁVNĚ, jeho přibývání není leak).
        if ftype == "leak":
            term = by_id.get(f.get("term_id")) or {}
            canonical = (term.get("canonical_en") or "").strip().lower()
            cz = (term.get("cz") or "").strip().lower()
            if canonical and cz != canonical:
                surfaces += [s for s in ([term.get("canonical_en", "")]
                             + list(term.get("aliases") or [])) if s]
        for s in set(surfaces):
            if (len(concordance.find_form_occurrences(cz_after, s))
                    > len(concordance.find_form_occurrences(cz_before, s))):
                return True
    return False


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
    disaster recovery (main.py musí být zastavený), ne testovaná,
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
    print(f"Záloha DB (stav před tímto během `polish`): {backup_path}")
    backup_state["done"] = True


def _polish_one_chapter(c, glossary_rows, cf, db, model: str, guide_block: str,
                        codex_cmd: list, backup_state: dict):
    """Vrací 'polished' | 'unchanged' | 'rejected' | 'failed'. Výjimky
    NEchytá (kromě `stylist.StylistError` → `"failed"` a záloha/DB zápisu
    → `FatalRunError`, viz níže) - volající (_cmd_polish) rozhoduje, co je
    per-kapitolové (chytit, pokračovat) a co ukončuje celý běh
    (FatalRunError).

    `codex_cmd` je JIŽ rozřešený (`_cmd_polish` ho spočítal jednou v
    preflightu) - `stylist.polish` ho díky tomu nemusí znovu hledat přes
    `shutil.which` na každou kapitolu (kolo 8 NIT)."""
    from src.agents import stylist
    idx, en, cz = c["idx"], c["raw_text"], c["translated_text"]
    try:
        styled = stylist.polish(en, cz, codex_cmd=codex_cmd, codex_model=model,
                                guide_block=guide_block,
                                timeout=config.STYLIST_TIMEOUT_SECONDS)
    except stylist.StylistError as e:
        print(f"Kapitola {idx}: stylista selhal ({e}), ponechávám původní.")
        return "failed"

    if styled == cz:
        print(f"Kapitola {idx}: beze změny (Codex nenavrhl žádnou úpravu).")
        return "unchanged"

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
    critic_findings, critic_failed = pipeline._run_critic(en, styled, cf("critic"))
    findings += critic_findings
    # Kolo 9 NIT: `check_meaning_preserved` je DALŠÍ placené volání
    # (Anthropic request) - když konkordance nebo kritik SAMY o sobě
    # zamítnutí už zaručují (viz `_polish_rejected`), nemá smysl za něj
    # platit. `_polish_rejected` se volá DVAKRÁT (žádná duplicitní
    # rozhodovací logika, jen fail-fast dřív) - poprvé nad tím, co je
    # zadarmo/už stejně zaplaceno, podruhé (jen když první nezamítlo) i s
    # meaning-check nálezy.
    if critic_failed or _polish_rejected(baseline_concordance, findings, cz, styled, glossary_rows):
        print(f"Kapitola {idx}: stylizace zamítnuta kontrolou, ponechávám původní.")
        return "rejected"
    findings += stylist.check_meaning_preserved(cz, styled, cf("stylist_check"))
    if _polish_rejected(baseline_concordance, findings, cz, styled, glossary_rows):
        print(f"Kapitola {idx}: stylizace zamítnuta kontrolou, ponechávám původní.")
        return "rejected"

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
        raise FatalRunError(
            f"Zápis výsledku kapitoly {idx} selhal ({type(e).__name__}: {e}) "
            "- záloha/DB zápis je infrastrukturní selhání, ne per-kapitolová "
            "chyba, celý běh `polish` se zastavuje.") from e
    print(f"Kapitola {idx}: vylepšeno.")
    return "polished"


def _cmd_polish(args) -> int:
    from src.agents import stylist
    db = config.DB_PATH
    # Bezpečnostní opt-in - ČASNÁ HLÁŠKA (kolo 19 BLOCKING, kolo 20 -
    # závazná brána je teď PŘÍMO v `stylist.polish()`, tohle je jen hezčí
    # UX: jeden srozumitelný výpis místo N per-kapitolových StylistError).
    # `codex exec` má ověřeně neomezené ČTENÍ celého disku - prompt
    # injection z textu knihy může exfiltrovat citlivý soubor dřív, než
    # výstupní kontroly proběhnou. Kontrola JAKO PRVNÍ (před `CODEX_MODEL`).
    if config.STYLIST_ACCEPT_FS_RISK is not True:
        print(
            "polish je vypnutý: spouští agentní `codex exec`, který má "
            "ČTECÍ přístup k CELÉMU disku (ověřeno). Prompt injection z "
            "textu knihy tak MŮŽE exfiltrovat citlivý soubor jako součást "
            "stylizovaného textu, dřív než guardraily proběhnou.\n"
            "Chceš-li to i tak spustit, nastav v config.py "
            "`STYLIST_ACCEPT_FS_RISK = True`. Bezpečnější varianty "
            "(neagentní API, kontejner) viz spec sekce "
            "'Bezpečnostní rozhodnutí (kolo 19)'.")
        return 1
    model = (config.CODEX_MODEL or "").strip()
    if not model:
        print("Chybí config.CODEX_MODEL - nastav ho (audit stylizace musí "
              "vědět, jaký model se skutečně použil).")
        return 1
    try:
        # Preflight - JEDNOU ověří a rozřeší executable (levné, žádné
        # skutečné volání Codexu). Chybějící CLI je systémový problém, ne
        # per-kapitolové selhání - bez tohohle by N kapitol vypsalo N
        # stejných chyb (dnes už by run správně skončil "fatal", ne "ok" -
        # kolo 5/6 - ale zbytečně by se to zjišťovalo N-krát). Rozřešený
        # `codex_cmd` se posílá dál (kolo 8 NIT) - `_polish_one_chapter`/
        # `stylist.polish` ho pak NEřeší znovu přes `shutil.which` na
        # každou kapitolu.
        codex_cmd = stylist._resolve_codex_cmd(["codex"])
    except stylist.StylistError as e:
        print(f"Codex CLI není použitelné: {e}")
        return 1

    # `rid`/`backup_state` PŘEDEM na `None` (kolo 14 IMPORTANT, rozšiřuje
    # kola 10/11/13) - CELÝ zbytek příkazu, VČETNĚ výběru kapitol
    # (`chapters_by_status` apod.), je teď uvnitř JEDNOHO try/except/
    # finally. Dřív (kolo 13) byl chráněný jen `shutil.copy2` a to, co po
    # něm následovalo - `chapters_by_status`/`glossary.all_terms`/
    # `load_guide`/`create_run`/`_print_usage` zůstávaly BEZ obecného
    # `except`, takže by nezachycená výjimka propadla jako traceback
    # (STEJNÁ třída chyby jako `_snapshot_db` níž, jen na jiných
    # místech). `backup_state` zůstává `None`, dokud se skutečně nevytvoří
    # (těsně před voláním `_snapshot_db`) - `finally` to zohledňuje.
    rid = None
    status = "fatal"
    backup_state = None
    try:
        all_done = state.chapters_by_status(db, ("done",))
        chapters = all_done
        if args.only:
            wanted = set(args.only)
            chapters = [c for c in all_done if c["idx"] in wanted]
            # Hlásit přeskočené (kolo 4 NIT) - stejný vzor jako `run --only`,
            # ne tiché "nic se nestalo" pro číslo, co není 'done'/už existuje.
            chybi = sorted(wanted - {c["idx"] for c in chapters})
            if chybi:
                print("Přeskočeno (nejsou 'done', nebo neexistují): "
                     + ", ".join(str(i) for i in chybi))
        if not args.force:
            pred_force = len(chapters)
            chapters = [c for c in chapters if not _already_styled(c["notes"])]
            preskoceno_stylizovane = pred_force - len(chapters)
            if preskoceno_stylizovane:
                print(f"Přeskočeno (už stylizováno, zkus --force): "
                     f"{preskoceno_stylizovane}")
        if not chapters:
            print("Žádné kapitoly ke stylizaci.")
            status = "ok"
            return 0

        # Záloha CELÉ DB (kolo 7 IMPORTANT, časování upřesněno kolo 8, ZDROJ
        # dat zpřesněn kolo 9 BLOCKING). Snapshot se pořizuje HNED TADY -
        # PŘED `state.create_run` i před jakýmkoli LLM voláním - protože
        # obojí by jinak DB změnilo dřív, než by líná záloha vůbec proběhla
        # (viz `_backup_db_once`). Snapshot jde do DOČASNÉHO souboru vedle
        # DB; na kanonickou `.pre-polish-backup` cestu se PROMUJE atomicky
        # (`os.replace`) až `_backup_db_once`, těsně před prvním skutečným
        # zápisem výsledku - aby běh, co nakonec nic nezapíše, nepřepsal
        # poslední UŽITEČNOU zálohu z předchozího běhu (stejný důvod jako
        # kolo 8). Pokud se nakonec nic nezapíše (nebo cokoli spadne),
        # dočasný snapshot se ve `finally` smaže.
        backup_state = {"done": False, "snapshot_path": db + ".pre-polish-snapshot"}
        # Kolo 13 BLOCKING: `_snapshot_db` (kolo 14 IMPORTANT nahradilo
        # `shutil.copy2`, viz jeho docstring) sama může vyhodit výjimku
        # (plný disk, práva, neprošlý integrity_check) - `except
        # Exception` o pár řádků níž tohle teď taky pokryje, ale zabalení
        # do `FatalRunError` HNED TADY dává přesnější hlášku (víme, že
        # jde konkrétně o zálohu, ne o obecné "něco spadlo") a
        # zdůrazňuje, že žádný `run` řádek v DB ještě nevznikl.
        try:
            _snapshot_db(db, backup_state["snapshot_path"])
        except Exception as e:
            raise FatalRunError(
                f"Vytvoření zálohy DB selhalo ({type(e).__name__}: {e}) - "
                "zastavuji se PŘED zahájením zpracování, žádný run "
                "nevznikl.") from e

        glossary_rows = glossary.all_terms(db)
        # Stejný blok jako translator (translate_scene i revise_chapter) v
        # pipeline.py dostává přes `_guide_block` - tykání/vykání, hlas
        # vypravěče, rejstřík (kolo 6 IMPORTANT; kolo 17 NIT - NE kritik,
        # `_run_critic` guide_block nedostává). Bez něj stylista neví, co
        # NESMÍ nepozorovaně změnit - EN sám tuhle informaci nenese,
        # kritik na to nemá signál.
        guide_block = guide_mod.guide_as_prompt_block(guide_mod.load_guide(config.GUIDE_PATH))
        rid = state.create_run(db, "polish")
        counts = {"polished": 0, "unchanged": 0, "rejected": 0, "failed": 0}
        cf = _client_factory(rid, interactive=True)
        for c in chapters:
            try:
                outcome = _polish_one_chapter(c, glossary_rows, cf, db, model,
                                              guide_block, codex_cmd, backup_state)
            except FatalRunError:
                raise
            except Exception as e:
                # Neočekávaná chyba u JEDNÉ kapitoly nesmí shodit zbytek
                # dávky - `run` má stejnou filozofii (`_cmd_run` dělá totéž
                # kolem `pipeline.process_chapter`).
                print(f"Kapitola {c['idx']}: neočekávaná chyba "
                      f"({type(e).__name__}: {e}), ponechávám původní.")
                outcome = "failed"
            counts[outcome] += 1

        print(f"Vylepšeno: {counts['polished']}, beze změny: {counts['unchanged']}, "
              f"zamítnuto kontrolou: {counts['rejected']}, selhalo: {counts['failed']}")
        _print_usage(db, rid)
        # Kolo 5 IMPORTANT (opravuje kolo-4 rozpor): "všechno selhalo" musí
        # znamenat status="fatal", ne "ok" - "mechanismus doběhl do konce"
        # neobstálo, protože DB audit (`runs` tabulka) by pak hlásil úspěch
        # u běhu, který fakticky nic neudělal. Nenulový exit kód JDE ruku v
        # ruce se `status="fatal"`, ne místo něj.
        if counts["failed"] == len(chapters) and counts["failed"] > 0:
            print("POZOR: všechny kapitoly selhaly - zkontroluj Codex CLI "
                  "(přihlášení, config.CODEX_MODEL, síť).")
            status = "fatal"
            return 1
        status = "ok"
        return 0
    except FatalRunError as e:
        print(e)
        return 1
    except KeyboardInterrupt:
        status = "interrupted"
        raise
    except Exception as e:
        # Kolo 14 IMPORTANT: cokoli neočekávané MIMO per-kapitolovou smyčku
        # (ta má vlastní `except` výš, viz `_polish_one_chapter` volání) je
        # infrastrukturí/programová chyba (výběr kapitol, glosář, návod,
        # založení runu, výpis spotřeby), ne obsahová - zastavit celý
        # příkaz čistě (`return 1`), ne propadnout jako nezachycený
        # traceback.
        print(f"Neočekávaná chyba: {type(e).__name__}: {e}")
        return 1
    finally:
        # Snapshot, co nikdy nebyl promován (nic se nezapsalo - všechny
        # kapitoly 'unchanged'/'rejected'/'failed', nebo běh spadl dřív, než
        # `_backup_db_once` proběhla - VČETNĚ selhání samotného `_snapshot_
        # db` o pár řádků výš, kolo 11 IMPORTANT) - dočasný soubor po
        # sobě uklidit, ať se nehromadí (kolo 9 BLOCKING oprava - viz
        # snapshot výš). `os.remove` na neexistující/částečný soubor
        # nevadí - `OSError` (podtřída i `FileNotFoundError`) se tiše
        # pohltí. `backup_state is not None` (kolo 14 IMPORTANT) - selže-li
        # něco PŘED jeho vytvořením (`chapters_by_status` apod.), proměnná
        # ještě neexistuje, přístup k ní by `finally` sám havaroval.
        if backup_state is not None and not backup_state["done"]:
            try:
                os.remove(backup_state["snapshot_path"])
            except OSError:
                pass
        # `rid is not None` (kolo 10 IMPORTANT) - `create_run` sám mohl
        # spadnout dřív, než vůbec vrátil `rid`; volat `finish_run` na
        # neexistující/cizí run by bylo horší než ho prostě nevolat (a
        # `NameError` na nedefinovaném `rid` by tenhle `finally` blok
        # samotný havaroval).
        if rid is not None:
            # Kolo 13 IMPORTANT: `finish_run` sám NESMÍ shodit tenhle
            # `finally` - kdyby selhal (STEJNÁ třída chyby, co nás sem
            # často přivedla - plný disk, poškozená DB), NOVÁ výjimka by
            # PŘEBILA tu původní (nebo právě dokončovaný `return`), co
            # `finally` blok zrovna zpracovává (standardní Python chování
            # - výjimka ve `finally` nahradí tu, co propaguje). Volající
            # by tak dostal MATOUCÍ/JINOU chybu a ztratil skutečnou
            # příčinu. Selhání finalizace se jen VYPÍŠE (best-effort),
            # nepřepíše výsledek/chybu, co `finally` právě dokončuje.
            try:
                state.finish_run(db, rid, status)
            except Exception as e:
                print(f"POZOR: zápis konečného stavu běhu selhal "
                      f"({type(e).__name__}: {e}) - run zůstává "
                      "nedokončený v DB, ale výsledek/chyba výš je platná.")
```

Registrace v `_build_parser()`:

```python
p_pol = sub.add_parser("polish", help="stylistický průchod přes Codex (nad hotovými kapitolami)")
p_pol.add_argument("--only", nargs="+", type=int, default=None,
                   help="jen tyhle kapitoly (musí být status=='done')")
p_pol.add_argument("--force", action="store_true",
                   help="stylizuj i kapitoly, co už prošly (přepíše dřívější stylizaci)")
p_pol.set_defaults(func=_cmd_polish)
```

A přidat `"polish"` do `_MUTATING` (drží zámek, mění `data/`).

A doplnit `polish` do modulového docstringu `main.py` (sekce "Fáze
běhu:", kolo 23 NIT - jinak nový příkaz v přehledu chybí):
`polish [--only IDX...] [--force]   stylistický průchod přes Codex (nad
status=="done", volitelné, za opt-inem STYLIST_ACCEPT_FS_RISK)`.

`pipeline._run_critic` už existuje a je přesně to, co polish potřebuje -
volá se modulově-kvalifikovaně (`pipeline._run_critic`), žádná duplikace
kódu kritika. `cf("stylist_check")` používá STEJNOU `_client_factory`
(Anthropic, ne Codex) jako `cf("critic")` - `check_meaning_preserved` je
Anthropic volání, ne volání Codexu (viz jeho vlastní docstring).

## Testování

`stylist.polish()` se testuje s `codex_cmd` ukazujícím na fake skript
(žádné reálné volání Codexu v testech - stejný princip jako `FakeLLMClient`
u Anthropic agentů). `codex_cmd` je VŽDY seznam (`[sys.executable,
str(fake)]`), ne string - viz docstring výše, proč string s mezerou nejde.

**Autouse fixture (kolo 20 BLOCKING, kolo 22):** `stylist.polish()` od
kola 20 tvrdě odmítá bez `config.STYLIST_ACCEPT_FS_RISK is True` a od
kola 22 i bez neprázdného modelu. Test modul má
`@pytest.fixture(autouse=True)`, co pro každý test nastaví OBOJÍ (opt-in
`True`, `CODEX_MODEL` na testovací hodnotu) - jinak by KAŽDÝ test
volající `polish()` bez `codex_model=` spadl. Testy, co CÍLENĚ ověřují
brány, si příslušnou hodnotu přebijí zpět.

```python
@pytest.fixture(autouse=True)
def _stylist_test_config(monkeypatch):
    monkeypatch.setattr(config, "STYLIST_ACCEPT_FS_RISK", True)
    monkeypatch.setattr(config, "CODEX_MODEL", "gpt-5-codex")


def test_polish_refuses_without_fs_risk_optin(tmp_path, monkeypatch):
    """Kolo 20 BLOCKING - PŘÍMÉ volání `polish()` (ne přes `_cmd_polish`)
    s vypnutým opt-inem MUSÍ vyhodit `StylistError`, ne spustit Codex."""
    monkeypatch.setattr(config, "STYLIST_ACCEPT_FS_RISK", False)
    with pytest.raises(stylist.StylistError, match="vypnutý"):
        stylist.polish("EN", "CZ", codex_cmd=["nonexistent-binary"])
    monkeypatch.setattr(config, "STYLIST_ACCEPT_FS_RISK", 1)   # truthy != True
    with pytest.raises(stylist.StylistError, match="vypnutý"):
        stylist.polish("EN", "CZ", codex_cmd=["nonexistent-binary"])


def test_polish_config_invariants(tmp_path, monkeypatch):
    """Kolo 22 IMPORTANT - `polish()` sama vynutí neprázdný codex_cmd a
    neprázdný model."""
    with pytest.raises(stylist.StylistError, match="prázdný nebo neúplný"):
        stylist.polish("EN", "CZ", codex_cmd=[])
    monkeypatch.setattr(config, "CODEX_MODEL", "")
    with pytest.raises(stylist.StylistError, match="chybí model"):
        stylist.polish("EN", "CZ", codex_cmd=["x"], codex_model="")


def test_polish_uses_config_timeout_and_strips_model(tmp_path, monkeypatch):
    """Kolo 23 IMPORTANT - bez `timeout=` se použije `config.STYLIST_
    TIMEOUT_SECONDS` (ne natvrdo 180); whitespace-padded model se
    OŘÍZNE, ne jen zvaliduje."""
    monkeypatch.setattr(config, "STYLIST_TIMEOUT_SECONDS", 999)
    seen = {}
    real_popen = stylist.subprocess.Popen

    class SpyPopen(real_popen):
        def communicate(self, *a, **kw):
            seen["timeout"] = kw.get("timeout")
            return super().communicate(*a, **kw)

    monkeypatch.setattr(stylist.subprocess, "Popen", SpyPopen)
    argv_path = tmp_path / "argv.json"
    fake = tmp_path / "f.py"
    fake.write_text(
        "import sys, json\n"
        f"json.dump(sys.argv, open({str(argv_path)!r}, 'w'))\n"
        "sys.stdin.read()\n"
        "out = sys.argv[sys.argv.index('-o') + 1]\n"
        "open(out, 'w', encoding='utf-8').write('Prvni odstavec upraveny.')\n",
        encoding="utf-8")
    stylist.polish("EN", "Prvni odstavec.", codex_cmd=[sys.executable, str(fake)],
                   codex_model="  gpt-5-codex  ")
    assert seen["timeout"] == 999
    argv = json.loads(argv_path.read_text())
    assert argv[argv.index("-m") + 1] == "gpt-5-codex"   # oříznuté
```

```python
def _fake_codex(tmp_path, body, *, exit_code=0):
    """Fake skript simulující 'codex exec ... -o out_path ...' - najde `-o`
    v argv (přesně jak to `stylist.polish` volá) a zapíše `body` tam. Žádné
    parsování promptu - `-o` je teď skutečný CLI flag (capture poslední
    zprávy), ne cesta zmíněná uvnitř textu."""
    fake = tmp_path / "fake_codex.py"
    # `encoding="utf-8"` explicitně (kolo 12 NIT) - `body!r` může obsahovat
    # český text, `repr()` ho do zdrojáku vloží doslovně (ne uniklý), a
    # `write_text` bez explicitního kódování by na Windows sáhla po
    # lokálním kódování (cp1252), které českou diakritiku (č/ě/ř/š/ž/ů)
    # neumí - STEJNÁ třída chyby, jakou produkční `Popen` řešil v kole 5
    # BLOCKING, jen tady ve fake skriptu pro testy.
    fake.write_text(
        "import sys\n"
        "out = sys.argv[sys.argv.index('-o') + 1]\n"
        f"open(out, 'w', encoding='utf-8').write({body!r})\n"
        f"sys.exit({exit_code})\n",
        encoding="utf-8")
    return [sys.executable, str(fake)]


def test_polish_returns_output_file_contents(tmp_path):
    # Délka/počet odstavců podobné vstupu - jinak by to spadlo na
    # strukturální kontrolu (viz testy níže, které tu kontrolu cíleně testují).
    cmd = _fake_codex(tmp_path, "Prvni odstavec upraveny.\n\nDruhy odstavec upraveny.")
    result = stylist.polish("EN text", "Prvni odstavec.\n\nDruhy odstavec.", codex_cmd=cmd)
    assert result == "Prvni odstavec upraveny.\n\nDruhy odstavec upraveny."


def test_polish_invokes_codex_with_expected_argv(tmp_path):
    """Kolo 9 IMPORTANT: dosavadní testy ověřují jen ROUNDTRIP dat (co
    fake skript dostane na stdinu / vrátí přes `-o`), ne KTERÉ PŘÍZNAKY
    se Codexu skutečně předávají - regrese, co by tiše upustila
    `--ephemeral` nebo přepnula `--sandbox` na jinou hodnotu, by žádný
    stávající automatický test nechytil (jen ruční checklist v "Manuální
    ověření" níže, který se nespouští při každém běhu testů). Fake skript
    si SVŮJ `sys.argv` zapíše do vedlejšího JSON souboru, test ho pak
    přečte a ověří přesný seznam.

    Kolo 10 BLOCKING: `sys.argv` UVNITŘ fake skriptu NEobsahuje interpret
    (`sys.executable`) - to je jen argv[0] procesu na úrovni OS/`Popen`,
    Python ho do `sys.argv` skriptu nezahrnuje. `sys.argv[0]` uvnitř
    skriptu je CESTA KE SKRIPTU samotnému, teprve `sys.argv[1]` je první
    SKUTEČNÝ argument ("exec") - dřívější verze tenhle rozdíl přehlédla
    (`tail = argv[2:]` omylem zahazovalo i "exec", `tail[0] == "exec"` by
    tak VŽDY selhalo). Kolo 10 IMPORTANT: přítomnostní `in` kontrola by
    navíc nechytila duplicitní/přidané nebezpečné přepínače ani špatnou
    hodnotu - test teď porovná CELÝ ocas přesně a ověří i vztah
    `-o == <-C hodnota>/out.txt` (viz `polish()` - `out_path =
    os.path.join(work_dir, "out.txt")`, `work_dir` je STEJNÝ adresář jako
    `-C`)."""
    argv_path = tmp_path / "argv.json"
    fake = tmp_path / "argv_codex.py"
    fake.write_text(
        "import sys, json\n"
        f"json.dump(sys.argv, open({str(argv_path)!r}, 'w'))\n"
        "sys.stdin.read()\n"
        "out = sys.argv[sys.argv.index('-o') + 1]\n"
        "open(out, 'w', encoding='utf-8').write("
        "'Prvni odstavec upraveny.\\n\\nDruhy odstavec upraveny.')\n",
        encoding="utf-8")
    cmd = [sys.executable, str(fake)]
    stylist.polish("EN text", "Prvni odstavec.\n\nDruhy odstavec.",
                   codex_cmd=cmd, codex_model="gpt-5-codex")
    argv = json.loads(argv_path.read_text())
    # argv[0] = cesta k fake skriptu SAMOTNÉMU (interpret není součástí
    # `sys.argv`) - skutečné argumenty začínají od argv[1].
    tail = argv[1:]
    c_idx = tail.index("-C")
    work_dir = tail[c_idx + 1]
    o_idx = tail.index("-o")
    out_path = tail[o_idx + 1]
    # RUČNĚ PŘEPSANÝ očekávaný seznam (kolo 20 IMPORTANT - kolo 19
    # skládalo `expected` stejnou `_codex_argv` funkcí jako produkce,
    # čímž byl test tautologický a nezachytil by odstranění `--sandbox
    # read-only`/`--ephemeral`/`--skip-git-repo-check`). Tady je
    # duplicita mezi implementací a testovacím oracle ZÁMĚRNÁ - test
    # střeží celý bezpečnostní kontrakt argv.
    assert tail == [
        "exec", "--sandbox", "read-only", "--skip-git-repo-check",
        "--ephemeral", "--ignore-user-config",
        "-C", work_dir, "-o", out_path, "-m", "gpt-5-codex", "-",
    ]
    assert out_path == os.path.join(work_dir, "out.txt")


def test_polish_roundtrips_utf8_diacritics(tmp_path):
    """Kolo 5 BLOCKING: bez explicitního `encoding='utf-8'` použije
    `Popen(text=True)` na Windows lokální kódování (typicky cp1252), které
    diakritiku nezakóduje - `UnicodeEncodeError` ještě PŘED spuštěním
    Codexu. Fake skript přečte stdin, VYTÁHNE si jen český text (mezi
    značkami promptu - stejná délka/struktura jako originál, ať neselže na
    strukturální kontrole) a s drobnou úpravou ho napíše do `-o` - test tak
    ověří CELOU cestu tam (stdin) i zpět (-o), ne jen jednu stranu."""
    fake = tmp_path / "echo_codex.py"
    fake.write_text(
        "import sys, re\n"
        "out = sys.argv[sys.argv.index('-o') + 1]\n"
        "received = sys.stdin.read()\n"
        "m = re.search(r'--- ČESKÝ PŘEKLAD K UPRAVENÍ ---\\n(.*?)\\n\\nOdpověz',\n"
        "             received, re.DOTALL)\n"
        "cz = m.group(1)\n"
        "open(out, 'w', encoding='utf-8').write(cz.replace('Řekl', 'Pravil'))\n",
        encoding="utf-8")
    cmd = [sys.executable, str(fake)]
    cz = "CZ: Řekl že středověká věž měří dvě stě čtyřicet stop — nikdo mu nevěřil."
    result = stylist.polish("EN text s pomlčkou — a uvozovkami „jako“ tady.",
                            cz, codex_cmd=cmd)
    assert "Pravil" in result
    assert "středověká věž" in result   # diakritika přežila stdin i zpět


def test_polish_long_input_goes_through_stdin_not_argv(tmp_path, monkeypatch):
    """Dlouhý text (přes limit argv na Windows, ~32 KiB) nesmí selhat - jde
    přes stdin (`Popen.communicate(input=...)`), argument procesu (`-`)
    zůstává úplně stejný bez ohledu na délku vstupu. Fake vrací text
    PODOBNÉ délky/struktury jako vstup, ať neselže na strukturální kontrole -
    testuje se jen to, že dlouhý vstup vůbec projde skrz.

    `monkeypatch` na `config.STYLIST_MAX_CHARS` (kolo 18 IMPORTANT,
    opravuje kolo 17) - tenhle test úmyslně používá vstup PŘES 32 KiB
    (argv limit), ale od kola 17 existuje SAMOSTATNÝ `STYLIST_MAX_CHARS`
    guard (výchozí 60 000 znaků), co by takhle dlouhý vstup (přes 100
    000 znaků) odmítl JEŠTĚ PŘED tím, než by se stdin cesta vůbec
    zkoušela - test by tak ve skutečnosti přestal testovat to, co má
    (stdin mechanismus), a jen tiše ověřoval size guard. Limit se pro
    tenhle test zvedne, aby test zůstal o TOM, co má testovat.

    Fake skript SKUTEČNĚ ČTE STDIN a vytáhne si z něj celý CZ text (kolo
    21 IMPORTANT - dřívější `_fake_codex` stdin vůbec nečetl, takže test
    by prošel i kdyby se dlouhý prompt cestou zahodil/uřízl). Vrátí ho
    (s drobnou úpravou) do `-o` - test tak ověří, že CELÝ vstup dorazil
    přes stdin nepoškozený."""
    monkeypatch.setattr(config, "STYLIST_MAX_CHARS", 1_000_000)
    long_cz = "\n\n".join(["Odstavec o délce, co by se do argv nevešla. " * 800
                           for _ in range(3)])
    assert len(long_cz) > 32 * 1024        # ověř, že test skutečně testuje limit
    fake = tmp_path / "echo_stdin_codex.py"
    fake.write_text(
        "import sys, re\n"
        "out = sys.argv[sys.argv.index('-o') + 1]\n"
        "received = sys.stdin.read()\n"
        "m = re.search(r'--- ČESKÝ PŘEKLAD K UPRAVENÍ ---\\n"
        "(.*?)\\n\\nOdpověz upravenou', received, re.DOTALL)\n"
        "cz = m.group(1)\n"
        "open(out, 'w', encoding='utf-8').write("
        "cz.replace('Odstavec', 'Upraveny odstavec'))\n",
        encoding="utf-8")
    result = stylist.polish("EN", long_cz, codex_cmd=[sys.executable, str(fake)])
    assert "Upraveny odstavec" in result
    # CELÝ vstup dorazil - délka po substituci sedí (fake pracoval s
    # kompletním CZ textem, ne uřízlým).
    assert len(result) == len(long_cz.replace("Odstavec", "Upraveny odstavec"))


def test_polish_raises_on_nonzero_exit(tmp_path):
    cmd = _fake_codex(tmp_path, "cokoli", exit_code=1)
    with pytest.raises(stylist.StylistError):
        stylist.polish("EN", "CZ", codex_cmd=cmd)


def test_polish_raises_on_missing_output_file(tmp_path):
    fake = tmp_path / "noop.py"
    fake.write_text("pass")   # nezapíše žádný výstupní soubor (-o nevznikne)
    with pytest.raises(stylist.StylistError, match="nevytvořil"):
        stylist.polish("EN", "CZ", codex_cmd=[sys.executable, str(fake)])


def test_polish_raises_on_timeout(tmp_path):
    fake = tmp_path / "slow.py"
    fake.write_text("import time; time.sleep(5)")
    with pytest.raises(stylist.StylistError, match="timeout"):
        stylist.polish("EN", "CZ", codex_cmd=[sys.executable, str(fake)], timeout=1)


def test_polish_raises_on_missing_command():
    with pytest.raises(stylist.StylistError, match="nenalezen"):
        stylist.polish("EN", "CZ", codex_cmd=["prikaz-co-neexistuje-xyz"])


def test_polish_raises_stylist_error_on_permission_error(tmp_path, monkeypatch):
    """Kolo 8 IMPORTANT: `PermissionError` (podtřída `OSError`, ne
    `FileNotFoundError`) - soubor existuje, ale není spustitelný. Musí
    dát `StylistError`, ne neošetřenou výjimku mimo modul."""
    def _boom(*a, **kw):
        raise PermissionError("Access is denied")
    monkeypatch.setattr(stylist.subprocess, "Popen", _boom)
    with pytest.raises(stylist.StylistError, match="nepodařilo spustit"):
        stylist.polish("EN", "CZ", codex_cmd=[sys.executable])


def test_kill_process_tree_falls_back_to_proc_kill_when_taskkill_fails(monkeypatch):
    """Kolo 6 IMPORTANT: `taskkill` může selhat (proces mezitím sám skončil,
    nedostatečná oprávnění) - `proc.kill()` musí zafungovat jako záchranná
    síť, ne nechat volajícího čekat na proces, co se nikdy neukončí."""
    monkeypatch.setattr(stylist.sys, "platform", "win32")

    class _FakeCompletedProcess:
        returncode = 1   # taskkill "selhal"

    monkeypatch.setattr(stylist.subprocess, "run",
                        lambda *a, **kw: _FakeCompletedProcess())

    killed = {"called": False}

    class _FakeProc:
        pid = 12345
        def kill(self):
            killed["called"] = True

    stylist._kill_process_tree(_FakeProc())
    assert killed["called"]


def test_kill_process_tree_falls_back_when_taskkill_itself_times_out(monkeypatch):
    """Kolo 7 IMPORTANT: `taskkill` sám by mohl viset - bez vlastního
    timeoutu by `_kill_process_tree` (volaná PRÁVĚ PROTO, že něco viselo)
    mohla viset na `taskkill` a `proc.kill()` by se nikdy nespustil."""
    monkeypatch.setattr(stylist.sys, "platform", "win32")

    def _boom(*a, **kw):
        raise stylist.subprocess.TimeoutExpired(cmd="taskkill", timeout=10)

    monkeypatch.setattr(stylist.subprocess, "run", _boom)

    killed = {"called": False}

    class _FakeProc:
        pid = 12345
        def kill(self):
            killed["called"] = True

    stylist._kill_process_tree(_FakeProc())
    assert killed["called"]


def test_polish_raises_on_paragraph_count_mismatch(tmp_path):
    """Levná strukturální kontrola - jeden odstavec místo dvou = podezřele
    zkrácený výstup, i kdyby exit kód byl 0 a soubor neprázdný."""
    cmd = _fake_codex(tmp_path, "Jen jeden odstavec, podobně dlouhý jako vstup celkem.")
    with pytest.raises(stylist.StylistError, match="odstavců"):
        stylist.polish("EN", "Prvni odstavec.\n\nDruhy odstavec.", codex_cmd=cmd)


def test_polish_raises_on_wildly_different_length(tmp_path):
    cmd = _fake_codex(tmp_path, "X")   # jeden znak místo dlouhého textu, ale STEJNÝ počet odstavců (1)
    with pytest.raises(stylist.StylistError, match="délka"):
        stylist.polish("EN", "Dost dlouhý český text pro porovnání délky výstupu.", codex_cmd=cmd)


def test_polish_raises_on_chapter_too_long(tmp_path, monkeypatch):
    """Kolo 17 IMPORTANT - kapitola nad `config.STYLIST_MAX_CHARS` selže
    OKAMŽITĚ s jasnou zprávou, NE až po vyčerpání `timeout` (fake Codex se
    tu vůbec nezavolá - test to ověří tím, že `codex_cmd` míří na
    neexistující cestu, a přesto test neselže na `FileNotFoundError`,
    protože `_resolve_codex_cmd` se vůbec nedostane ke slovu)."""
    monkeypatch.setattr(config, "STYLIST_MAX_CHARS", 100)
    long_cz = "Odstavec. " * 20   # přes 100 znaků
    with pytest.raises(stylist.StylistError, match="moc dlouhá"):
        stylist.polish("EN", long_cz, codex_cmd=["nonexistent-codex-binary"])


def test_polish_allows_chapter_at_size_limit(tmp_path, monkeypatch):
    """Hraniční případ - PŘESNĚ na limitu (ne nad ním) projde dál k
    samotnému volání Codexu, guard neodmítne rovnost (`>`, ne `>=`)."""
    cz = "X" * 50
    monkeypatch.setattr(config, "STYLIST_MAX_CHARS", len("EN") + len(cz))
    cmd = _fake_codex(tmp_path, cz)
    result = stylist.polish("EN", cz, codex_cmd=cmd)
    assert result == cz


def test_polish_raises_on_changed_number(tmp_path):
    """Kolo 6 IMPORTANT: přehozená číslice ("12"→"21") zůstává čitelná pro
    LLM kontroly, ale je to faktická změna - deterministická kontrola
    čísel to musí chytit sama, bez spoléhání na kritika."""
    cz = "Bylo jich 12 a čekali od rána."
    cmd = _fake_codex(tmp_path, "Bylo jich 21 a čekali od rána.")
    with pytest.raises(stylist.StylistError, match="čísla"):
        stylist.polish("EN", cz, codex_cmd=cmd)


def test_polish_raises_on_swapped_numbers_same_set(tmp_path):
    """Kolo 13 BLOCKING: DVĚ RŮZNÁ čísla prohozená mezi dvěma místy v
    textu dají STEJNOU seřazenou množinu ({"3","5"} oběma směry) - dřívější
    `_number_multiset` (řadila výstup) by tohle NEZACHYTILA. `_number_
    sequence` (bez řazení, v pořadí výskytu) rozdíl vidí."""
    cz = "Anna měla 3 jablka, Petr 5 hrušek."
    cmd = _fake_codex(tmp_path, "Anna měla 5 jablek, Petr 3 hrušek.")
    with pytest.raises(stylist.StylistError, match="čísla"):
        stylist.polish("EN", cz, codex_cmd=cmd)


def test_polish_raises_on_decimal_separator_change(tmp_path):
    """Kolo 14 IMPORTANT - INVERTUJE dřívější kolo-13 test (`test_polish_
    allows_decimal_separator_convention_change`), co tvrdil OPAK: dřív se
    tečka/čárka normalizovaly jako stejný token, aby stylistova oprava
    anglicismu ("3.5" → "3,5") neprošla jako falešný poplach. Codex v
    kole 14 dal konkrétní protipříklad, proč to byla chyba: "Python 3.5"
    (verzové číslo, ne desetinná hodnota) → "Python 3,5" by normalizace
    tiše PŘIJALA jako "jen formátování", i když jde o skutečné poškození
    technického identifikátoru - regex nemá jak rozlišit "desetinné
    číslo" od "identifikátoru, co jako desetinné číslo vypadá". U
    bezpečnostní brány je falešné ZAMÍTNUTÍ (tenhle test - legitimní
    "3.5 metru"→"3,5 metru" teď taky spadne na `StylistError`) levnější
    než falešné PŘIJETÍ (co dřívější normalizace umožňovala)."""
    cz = "Věž měřila 3.5 metru."
    cmd = _fake_codex(tmp_path, "Věž měřila 3,5 metru.")
    with pytest.raises(stylist.StylistError, match="čísla"):
        stylist.polish("EN", cz, codex_cmd=cmd)


def test_polish_raises_on_markdown_fence_wrapper(tmp_path):
    """Model navzdory promptu obalí odpověď do ``` bloku - deterministická
    kontrola to musí odmítnout, ne spoléhat na to, že se poslechne pokyn."""
    cmd = _fake_codex(tmp_path, "```\nPrvni odstavec.\n\nDruhy odstavec.\n```")
    with pytest.raises(stylist.StylistError, match="markdown"):
        stylist.polish("EN", "Prvni odstavec.\n\nDruhy odstavec.", codex_cmd=cmd)


def test_resolve_codex_cmd_uses_absolute_path_directly(tmp_path):
    """sys.executable je absolutní cesta - `shutil.which` se nevolá (a
    nemusí ho umět najít), použije se přímo."""
    cmd = stylist._resolve_codex_cmd([sys.executable, "-c", "pass"])
    assert cmd[0] == sys.executable


def test_resolve_codex_cmd_raises_clear_error_for_missing_bare_name():
    with pytest.raises(stylist.StylistError, match="nenalezen"):
        stylist._resolve_codex_cmd(["prikaz-co-opravdu-neexistuje-xyz"])
```

`stylist.check_meaning_preserved()` se testuje s `FakeLLMClient` (stejný
vzor jako `test_lexicographer.py`):
- `{"meaning_changed": false, "register_changed": false}` → prázdný seznam.
- `{"meaning_changed": true, ...}` → nález typu `"meaning_drift"`.
- `{"meaning_changed": false, "register_changed": true, ...}` → nález
  typu `"register_drift"` (kolo 7 IMPORTANT - stylista dostane pokyn
  neměnit tykání/vykání/hlas, ale nic to dřív NEVERIFIKOVALO).
- oba `true` najednou → OBA nálezy v seznamu.
- useknutá odpověď, nečitelný JSON, nebo neplatný tvar (chybějící/špatný
  typ klíče `meaning_changed` NEBO `register_changed`) → nález typu
  `"meaning_drift"` - "nevím" se bere jako "radši zamítnout", ne propuštění.

**Manuální ověření (kolo 4 nález, checklist zpřesněn v kole 8):** všechny
automatizované testy mockují Codex CLI (`codex_cmd` na fake skript) - to
jsou testy LOGIKY (`stylist.py`, `_cmd_polish`), ne testy skutečného
kontraktu reálného `codex exec`. Po implementaci Tasku (dřív, než se
`polish` považuje za hotový) spustit JEDNOU ručně nad reálnou `done`
kapitolou a zkontrolovat výstup okem - stejný princip jako vizuální
kontrola u review formuláře (Task 12, reference-mining plán). Konkrétně
ověřit:

- [ ] `shutil.which("codex")` najde executable (preflight v `_cmd_polish`
      neselže).
- [ ] `--ephemeral` je přijímaný flag (ne chyba "unknown option") -
      ověřit i verzí Codex CLI na cílovém stroji, `--ephemeral` byl
      potvrzený v tomhle prostředí (`codex exec --help`), ale CLI verze
      se může lišit.
- [ ] Vstup skutečně jde přes stdin (pozicionální `-`) - prompt s
      diakritikou (viz `test_polish_roundtrips_utf8_diacritics`) dorazí
      k modelu nepoškozený.
- [ ] `-m <model>` skutečně vynutí konkrétní model, ne že se tiše
      ignoruje a použije se výchozí.
- [ ] `-C <dir>` izoluje PRACOVNÍ ADRESÁŘ a automatické načítání
      projektového kontextu (kolo 20 NIT - NE filesystem obecně, čtení
      mimo `-C` je ověřeně možné, viz POVINNÝ CANARY TEST níž) - Codex v odpovědi
      nezmiňuje nic z obsahu `book-translator` repa (žádná zmínka
      `AGENTS.md`, jmen souborů projektu apod.), pokud sám aktivně
      nesáhne po absolutní cestě.
- [ ] `-o <path>` skutečně zachytí poslední zprávu do souboru.
- [ ] `--ignore-user-config` je přijímaný flag (kolo 17 IMPORTANT, stejná
      výhrada jako u `--ephemeral` - verzí CLI se může lišit) a SKUTEČNĚ
      potlačí načtení uživatelova `~/.codex/config.toml` - zkontrolovat
      na stroji s neprázdným configem (MCP servery/pluginy), že běh
      neváhá/nehangne na jejich startu a že se v logu/chování neprojeví
      nic z toho, co config obsahuje.
- [ ] **POVINNÝ CANARY TEST (kolo 18 IMPORTANT, bezpečnostně kritické -
      NEpřeskakovat; kolo 19-20 IMPORTANT - PŘESNÁ produkční argv):**
      spustit `codex exec` s PŘESNĚ tím, co vrací `stylist._codex_argv(
      stylist._resolve_codex_cmd(["codex"]), <izolovaný dočasný
      adresář>, <out.txt v tom adresáři>, config.CODEX_MODEL)` - tedy s
      ROZŘEŠENÝM příkazem (na Windows absolutní `codex.cmd`, kolo 20 NIT)
      a VČETNĚ `--ephemeral`, `--ignore-user-config`,
      `-m <model>` a koncového `-` (dřívější znění vypisovalo jen část
      přepínačů). `--ignore-rules` se v argv NEVYSKYTUJE (kolo 25 ho
      vrátilo - viz `_CODEX_STATIC_FLAGS` komentář); pokud ho tam test
      najde, je to regrese. Prompt (stdinem, jako
      produkce) žádá přečíst a vrátit obsah souboru MIMO `-C` adresář
      (např. jiný soubor v `%TEMP%`). Přímo ověřeno v týhle relaci na
      Windows/verzi CLI z kola 18: **ÚSPĚŠNĚ přečetl** - `read-only`
      omezuje ZÁPISY, NE ČTENÍ. Pokud tenhle test na CÍLOVÉM stroji/verzi
      CLI taky uspěje (pravděpodobné), je to POTVRZENÉ, ne jen teoretické
      riziko prompt injection z textu knihy - rozhodnutí, jestli s tímhle
      rizikem `polish` nasadit, patří uživateli/vlastníkovi projektu
      (viz "Bezpečnostní rozhodnutí" níže).

`_cmd_polish` se testuje monkeypatchnutím `stylist.polish`,
`stylist.check_meaning_preserved` (fake funkce vracející pevný
text/prázdný seznam nálezů) a `pipeline._run_critic`/
`concordance.check_chapter` - stejný vzor jako existující
`tests/test_cli.py`. Klíčové scénáře:

- `config.CODEX_MODEL` prázdné → `_cmd_polish` vrátí 1 hned na začátku,
  žádný `run` se ani nevytvoří (žádné volání `stylist.polish`).
- `config.STYLIST_ACCEPT_FS_RISK` NENÍ `True` (default) → `_cmd_polish`
  vypíše bezpečnostní hlášku a vrátí 1 JAKO ÚPLNĚ PRVNÍ věc (před
  kontrolou modelu i preflightem, kolo 19 BLOCKING / kolo 20). ZÁVAZNÁ
  brána je ale PŘÍMO v `stylist.polish()` (kolo 20 BLOCKING - jinak by
  přímé volání veřejné funkce gate obešlo) - i kdyby se `_cmd_polish`
  check obešel, `polish()` sama vyhodí `StylistError`. `is not True`, ne
  `if not` - `STYLIST_ACCEPT_FS_RISK = 1` (truthy) NEprojde.
- preflight (`_resolve_codex_cmd`) selže → `_cmd_polish` vrátí 1 hned na
  začátku, žádná kapitola se nezpracuje (žádný `run` se nevytvoří).
- `_cmd_polish` volá `stylist.polish` s `guide_block` NEPRÁZDNÝM, když
  `guide.json` obsahuje `rules`/`style` (mock `guide_mod.load_guide` a
  ověřit, že `_polish_one_chapter`/`stylist.polish` dostane tenhle text) -
  kolo 6 IMPORTANT.
- `_cmd_polish` (s aspoň jednou kapitolou, co skutečně skončí PŘIJETÍM -
  ne jen "ke zpracování", viz upřesnění pár řádků níž, kolo 14 NIT)
  vytvoří `db + ".pre-polish-backup"` PŘED prvním zápisem, a soubor
  je LOGICKY ROVNOCENNÝ s DB PŘED spuštěním `_cmd_polish` (kolo 15 NIT -
  opravuje dřívější "BYTOVĚ IDENTICKÝ": od kola 14 vzniká přes `sqlite3.
  Connection.backup()`, ne `shutil.copy2` - `backup()` kopíruje na
  úrovni STRÁNEK, ne bajtů, výsledný soubor tak nemusí být bajtově
  totožný, i když obsahuje STEJNÁ data. Test místo hashe porovná obsah
  všech tabulek řádek po řádku, případně `PRAGMA integrity_check` +
  logickou rovnost - ne `hashlib` na syrových bajtech souboru) - kolo 7
  IMPORTANT, mechanismus zpřesněn kolo 9 BLOCKING (snapshot vzniká PŘED
  `state.create_run`, ne až u prvního `commit_chapter_result` - jinak by
  "záloha" nesla vlastní `runs`/`llm_calls` zápisy tohohle běhu). Test i
  ověří, že se záloha
  NEvytvoří, když `chapters` vyjde prázdné (funkce skončí dřív, `return
  0`) - a ODDĚLENĚ, že se NEVYTVOŘÍ ani při NEprázdných `chapters`, když
  všechny skončí jinak než přijetím (`unchanged`/`rejected`/`failed`) -
  dočasný `.pre-polish-snapshot` v tom případě zmizí (uklizený ve
  `finally`), žádný `.pre-polish-backup` nevznikne ani se nepřepíše
  (kolo 9 BLOCKING).
- selhání SAMOTNÉHO `_snapshot_db` při vytváření snapshotu (kolo 11
  IMPORTANT mechanismus, kolo 13 BLOCKING - zabaleno do `FatalRunError`,
  jinak by nezachycená výjimka propadla jako traceback; kolo 14 IMPORTANT
  nahradilo `shutil.copy2` SQLite vlastním `backup()` API + integrity_
  check - test i ověří, že `integrity_check` selhání (mock vrátí jinou
  hodnotu než `"ok"`) taky vede k `FatalRunError`, ne jen `OSError` ze
  souborového kopírování) → `_cmd_polish` vrátí 1, žádná kapitola se
  nezpracuje (výjimka spadne PŘED smyčkou,
  `finally` uklidí případný částečný soubor). BEZ perzistentního
  `status="fatal"` v DB - `create_run` ještě NEPROBĚHL, žádný `run` řádek
  neexistuje, fatálnost nese jen návratový kód a vypsaná hláška.
- `_snapshot_db`'s volání `.backup()` dostane `pages=100` - ověřeno
  PŘÍMO na argumentu volání, ne jen na konečném výsledku (kolo 18
  IMPORTANT, opravuje kolo 16 - test na `timeout=0` → `TimeoutError`
  NEROZLIŠÍ opravu od původní chyby, protože i rozbité `pages=-1` by
  nakonec `TimeoutError` vyhodilo, jen AŽ PO dokončení celé kopie, ne
  uprostřed). `sqlite3.Connection` je immutable C typ - JEHO metody
  monkeypatchnout NEJDE (`TypeError`, kolo 19 IMPORTANT). Místo toho:
  monkeypatch `main.sqlite3.connect` na wrapper, co vrátí proxy objekt
  delegující všechno na skutečné spojení, ale u `.backup()` si nejdřív
  zaznamená `kwargs` do sdíleného seznamu. Test pak zkontroluje, že
  aspoň jedno zaznamenané volání mělo `pages == 100`.
- `_snapshot_db` deadline SKUTEČNĚ přeruší kopírování (kolo 24 IMPORTANT -
  pages=100 test sám nezachytí regresi, co odstraní `progress=_check_
  deadline` nebo samotné vyhození `TimeoutError`). Proxy `.backup()`
  (přes stejný monkeypatch `main.sqlite3.connect`) místo skutečné kopie
  ZAVOLÁ předaný `progress` callback s `(0, remaining=5, total=10)` a
  vrátí; `main.time.monotonic` je monkeypatchnutý tak, aby PRVNÍ volání
  (výpočet `deadline`) vrátilo malou hodnotu a další volání hodnotu ZA
  `deadline` → `_check_deadline` vyhodí `TimeoutError`, `_snapshot_db`
  ji propaguje ven (a `_cmd_polish` ji zabalí do `FatalRunError`). Test
  očekává `TimeoutError` z přímého volání `main._snapshot_db(...)`.
- selhání `os.replace` uvnitř `_backup_db_once` NEBO `state.commit_
  chapter_result` u JEDNÉ kapitoly uprostřed dávky (mock vyhodí `OSError`/
  `sqlite3.OperationalError`) → `FatalRunError` (kolo 12 IMPORTANT), CELÝ
  `polish` se zastaví, `status="fatal"`, `return 1` - i kdyby PŘEDCHOZÍ
  kapitoly v téže dávce už úspěšně skončily `"polished"`/`"unchanged"`/
  `"rejected"` (test na SMÍŠENOU dávku: kapitola 1 OK, kapitola 2 selže na
  zápisu, kapitola 3 se vůbec NEZPRACUJE - fronta se nezpracovává dál po
  `FatalRunError`). Předtím zapsané kapitoly zůstávají zapsané (žádný
  automatický rollback) - k tomu slouží `.pre-polish-backup`.
- SAMOSTATNĚ (kolo 13 IMPORTANT): mock `state.finish_run` tak, aby SÁM
  vyhodil výjimku (nezávisle na úspěchu/selhání `commit_chapter_result`)
  → `_cmd_polish` vypíše varovnou hlášku o selhání finalizace, ale VRÁTÍ
  původní `return`/`status` z hlavní logiky (0/1 podle toho, co se stalo
  PŘED `finally`) - `finish_run`'s vlastní selhání nesmí přepsat/zamaskovat
  výsledek, ke kterému run už dospěl.
- `_number_sequence`: `"12%"`, `"12 %"` (obyčejná mezera), `"12 %"`
  (NBSP) a `"12 %"` (úzká nezalomitelná mezera) dají VŠECHNY STEJNÝ
  normalizovaný token (kolo 10-11 IMPORTANT, kolo 12 regresní test) -
  žádná z těchhle čtyř variant se navzájem nevyhodnotí jako změna čísla.
  Ztráta "%" (`"12 %"` → `"12"`) naopak MUSÍ vyhodit `StylistError`
  (sekvence se liší) - obě strany testu, ne jen ekvivalence variant.
- `_polish_rejected`: čerstvě přepočítaná baseline (`concordance.check_chapter`
  nad PŮVODNÍM `cz`) má nález `{"source": "concordance", "type": "omission",
  "term_id": "term_x", "actual": None, ...}` (běžný stav i pro `done`
  kapitolu). PO stylizaci se najde STEJNÝ `(type, term_id, actual)` klíč →
  **NENÍ odmítnuto** (nic nového/horšího). Objeví-li se NOVÝ klíč (jiný
  `term_id`, jiná `actual` hodnota, nebo nový `type`), co v baseline nebyl
  → **odmítnuto**.
- `_polish_rejected` - REGRESE "1 leak → 2 leaky v textu" (kolo 20
  IMPORTANT): `cz_before` má JEDEN výskyt povrchu `"White Council"`
  (leaklý termín), baseline i `after` findings z `check_chapter()` mají
  STEJNÝ jediný klíč `("leak", ..., "White Council")` (funkce dedupuje).
  `cz_after` má ale povrch DVAKRÁT → `_polish_rejected` vrátí `True`
  (`len(find_form_occurrences(cz_after, s)) > len(find_form_occurrences(
  cz_before, s))`). Opačný směr (stylista jeden leak opravil, výskytů
  MÉNĚ) → **NENÍ** odmítnuto.
- `_polish_rejected` - přidaný výskyt v JINÉM PÁDU nebo s JINOU
  VELIKOSTÍ PÍSMEN (kolo 21 IMPORTANT): `cz_before` má "White Council"
  1×, `cz_after` má "White Council" + "white councilu" (skloňováno,
  malé písmeno) → `find_form_occurrences` (stemuje + lowercasuje) oba
  zachytí, count 1→2 → **odmítnuto**. `str.count` by druhý výskyt
  minul.
- `_polish_rejected` - NOVÝ LEAK JINÉHO ALIASU (kolo 22 IMPORTANT):
  termín má `canonical_en="White Council"`, `aliases=["the Council"]`.
  `cz_before` má "White Council" 1× (leak), `check_chapter()` hlásí
  `actual="White Council"`. `cz_after` má "White Council" 1× + PŘIDANÝ
  "the Council" 1× (nový leak jiného aliasu). Klíč (`actual`) se
  NEZMĚNIL, ale `_polish_rejected` počítá VŠECHNY zakázané povrchy
  termínu → "the Council" 0→1 → **odmítnuto**. Kdyby počítal jen
  `actual`, prošlo by to.
- `_polish_rejected` - keep-untranslated termín (`cz == canonical_en`,
  např. "Mouse"): PŘIDANÝ výskyt "Mouse" v `cz_after` → **NENÍ**
  odmítnuto (EN povrch je u tohohle termínu SPRÁVNĚ, ne leak).
- `_polish_rejected` - VĚDOMĚ NEODMÍTNUTÝ pokles počtu schválených CZ
  forem (kolo 22): stylista sloučí dvě věty s opakovaným "Bílá rada" na
  jednu → 2×→1× → **NENÍ** odmítnuto (legitimní stylistické sloučení,
  ne regrese; viz `_polish_rejected` docstring "VĚDOMĚ NEPŘIJATO").
- integrační test s REÁLNÝM `concordance.check_chapter()` (ne ručně
  sestavenými findings) - text s termínem leaklým v CZ na 2 místech →
  `check_chapter()` vrátí JEDEN `leak` nález, ale `_polish_rejected`
  (dostává `cz_before`/`cz_after` + `glossary_rows`) rozdíl v počtu
  výskytů zachytí. Dokládá, že sama množina findings NESTAČÍ.
- `_polish_rejected`: kritikův nález se `severity="minor"`/`action="note"`
  (žádná `revise`) → **přijato** - to je přesně doména stylisty, subjektivní
  drobnost se nepočítá. Kritikův nález s `action="revise"` → **odmítnuto**,
  bez ohledu na baseline (kapitola `status=="done"` už předem znamená, že
  žádný takový v baseline neměla).
- `_polish_rejected`: kritikův nález s `type="fluency"`, ale
  `severity="critical"` (tedy `action="revise"`) → **odmítnuto** stejně
  jako kterýkoli jiný `revise` nález (kolo 15 IMPORTANT - `type=="fluency"`
  sám o sobě žádnou výjimku nedává, jen `severity=="minor"` ano; test
  ověřuje, že se "fluency" nezaměňuje s "vždy přijato").
- `check_meaning_preserved` vrátí `meaning_drift` nález (kritik i
  konkordance jsou čisté) → **taky zamítnuto** - to je přesně důvod, proč
  tahle třetí kontrola existuje.
- `check_meaning_preserved` vrátí SAMOSTATNÝ `register_drift` nález, bez
  `meaning_drift` (kritik i konkordance jsou čisté) → **taky zamítnuto**
  (kolo 13 NIT - dosavadní scénář testoval jen `meaning_drift`, ne
  `register_drift` samotný; `_polish_rejected`'s pravidlo 1 kontroluje
  OBA typy, potřebuje vlastní regresní test na ten druhý).
- stylista vrátí text IDENTICKÝ s originálem (`styled == cz`) → `unchanged
  == 1`, ŽÁDNÉ volání `pipeline._run_critic`/`check_meaning_preserved`
  (nic k ověření), `notes`/`translated_text` beze změny, ŽÁDNÝ `stylist`
  marker (další `polish` bez `--force` to zkusí znovu, ne navždy přeskočí).
- `stylist.polish` zvedne `StylistError` → `translated_text` zůstává
  původní, `failed == 1`.
- `stylist.polish`/konkordance/kritik/`check_meaning_preserved` zvednou
  NEOČEKÁVANOU výjimku, co NENÍ `FatalRunError` → zachyceno, `failed += 1`,
  zbytek dávky pokračuje.
- `_backup_db_once`/`state.commit_chapter_result` zvednou JAKOUKOLI
  výjimku (plný disk, poškozená DB, ztráta práv) → `_polish_one_chapter`
  ji zabalí do `FatalRunError` a přehodí dál - NEpočítá se jako `failed`
  téhle jedné kapitoly, CELÝ `polish` se zastaví (kolo 12 IMPORTANT -
  infrastrukturní selhání není per-kapitolová chyba).
- `pipeline._run_critic` zvedne `FatalRunError` (např. cost guard) → CELÝ
  `polish` se ukončí (`return 1`), zbylé kapitoly ve frontě se NEZPRACUJÍ,
  `state.finish_run(..., "fatal")` - ne tiché `failed += 1` a pokračování.
- VŠECHNY kapitoly v dávce skončí `failed` → extra varovná hláška o
  možném problému s CLI/přihlášením, `status="fatal"`, `return 1` (kolo
  5/6 - NE `"ok"`; DB audit nesmí hlásit úspěch u běhu, co nic neudělal).
- kapitola se `status != "done"` (např. `flagged`) se do zpracování vůbec
  nedostane, i když je zadaná v `--only`.
- kapitola už MÁ `{"source": "stylist"}` záznam v `notes` → bez `--force`
  se přeskočí (není v seznamu ke zpracování, `stylist.polish` se pro ni
  vůbec nezavolá); s `--force` se zpracuje znovu.
- kapitola má v `notes` platný JSON, co NENÍ seznam (např. `{}`) →
  `_parse_findings`/`_already_styled` vrátí prázdno/`False` (bezpečný
  default), kapitola se zpracuje, žádný pád.
- `--only` bez odpovídající `done` kapitoly → nic se nezpracuje, `polished
  == 0`, žádná chyba.
- `state.finish_run` se o zápis POKUSÍ vždy, KDYŽ `create_run` už
  proběhl (i při `failed`/`rejected` výsledcích v dávce) - NE úplně vždy
  bezpodmínečně (kolo 14 NIT - opravuje nepřesnou prózu: selže-li něco
  PŘED `create_run`, žádný `run` řádek neexistuje, `finish_run` se
  nevolá vůbec; a selže-li `finish_run` SÁM, je to jen best-effort
  vypsané varování, ne důvod k dalšímu pádu, viz kolo 13 IMPORTANT). Test
  čte `runs` tabulku a ověří `status == "ok"` po úspěšném dokončení
  smyčky, KDYŽ ASPOŇ JEDNA kapitola vyšla jinak než `failed` (i s nějakými
  `rejected`/`failed` mezi nimi - to je normální výsledek běhu, ne selhání
  běhu), a `status == "fatal"` po `FatalRunError` NEBO po tom, co VŠECHNY
  kapitoly v dávce vyšly `failed` (kolo 5/6 - "všechno selhalo" je
  `"fatal"`, ne `"ok"`, viz tabulka chybových stavů níže).

## Chybové stavy a jejich zpracování

| Stav | Reakce |
|---|---|
| `config.STYLIST_ACCEPT_FS_RISK` není `True` (default) | `_cmd_polish` vypíše bezpečnostní hlášku jako ÚPLNĚ PRVNÍ věc, `return 1`; NEZÁVISLE `stylist.polish()` sama vyhodí `StylistError` (kolo 19 BLOCKING / kolo 20 - závazná brána je v `polish()`, ne jen v CLI) |
| `config.CODEX_MODEL` prázdné | `_cmd_polish` odmítne rovnou spustit, `return 1` |
| Preflight (`shutil.which`) nenajde Codex CLI | `_cmd_polish` odmítne rovnou spustit, `return 1`, žádná kapitola se nezpracuje |
| Codex timeoutuje / nepodaří se spustit | `StylistError`, kapitola beze změny, pokračuje se další |
| Codex vrátí prázdnou odpověď nebo `-o` soubor nevznikne | `StylistError`, kapitola beze změny |
| Výstup má jiný počet odstavců nebo výrazně jinou délku | `StylistError` (strukturální kontrola v `stylist.polish`), kapitola beze změny |
| Sekvence arabských číslic/procent (`_number_sequence`) se mezi PŮVODNÍM CZ a stylizovaným CZ liší (kolo 18 NIT - opravuje "EN a stylizovaným", kód srovnává `cz_text` vs. `styled`) | `StylistError` (strukturální kontrola v `stylist.polish`, kolo 6/13/16), kapitola beze změny |
| Kapitola nad `config.STYLIST_MAX_CHARS` (EN+CZ znaků) | `StylistError` OKAMŽITĚ, bez volání Codexu (kolo 17 IMPORTANT), kapitola beze změny |
| Codex vrátí text identický s originálem | `unchanged`, žádné LLM kontroly, žádný marker, kapitola beze změny |
| NOVÝ konkordanční nález (`(type, term_id, actual)`, co v baseline nebyl) | zahozeno, kapitola beze změny |
| Kritikův nález s `action=="revise"` | zahozeno, kapitola beze změny |
| `meaning_drift`/`register_drift` nález | zahozeno, kapitola beze změny |
| Konkordanční nález se STEJNÝM klíčem jako v baseline (a `leak`/`inconsistency` bez nárůstu výskytů zakázaných povrchů, viz níž; nebo `omission` - tam se počet neřeší) | **přijato** - nic se nezhoršilo |
| Pre-existující `leak`/`inconsistency`, kde PO stylizaci PŘIBYL výskyt zakázaného povrchu (u `inconsistency` konkrétní chybný CZ tvar `actual`; u `leak` KTERÝKOLI zakázaný EN povrch termínu - canonical i alias) v `cz_after` oproti `cz_before` (kolo 20-22 IMPORTANT) | **zahozeno** - stejný problém, ale na víc místech / nový leak jiného aliasu; `check_chapter()` klíč dedupuje, `_polish_rejected` počítá výskyty přes `find_form_occurrences` |
| Kritikův `minor`/`action=="note"` nález (JAKÉHOKOLI `type`) | **přijato** - subjektivní drobnost, doména stylisty |
| Kritikův nález s `type=="fluency"`, ale `severity=="critical"`/`action=="revise"` | **zahozeno** stejně jako kterýkoli jiný `action=="revise"` nález (kolo 15 IMPORTANT - opravuje zavádějící řádek "jen fluency → přijato": `_to_finding`'s `action` závisí VÝHRADNĚ na `severity`, ne na `type` - "fluency" samo o sobě žádnou výjimku nedává, jen `minor`/`note` závažnost) |
| Neočekávaná výjimka (ne `FatalRunError`) u jedné kapitoly | zachyceno, `failed += 1`, dávka pokračuje |
| Selhání `_backup_db_once`/`state.commit_chapter_result` (plný disk, poškozená DB, práva) | zabaleno do `FatalRunError` (kolo 12 IMPORTANT) - NE `failed += 1`, CELÝ `polish` se zastaví |
| `FatalRunError` (např. cost guard, selhání zálohy/DB zápisu) kdekoli v `_polish_one_chapter` | CELÝ `polish` se ukončí, `status="fatal"`, zbylé kapitoly nezpracované |
| VŠECHNY kapitoly v dávce `failed` | extra varovná hláška, `status="fatal"`, `return 1` (kolo 5/6 - ne `"ok"`) |
| `--only` míří na kapitolu, co není `done`, nebo neexistuje | HLÁŠENO (vypsáno jmenovitě), kapitola se nezpracuje |
| Kapitola už má `stylist` záznam v `notes`, bez `--force` | HLÁŠENO (počet přeskočených), kapitola se nezpracuje |
| `notes` je platný JSON, ale ne seznam (poškozený/cizí tvar) | `_parse_findings` vrátí `[]` (jen ovlivní `_already_styled` - konkordanční baseline se počítá čerstvě, ne z `notes`) |
| Odpověď obalená v markdown bloku (```) | `StylistError` (deterministická kontrola v `stylist.polish`), kapitola beze změny |

## Rozhodnutí z kol 1-26 (plan-consensus)

Otázky z draftu, teď rozhodnuté (viz `plan-consensus/round-{1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26}-claude.md`
pro plné zdůvodnění):

- **Idempotence:** ano, přes marker v `notes` (`_already_styled`), ne přes
  nový sloupec. `--force` obchází.
- **`run_id`/`client_factory`:** vlastní typ běhu `"polish"`, ale
  `interactive=True` jako `run`, ne `interactive=False` jako
  `scan`/`reference` - `polish` je taky smyčka přes víc kapitol.
- **Plný audit každého pokusu (i zamítnutých/selhaných):** vědomě NE -
  jen konzolový výstup pro tenhle běh, žádná perzistentní tabulka pokusů.
  Zdůvodnění: zamítnutá/selhaná stylizace nic v DB nemění (žádný
  nekonzistentní stav k dohledání), takže perzistentní log by byl čistě
  diagnostický nice-to-have, ne oprava mezery. Přijatá stylizace SVŮJ
  audit (model, hash, délka) dostává v `notes` markeru.
- **Výstup Codexu jde přes `-o` (capture poslední zprávy), ne přes soubor,
  který by zapisoval sám agent** - `--sandbox read-only` by mu to
  zablokovalo (kolo 2 BLOCKING). (Vstupní mechanismus se od kola 2 ještě
  změnil - viz kolo 4 bullet níže, dnes jde stdinem, ne souborem.)
- **Executable se řeší přes `shutil.which`** - holé `"codex"` na Windows
  (kde je typicky `codex.cmd`) by `subprocess.run(shell=False)` nenašel
  (kolo 2 BLOCKING).
- **Třetí kontrolní vrstva (`check_meaning_preserved`, CZ-před vs. CZ-po)**
  - kritik sám (EN vs. CZ-po) nemusí odhalit posun, co je vůči EN pořád
  obhajitelný, ale liší se od PŮVODNÍHO výkladu (kolo 2 IMPORTANT).
- **`CODEX_MODEL` je POVINNÉ, ne volitelné s `None` fallbackem** - "model
  je výchozí" v auditu časem přestane být k čemu dohledatelné, jakmile se
  výchozí model CLI změní (kolo 2 IMPORTANT).
- **`FatalRunError` musí ukončit celý `polish`, ne se ztratit v
  per-kapitolovém `except Exception`** - jinak by cost guard byl bezzubý
  (kolo 2 IMPORTANT).
- **`critic.review()` musí synteticky vynutit revizi, když `verdict` a
  `findings` nesedí** (`verdict="revise"` bez žádného `action=="revise"`
  nálezu) - předexistující mezera v jádru pipeline, kterou `polish`
  zdědil skrz `pipeline._run_critic`. Oprava v `src/agents/critic.py`,
  prospívá i `run` (kolo 3 BLOCKING).
- **Pravidlo přijetí srovnává PROTI BASELINE (nálezy PŘED stylizací), ne
  absolutně** - `done` kapitola smí mít pre-existující minor nález,
  absolutní odmítání by takovou kapitolu navždy zablokovalo, i kdyby styl
  nic nezhoršil (kolo 3 IMPORTANT; ZDROJ baseline upřesněn kolo 4 - viz
  `_polish_rejected` výš - ne z uložených `notes` z doby, kdy kapitola
  dostala `done`, ale ČERSTVĚ přepočítaná těsně před stylizací proti
  AKTUÁLNÍMU glosáři, kolo 11 NIT opravuje tuhle větu, co pořád zmiňovala
  jen starší kolo-3 verzi).
- **Detekce `styled == cz`** (Codex nenavrhl žádnou změnu) - krátký okruh
  PŘED zaplacením za kritika/kontrolu významu, žádný marker (jinak by
  `--force` byl jediná cesta zkusit to znovu, přestože se fakticky nic
  nestylizovalo) (kolo 3 IMPORTANT).
- **Preflight** - `_resolve_codex_cmd(["codex"])` se zavolá JEDNOU na
  začátku `_cmd_polish`, ne až uvnitř smyčky - chybějící/nenalezitelné
  CLI je systémový problém, ne N per-kapitolových selhání, co by run
  přesto označila `status="ok"` (kolo 3 IMPORTANT).
- **`tempfile.TemporaryDirectory()` jako context manager** místo ručního
  `mkdtemp()` + `finally`-cleanup - chrání i samotné VYTVOŘENÍ adresáře,
  ne jen fázi po něm (kolo 3 IMPORTANT; od kola 4 už žádný vstupní soubor
  neexistuje, adresář slouží jen jako `-C` kořen a cíl `-o`).
- **Model se normalizuje (`.strip()`) JEDNOU**, stejná hodnota všude dál -
  dřívější draft testoval `.strip()`, ale do CLI/markeru posílal
  nenormalizovanou hodnotu (kolo 3 NIT).
- **`isinstance(e, (FatalRunError, KeyboardInterrupt))` zjednodušeno na
  jen `FatalRunError`** - `KeyboardInterrupt` dědí z `BaseException`, ne
  `Exception`, takže `except Exception` ho nikdy nezachytí; kontrola byla
  mrtvý kód (kolo 3 NIT).
- **`critic.review()` navíc validuje typ `findings`** - `data.get("findings")`
  může být cokoli platné JSON (string, číslo), ne jen seznam/`None`;
  netypový tvar teď skončí jako parse-chyba (retry, pak výjimka), ne
  `AttributeError` uvnitř `_to_finding` (kolo 4 BLOCKING).
- **Vstup jde přes STDIN, ne soubor** (`Popen.communicate(input=...)`,
  pozicionální `-` jako prompt) - ověřeno `codex exec --help`. Zjednodušení
  oproti kolu 1-3 (žádný vstupní soubor, žádná cesta v promptu) A bonus k
  privacy - PŮVODNÍ (EN+CZ) text kapitoly se nezapisuje jako samostatný
  čitelný soubor navíc (kolo 4). **Pozor (kolo 6 NIT, oprava nadsázky):**
  tohle NEznamená, že se text kapitoly na disk nedostane vůbec - `-o
  out_path` zapisuje STYLIZOVANOU verzi do `out.txt` v `TemporaryDirectory`,
  jinak by ji nešlo přečíst zpátky. Ten soubor po použití mažeme (context
  manager), ale to je normální smazání souboru, ne kryptograficky
  zaručené vymazání dat z disku - žádná záruka nenávratnosti se netvrdí.
- **`--ephemeral` flag** - ověřeno `codex exec --help` ("Run without
  persisting session files to disk"). Bez něj by Codexova VLASTNÍ session
  historie mohla obsahovat text knihy i po smazání dočasného adresáře -
  `TemporaryDirectory` čistí jen NAŠE soubory, ne Codexovo interní
  úložiště (kolo 4 IMPORTANT).
- **Odmítnutí `` ``` `` obalené odpovědi** - deterministická kontrola v
  `stylist.polish`, ne spoléhání na to, že model poslechne "žádné
  markdown bloky" v promptu (kolo 4 NIT).
- **`_polish_rejected` srovnává konkordanci proti ČERSTVĚ přepočítanému
  stavu PŘED stylizací** (`concordance.check_chapter(en, cz, ...)` volané
  přímo v `_polish_one_chapter`), ne proti uloženým `notes` - ty mohly
  vzniknout pod STARŠÍM glosářem (uživatel mezitím mohl `answer`
  aktualizovat termín) a dávaly by falešně nové/staré nálezy. Klíč pro
  srovnání navíc zahrnuje `actual` hodnotu, ne jen `(type, term_id)` - jinak
  by změna JEDNÉ špatné hodnoty na JINOU špatnou hodnotu prošla jako
  "stejný, už známý" nález (kolo 4 IMPORTANT).
- **Preflight jen kontroluje dostupnost executable, ne přihlášení/model** -
  vědomě zúženo (viz "Disagreed" v `round-4-claude.md`). Plná kontrola by
  vyžadovala skutečné (placené) volání Codexu; místo toho `_cmd_polish`
  vrací nenulový exit kód, když VŠECHNY kapitoly v dávce selžou - programově
  zjistitelný symptom bez nutnosti platit za preflight volání (kolo 4
  IMPORTANT, částečné řešení).
- **`--only` hlásí přeskočené kapitoly** (číslo není `'done'`, neexistuje,
  nebo už je stylizované bez `--force`) - stejný vzor jako `run --only`
  (kolo 4 NIT).
- **Deterministická kontrola ARABSKÝCH číslic PŘIDÁNA v kole 6** (viz
  bullet níže) - tenhle bullet z kola 4 je STARÝ, nahrazený. Co zůstává
  mimo rozsah po kole 6: SLOVNĚ vypsaná čísla ("pět"), datumy v netriviálním
  formátu (extrakce/normalizace dat napříč přirozeným textem je vlastní
  NLP úloha) a jména - ta hlídají `check_meaning_preserved` (LLM vrstva) a
  konkordance (zavedené termíny/jména), ne nová deterministická extrakce.
- **Kvalitativní vylepšení stylu se automaticky NEOVĚŘUJE** (jen bezpečnost/
  věrnost) - vědomý nesouhlas. Automatizovaný "je to lepší?" LLM soudce by
  byl sám subjektivní/nespolehlivý, přidal by další placené volání na
  kapitolu, a je mimo explicitní zadání (ochrana proti halucinaci, ne
  kvalitativní brána). Uživatel zůstává posledním soudcem - stejně jako u
  prvního pilotního běhu, kdy sám posoudil čitelnost výstupu.
- **`rendered_terms=[]` OPRAVENO, ne jen zdokumentováno jako kompromis**
  (revize kola 4 rozhodnutí) - kolo 4 to hodnotilo jako pouhou ztrátu
  METADAT (provenience), ale kolo 5 upřesnilo: `examined_terms()` termín
  zachycený VÝHRADNĚ přes `rendered_terms` (bez přesné EN shody povrchu)
  by se s `rendered_terms=[]` vůbec nezkoumal - skutečná slepá skvrna, ne
  jen ztráta metadat. Oprava: nový getter `state.chapter_mentions()`
  (malý, stejný vzor jako `get_chapter`) - `_polish_one_chapter` z něj
  postaví `rendered_terms` a použije ho pro baseline i `after` konkordanci
  i pro přepočet mentions, stejně jako to dělá `process_chapter` s
  translatorovým vlastním hlášením (kolo 5 BLOCKING).
- **`encoding="utf-8"` explicitně na `Popen`** - bez toho `text=True`
  použije lokální kódování OS; na Windows bývá cp1252, které český text
  (diakritika) nezakóduje, a volání spadne dřív, než se Codex vůbec spustí.
  Ověřeno přímo vlastní zkušeností v tomhle prostředí (kolo 5 BLOCKING).
- **`Popen`+`communicate` místo `subprocess.run`, `_kill_process_tree` při
  timeoutu** - `subprocess.run(timeout=...)` na Windows ukončí jen
  PŘÍMÉHO potomka; `codex.cmd` spouští `node.exe` jako dalšího potomka,
  který by na timeoutu běžel dál a čerpal kvótu. `taskkill /T /F` ukončí
  celý strom (kolo 5 IMPORTANT).
- **`critic.review()` validuje i `verdict` enum** (`"pass"`/`"revise"`,
  nic jiného) - chybějící/neplatná hodnota se dřív tiše brala jako "ne
  revise", takže rozbitá odpověď s prázdnými `findings` vyšla jako klidné
  "pass" (kolo 5 IMPORTANT).
- **`rendered_terms=[]` u `_polish_one_chapter` OPRAVENO** (nový
  `state.chapter_mentions()` getter) - kolo 4 to hodnotilo jako ztrátu
  metadat, kolo 5 upřesnilo na skutečnou slepou skvrnu (termín zachycený
  jen translatorovým hlášením by se vůbec nezkoumal) - viz "Oprava mimo
  nový modul: src/state.py" výše (kolo 5 BLOCKING).
- **"Všechno selhalo" nastavuje `status="fatal"`, ne `"ok"`** - kolo 4
  rozhodnutí (nenulový exit kód, ale `status="ok"`) bylo vnitřně
  rozporné - DB audit by hlásil úspěch u běhu, který nic neudělal (kolo 5
  IMPORTANT, opravuje kolo 4).
- **Deterministická kontrola čísel PŘIDÁNA - kolo 4-5 nesouhlas REVIDOVÁN.**
  Codex ve 3 kolech postupně zúžil návrh na úzký, levný multiset arabských
  číslic/procent (ne plný NLP extraktor) a upřesnil klíčový argument:
  `polish` běží nad UŽ SCHVÁLENÝM textem (regresní riziko), ne nad prvním
  konceptem (počáteční kvalita) - přesnou multiset kontrolu jde napsat
  jako pár řádků regexu, žádná nová netriviální schopnost. Řazení
  odstraněno kolo 13 (přesně proto multiset → sekvence, viz níže).
  Desetinný oddělovač (`,`/`.`) se PŮVODNĚ (kolo 6) normalizoval, ať
  legitimní počeštění zápisu čísla neprojde jako falešný poplach - kolo
  14 tohle ZRUŠILO (viz kolo-14 bullet níže, "Python 3.5" protipříklad).
- **`guide_block` (tykání/vykání, hlas, rejstřík) se předává stylistovi** -
  stejný text jako translator (`translate_scene`/`revise_chapter`)
  dostává v `pipeline.py` - NE kritik (kolo 17 NIT opravuje dřívější
  nepřesné "translator/kritik" - `_run_critic` guide_block nikdy
  nedostávala). Dva různé
  důvody: (1) stylista SÁM by bez návodu mohl nepozorovaně změnit už
  rozhodnutý registr - Codex nedostane nic jiného, co by mu řeklo, jaký
  registr platí; (2) kritik (EN vs. CZ-po) na drift tykání/vykání nemá
  signál, protože EN sám informaci o českém rejstříku nenese (kolo 6
  IMPORTANT). `check_meaning_preserved` (CZ-před vs. CZ-po) drift SAMA
  zachytí i bez `guide_block` - srovnává přímo dvě verze stejného textu,
  nepotřebuje znát PRAVIDLO, jen že se něco změnilo (od kola 7 kontroluje
  i REJSTŘÍK, ne jen VÝZNAM - viz níže) - ale `guide_block` v `polish()`
  promptu zůstává důležitý jako PREVENCE (instrukce stylistovi PŘEDEM), ne
  jen jako DETEKCE PO FAKTU (kolo 10 - zpřesňuje zastaralé tvrzení, že
  `check_meaning_preserved` na registr signál nemá, což od kola 7 už
  neplatí).
- **`taskkill` fallback na `proc.kill()` + omezený `wait()`** - `taskkill`
  může sám selhat (proces mezitím zmizel, nedostatečná práva); bez
  fallbacku a bez limitu na `wait()` by volající mohl čekat navždy
  (kolo 6 IMPORTANT).
- **Celý SHA-256 místo zkráceného SHA-1** v auditním markeru - žádná
  praktická režie, žádný důvod šetřit na síle hashe (kolo 6 NIT).
- **Oprava nadsázky "text knihy se nikdy nezapíše na disk"** - PŮVODNÍ
  text jde stdinem (pravda), ale STYLIZOVANÁ verze se zapisuje přes `-o`
  do dočasného souboru, co se pak maže (normální smazání, ne bezpečné
  vymazání dat) - tvrzení bylo nadsázka, opraveno na přesné (kolo 6 NIT).
- **Zastaralá próza (test dokumentace zmiňující `subprocess.run` místo
  `Popen`, tabulka s "tiché přeskočení" navzdory hlášení, `status="ok"`
  místo `"fatal"` v testovací próze/tabulce)** - opraveno na 6 místech,
  kde předchozí kola nechala text neaktualizovaný po změně kódu (kolo 6
  NITS a BLOCKING - kolo-5 oprava `status="fatal"` se nepromítla do
  testovací prózy a tabulky).
- **Záloha CELÉ DB před `polish` PŘIDÁNA - kolo 1-6 "hash stačí" ROZŠÍŘENO
  na skutečnou obnovitelnost.** Argument "uživatel je poslední soudce"
  (kola 4-6) nesouvisel s tím, že v době, kdy uživatel posuzuje výsledek,
  je DB UŽ přepsaná. Hash v `_stylist_marker` uměl jen DETEKOVAT změnu,
  ne ji vrátit zpět. `shutil.copy2` na `db + ".pre-polish-backup"` PŘED
  prvním zápisem dávky dává reálnou, triviální cestu zpět (kolo 7
  IMPORTANT) - bez potřeby plné verzované historie, kterou jsem
  dlouhodobě odmítal jako nekonzistentní s `translator.revise_chapter`.
  **POZN. (kolo 12): tenhle PŘÍMÝ `shutil.copy2` mechanismus je od kola
  9 NAHRAZENÝ dvoufázovým snapshot+`os.replace` (viz `_backup_db_once`
  výš i bullet o pár řádků níž) - bullet zůstává jako historický záznam
  ROZHODNUTÍ (zálohovat vůbec), ne jako popis AKTUÁLNÍHO mechanismu.**
- **`check_meaning_preserved` kontroluje i REJSTŘÍK** (`register_changed`,
  nový nález typu `register_drift`), ne jen VÝZNAM - `guide_block` (kolo
  6) dá stylistovi INSTRUKCI neměnit tykání/vykání/hlas, ale žádná vrstva
  to předtím neVERIFIKOVALA (kritik na to nemá signál, EN sám tykání/vykání
  nenese). Instrukce bez verifikace by odporovala vlastní zásadě "nikdy
  nevěřit naslepo" (kolo 7 IMPORTANT).
- **`critic.review()` teď fail-closed i na top-level ne-dict a na
  SMÍŠENÉ `findings` (místo tichého přeskočení nedict položek)** - kolo 4
  BLOCKING řešilo jen `findings` jako celek špatného typu, ne top-level
  odpověď jako celek špatného typu, ani jednotlivé nedict položky uvnitř
  jinak platného seznamu (kolo 7 BLOCKING).
- **`taskkill` má VLASTNÍ timeout** - bez něj by `_kill_process_tree`
  (volaná právě proto, že něco viselo) mohla sama viset na `taskkill` a
  fallback na `proc.kill()` (kolo 6) by se nikdy nespustil (kolo 7
  IMPORTANT).
- **Rozhodnutí "deterministická kontrola čísel MIMO ROZSAH" (kolo 4)
  ODSTRANĚNO jako protimluv** - kolo 6 kontrolu PŘIDALO, ale starý bullet
  z kola 4 zůstal ve spisu a tvrdil opak. Nahrazeno přesným popisem, co
  PO kole 6 zůstává mimo rozsah (slovně vypsaná čísla, netriviální formáty
  dat) - kolo 7 NIT.
- **Kolo-5 `status="fatal"` oprava dopromítnuta do ZBÝVAJÍCÍ zastaralé
  prózy** - kolo 6 opravilo tabulku a jeden odstavec testovacích scénářů,
  ale JINÝ odstavec o pár řádků výš pořád tvrdil `status="ok"` (kolo 7
  BLOCKING - přímý rozpor mezi dvěma částmi téhož dokumentu).
- **Záloha DB je LÍNÁ, ne eager** - kolo 7 zálohovalo bezpodmínečně na
  začátku `_cmd_polish`; kolo 8 upřesnilo, že to přepisuje poslední
  UŽITEČNOU zálohu i během během, co nakonec nic nezapíše (samé
  `unchanged`/`rejected`/`failed`). `_backup_db_once` zálohuje jen těsně
  PŘED prvním skutečným `commit_chapter_result` (kolo 8 IMPORTANT).
  **POZN. (kolo 12): "zálohuje" tady = kolo-8 PŘÍMÉ kopírování v tomhle
  bodě - kolo 9 zjistilo, že i TOHLE je pozdě (`create_run`/`llm_calls`
  už DB mezitím změnily) a nahradilo to snapshotem PŘED `create_run` +
  atomickou promocí (`os.replace`) přesně tady - viz `_backup_db_once`
  výš. Tenhle bullet zůstává jako záznam ROZHODNUTÍ "líné, ne eager",
  které platí dodnes, jen MECHANISMUS zálohování samotného se od kola 9
  liší.**
- **`Popen` chytá `OSError`, ne jen `FileNotFoundError`** -
  `PermissionError` (existující, ale nespustitelný soubor) je taky
  `OSError`, ale NENÍ `FileNotFoundError`, takže by unikl mimo `StylistError`
  kontrakt (kolo 8 IMPORTANT).
- **`codex_cmd` se řeší JEDNOU ve skutečnosti, ne jen podle tvrzení** -
  preflight v `_cmd_polish` teď vrácenou hodnotu `_resolve_codex_cmd`
  UCHOVÁ a posílá dál do `_polish_one_chapter`/`stylist.polish` -
  předtím se sice preflight zavolal jednou, ale `stylist.polish` si
  stejně řešil `shutil.which` znovu na každou kapitolu, takže tvrzení
  "JEDNOU" bylo nepřesné (kolo 8 NIT).
- **Manuální ověření rozšířeno o explicitní checklist** (`--ephemeral`,
  stdin, `-m`, `-C` izolace, `-o`) - obecné "spusť a zkontroluj okem" by
  nemuselo zachytit nekompatibilitu konkrétního přepínače na starší verzi
  CLI (kolo 8 IMPORTANT).
- **Zbylé 3 výskyty zastaralé prózy opraveny** (`_polish_rejected`
  docstring pořád zmiňoval `notes` jako zdroj baseline i po kole 4 opravě
  kódu; `TemporaryDirectory` komentář tvrdil "žádný soubor s textem
  knihy" a v TÉŽE větě zmiňoval `-o` jako cíl zápisu - vnitřní rozpor;
  shrnutí tří vrstev nezmiňovalo čísla ani registr) - kolo 8 NITS/IMPORTANT,
  potvrzuje stejný vzorec jako kola 6-7 (kód opravený dřív, próza
  dotažena později).
- **Záloha DB: snapshot PŘED `create_run`, promoce AŽ při prvním zápisu**
  (kolo 9 BLOCKING, zpřesňuje kolo 8) - `_backup_db_once` volaná těsně
  před prvním `commit_chapter_result` (kolo 8) NESTAČÍ, protože `state.
  create_run` i kritik/`check_meaning_preserved` volané pro kapitoly, co
  skončí `rejected`/`failed`, zapisují do DB (`runs`, `llm_calls`) DŘÍV,
  než tenhle bod vůbec nastane - "záloha" by tak nesla vlastní bookkeeping
  tohohle běhu, ne skutečný stav před spuštěním `polish`. Oprava: `_cmd_
  polish` pořídí `shutil.copy2` do DOČASNÉHO souboru HNED (před `create_
  run`), `_backup_db_once` ho pak jen atomicky PROMUJE (`os.replace`) na
  kanonickou `.pre-polish-backup` cestu - nezůstává tak vidět částečně
  přepsaná stará záloha (na rozdíl od opakovaného `shutil.copy2`, což byla
  samostatná kolo-9 IMPORTANT připomínka ke stejnému místu). Nepromovaný
  snapshot (běh nic nezapsal) se uklidí ve `finally`.
  **POZN. (kolo 15): samotné `shutil.copy2` pro vytvoření snapshotu je od
  kola 14 nahrazené `_snapshot_db` (`sqlite3.Connection.backup()` +
  `integrity_check`) - princip "snapshot HNED, promoce až při prvním
  zápisu" popsaný tady zůstává v platnosti, jen kopírovací mechanismus
  samotný je jiný.**
- **Kritik: neplatné `severity`/`type` v jednotlivém nálezu zneplatní
  CELOU odpověď** (kolo 9 IMPORTANT) - existující `_to_finding` tiše
  domýšlí chybějící/špatnou hodnotu na bezpečné "minor"/"fidelity"
  (`{"severity": 0}` by prošlo jako neškodný nález, `0` je v Pythonu
  falsy). `review()` teď validuje `severity`/`type` PŘED voláním
  `_to_finding` - stejná filozofie jako kolo 7 (nedict položka = celá
  odpověď nedůvěryhodná), jen o úroveň hlouběji.
- **`check_meaning_preserved`: `isinstance(..., bool)`, ne `in (True,
  False)`** (kolo 9 IMPORTANT) - v Pythonu `0 == False`/`1 == True`, takže
  `0 in (True, False)` vrací `True`. Odpověď `{"meaning_changed": 0}` by
  tak prošla jako platné "false", přestože jde o jiný typ, než prompt
  žádá.
- **Test na PŘESNÝ argv Codex volání** (kolo 9 IMPORTANT) - dosavadní
  testy ověřovaly jen roundtrip dat (co fake skript dostal/vrátil), ne
  KTERÉ přepínače se skutečně posílají. Regrese, co by tiše upustila
  `--ephemeral` nebo přepnula `--sandbox`, by prošla nepovšimnutá (jen
  ruční checklist). Nový test nechá fake skript zapsat svůj `sys.argv` do
  vedlejšího JSON souboru a ověří ho.
- **Fail-fast pořadí guardrail vrstev v `_polish_one_chapter`** (kolo 9
  NIT) - `check_meaning_preserved` (placené Anthropic volání) se teď
  přeskočí, když konkordance nebo kritik SAMY o sobě zamítnutí už
  zaručují. `_polish_rejected` se volá dvakrát se STEJNOU logikou (žádná
  duplicitní rozhodovací cesta), jen podruhé až s meaning-check nálezy.
- **Argv test měl chybnou indexaci** (kolo 10 BLOCKING) - `sys.argv`
  UVNITŘ spuštěného skriptu neobsahuje interpret (`sys.executable`), jen
  cestu ke skriptu jako `argv[0]` - `tail = argv[2:]` omylem zahazovalo
  i `"exec"`, test by VŽDY spadl. Opraveno na `argv[1:]`, test teď navíc
  porovnává celý seznam přesně (ne jen přítomnost).
- **Lifecycle snapshotu DB nebyl PLNĚ chráněný `try/finally`** (kolo 10
  IMPORTANT, kolo 11 IMPORTANT dotáhlo) - kolo 10 přesunulo `glossary.
  all_terms`/`guide_mod.load_guide`/`state.create_run` dovnitř `try`, ale
  SAMOTNÝ `shutil.copy2` (vytvoření snapshotu) zůstal PŘED ním - selhání
  kopírování (plný disk, práva) by nechalo částečný `.pre-polish-snapshot`
  bez úklidu. Kolo 11: `backup_state` se sestaví (s hotovou cestou) PŘED
  `try`, ale samotné `shutil.copy2` je AŽ uvnitř - `finally` tak uklidí i
  tenhle případ.
- **Číselný guard nezachytával českou mezeru před "%"** (kolo 10
  IMPORTANT, kolo 11 rozšířilo) - regex vůbec nepovoloval mezeru před
  "%", takže běžný český zápis "12 %" nikdy nezachytil "%" jako součást
  čísla - kontrola byla na reálném textu prakticky mrtvá. Kolo 10 přidalo
  obyčejnou mezeru a NBSP, kolo 11 přidalo i úzkou nezalomitelnou mezeru
  (U+202F) - LLM výstup může použít kteroukoli variantu. Znaménko čísel
  (`-12`→`12`) zůstává záměrně mimo rozsah (riziko falešných poplachů na
  přetížené pomlačce - rozsahy stran, vsuvky).
- **Obnova DB ze zálohy nebyla atomická** (kolo 11 IMPORTANT) -
  dokumentovaný postup `shutil.copy2(backup, db)` přímo na aktivní
  cestu měl stejné riziko částečného zápisu jako dřívější zálohování,
  jen by teď poškodil `db` samotnou. Přepsáno na kopírování do
  dočasného souboru ve stejném adresáři + `PRAGMA integrity_check` +
  `os.replace`.
- **Chybí regresní testy na validaci `severity`/`type`** (kolo 11
  IMPORTANT) - kolo 9 přidalo fail-closed validaci jednotlivých nálezů
  v `critic.review()`, ale žádný test scénář ji neověřoval. Přidáno 4
  nových scénářů (chybějící `severity`, neplatná hodnota `0`, neplatný
  `type`, oba pokusy retry smyčky).
- **Zbylá stale próza opravena** (kolo 11 NIT) - "Rozhodnutí" bullet o
  baseline pořád primárně odkazoval na kolo-3 verzi ("z doby, kdy
  kapitola dostala done") bez zmínky, že kolo 4 zdroj baseline upřesnilo
  na čerstvý přepočet; nadpis týhle sekce zůstal na "kol 1-9", i když
  kolo 10 dokument dál měnilo.
- **Selhání zálohy/DB zápisu je FATÁLNÍ, ne per-kapitolová chyba** (kolo
  12 IMPORTANT) - vnější `except Exception` v `_cmd_polish` smyčce by
  jinak spolykalo selhání `_backup_db_once`/`commit_chapter_result` jako
  obyčejné `outcome="failed"` JEDNÉ kapitoly, a run by mohl skončit
  `status="ok"` navzdory rozbité DB/disku, pokud by jiná kapitola v dávce
  dopadla "unchanged"/"rejected". Zabaleno do `FatalRunError`.
- **`_fake_codex` bez explicitního UTF-8 encoding** (kolo 12 NIT) -
  `write_text` bez encoding na Windows sáhne po cp1252, co českou
  diakritiku neumí - stejná třída chyby jako produkční `Popen` (kolo 5
  BLOCKING), jen v testovacím helperu.
- **`shutil.copy2` snapshotu bez vlastního `except`** (kolo 13 BLOCKING) -
  `_cmd_polish`'s vnější `try` chytal jen `FatalRunError`/
  `KeyboardInterrupt`, takže obyčejný `OSError` ze SAMOTNÉHO kopírování
  by propadl jako nezachycený traceback, ne `return 1`, jak tvrdila
  próza scénáře. Zabaleno do `FatalRunError` - PŘED `create_run`, takže
  žádný `run` řádek v DB nevzniká, fatálnost nese jen návratový kód.
- **`finish_run` ve `finally` NESMÍ přebít původní chybu/return** (kolo
  13 IMPORTANT) - kdyby `finish_run` sám selhal (stejná třída chyby, co
  nás do `finally` často přivedla), nová výjimka by přepsala tu původní
  (standardní Python chování u výjimky ve `finally`). Zabaleno do
  vlastního `try/except`, selhání finalizace se jen vypíše, nepřepíše nic.
- **`_number_multiset` PŘEJMENOVÁNO na `_number_sequence`, ŘAZENÍ
  ODSTRANĚNO** (kolo 13 BLOCKING) - seřazená množina nerozliší přehození
  DVOU RŮZNÝCH čísel mezi sebou (`{"3","5"}` je stejná množina oběma
  směry) - přesně ta třída chyby ("přehození číslic"), co má tahle
  kontrola zachytit. Bezpečné přejít na sekvenci, protože `SYSTEM_PROMPT_
  TEMPLATE` stylistovi už beztak zakazuje měnit pořadí událostí/čísel.
- **Zdůvodnění normalizace desetinného oddělovače zpřesněno kolo 13, PAK
  CELÁ NORMALIZACE ZRUŠENA kolo 14** - PŮVODNÍ příklad ("anglické 3.5 →
  české 3,5") popisoval EN→CZ převod, ale funkce srovnává dvě ČESKÉ
  verze stejného textu (kolo 13 IMPORTANT tohle zpřesnilo, normalizaci
  ale ještě zachovalo s odůvodněním "riziko skutečné kolize je v tomhle
  úzkém CZ-vs-CZ kontextu zanedbatelné"). Kolo 14 IMPORTANT tenhle
  závěr vyvrátilo konkrétním protipříkladem: "Python 3.5" (verzové
  číslo, technický identifikátor) → "Python 3,5" by normalizace tiše
  PŘIJALA jako neškodné přeformátování, přestože jde o viditelné
  poškození technického termínu - regex nemá jak rozlišit "desetinné
  číslo" od "identifikátoru, co jako desetinné číslo vypadá" bez
  kontextové/sémantické analýzy (přesně ta "drahá NLP úloha", co je
  jinde v dokumentu záměrně mimo rozsah). U bezpečnostní brány je
  falešné ZAMÍTNUTÍ levnější než falešné PŘIJETÍ - normalizace ZRUŠENA
  (ne zúžena), `test_polish_allows_decimal_separator_convention_change`
  invertován na `test_polish_raises_on_decimal_separator_change`.
- **Snapshot DB přes `sqlite3.Connection.backup()`, ne `shutil.copy2`**
  (kolo 14 IMPORTANT) - prostý souborový copy může zachytit DB uprostřed
  cizího zápisu (nekonzistentní stav) a nezná WAL/SHM sidecar soubory
  (dnešní `state.connect()` WAL nepoužívá, takže tohle konkrétně je
  teoretická hrozba, ne aktuální - `backup()` ji ale řeší obecně, bez
  ohledu). Nová funkce `_snapshot_db` navíc ověří `PRAGMA integrity_
  check` na výsledku - `backup()` samo nezaručuje čitelný výsledek při
  přerušení uprostřed. `import shutil` v `main.py` runtime kódu díky
  tomu odpadl (nahrazen `import sqlite3`).
- **Top-level `try/except` v `_cmd_polish` rozšířen na CELÝ příkaz**
  (kolo 14 IMPORTANT) - kolo 13 chránilo jen `shutil.copy2`
  (resp. teď `_snapshot_db`) vlastním zabalením do `FatalRunError`, ale
  `chapters_by_status`/`glossary.all_terms`/`load_guide`/`create_run`/
  `_print_usage` zůstávaly BEZ obecného `except` - nezachycená výjimka
  by propadla jako traceback, STEJNÁ třída chyby jako u `shutil.copy2`,
  jen na jiných místech. Přidán finální `except Exception` (po
  `FatalRunError`/`KeyboardInterrupt`), `rid`/`backup_state` inicializace
  posunuta před CELÝ zbytek příkazu (`backup_state` teď může být i
  `None`, dokud se skutečně nevytvoří - `finally` to zohledňuje).
  Vědomě NEpromítnuto do `_cmd_run` (stejná mezera tam existuje taky,
  ale je mimo rozsah týhle spec - `_cmd_run` tímhle plánem není měněný).
- **`_snapshot_db` dostala časový limit** (kolo 15 IMPORTANT) -
  `Connection.backup()` sama nemá žádný deadline, při dlouhodobě zamčené
  DB by mohla viset neomezeně. `progress` callback (SQLite ho volá po
  každé dávce zkopírovaných stránek) hlídá `time.monotonic()` a po 30 s
  vyhodí `TimeoutError`.
- **Obnova ze zálohy teď počítá i s `-wal`/`-shm` sidecary** (kolo 15
  IMPORTANT) - `os.replace` sám je nesmaže, novější/cizí `-wal` obsah by
  po obnově mohl DB při příštím otevření změnit nebo poškodit. Dnešní
  `state.connect()` WAL nepoužívá, takže jde o obranu proti BUDOUCÍ
  změně žurnálovacího režimu, ne dnešní hrozbu.
- **Chybová tabulka "jen fluency → přijato" byla zavádějící** (kolo 15
  IMPORTANT) - `_to_finding`'s `action` závisí VÝHRADNĚ na `severity`,
  ne na `type`, takže kritický `fluency` nález (`action="revise"`) se
  ODMÍTÁ stejně jako kterýkoli jiný `revise` nález - "fluency" sám o
  sobě žádnou výjimku nedává. Tabulka i testovací scénář opraveny.
- **Test zálohy z "bytově identický" na "logicky rovnocenný"** (kolo 15
  NIT) - od kola 14 vzniká přes `sqlite3.Connection.backup()` (kopíruje
  na úrovni STRÁNEK, ne bajtů), takže výsledný soubor nemusí být bajtově
  totožný s originálem, i když obsahuje stejná data - starší test
  tvrzení bylo nechtěný vedlejší efekt kolo-14 změny mechanismu.
- **`critic.review()` docstring rozšířen na oba volající kontexty** (kolo
  15 NIT) - tvrdil jen "pipeline udělá flagged kapitolu" (platí pro
  `run`), ale `polish` (druhý volající, stejná `pipeline._run_critic`)
  vede k `outcome="rejected"` BEZ jakékoli změny statusu kapitoly v DB -
  kvalitativně jiný výsledek téže výjimky podle kontextu.
- **Rozhodnutí kolo 9 (backup mechanismus) dostalo POZN. o kolo-14
  náhradě** (kolo 15 NIT) - stejný vzorec jako kolo-12 POZN. u kola 7/8,
  jen kolo 9 samo tehdy nedostalo.
- **`_snapshot_db` dostala `pages=100`** (kolo 16 IMPORTANT, opravuje
  kolo 15) - výchozí `pages=-1` zkopíruje CELOU DB v jednom kroku, takže
  `progress` callback (a tedy i deadline z kola 15) by se zavolal nejvýš
  jednou, AŽ PO dokončení - kosmetický, ne skutečný časový limit. Ověřeno
  přímo v Python `sqlite3` dokumentaci.
  **POZN. (kolo 18): regresní test z kola 16 sám byl slepý** - `timeout=0`
  → `TimeoutError` nerozliší opravu od původní chyby, protože OBOJÍ
  varianty nakonec `TimeoutError` vyhodí, jen v jiný moment (rozbitá
  `pages=-1` AŽ po dokončení celé kopie, opravená `pages=100` UPROSTŘED).
  Přepsáno na přímé ověření argumentu `pages` volání `backup()` -
  `sqlite3.Connection` je immutable C typ (jeho metody nejdou
  monkeypatchnout), takže spy jde přes proxy connection z
  monkeypatchnutého `main.sqlite3.connect` (kolo 19 IMPORTANT).
- **`_polish_rejected` srovnává POČTY výskytů konkordančních klíčů, ne
  jen přítomnost** (kolo 16 IMPORTANT) - čisté množinové srovnání
  (`k not in baseline_keys`) přehlédne, když se STEJNÝ pre-existující
  problém objeví VÍCKRÁT po stylizaci (klíč sám "už byl známý"). Přepsáno
  na `Counter`-based srovnání (`after_counts[k] > baseline_counts.
  get(k, 0)`).
  **POZN. (kolo 17-18): VRÁCENO ZPĚT na množinové srovnání** - přímé
  ověření `src/concordance.py` ukázalo, že `check_chapter()` sama
  dedupuje KAŽDÝ typ nálezu na úrovni jednoho volání (`leak` nejvýš
  jednou na term_id, `inconsistency` přes vlastní `reported` množinu,
  `omission` Mention jen `if not mentions`) - scénář "1× → 2×", co měl
  `Counter` chytat, touhle cestou nikdy nenastane. `Counter` byl
  zbytečná komplikace řešící neexistující problém, ne špatná oprava -
  vráceno na jednodušší množinu + integrační test s REÁLNÝM
  `check_chapter()`, co tohle tvrzení dokládá.
- **Obnova ze zálohy: sidecar soubory se mažou AŽ PO `os.replace`, ne
  před ním** (kolo 16 IMPORTANT, opravuje kolo 15) - mazání PŘED
  přejmenováním otvíralo okno, kdy by pád uprostřed mohl připravit
  AKTUÁLNÍ (ještě nenahrazenou) `db` o její vlastní potřebný `-journal`.
  Přidán i `-journal` (rollback-mode sidecar, co tenhle projekt SKUTEČNĚ
  používá, na rozdíl od teoretického WAL `-wal`/`-shm`). VĚDOMĚ
  NEPŘIJATO: "testovaná, zamykaná příkazová obálka pro obnovu" - obnova
  zůstává dokumentovaný ruční postup (main.py zastavený), plná
  automatizace by byla nová netriviální schopnost mimo rozsah týhle
  spec (viz nový bullet v "Mimo rozsah").
- **`_paragraph_count` normalizuje konce řádků a prázdné řádky s bílými
  znaky** (kolo 16 NIT) - holé `text.split("\n\n")` nezachytí CRLF
  (`\r\n\r\n` neobsahuje dva `\n` za sebou) ani "prázdný" řádek s jen
  mezerami. V praxi spíš teoretické riziko (`open(..., "r")` už dělá
  universal-newlines normalizaci při čtení), oprava je ale zadarmo a
  robustnější.
- **`--ignore-user-config` přidán do `codex exec` volání** (kolo 17
  IMPORTANT) - ověřeno přímo `codex exec --help`. `-C work_dir` izoluje
  jen pracovní adresář, NE uživatelův globální `~/.codex/config.toml`
  (MCP servery, pluginy) - ten se BEZ týhle vlajky načítá vždy, bez
  ohledu na `-C`. Dvojí přínos: spolehlivost (tenhle samotný
  plan-consensus proces opakovaně narazil na `codex exec` viset na
  startu kvůli MCP serveru bez vlastního timeoutu v globálním configu -
  `polish` by v produkci zdědilo stejné riziko při KAŽDÉM spuštění) a
  zúžená útočná plocha (méně nástrojů, co by prompt injection z textu
  knihy mohla zneužít).
  **POZN. (kolo 18): otázka "omezuje `read-only` i ČTENÍ mimo `-C`?"
  VYŘEŠENA živým testem - NE, čtení zůstává neomezené (viz kolo-18
  bullet níže a bezpečnostní detail 6 v `polish` docstringu). Kolo 19
  eskalovalo tenhle nález na BLOCKING - viz sekce "Bezpečnostní
  rozhodnutí" níže.**
- **Obnova ze zálohy: zdokumentováno zbývající riziko + přidán ověřovací
  krok** (kolo 17 IMPORTANT) - i "sidecar mazání AŽ PO `os.replace`"
  (kolo 16) má vlastní úzké okno (pád mezi replace a úklidem sidecarů
  nechá STARÝ `-journal`/`-wal` vedle ČERSTVĚ obnoveného souboru). SQLite
  hot-journal validace proti change-counteru by tohle měla ošetřit, ale
  v týhle relaci NEOVĚŘENO s jistotou. Recept teď žádá druhé `PRAGMA
  integrity_check` PO celém postupu (na finální `db`, ne jen na
  `tmp_path` před přejmenováním) - žádný nový kód, jen další krok
  ručního postupu.
- **`config.STYLIST_TIMEOUT_SECONDS`/`STYLIST_MAX_CHARS` PŘIDÁNY** (kolo
  17 IMPORTANT) - `timeout=180` byl natvrdo v parametru `stylist.polish`
  bez cesty ke konfiguraci; dlouhá kapitola nemá jak dostat víc času bez
  zásahu do kódu. `STYLIST_MAX_CHARS` (výchozí 60 000 znaků EN+CZ) dá
  RYCHLÉ, jasné odmítnutí extrémně dlouhé kapitoly MÍSTO čekání na jistý
  timeout - hrubá, ručně nastavitelná pojistka, ne přesný odhad
  tokenového limitu konkrétního modelu (ten je uživatelsky
  konfigurovaný). NEMĚNÍ rozhodnutí "žádné dělení kapitoly na scény" -
  jde jen o rychlé odmítnutí, ne o zpracování po částech.
- **Próza opravena: "translator/kritik" →
  "translator (translate_scene/revise_chapter)"** (kolo 17 NIT) - ověřeno
  přímo v `src/pipeline.py`: `_run_critic(en, cz, client)` volá
  `critic.review(en, cz, client)` BEZ `guide_block` - `guide_block`
  dostává jen translator (obě jeho funkce), nikdy kritik. Opraveno na 3
  místech.
- **Chybová tabulka doplněna o číselný guard a upřesněna o multiplicitu**
  (kolo 17 NIT) - chyběl samostatný řádek pro selhání `_number_sequence`
  a pro `config.STYLIST_MAX_CHARS`; řádek "stejná podoba → přijato"
  neuváděl podmínku "stejný nebo nižší počet výskytů" (kolo 16).
- **`Counter`-based multiplicita v `_polish_rejected` VRÁCENA ZPĚT na
  množinové srovnání** (kolo 17-18 IMPORTANT) - přímé ověření `src/
  concordance.py` prokázalo, že `check_chapter()` sama dedupuje KAŽDÝ
  typ nálezu (leak nejvýš jednou na term_id, inconsistency přes vlastní
  `reported` množinu, omission Mention jen `if not mentions`) - scénář
  "1× → 2×" z kola 16 je touhle cestou nedosažitelný. `Counter` řešil
  neexistující problém - vráceno na jednodušší množinu + integrační test
  s REÁLNÝM `check_chapter()`, co tohle tvrzení dokládá (ne jen ručně
  sestavené duplicity).
- **Test dlouhého stdin vstupu opraven po kole-17 kolizi** (kolo 18
  IMPORTANT) - `test_polish_long_input_goes_through_stdin_not_argv`'s
  vstup (>100 000 znaků) je od kola 17 nad `config.STYLIST_MAX_CHARS`
  (60 000), takže by test spadl na size guardu dřív, než by vůbec
  otestoval to, co má (stdin mechanismus) - `monkeypatch` limit nahoru
  pro tenhle konkrétní test.
- **Regresní test na `pages=100` byl slepý, přepsán na přímé ověření
  argumentu** (kolo 18 IMPORTANT) - `timeout=0` → `TimeoutError` test
  nerozliší opravu od původní chyby (obojí nakonec `TimeoutError`
  vyhodí, jen v jiný moment). Přepsáno na přímé ověření `pages` -
  přes proxy connection z monkeypatchnutého `main.sqlite3.connect`
  (`sqlite3.Connection` je immutable C typ, jeho metody nejdou
  monkeypatchnout přímo - kolo 19 IMPORTANT opravuje kolo-18 návrh spy
  na typu).
- **Bezpečnostní hranice čtení mimo `-C` OVĚŘENA PŘÍMÝM TESTEM, ne jen
  zdokumentovaná jako otevřená otázka** (kolo 18 IMPORTANT) - spustil
  jsem živě `codex exec --sandbox read-only -C <izolovaný adresář>` s
  promptem žádajícím přečíst soubor MIMO `-C` - Codex ho ÚSPĚŠNĚ přečetl
  a vrátil přesný obsah. `read-only` tedy omezuje ZÁPISY, ne ČTENÍ -
  prompt injection z textu knihy by TEORETICKY (teď POTVRZENĚ TECHNICKY
  MOŽNÉ) mohla exfiltrovat obsah citlivého souboru. Plná OS/kontejnerová
  izolace VĚDOMĚ mimo rozsah (infrastrukturní rozhodnutí, patří
  uživateli) - přidán povinný canary test do "Manuální ověření" a nový
  bullet do "Mimo rozsah", riziko zůstává zdokumentované a OVĚŘENÉ, ne
  skryté.
- **Próza opravena: "EN a stylizovaným" → "PŮVODNÍ CZ a stylizovaným
  CZ"** (kolo 18 NIT) - `_number_sequence` srovnává `cz_text` vs.
  `styled`, ne EN vs. stylizovaný.
- **Nadpis "Bezpečnostní detaily (kola 1-6)" rozšířen na "kola 1-6 a
  17-18"** (kolo 18 NIT) - bod 6 (`--ignore-user-config`) přibyl v kole
  17, nadpis se neaktualizoval.
- **BEZPEČNOSTNÍ BLOCKER VYŘEŠEN: povinný opt-in `config.STYLIST_ACCEPT_
  FS_RISK`** (kolo 19 BLOCKING) - Codex eskaloval kolo-18 ověřený nález
  (`codex exec` čte celý disk) na BLOCKING: dokumentovat + canary test
  nestačí, exfiltrace nastane DŘÍV než guardraily. Rozhodnutí uživatele:
  varianta 1 - `polish` běží jen s `STYLIST_ACCEPT_FS_RISK = True`
  (default `False`), jinak `_cmd_polish` rovnou odmítne s hláškou o
  riziku. Nová sekce "Bezpečnostní rozhodnutí (kolo 19)" dokumentuje
  ověřený nález, rozhodnutí i migrační cestu na variantu 2/3 (neagentní
  API / kontejner) - jde odložit, protože celé riziko je uvnitř
  `stylist.polish()`, zbytek systému je provider-agnostický.
- **`_codex_argv` helper - JEDINÉ místo skládání argv V PRODUKCI** (kolo
  19 IMPORTANT, zpřesněno kolo 20/24) - argv pro `codex exec` byl inline
  v `polish`, zvlášť v argv testu a zvlášť v ručním canary checklistu.
  Teď `polish()` ho volá a canary checklist ho odkazuje. Argv TEST ho
  ale VĚDOMĚ NEVOLÁ - má ručně zapsaný oracle (kolo 20 - jinak by byl
  tautologický a nezachytil odstranění bezpečnostních flagů).
- **Spy test na `pages=100` přes proxy connection, ne monkeypatch typu**
  (kolo 19 IMPORTANT) - `sqlite3.Connection` je immutable C typ, jeho
  metody nejdou monkeypatchnout (`TypeError`). Spy jde přes
  monkeypatchnutý `main.sqlite3.connect` vracející proxy.
- **Kolo-17 Rozhodnutí bullet o "read-only čtení mimo -C" dostal POZN. o
  kolo-18 ověření** (kolo 19 NIT) - stejný vzorec jako u ostatních
  historických bullet, kolo 17 samo tehdy ještě nemělo odpověď.
- **Bezpečnostní brána VYNUCENA PŘÍMO v `stylist.polish()`, ne jen v
  `_cmd_polish`** (kolo 20 BLOCKING) - kolo 19 dalo opt-in check jen do
  CLI obálky; přímé volání veřejné `stylist.polish()` by ho obešlo.
  `polish()` teď bez `STYLIST_ACCEPT_FS_RISK is True` rovnou vyhodí
  `StylistError`. `_cmd_polish` si nechává vlastní časnou hlášku (hezčí
  UX). Test modul má autouse fixture nastavující flag na `True`, jinak
  by KAŽDÝ test volající `polish()` spadl.
- **`_polish_rejected` počítá VÝSKYTY povrchu v textu, ne jen množinu
  findings** (kolo 20 IMPORTANT) - kolo 16→18 řešilo, jestli srovnávat
  množinu nebo `Counter` NAD FINDINGS; kolo 20 ukázalo, že OBOJÍ míjí
  skutečný scénář: `check_chapter()` dedupuje "1 leak `White Council`" i
  "2 leaky `White Council`" na STEJNÝ jediný klíč. Přidána DRUHÁ
  kontrola: pro pre-existující leak/inconsistency nález se počítá výskyt
  jeho `actual` povrchu v `cz_before` vs. `cz_after` - víc PO stylizaci
  = nové zhoršení. `_polish_rejected` proto teď bere i `cz_before`/
  `cz_after`.
- **Argv test PŘESTAL být tautologický** (kolo 20 IMPORTANT) - kolo 19
  skládalo `expected` stejnou `_codex_argv()` funkcí jako produkce,
  takže by nezachytil odstranění `--sandbox read-only` apod. Vrácen
  ručně přepsaný seznam - duplicita mezi implementací a testovacím
  oracle je tu ZÁMĚRNÁ. (`_codex_argv` helper pro PRODUKCI zůstává - DRY
  je správně tam, ne v testu bezpečnostního kontraktu.)
- **`rendered_terms` forwarduje JEN `source == "rendered"`** (kolo 20
  IMPORTANT) - dřív procházely i `detected` mentions, co se po úspěšném
  průchodu uložily jako `rendered` - falešná provenience. `detected`
  concordance dohledá sama.
- **Stale komentář o `shutil.copy2` v `finally` bloku opraven** (kolo 20
  NIT) - "VČETNĚ selhání samotného `shutil.copy2`" → `_snapshot_db`.
  (Codexovo opakované hlášení stale `shutil.copy2` prózy - kola 15-19
  falešné poplachy podle posunutého číslování, kolo 20 skutečný zásah.)
- **`_polish_rejected` počítá výskyty přes `concordance.find_form_
  occurrences`, ne `str.count`** (kolo 21 IMPORTANT) - `str.count` je
  case-sensitive a nezná skloňování, takže přidaný výskyt s jinou
  velikostí písmen nebo v jiném pádu by prošel. `find_form_occurrences`
  stemuje + lowercasuje obě strany stejně.
- **Test dlouhého stdin vstupu SKUTEČNĚ čte stdin** (kolo 21 IMPORTANT) -
  dřívější `_fake_codex` stdin vůbec nečetl, takže test by prošel i při
  zahození/uříznutí promptu. Nová fake varianta vytáhne CZ text ze
  stdinu, vrátí ho upravený a test ověří délku.
- **Chybová tabulka: řádek "stejný konkordanční nález → přijato"
  rozdělen na DVĚ podmínky** (kolo 21 IMPORTANT) - po kolo-20 opravě je
  "stejný klíč" přijat JEN se stejným/nižším počtem výskytů povrchu;
  víc výskytů = zahozeno.
- **Docstring nadpis + opt-in odstavec dotažené na kolo 20** (kolo 21
  NIT) - nadpis "kola 1-6 a 17-18" → "17-20", odstavec doplněn o
  závaznou kontrolu v `polish()`; směrový odkaz "výš" → "níže".
- **`_polish_rejected` počítá VŠECHNY zakázané EN povrchy termínu, ne
  jen `actual`** (kolo 22 IMPORTANT) - nový leak JINÉHO aliasu, když
  `check_chapter()` dál hlásí jako `actual` první existující leak, by
  jinak prošel. `_polish_rejected` teď bere i `glossary_rows`. VĚDOMĚ
  NEPŘIJATA druhá půlka návrhu ("pokles počtu schválených CZ forem →
  odmítnout") - pokles je nejednoznačný (legitimní stylistické sloučení
  vět), false-reject cena je vyšší než úzká zbytková skulina, co je
  navíc pokrytá `check_chapter()` novou-inconsistency detekcí +
  meaning-check.
- **`stylist.polish()` VYNUCUJE konfigurační invarianty PŘÍMO** (kolo 22
  IMPORTANT) - veřejné API tiše obcházelo `_cmd_polish` kontroly:
  `codex_cmd=[]` (prázdný, falsy) spadl na produkční `["codex"]`
  (nebezpečné po opt-inu), `codex_model=None` obešel povinný
  `CODEX_MODEL`, `timeout=180` natvrdo obešel `STYLIST_TIMEOUT_SECONDS`.
  Teď: `codex_cmd None` = "vezmi produkční", `[]`/neúplný = `StylistError`;
  `codex_model` fallback na `config.CODEX_MODEL`, prázdný = `StylistError`;
  `timeout: int | None = None` → `config.STYLIST_TIMEOUT_SECONDS`. Test
  autouse fixture nastavuje i `CODEX_MODEL`.
- **3 NITS opraveny** (kolo 22) - preflight próza (`_resolve_codex_cmd`
  se volá i v `polish()`, jen `shutil.which` ne podruhé); sidecar úklid
  při obnově je "bezpečnostně nutný", ne "kosmetický"; chybová tabulka
  omezuje multiplicitu na `leak`/`inconsistency` (ne `omission`).
- **`codex_model.strip()` se PŘIŘADÍ, ne jen zvaliduje** (kolo 23
  IMPORTANT) - kolo 22 ořezanou hodnotu použilo jen ke kontrole,
  netrimovaná šla do `-m`. Whitespace-padded model by šel s mezerami.
- **timeout dostal SKUTEČNÝ test** (kolo 23 IMPORTANT) - kolo-22
  `test_polish_config_invariants` to tvrdil v docstringu, ale assertci
  neměl. Timeout ověřuje SAMOSTATNÝ `test_polish_uses_config_timeout_
  and_strips_model` - spy na `subprocess.Popen.communicate` zachytí
  `timeout` kwarg a ověří, že == monkeypatchnutý
  `config.STYLIST_TIMEOUT_SECONDS`; zároveň ověří ořez modelu v argv.
- **`--ignore-rules` NEPŘIDÁN / kolo-23 přidání VRÁCENO** (kolo 23 NIT
  přidalo, kolo 25 IMPORTANT vrátilo) - zdůvodnění bylo obrácené.
  `--ignore-rules` NEnačte user/project execpolicy `.rules`, čímž
  útočnou plochu ROZŠIŘUJE: `codex exec` je agentní a shell příkazy
  SPOUŠTÍ (canary test - Codex spustil `Get-Content`), takže restriktivní
  `forbidden`/`prompt` pravidla v uživatelových `.rules` můžou exfiltraci
  omezit. `--ignore-user-config` (hang fix) zůstává - je SAMOSTATNÝ a
  execpolicy `.rules` neřeší. Argv test + canary checklist upraveny zpět.
- **`polish` doplněn do modulového docstringu `main.py`** (kolo 23 NIT) -
  sekce "Fáze běhu:" nový příkaz neuváděla.
- **`_snapshot_db` deadline má SKUTEČNÝ test** (kolo 24 IMPORTANT) -
  pages=100 test sám nezachytí regresi, co odstraní `progress=_check_
  deadline` nebo vyhození `TimeoutError`. Přidán test s proxy `.backup()`
  (zavolá callback) + monkeypatchnutý `main.time.monotonic` za deadline
  → očekává `TimeoutError`.
- **2 NITS - stale próza** (kolo 24) - `_codex_argv` docstring +
  kolo-19 bullet tvrdily, že argv test `_codex_argv` volá; od kola 20 ho
  VĚDOMĚ nevolá (ruční oracle). "Mimo rozsah" backup próza upřesněna:
  "nejvýš jedna záloha za běh, jen před prvním PŘIJATÝM zápisem" (běh bez
  přijaté změny zálohu nevytvoří).
- **3 NITS - prozaická konzistence** (kolo 26, poslední kolo -
  CONSENSUS): (a) "viz canary výš" v canary checklistu → POVINNÝ CANARY
  TEST je NÍŽ; (b) preflight próza tvrdila `status="ok"` bez preflightu -
  zastaralé, spec jinde (kolo 5/6) říká `fatal` když všechny kapitoly
  `failed`; přeformulováno na "N hlášek + fatal, drahá cesta ke správnému
  stavu"; (c) docstring "výstup prochází STEJNOU kontrolou jako originál"
  → "STEJNÝMI (konkordance + kritik) PLUS DODATEČNÝMI" (číselný guard,
  odstavce, CZ-před vs. CZ-po meaning check - originál nemá "před" verzi).

**Po kole 26 vydali Codex i Claude CONSENSUS ve stejném kole - plán je
hotov. Viz `plan-consensus/final-verdict.md`.**
