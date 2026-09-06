## BLOCKING

- [design.md:408](C:/Users/Honza/Nextcloud/Jan/PROJECTS/book-translator/docs/superpowers/specs/2026-09-06-book-translator-design.md:408) + [design.md:424](C:/Users/Honza/Nextcloud/Jan/PROJECTS/book-translator/docs/superpowers/specs/2026-09-06-book-translator-design.md:424): `glossary` nemá aliasy ani entity ID, ale `concordance` má hledat `term_en/alias` a chunked scout umí „stejný povrch, různé entity“. Se `term_en PK` to nejde konzistentně implementovat.  
  Fix: přidat `term_id PK`, `canonical_en`, `aliases JSON` nebo `term_aliases`; unikátní klíč dělat nad normalizovaným kanonickým ID, ne povrchem.

## IMPORTANT

- [design.md:141](C:/Users/Honza/Nextcloud/Jan/PROJECTS/book-translator/docs/superpowers/specs/2026-09-06-book-translator-design.md:141): `rendered_terms = union podle term_en, poslední vyhrává` ztrácí více tvarů v jedné kapitole/scénách. Tím se rozbije detekce intra-chapter inconsistency i drift.  
  Fix: `rendered_terms` jako list výskytů `{term_en, cz_as_used, scene_idx?}`, bez last-wins.

- [design.md:501](C:/Users/Honza/Nextcloud/Jan/PROJECTS/book-translator/docs/superpowers/specs/2026-09-06-book-translator-design.md:501): SQLite `UNIQUE(chapter_idx, kind, scope_key, severity)` nededuplikuje řádky se `scope_key NULL`. `style/other` budou duplikovatelné.  
  Fix: nepoužívat NULL v unikátním klíči; uložit sentinel `""`/`__global__`, nebo použít generated column `scope_key_norm`.

- [design.md:168](C:/Users/Honza/Nextcloud/Jan/PROJECTS/book-translator/docs/superpowers/specs/2026-09-06-book-translator-design.md:168) + [design.md:496](C:/Users/Honza/Nextcloud/Jan/PROJECTS/book-translator/docs/superpowers/specs/2026-09-06-book-translator-design.md:496): drift otázka nemá jasný `chapter_idx`, ale schema ho vyžaduje a `UNIQUE` je po kapitole. Drift je globální přes více kapitol.  
  Fix: povolit `chapter_idx NULL` pro globální otázky se zvláštním unikátním indexem, nebo zavést `origin_chapter_idx` + samostatný `question_scope`.

- [design.md:357](C:/Users/Honza/Nextcloud/Jan/PROJECTS/book-translator/docs/superpowers/specs/2026-09-06-book-translator-design.md:357) + [design.md:520](C:/Users/Honza/Nextcloud/Jan/PROJECTS/book-translator/docs/superpowers/specs/2026-09-06-book-translator-design.md:520): „zápis po každém volání“ není pravda pro výjimky, protože plán loguje až po `inner.complete`. Selhaná API volání a retry exhaustion zmizí z auditu i cost reportu.  
  Fix: definovat logging v `try/finally`; `status=ok|truncated|error`, `error_class`, tokeny nullable.

- [design.md:537](C:/Users/Honza/Nextcloud/Jan/PROJECTS/book-translator/docs/superpowers/specs/2026-09-06-book-translator-design.md:537): transakční hranice jsou rozporné. Krok 0 se commituje před LLM, kroky 6-8 mají být jedna transakce, obecná sekce říká `glossary`, `term_mentions`, `chapters`, `questions` při kapitole jedna transakce.  
  Fix: explicitně: transakce A = `processing`; mimo transakci LLM; transakce B = kroky 6-8 včetně questions.

## NITS

- Model `claude-sonnet-5` jsem ověřil jako aktivní podle Anthropic docs; ponechat ale odkaz/checklist v pilotu, ne jen text „ověřit“. Zdroj: https://docs.anthropic.com/en/docs/about-claude/model-deprecations

## VERDICT

CHANGES_NEEDED