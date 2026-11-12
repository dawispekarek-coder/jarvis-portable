from pathlib import Path
p=Path(__file__).with_name('companion_agent.py')
s=p.read_text(encoding='utf-8')
needle=' return json.dumps(v,ensure_ascii=False)[:8000]'
assert needle in s, 'generic fallback missing'
s=s.replace(needle," return ('Krok jsem zpracoval a výsledek zaznamenal do přehledu úloh. ' + ('Podle nástroje byl ověřený. ' if v.get('verified') else 'Úspěch zatím nemám plně ověřený. ') + 'Podrobnosti nechávám v technickém protokolu a mohu se podle nich pustit do dalšího kroku.')",1)
needle2="SYSTEM='''ANIMATOR MISSION:"
assert needle2 in s
s=s.replace(needle2,"SYSTEM='''PŘIROZENÝ MLUVENÝ PROJEV: Mluv jako příjemný, schopný český osobní společník. Uživatel chce delší a živější přirozené odpovědi, ne strohé JSON ani názvy interních nástrojů. Pro běžnou činnost odpovídej 2 až 5 jasnými větami: krátké přijetí, co skutečně děláš, co bude výsledkem a co ještě není hotové. Na začátku úkolu se hodí 'Jdu na to, pane.' nebo 'Rozumím, pane. Postarám se o to.' Neopakuj oslovení v každé větě. Neodhaluj debug kódy, PID, JSON, interní cesty a nástrojové argumenty v běžném hovoru. Technické detaily patří do výpisu úloh. Když se práce jen spustila, NEVYDÁVEJ JI ZA HOTOVOU. Když je chyba, vysvětli stručně česky, co se stalo a co s tím dál.\nANIMATOR MISSION:",1)
p.write_text(s,encoding='utf-8')
print('UPDATED')