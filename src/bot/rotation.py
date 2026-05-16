from random import uniform, random
from time import sleep
from typing import Dict
from pathlib import Path
from pydirectinput import keyDown, keyUp, leftClick, rightClick
from threading import Lock

from helper import image_helper, timer_helper, logging_helper
from helper.timer_helper import TIMER_STOPPED
from bot import bot_config

SKILLPATH = Path(__file__).resolve().parents[2] / "assets" / "skills"

timer1 = timer_helper.TimerHelper('timer1')
timer2 = timer_helper.TimerHelper('timer2')

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
    _lock = Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._casts = {}
                    cls._instance._flash_duration = 0.4
        return cls._instance

    def record_cast(self, skill_key: str) -> None:
        import time
        with self._lock:
            self._casts[skill_key] = time.time()

    def is_flashing(self, skill_key: str) -> bool:
        import time
        with self._lock:
            if skill_key not in self._casts:
                return False
            elapsed = time.time() - self._casts[skill_key]
            return elapsed < self._flash_duration

    def get_all_flashing(self) -> Dict[str, float]:
        import time
        with self._lock:
            result = {}
            for key, ts in self._casts.items():
                elapsed = time.time() - ts
                if elapsed < self._flash_duration:
                    result[key] = elapsed
            return result


_cast_tracker = SkillCastTracker()


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


def _compute_hp_ratio(c: bot_config.BotConfig) -> float:
    try:
        raw = c.hp_pixel
        if not isinstance(raw, (list, tuple)) or len(raw) < 2:
            raw = [608, 980, [[95, 10, 15], [148, 14, 24], [97, 29, 82]]]
        hp_x, hp_y = raw[0], raw[1]
        hp_colors = raw[2] if len(raw) > 2 and isinstance(raw[2], list) else [[95, 10, 15], [148, 14, 24], [97, 29, 82]]
        if hp_colors and isinstance(hp_colors[0], (int, float)):
            hp_colors = [hp_colors]
        for color in hp_colors:
            if len(color) >= 3 and image_helper.pixel_matches_color(hp_x, hp_y, color[0], color[1], color[2], 45):
                return 1.0
        return 0.0
    except Exception:
        return 0.5


def _hp_delay_multiplier(hp_ratio: float) -> float:
    return 0.35 + (hp_ratio * 0.65)


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
    hp_ratio = _compute_hp_ratio(c)
    mult = _hp_delay_multiplier(hp_ratio)

    if handle_health_and_evade(c, mult):
        sleep(_hp_hesitation_delay())

    use_skills(c, mult)

    sleep(uniform(0.04, 0.18) * mult)
    _distracted_pause()


def handle_health_and_evade(c: bot_config.BotConfig, delay_mult: float = 1.0) -> bool:
    try:
        hp_ratio = _compute_hp_ratio(c)
        if hp_ratio >= 1.0:
            return False

        if c.is_skill_enabled('pot'):
            if locate_and_use_potion(c, delay_mult):
                logging_helper.log_info('Used potion')

        if c.is_skill_enabled('evade'):
            if locate_and_use_evade(c, delay_mult):
                logging_helper.log_info('Used evade')

        return True
    except Exception as ex:
        logging_helper.log_debug("handle_health_and_evade error: %s" % ex)

    return False


def locate_and_use_potion(c: bot_config.BotConfig, delay_mult: float = 1.0) -> bool:
    try:
        path = str(SKILLPATH / 'pot.png')
        region = c.skill_region('pot')
        try:
            found = image_helper.locate_needle(path, conf=0.7, region=region)
        except Exception as ex:
            logging_helper.log_debug("locate_needle error for %s: %s" % (path, ex))
            found = False

        if found and timer1.get_timer_state() == TIMER_STOPPED:
            timer1.start_timer(POTION_TIMER_SEC)
            sleep(_hp_hesitation_delay() * delay_mult)
            try:
                human_press(c.pot_key)
                _cast_tracker.record_cast('pot')
            except Exception as ex:
                logging_helper.log_debug("human_press(pot) failed: %s" % ex)
            sleep(uniform(0.08, 0.20) * delay_mult)
            return True
    except Exception as ex:
        logging_helper.log_debug("locate_and_use_potion error: %s" % ex)

    return False


def locate_and_use_evade(c: bot_config.BotConfig, delay_mult: float = 1.0) -> bool:
    try:
        path = str(SKILLPATH / 'evade.png')
        region = c.skill_region('evade')
        try:
            found = image_helper.locate_needle(path, conf=0.7, region=region)
        except Exception as ex:
            logging_helper.log_debug("locate_needle error for evade: %s" % ex)
            found = False

        if found and timer2.get_timer_state() == TIMER_STOPPED:
            timer2.start_timer(EVADE_TIMER_SEC)
            sleep(_hp_hesitation_delay() * delay_mult)
            try:
                human_press(c.evade_key)
                _cast_tracker.record_cast('evade')
            except Exception as ex:
                logging_helper.log_debug("human_press(evade) failed: %s" % ex)
            sleep(uniform(0.08, 0.20) * delay_mult)
            return True
    except Exception as ex:
        logging_helper.log_debug("locate_and_use_evade error: %s" % ex)

    return False


def use_skills(c: bot_config.BotConfig, delay_mult: float = 1.0) -> None:
    try:
        skill_order = [
            ('skill4', c.skill_key('skill4'), '04', c.skill_region('skill4')),
            ('skill3', c.skill_key('skill3'), '03', c.skill_region('skill3')),
            ('skill1', c.skill_key('skill1'), '01', c.skill_region('skill1')),
            ('skill2', c.skill_key('skill2'), '02', c.skill_region('skill2')),
        ]

        if random() < PRIORITY_NOISE_CHANCE:
            skill_order = skill_order[::-1]

        cast_done = False
        for skill_key, skill_hotkey, icon_idx, skill_pos in skill_order:
            if c.is_skill_enabled(skill_key):
                found = image_helper.locate_needle(c.skill_icon(icon_idx), conf=0.6, region=skill_pos)
                if found:
                    sleep(_reaction_delay() * delay_mult)
                    human_press(skill_hotkey)
                    _cast_tracker.record_cast(skill_key)
                    logging_helper.log_info(f'Used {skill_key}')
                    sleep(_post_cast_delay() * delay_mult)
                    cast_done = True
                    break

        if not cast_done:
            sleep(uniform(HUMAN_SKILL_LOOP_MIN, HUMAN_SKILL_LOOP_MAX) * delay_mult)

        if c.is_skill_enabled('skill5'):
            found = image_helper.locate_needle(c.skill_icon('05'), conf=0.9, region=c.skill_region('skill5'))
            if found:
                sleep(_reaction_delay() * delay_mult)
                leftClick()
                _cast_tracker.record_cast('skill5')
                logging_helper.log_info('Used skill 5 (LMouse)')
                sleep(_post_cast_delay() * delay_mult)
                return

        if c.is_skill_enabled('skill6'):
            found = image_helper.locate_needle(c.skill_icon('06'), conf=0.9, region=c.skill_region('skill6'))
            if found:
                sleep(_reaction_delay() * delay_mult)
                rightClick()
                _cast_tracker.record_cast('skill6')
                logging_helper.log_info('Used skill 6 (RMouse)')
                sleep(_post_cast_delay() * delay_mult)
                return

        sleep(uniform(HUMAN_ULT_LOOP_MIN, HUMAN_ULT_LOOP_MAX) * delay_mult)
    except Exception as ex:
        logging_helper.log_debug("use_skills error: %s" % ex)
