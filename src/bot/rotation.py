from random import uniform, random, shuffle
from time import sleep
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from pydirectinput import keyDown, keyUp, leftClick, rightClick

from helper import image_helper, timer_helper, logging_helper
from helper.timer_helper import TIMER_STOPPED
from helper.config_helper import SKILL_SLOTS
from bot import bot_config

SKILLPATH = Path(__file__).resolve().parents[1] / "assets" / "skills"

POTION_TIMER_SEC = 3
EVADE_TIMER_SEC = 3

HUMAN_REACTION_MIN = 0.03
HUMAN_REACTION_MAX = 0.10
HUMAN_KEY_HOLD_MIN = 0.03
HUMAN_KEY_HOLD_MAX = 0.12
HUMAN_POST_CAST_MIN = 0.04
HUMAN_POST_CAST_MAX = 0.15
HUMAN_HP_HESITATION_MIN = 0.05
HUMAN_HP_HESITATION_MAX = 0.18
HUMAN_PRE_KEY_MIN = 0.01
HUMAN_PRE_KEY_MAX = 0.04
HUMAN_RELEASE_GAP_MIN = 0.01
HUMAN_RELEASE_GAP_MAX = 0.03
HUMAN_SKILL_LOOP_MIN = 0.08
HUMAN_SKILL_LOOP_MAX = 0.25
HUMAN_ULT_LOOP_MIN = 0.10
HUMAN_ULT_LOOP_MAX = 0.30
DISTRACTED_PROBABILITY = 0.03
DISTRACTED_DELAY_MIN = 0.2
DISTRACTED_DELAY_MAX = 0.5
PRIORITY_NOISE_CHANCE = 0.2


class SkillCastTracker:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._casts = {}
            cls._instance._flash_duration = 0.4
        return cls._instance

    def record_cast(self, skill_key: str) -> None:
        import time
        self._casts[skill_key] = time.time()

    def is_flashing(self, skill_key: str) -> bool:
        import time
        ts = self._casts.get(skill_key)
        if ts is None:
            return False
        return (time.time() - ts) < self._flash_duration

    def get_all_flashing(self) -> Dict[str, float]:
        import time
        now = time.time()
        return {k: now - v for k, v in self._casts.items() if (now - v) < self._flash_duration}


_cast_tracker = SkillCastTracker()

_skill_states: Dict[str, dict] = {}
_skill_timers: Dict[str, timer_helper.TimerHelper] = {}
for _s in SKILL_SLOTS:
    _skill_timers[_s] = timer_helper.TimerHelper(_s)

_chain_pending: Optional[str] = None


def get_skill_states():
    return _skill_states.copy()


def _record_skill_state(key: str, found: bool, enabled: bool, mode: str = ''):
    if not enabled:
        _skill_states[key] = {'state': 'disabled', 'mode': mode}
    elif found:
        _skill_states[key] = {'state': 'ready', 'mode': mode}
    else:
        _skill_states[key] = {'state': 'cd', 'mode': mode}


def _reaction_delay() -> float:
    return uniform(HUMAN_REACTION_MIN, HUMAN_REACTION_MAX)


def _post_cast_delay() -> float:
    return uniform(HUMAN_POST_CAST_MIN, HUMAN_POST_CAST_MAX)


def _hp_hesitation_delay() -> float:
    return uniform(HUMAN_HP_HESITATION_MIN, HUMAN_HP_HESITATION_MAX)


def _distracted_pause() -> None:
    if random() < DISTRACTED_PROBABILITY:
        sleep(uniform(DISTRACTED_DELAY_MIN, DISTRACTED_DELAY_MAX))


def human_press(key: str) -> None:
    sleep(_reaction_delay())
    sleep(uniform(HUMAN_PRE_KEY_MIN, HUMAN_PRE_KEY_MAX))
    keyDown(key)
    sleep(uniform(HUMAN_KEY_HOLD_MIN, HUMAN_KEY_HOLD_MAX))
    sleep(uniform(HUMAN_RELEASE_GAP_MIN, HUMAN_RELEASE_GAP_MAX))
    keyUp(key)


