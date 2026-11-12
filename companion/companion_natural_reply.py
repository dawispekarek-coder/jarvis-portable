"""Readable Czech user-facing tool results. Keep full JSON only in task audit records."""

def summarize(name, result):
    """Return human-readable verified messages for selected real tool workflows."""
    if not result.get('ok'):
        return None
    v=result.get('value') or {}
    if not isinstance(v,dict):
        return None
    if name in ('lali_pooli_regenerate_ten_scenes','lali_pooli_story_scenes_create'):
        total=int(v.get('total_scenes',10 if name=='lali_pooli_regenerate_ten_scenes' else 9))
        if v.get('started'):
            return ('Jdu na to, pane. Spustil jsem vytváření '+str(total)+' obrazových scén Lali a Pooliho. '
                    'Používám schválené předlohy postav a budu je zpracovávat postupně, jednu po druhé. '
                    'Pooli musí zůstat stejně velký nebo o něco větší než Lali. '
                    'Teď běží samotné generování; hotové ilustrace ještě nemám a nic nepublikuji. '
                    'Výsledky uložím do storyboardu k vaší kontrole.')
        if v.get('reason')=='already_running' or v.get('running') or v.get('background_process_running'):
            return ('Na ilustracích už pracuji, pane. Výroba běží na pozadí a nové obrázky přibývají postupně. '
                    'Průběh kontroluji podle skutečných výstupů, nikoli podle pouhého potvrzení úlohy. '
                    'Všechny návrhy zůstávají neschválené, dokud je neuvidíte.')
        return ('Sérii už mám v pracovním systému založenou. Před novým spuštěním ověřím výsledky '
                'a nebudu přepisovat již vytvořené obrázky. O případné překážce vás budu informovat.')
    if name in ('lali_pooli_regenerate_ten_status','lali_pooli_story_scenes_status'):
        p=v.get('progress') or {};steps=p.get('scenes') or {}
        count=sum(1 for x in steps.values() if isinstance(x,dict) and x.get('status')=='CANDIDATE_GENERATED')
        total=int(v.get('total_scenes') or p.get('total') or 10)
        plural='návrh' if count==1 else 'návrhy' if 2<=count<=4 else 'návrhů'
        state=p.get('status','bez záznamu')
        if v.get('running') or v.get('background_process_running'):
            return (f'Pracuji na tom, pane. Z {total} scén je v tuto chvíli vytvořeno {count} {plural}. '
                    'Další scéna se právě připravuje. Zatím se jedná o pracovní obrázky, které bude potřeba vizuálně zkontrolovat.')
        return (f'Právě jsem zkontroloval stav výroby. Z {total} scén má {count} {plural}. '
                f'Úloha teď neběží, evidovaný stav je {state}. '
                'To samo o sobě ještě nepotvrzuje výtvarnou kvalitu a nic nebylo zveřejněno.')
    return None