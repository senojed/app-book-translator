# Pilotní checklist (2-3 reálné kapitoly, ~$1)

- [ ] **Ověřit model + ceny + limity** proti https://docs.anthropic.com/en/docs/about-claude/model-deprecations
      a https://platform.claude.com/docs/en/models/sonnet-5/whats-new-sonnet-5 .
      Zapsat aktuální hodnoty do `config.py` (MODEL_*, PRICE_*_PER_MTOK, MAX_TOKENS_*).
- [ ] `python main.py init <kniha.epub>` - sedí počet kapitol?
- [ ] `python main.py scan` - vejde se do 1 volání, nebo hlásí truncated → `scan --chunked`?
- [ ] `python main.py review` - dá se návod pohodlně projít? Ulož.
- [ ] Zúžit `chapters` v DB na 2-3 (ručně `DELETE FROM chapters WHERE idx > 3`).
- [ ] `python main.py run` - projde? Kolik `guess` otázek / `candidate` termínů na kapitolu?
- [ ] Přečti výstup: je překlad použitelný? Kde selhává?
- [ ] Rozchází se kritik s translatorem smysluplně? (Kolikrát se spustila revizní smyčka a pomohla?)
      → Pokud skoro nikdy: signál, že revizní smyčka je zbytečná režie - zvážit zjednodušení.
- [ ] `SELECT SUM(cost_usd) FROM llm_calls` - cena za kapitolu → extrapoluj na celou knihu.
- [ ] Falešné drift nálezy z kmenového porovnání - kolik? (→ potřeba LLM soudce dřív?)