def _read_bars(c: bot_config.BotConfig) -> Tuple[float, float]:
    hp = 0.5
    try:
        if c.hp_orb_center and c.hp_orb_radius and c.hp_orb_full_color:
            fc = c.hp_orb_full_color
            dc = c.hp_orb_dark_color or fc
            hp = image_helper.read_orb_fill_percentage(
                c.hp_orb_center[0], c.hp_orb_center[1], c.hp_orb_radius,
                fc[0], fc[1], fc[2], dc[0], dc[1], dc[2],
                c.hp_orb_tolerance
            )
    except Exception as ex:
        logging_helper.log_debug(f"_read_bars hp error: {ex}")

    resource = 0.5
    try:
        if c.resource_orb_center and c.resource_orb_radius and c.resource_orb_full_color:
            fc = c.resource_orb_full_color
            dc = c.resource_orb_dark_color or fc
            resource = image_helper.read_orb_fill_percentage(
                c.resource_orb_center[0], c.resource_orb_center[1], c.resource_orb_radius,
                fc[0], fc[1], fc[2], dc[0], dc[1], dc[2],
                c.resource_orb_tolerance
            )
    except Exception as ex:
        logging_helper.log_debug(f"_read_bars resource error: {ex}")

    return hp, resource


def _hp_delay_multiplier(hp_ratio: float) -> float:
    return 0.35 + (hp_ratio * 0.65)


def _icon_index(key: str) -> str:
    mapping = {
        'skill1': '01', 'skill2': '02', 'skill3': '03',
        'skill4': '04', 'skill5': '05', 'skill6': '06',
    }
    return mapping.get(key, '')


def _skill_conf(key: str) -> float:
    if key in ('skill5', 'skill6'):
        return 0.9
    return 0.6


def _evaluate_skill(c: bot_config.BotConfig, key: str, hp_pct: float, resource_pct: float) -> bool:
    mode = c.skill_mode(key)
    can_cast = True

    if mode == 'delay':
        dmax = c.skill_delay_max(key)
        if dmax > 0 and _skill_timers[key].get_timer_state() != TIMER_STOPPED:
            can_cast = False
    elif mode == 'hp_guard':
        if not (c.skill_hp_min(key) <= hp_pct <= c.skill_hp_max(key)):
            can_cast = False
    elif mode == 'resource_guard':
        if not (c.skill_resource_min(key) <= resource_pct <= c.skill_resource_max(key)):
            can_cast = False

    if can_cast:
        hp_ok = (c.skill_hp_min(key) <= hp_pct <= c.skill_hp_max(key))
        res_ok = (c.skill_resource_min(key) <= resource_pct <= c.skill_resource_max(key))
        if not hp_ok or not res_ok:
            can_cast = False

    icon_idx = _icon_index(key)
    if icon_idx:
        found = image_helper.locate_needle(c.skill_icon(icon_idx), conf=_skill_conf(key), region=c.skill_region(key))
    elif key == 'pot':
        found = image_helper.locate_needle(str(SKILLPATH / 'pot.png'), conf=0.7, region=c.skill_region('pot'))
    elif key == 'evade':
        found = image_helper.locate_needle(str(SKILLPATH / 'evade.png'), conf=0.7, region=c.skill_region('evade'))
    else:
        _record_skill_state(key, False, True, mode)
        return False

    _record_skill_state(key, bool(found), True, mode)
    return can_cast and bool(found)


