## IMPORTANT

- `config.py` ř. 373–383, bezpečnostní rozhodnutí ř. 92–107: `STYLIST_REPORT_REJECTED_TEXT=True` je nebezpečný default. Argument, že persistence je „uvnitř“ již přijatého FS rizika, neplatí: opt-in k přístupu agenta na disk není souhlas s trvalým uložením potenciálně exfiltrovaných dat, navíc do synchronizovaného pracovního adresáře. Nastavit default `False`; plný obsah vyžadovat samostatným explicitním opt-inem.
- `_rejection_reasons`, ř. 1217–1262: deduplikace je širší než deklarovaný „týž `(source,type,term_id,actual)`“. Kód přeskočí celý `(type, term_id)`, takže při novém chybném povrchu B současně s nárůstem již existujícího povrchu A zaznamená pouze B. Rozhodnutí zůstane správné, ale `reasons` neobsahuje všechny skutečné příčiny, což porušuje hlavní účel reportu. Deduplikovat podle konkrétního povrchu/`_finding_key`, ne podle celého termínu; přidat test se dvěma různými `actual` stejného termínu.

## NITS

- Ř. 14–16 stále tvrdí, že zamítnutý výstup se „zahodí“. Při zapnutém reportování se nepřijme, ale trvale se uloží. Upravit úvodní shrnutí.
- Ř. 1044–1048 tvrdí, že vnější `KeyboardInterrupt` handler „stačí sám o sobě“; kolo 30 právě prokázalo opak kvůli reportu.
- Nadpis ř. 3439 uvádí „Kolo 27–29“, přesto sekce obsahuje i kolo 30.

## VERDICT

CHANGES_NEEDED