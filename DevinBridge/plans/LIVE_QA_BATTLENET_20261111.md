# Live QA ForeverRoute — Battle.net launcher requirement (2026-11-11)

Status: DESIGN ONLY. Not enabled for autonomous dispatch. The standing CDP grant expressly prohibits live-WoW and game-install modifications. Do not alter that grant to make this happen implicitly.

## Confirmed local paths
- Battle.net client: `H:\Battle.net\Battle.net.exe`
- WoW Forever client: `H:\World of Warcraft\_forever_\Wow.exe`
- Active addon install: `H:\World of Warcraft\_forever_\Interface\AddOns\ForeverRoute`
- Existing in-game health probe: `ForeverRoute_Diagnostics.lua` / `ModuleHealth()`.

## Required launch workflow
1. Finish offline tests and create a candidate artifact in a separate staging location.
2. Never replace live addon when the game is running. Preserve byte-identical backup of installed addon and DO NOT erase any WTF/SavedVariables or character data.
3. Only after an explicit owner authorization for live QA, stage the candidate into the exact `_forever_` addon folder, with atomic restore and manifest validation. Never modify retail/classic paths.
4. Open the already-installed `Battle.net.exe` as the signed-in desktop user. Select World of Warcraft: Forever, press Play through the launcher UI. Do not invoke `Wow.exe` directly. Do not guess unsupported `--exec` codes.
5. Rely only on Battle.net's existing remembered session. Never read/store credentials, pass passwords on command line or bypass Authenticator. If login, account or realm/character selection requires user action, report WAITING_HUMAN. No character movement or gameplay actions.
6. In-game read-only probe records ADDON_LOADED, PLAYER_LOGIN, module health, safe initialization checks, and captured Lua errors. Only claim in-game PASS after actual client confirmation, not mere process existence or successful file copy.
7. Collect results after proper reload/logout in a designated QA output, distinguish no-result/timeout from PASS. Retain provenance (addon hash/build/client version). Restore previous addon after testing if authorized and safe.
8. Only after proven success and explicit safety scope, feed failing checks back to Jarvis repair planning; do NOT publish or merge automatically.

## Engineering limitations
- Battle.net single sign-on is conditional on the saved authenticated session. A launcher launch does not guarantee a character automatically enters the world.
- No verified unattended WoW Forever launch CLI on this machine yet; use the supported Battle.net GUI route for initial validation.
- The game is currently not running and screen sharing is currently off. No live test was performed.