def _cast_skill(c: bot_config.BotConfig, key: str, delay_mult: float) -> bool:
    hotkey = c.skill_key(key)
    if not hotkey:
        return False

    if key == 'skill5':
        leftClick()
    elif key == 'skill6':
        rightClick()
    else:
        human_press(hotkey)

    _cast_tracker.record_cast(key)
    logging_helper.log_info(f'Used {key}')

    dmax = c.skill_delay_max(key)
    if dmax > 0:
        dmin = c.skill_delay_min(key)
        delay = uniform(dmin, dmax)
        _skill_timers[key].start_timer(delay)

    if key == 'pot':
        _skill_timers['pot'].start_timer(POTION_TIMER_SEC)
    elif key == 'evade':
        _skill_timers['evade'].start_timer(EVADE_TIMER_SEC)

    chain_next = c.skill_chain_next(key)
    if chain_next:
        global _chain_pending
        _chain_pending = chain_next

    sleep(_post_cast_delay() * delay_mult)
    return True


def _apply_priority_noise(candidates: List[str]) -> List[str]:
    result = list(candidates)
    for i in range(len(result) - 1):
        if random() < PRIORITY_NOISE_CHANCE:
            result[i], result[i + 1] = result[i + 1], result[i]
    return result


def rotation() -> None:
    c = bot_config.get()
    if c is None:
        bot_config.init()
        c = bot_config.get()
    if c is None:
        logging_helper.log_error("No bot config available for rotation")
        return

    combat_rotation(c)


def combat_rotation(c: bot_config.BotConfig) -> None:
    global _chain_pending

    hp_ratio, resource_ratio = _read_bars(c)
    mult = _hp_delay_multiplier(hp_ratio)
    hp_pct = hp_ratio * 100
    resource_pct = resource_ratio * 100

    if hp_ratio < 1.0:
        _handle_survival(c, hp_pct, resource_pct, mult)
        sleep(_hp_hesitation_delay())

    if _chain_pending:
        chain_key = _chain_pending
        _chain_pending = None
        if c.is_skill_enabled(chain_key):
            chain_delay = uniform(0.05, 0.15)
            sleep(chain_delay * mult)
            if _evaluate_skill(c, chain_key, hp_pct, resource_pct):
                _cast_skill(c, chain_key, mult)
                sleep(uniform(0.04, 0.18) * mult)
                _distracted_pause()
                return

    regular = []
    fillers = []
    for key in SKILL_SLOTS:
        if key in ('pot', 'evade'):
            continue
        if not c.is_skill_enabled(key):
            _record_skill_state(key, False, False, c.skill_mode(key))
            continue
        mode = c.skill_mode(key)
        if mode == 'filler':
            fillers.append(key)
        else:
            regular.append((c.skill_priority(key), key))

    regular.sort(key=lambda x: (x[0], random()))
    ordered = [k for _, k in regular]
    ordered = _apply_priority_noise(ordered)

    for key in ordered:
        if _evaluate_skill(c, key, hp_pct, resource_pct):
            _cast_skill(c, key, mult)
            sleep(uniform(0.04, 0.18) * mult)
            _distracted_pause()
            return

    if fillers:
        shuffle(fillers)
        for key in fillers:
            if _evaluate_skill(c, key, hp_pct, resource_pct):
                _cast_skill(c, key, mult)
                sleep(uniform(0.04, 0.18) * mult)
                _distracted_pause()
                return

    sleep(uniform(HUMAN_SKILL_LOOP_MIN, HUMAN_SKILL_LOOP_MAX) * mult)
    sleep(uniform(0.04, 0.18) * mult)
    _distracted_pause()


def _handle_survival(c: bot_config.BotConfig, hp_pct: float, resource_pct: float, delay_mult: float) -> None:
    for key in ('pot', 'evade'):
        if not c.is_skill_enabled(key):
            _record_skill_state(key, False, False, c.skill_mode(key))
            continue
        if _skill_timers[key].get_timer_state() != TIMER_STOPPED:
            _record_skill_state(key, False, True, c.skill_mode(key))
            continue
        if _evaluate_skill(c, key, hp_pct, resource_pct):
            sleep(_hp_hesitation_delay() * delay_mult)
            _cast_skill(c, key, delay_mult)
            sleep(uniform(0.08, 0.20) * delay_mult)
