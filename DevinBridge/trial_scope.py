"""Owner-authorized, 24-hour, fail-closed extension of route-edit paths."""
from __future__ import annotations
import time
from pathlib import Path
from .bridge_store import read_json

EXTRA = frozenset({'ForeverRoute.lua','ForeverRoute.toc',
    'ForeverRoute_TravelTopology.lua','docs/route_engineering',
    # V3 dev repo paths (db70338, trial-only)
    'tools','tests','docs','audit','reports','Generated','Data',
    'ForeverRoute_PlannerV3.lua','ForeverRoute_PlannerV4.lua',
    'ForeverRoute_RuntimeContract.lua','ForeverRoute_QuestExpedition.lua',
    'ForeverRoute_SPFBridge.lua','ForeverRoute_BetaCollector.lua'})
# Second worktree grant is fail-closed too: only this exact repo path
# may be added by the 24h trial, never anything else.
EXTRA_WORKTREES = frozenset({
    r'C:\Users\Dawis\Saved Games\ForeverRoute-db70338'})
TRIAL = Path('autonomy_scope') / 'FOREVERROUTE_24H_TRIAL.json'

def extend_program(root, program, now=None):
    result = dict(program)
    result['trial_active'] = False
    if not program.get('owner_authorized') or not program.get('ongoing'):
        return result
    data = read_json(Path(root) / TRIAL, {})
    if not isinstance(data, dict) or data.get('owner_authorized') is not True:
        return result
    if data.get('program_id') != program.get('program_id'):
        return result
    try:
        start = float(data['starts_epoch'])
        end = float(data['expires_epoch'])
        current = time.time() if now is None else float(now)
    except (ValueError, KeyError, TypeError):
        return result
    if not start <= current < end or not 0 < end-start <= 86400.01:
        return result
    if str(data.get('worktree', '')).casefold() not in {
            str(x).casefold() for x in program.get('worktrees', [])}:
        return result
    extra = data.get('extra_allowed_paths')
    if not isinstance(extra, list) or not extra or not set(extra).issubset(EXTRA):
        return result
    result['allowed_paths'] = list(dict.fromkeys(
        [*program.get('allowed_paths', []), *extra]))
    # trial may also grant the pinned second worktree — expires with it
    extra_wt = data.get('extra_worktrees')
    if isinstance(extra_wt, list) and set(extra_wt).issubset(EXTRA_WORKTREES):
        result['worktrees'] = list(dict.fromkeys(
            [*program.get('worktrees', []), *extra_wt]))
    result['trial_active'] = True
    result['trial_expires_epoch'] = end
    return result