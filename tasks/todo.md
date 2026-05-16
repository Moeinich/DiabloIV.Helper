# Plan 01: Macro System Redesign — Task List

## Phase 1: Foundation (no behavior change)

- [ ] Step 0: Move `assets/` → `src/assets/`, update all 7 path references across 5 files
- [ ] Step 1: Create `src/GUI/styles.py` — shared dark stylesheet constants
- [ ] Step 2: Create `src/GUI/selectors.py` — BaseDragSelector, RectDragSelector, CircleDragSelector
- [ ] Step 3: Add `read_orb_fill_percentage()` and `sample_orb_empty_color()` to `image_helper.py`
- [ ] Phase 1 Verification: assets load, selectors work, orb detection returns sane values, existing rotation unchanged

## Phase 2: Macro Engine (behavior change)

- [ ] Step 4: Expand `config_helper.py` — CLASS_KEYS, SHARED_KEYS, migration defaults for macro fields + orb config
- [ ] Step 5: Expand `bot_config.py` — programmatic slots, macro accessor methods, load orb config
- [ ] Step 6: Rewrite `rotation.py` — macro evaluation, chains, per-skill timers, orb reading, no redundant checks
- [ ] Phase 2 Verification: config migration works, rotation backward compat, chains execute, thresholds enforced

## Phase 3: UI (visual change)

- [ ] Step 7: Major edit `toolbox.py` — tabbed UI (Skills & Input, Macro Rules, Bar Setup), dark styling, load/save
- [ ] Step 8: Edit `overlay.py` — use shared styles from `styles.py`
- [ ] Step 9: Update `config.yml` — macro defaults per class, orb config sections
- [ ] Phase 3 Verification: all tabs render, save/load round-trips, selectors integrate, orb test works

## Full Integration

- [ ] Complete rotation cycle with macro rules active
- [ ] Skill chain executes correctly
- [ ] HP/resource guard modes enforce thresholds
- [ ] Delay mode enforces minimum time between casts
- [ ] Filler mode only casts when nothing else available
- [ ] Orb detection tracks HP/resource during gameplay
- [ ] No crashes on missing orb config (graceful fallback)
- [ ] Config migration from old format produces working defaults

## Review

_To be filled after implementation._
