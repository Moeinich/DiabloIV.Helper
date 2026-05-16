from threading import Lock
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from helper import config_helper, logging_helper

SKILLPATH = Path(__file__).resolve().parents[2] / "assets" / "skills"

_cache_lock = Lock()
_cache = None

VALID_CLASSES = {'Druid', 'Spiritborn', 'Barbarian', 'Necromancer', 'Sorceress', 'Rogue', 'Warlock', 'Paladin'}


class BotConfig:
    __slots__ = (
        'class_name', 'class_lower',
        'skill1_key', 'skill2_key', 'skill3_key', 'skill4_key', 'skill5_key', 'skill6_key',
        'pot_key', 'evade_key',
        'skill1_enabled', 'skill2_enabled', 'skill3_enabled', 'skill4_enabled',
        'skill5_enabled', 'skill6_enabled',
        'pot_enabled', 'evade_enabled',
        'skill1_pos', 'skill2_pos', 'skill3_pos', 'skill4_pos',
        'skill5_pos', 'skill6_pos',
        'pot_pos', 'evade_pos',
        'hp_pixel',
        'rotation_hotkey',
    )

    def __init__(self):
        self.class_name = 'Paladin'
        self.class_lower = 'paladin'
        for attr in self.__slots__:
            if not hasattr(self, attr):
                setattr(self, attr, None)
        self.skill1_enabled = True
        self.skill2_enabled = True
        self.skill3_enabled = True
        self.skill4_enabled = True
        self.skill5_enabled = True
        self.skill6_enabled = True
        self.pot_enabled = True
        self.evade_enabled = True

    def skill_region(self, key: str) -> Optional[Tuple[int, int, int, int]]:
        pos = getattr(self, f'{key}_pos', None)
        if pos and isinstance(pos, (list, tuple)) and len(pos) >= 4:
            return (pos[0], pos[1], pos[0] + pos[2], pos[1] + pos[3])
        return None

    def skill_icon(self, idx: str) -> str:
        return str(SKILLPATH / self.class_lower / (idx + '.png'))

    def is_skill_enabled(self, key: str) -> bool:
        return getattr(self, f'{key}_enabled', True)

    def skill_key(self, key: str) -> str:
        return getattr(self, f'{key}_key', '') or ''


def init():
    global _cache
    try:
        cfg = config_helper.read_config() or {}
    except Exception as ex:
        logging_helper.log_error("bot_config init failed: %s" % ex)
        return

    c = BotConfig()
    class_name = str(cfg.get('class', '')).strip().capitalize()
    if class_name not in VALID_CLASSES:
        logging_helper.log_error("Invalid class in config: %r" % class_name)
        return

    c.class_name = class_name
    c.class_lower = class_name.lower()

    cls_cfg = config_helper.get_class_config(class_name)

    all_positions = []
    for key in ('skill1', 'skill2', 'skill3', 'skill4', 'skill5', 'skill6', 'pot', 'evade'):
        setattr(c, f'{key}_key', cls_cfg.get(key, ''))
        setattr(c, f'{key}_enabled', cls_cfg.get(f'{key}_enabled', True))
        pos = cls_cfg.get(f'{key}_pos')
        setattr(c, f'{key}_pos', pos)
        if pos and isinstance(pos, (list, tuple)) and len(pos) >= 4:
            all_positions.append(pos)

    c.hp_pixel = cfg.get('hp_pixel', (608, 980, [[95, 10, 15], [148, 14, 24], [97, 29, 82]]))
    c.rotation_hotkey = cfg.get('rotation_hotkey', 'f6')

    if all_positions:
        min_x = min(p[0] for p in all_positions) - 20
        min_y = min(p[1] for p in all_positions) - 20
        max_x = max(p[0] + p[2] for p in all_positions) + 20
        max_y = max(p[1] + p[3] for p in all_positions) + 20
        try:
            from helper import image_helper
            image_helper.set_skill_bar_region((min_x, min_y, max_x, max_y))
        except Exception:
            pass

    try:
        from helper import image_helper
        for idx in ('01', '02', '03', '04', '05', '06'):
            icon_path = str(SKILLPATH / c.class_lower / (idx + '.png'))
            image_helper._get_needle_image(icon_path)
        image_helper._get_needle_image(str(SKILLPATH / 'pot.png'))
        image_helper._get_needle_image(str(SKILLPATH / 'evade.png'))
    except Exception:
        pass

    with _cache_lock:
        _cache = c
    logging_helper.log_debug("bot_config initialized for %s" % class_name)


def get() -> Optional[BotConfig]:
    global _cache
    with _cache_lock:
        return _cache
