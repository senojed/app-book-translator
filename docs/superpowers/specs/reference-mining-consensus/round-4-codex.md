## BLOCKING

- ****§4 Pravidla hledání / `textnorm.py` / `count_cz_form`:** Specifikované algoritmy si odporují. `normalize_key()` vždy provede `casefold()`, takže následné case-sensitive hledání obecných slov není možné. Současně pravidla údajně platí pro obě strany, ale `concordance.find_form_occurrences()` používá jiné zpracování: `lower()`, `\w+`, žádné NFC ani zachování pomlček. Aktuálně proto nenajde ani `Za-Lord` v textu `Za-Lord` a naopak může zaměnit `Bílá rada` za `Bída rana`. Navržená oprava: oddělit normalizaci zachovávající velikost písmen od porovnávacího klíče a přesně vymezit odlišný kontrakt pro stupeň 0 a kmenové hledání stupně 1; případně rozšířit `concordance` a doplnit regresní testy falešných shod a pomlček.

- ****§ `merge_sources` / Review UI signatury:** Tvrzení, že přidání `reference_path=None` zachová kompatibilitu `build_app`, není samo o sobě pravdivé. Aktuální třetí poziční parametr je `on_saved` a testy jej tak volají. Přirozené vložení `reference_path` na třetí pozici interpretuje callback jako cestu. Navržená oprava: předepsat přesnou signaturu `build_app(draft_path, guide_path, on_saved, *, reference_path=None)` a předávat novou cestu pojmenovaně.

- ****§ Identita položek / `resolve`:** `id = section/normalize_key(surface)` není v existujícím vstupu zaručeně unikátní. `scout.scan_book()` nekontroluje prázdné ani duplicitní položky; deduplikace existuje pouze v `scan_chunks()`. Dvě položky stejné sekce proto mohou dostat stejné ID a nelze k nim jednoznačně přiřadit návrh ani finding. Navržená oprava: před těžbou validovat neprázdné klíče a deterministicky sloučit nebo odmítnout duplicity podle `(section, normalize_key(surface))`.

## IMPORTANT

- ****§ `write_reference`:** Pravidla slučování pokrývají pouze `attempted`, `failed` a `not_attempted`, přičemž `attempted` jsou výslovně jen ID poslaná modelu. Není určeno, jak se zapisují nové deterministické nálezy stupně 0. Navržená oprava: definovat kompletní stavový automat pro každé aktuální ID, včetně samostatného výsledku `stagestage0_resolved`.

- ****§ Validace lexikografa:** Chybějící ID v jinak validní odpovědi se změní na nové `unresolved`, čímž přepíše dřívější platný nález. Chybějící položka není totéž jako explicitní `cz: null`. Navržená oprava: chybějící ID považovat za selhání dané položky a převzít předchozí nález jako `stale`; pouze explicitní `null` má vytvořit `unresolved`.

- ****§ Fingerprint a `merge_sources`:** Při `fresh: false` se pouze skryjí čísla, ale stará hodnota `cz` či rozhodnutí `render` mohou stále předvyplnit formulář. Změna aliasů při zachovaném hlavním klíči tak může vytvoří hodnotu založenou na již neplatném důkazu. Navržená oprava: při nečerstvém fingerprintu nepoužívat reference k předvyplnění, nebo zavést fingerprint po jednotlivých položkách.

- ****§ Klasifikace `confirmed`:** Není určeno, zda prahy hitů a knih musí splnit primární povrch, nebo sjednocení primárního povrchu s aliasy. Jeden výskyt primárního tvaru a mnoho výskytů aliasu by podle současných datových struktur mohlo projít jako `confirmed`. Navržená oprava: prahy pro `confirmed` počítat výhradně z `per_form[primary]`; aliasy zobrazovat pouze jako doplňkový důkaz a přidat hraniční test.

- **§ Review UI – aktivní volba postavy:** Současný JavaScript používá `c.render || "keep"` a select nemá prázdnou volbu. Pouhé serverové odmítnutí `render=None` by uživateli zobrazilo „ponechat“, ale payload by zůstal prázdný; uživatel by musel volbu přepnout tam a zpět. Navržená oprava: explicitně požadovat prázdnou položku `-- vyber --`, nepoužívat fallback `"keep"` a otestovat serializovaný payload.

- **§ Chyby a persistence:** Není určeno chování běžných síťových/rate-limit výjimek, které současný `AnthropicClient` nepřevádí na `FatalRunError`. Rovněž `write_report(result, ...)` může reportovat nezmergovaný výsledek místo skutečně uložených převzatých `stale` nálezů. Navržená oprava: definovat taxonomii všech klientských výjimek a generovat report z finálního payloadu vráceného zápisem.

- **§ `load_reference`:** „Poškozený soubor se ignoruje“ platí pouze pro nevalidní JSON nebo neznámou verzi. Syntakticky validní soubor s chybnými typy může spadnout až v `merge_sources` nebo UI. Navržená oprava: validovat celé schéma včetně unikátních ID, sekcí a typů findings; jakékoli porušení ignorovat s varováním.

## VERDICT

CHANGES_NEEDED