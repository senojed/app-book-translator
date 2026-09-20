## IMPORTANT

- Task 2, Step 3 (ř. 870–892): Fatální revizní větev ukládá `mentions=[]`, ale `state.commit_chapter_result()` před vložením vždy smaže všechny existující `term_mentions` kapitoly. Zachovaný `translated_text` proto přijde o konkordanční metadata; tvrzení „jen bez nových mentions“ je nepřesné. Opravte větev tak, aby pro zachované `cz` deterministicky znovu sestavila mentions alespoň z existujícího glosáře a `rendered`, a přidejte regresní test s existujícím mention.

## VERDICT
CHANGES_NEEDED