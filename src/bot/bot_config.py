from threading import Lock
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from helper import config_helper, logging_helper

SKILLPATH = Path(__file__).resolve().parents[1] / "assets" / "skills"

_cache_lock = Lock()
_cache = None

VALID_CLASSES = {'Druid', 'Spiritborn', 'Barbarian', 'Necromancer', 'Sorceress', 'Rogue', 'Warlock', 'Paladin'}


_PER_SLOT_ATTRS = ['key', 'enabled', 'pos', 'mode', 'priority',
                   'delay_min', 'delay_max', 'hp_min', 'hp_max',
                   'resource_min', 'resource_max', 'chain_next', 'chain_delay']

_ORB_ATTRS = ['hp_orb_center', 'hp_orb_radius', 'hp_orb_full_color', 'hp_orb_dark_color', 'hp_orb_tolerance',
              'resource_orb_center', 'resource_orb_radius', 'resource_orb_full_color', 'resource_orb_dark_color', 'resource_orb_tolerance']


def _build_slots():
    slots = ['class_name', 'class_lower']
    for slot in config_helper.SKILL_SLOTS:
        for attr in _PER_SLOT_ATTRS:
            slots.append(f'{slot}_{attr}')
    slots.extend(_ORB_ATTRS)
    slots.append('rotation_hotkey')
    return tuple(slots)


class BotConfig:
    __slots__ = _build_slots()

    def __init__(self):
        self.class_name = 'Paladin'
        self.class_lower = 'paladin'
        for attr in self.__slots__:
            if not hasattr(self, attr):
                setattr(self, attr, None)
        for slot in config_helper.SKILL_SLOTS:
            setattr(self, f'{slot}_enabled', True)

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

    def skill_mode(self, key: str) -> str:
        return getattr(self, f'{key}_mode', 'ready') or 'ready'

    def skill_priority(self, key: str) -> int:
        return getattr(self, f'{key}_priority', 5) or 5

    def skill_delay_min(self, key: str) -> float:
        return getattr(self, f'{key}_delay_min', 0.0) or 0.0

    def skill_delay_max(self, key: str) -> float:
        return getattr(self, f'{key}_delay_max', 0.0) or 0.0

    def skill_hp_min(self, key: str) -> int:
        return getattr(self, f'{key}_hp_min', 0) or 0

    def skill_hp_max(self, key: str) -> int:
        return getattr(self, f'{key}_hp_max', 100) or 100

    def skill_resource_min(self, key: str) -> int:
        return getattr(self, f'{key}_resource_min', 0) or 0

    def skill_resource_max(self, key: str) -> int:
        return getattr(self, f'{key}_resource_max', 100) or 100

    def skill_chain_next(self, key: str) -> str:
        return getattr(self, f'{key}_chain_next', '') or ''

    def skill_chain_delay(self, key: str) -> float:
        return getattr(self, f'{key}_chain_delay', 0.1) or 0.1


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
    macro_attrs = [a for a in _PER_SLOT_ATTRS if a not in ('key', 'enabled', 'pos')]
    for key in config_helper.SKILL_SLOTS:
        setattr(c, f'{key}_key', cls_cfg.get(key, ''))
        setattr(c, f'{key}_enabled', cls_cfg.get(f'{key}_enabled', True))
        pos = cls_cfg.get(f'{key}_pos')
        setattr(c, f'{key}_pos', pos)
        if pos and isinstance(pos, (list, tuple)) and len(pos) >= 4:
            all_positions.append(pos)
        for attr in macro_attrs:
            val = cls_cfg.get(f'{key}_{attr}')
            if val is not None:
                setattr(c, f'{key}_{attr}', val)

    c.hp_orb_center = cfg.get('hp_orb_center')
    c.hp_orb_radius = cfg.get('hp_orb_radius')
    c.hp_orb_full_color = cfg.get('hp_orb_full_color')
    c.hp_orb_dark_color = cfg.get('hp_orb_dark_color')
    c.hp_orb_tolerance = cfg.get('hp_orb_tolerance', 45)
    c.resource_orb_center = cfg.get('resource_orb_center')
    c.resource_orb_radius = cfg.get('resource_orb_radius')
    c.resource_orb_full_color = cfg.get('resource_orb_full_color')
    c.resource_orb_dark_color = cfg.get('resource_orb_dark_color')
    c.resource_orb_tolerance = cfg.get('resource_orb_tolerance', 45)
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
