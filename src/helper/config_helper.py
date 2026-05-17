from typing import Any, Dict, Optional
from yaml import safe_load, safe_dump
from pathlib import Path
import os
import time
import threading

from helper import logging_helper

_CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"

_shared_cache = None
_shared_cache_time = 0.0
_class_cache: Dict[str, tuple] = {}
_cache_lock = threading.Lock()
_CACHE_TTL = 2.0

SKILL_SLOTS = ['skill1', 'skill2', 'skill3', 'skill4', 'skill5', 'skill6', 'pot', 'evade']

MACRO_KEYS_PER_SKILL = [
    '{key}_mode', '{key}_priority',
    '{key}_delay_min', '{key}_delay_max',
    '{key}_hp_min', '{key}_hp_max',
    '{key}_resource_min', '{key}_resource_max',
    '{key}_chain_next', '{key}_chain_delay',
    '{key}_always_available', '{key}_always_hold',
]

CLASS_KEYS = []
for _slot in SKILL_SLOTS:
    CLASS_KEYS.append(_slot)
    CLASS_KEYS.append(f'{_slot}_pos')
    CLASS_KEYS.append(f'{_slot}_enabled')
    CLASS_KEYS.append(f'{_slot}_cal')
    for _mk in MACRO_KEYS_PER_SKILL:
        CLASS_KEYS.append(_mk.format(key=_slot))

SHARED_KEYS = [
    'apptitle', 'class', 'rotation_hotkey',
    'hp_orb_center', 'hp_orb_radius', 'hp_orb_full_color', 'hp_orb_dark_color', 'hp_orb_tolerance',
    'resource_orb_center', 'resource_orb_radius', 'resource_orb_full_color', 'resource_orb_dark_color', 'resource_orb_tolerance',
    'region_detect',
]

ALL_CLASSES = ['Druid', 'Spiritborn', 'Barbarian', 'Necromancer', 'Sorceress', 'Rogue', 'Warlock', 'Paladin']

_MACRO_DEFAULTS = {
    'skill1': {'mode': 'ready', 'priority': 3},
    'skill2': {'mode': 'ready', 'priority': 4},
    'skill3': {'mode': 'ready', 'priority': 2},
    'skill4': {'mode': 'ready', 'priority': 1},
    'skill5': {'mode': 'ready', 'priority': 5},
    'skill6': {'mode': 'ready', 'priority': 6},
    'pot':    {'mode': 'hp_guard', 'priority': 7, 'hp_min': 0, 'hp_max': 80},
    'evade':  {'mode': 'hp_guard', 'priority': 8, 'hp_min': 0, 'hp_max': 60},
}
_SHARED_MACRO_DEFAULTS = {
    'delay_min': 0.0, 'delay_max': 0.0,
    'hp_min': 0, 'hp_max': 100,
    'resource_min': 0, 'resource_max': 100,
    'chain_next': '', 'chain_delay': 0.1,
    'always_available': False, 'always_hold': True,
}


class ConfigError(Exception):
    pass


def _shared_path() -> Path:
    return _CONFIG_DIR / "shared.yml"


def _class_path(class_name: str) -> Path:
    return _CONFIG_DIR / class_name / "config.yml"


def _read_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with open(path, 'r', encoding='utf8') as f:
            data = safe_load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _write_yaml(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf8') as f:
        safe_dump(data, f, default_flow_style=False, allow_unicode=True)


def _legacy_config_path() -> Path:
    return Path(__file__).resolve().parents[1] / "config.yml"


def _migrate_from_legacy() -> None:
    legacy = _legacy_config_path()
    if not legacy.exists():
        return
    data = _read_yaml(legacy)
    if not data:
        return

    shared_data = {}
    for key in SHARED_KEYS:
        if key in data:
            shared_data[key] = data.pop(key)

    classes_data = data.pop('classes', {})

    if classes_data:
        for cls_name, cls_cfg in classes_data.items():
            if not isinstance(cls_cfg, dict):
                continue
            cls_cfg = _clean_class_data(cls_name, cls_cfg)
            _write_yaml(_class_path(cls_name), cls_cfg)
    elif any(k in data for k in CLASS_KEYS):
        current_class = shared_data.get('class', 'Paladin')
        cls_cfg = {}
        for key in CLASS_KEYS:
            if key in data:
                cls_cfg[key] = data.pop(key)
        cls_cfg = _clean_class_data(current_class, cls_cfg)
        _write_yaml(_class_path(current_class), cls_cfg)

    for cls_name in ALL_CLASSES:
        cp = _class_path(cls_name)
        if not cp.exists():
            _write_yaml(cp, _build_defaults(cls_name))

    _write_yaml(_shared_path(), shared_data)
    legacy.rename(legacy.with_suffix('.yml.bak'))
    logging_helper.log_info("Migrated legacy config.yml to per-class config files")


def _clean_class_data(cls_name: str, cls_cfg: Dict[str, Any]) -> Dict[str, Any]:
    cleaned = {}
    for k, v in cls_cfg.items():
        if k in CLASS_KEYS:
            cleaned[k] = v
    return _ensure_class_defaults(cleaned)


def _build_defaults(cls_name: str) -> Dict[str, Any]:
    cfg = {
        'skill6': 'rightclick',
        'skill6_pos': [980, 45, 60, 60],
        'skill6_enabled': True,
    }
    return _ensure_class_defaults(cfg)


def _ensure_class_defaults(cls_cfg: Dict[str, Any]) -> Dict[str, Any]:
    for slot, slot_defaults in _MACRO_DEFAULTS.items():
        for mk, mv in slot_defaults.items():
            key = f'{slot}_{mk}'
            if key not in cls_cfg:
                cls_cfg[key] = mv
        for mk, mv in _SHARED_MACRO_DEFAULTS.items():
            key = f'{slot}_{mk}'
            if key not in cls_cfg:
                cls_cfg[key] = mv
    return cls_cfg


def ensure_config_exists(default: Optional[Dict[str, Any]] = None) -> None:
    try:
        if _legacy_config_path().exists():
            _migrate_from_legacy()
            return

        _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        sp = _shared_path()
        if not sp.exists():
            shared = default or {'class': 'Paladin', 'apptitle': 'notepad', 'rotation_hotkey': 'x'}
            _write_yaml(sp, shared)

        for cls_name in ALL_CLASSES:
            cp = _class_path(cls_name)
            if not cp.exists():
                _write_yaml(cp, _build_defaults(cls_name))

        logging_helper.log_info(f"Created config structure at {_CONFIG_DIR}")
    except Exception as ex:
        logging_helper.log_error(f"Failed to ensure config exists: {ex}")
        raise ConfigError(f"Failed to ensure config exists: {ex}")


def read_config() -> Dict[str, Any]:
    global _shared_cache, _shared_cache_time, _class_cache

    with _cache_lock:
        now = time.time()
        if _shared_cache is not None and (now - _shared_cache_time) < _CACHE_TTL:
            result = dict(_shared_cache)
            result['classes'] = {}
            for cls_name in ALL_CLASSES:
                cached = _class_cache.get(cls_name)
                if cached and (now - cached[1]) < _CACHE_TTL:
                    result['classes'][cls_name] = cached[0]
            return result

    if _legacy_config_path().exists():
        _migrate_from_legacy()

    shared_data = _read_yaml(_shared_path())

    with _cache_lock:
        _shared_cache = shared_data
        _shared_cache_time = time.time()
        _class_cache.clear()

    result = dict(shared_data)
    result['classes'] = {}
    for cls_name in ALL_CLASSES:
        cls_cfg = _ensure_class_defaults(_read_yaml(_class_path(cls_name)))
        result['classes'][cls_name] = cls_cfg
        with _cache_lock:
            _class_cache[cls_name] = (cls_cfg, time.time())

    return result


def write_config(data: Dict[str, Any]) -> None:
    global _shared_cache, _shared_cache_time, _class_cache

    shared_data = {}
    for key in SHARED_KEYS:
        if key in data:
            shared_data[key] = data[key]

    classes_data = data.get('classes', {})

    _write_yaml(_shared_path(), shared_data)

    for cls_name, cls_cfg in classes_data.items():
        if isinstance(cls_cfg, dict):
            _write_yaml(_class_path(cls_name), cls_cfg)

    with _cache_lock:
        _shared_cache = shared_data
        _shared_cache_time = time.time()
        _class_cache.clear()

    logging_helper.log_debug("Wrote config files")


def get_current_class() -> str:
    try:
        shared = _read_yaml(_shared_path())
        return shared.get('class', 'Paladin')
    except Exception:
        return 'Paladin'


def get_shared_config(key: str, default: Any = None) -> Any:
    try:
        shared = _read_yaml(_shared_path())
        return shared.get(key, default)
    except Exception:
        return default


def save_shared_config(key: str, value: Any) -> None:
    shared = _read_yaml(_shared_path())
    shared[key] = value
    _write_yaml(_shared_path(), shared)
    global _shared_cache, _shared_cache_time
    with _cache_lock:
        _shared_cache = shared
        _shared_cache_time = time.time()


def get_class_config(class_name: str) -> Dict[str, Any]:
    cls_cfg = _ensure_class_defaults(_read_yaml(_class_path(class_name)))
    return cls_cfg


def get_class_value(class_name: str, key: str, default: Any = None) -> Any:
    cls_cfg = _read_yaml(_class_path(class_name))
    return cls_cfg.get(key, default)


def save_class_config(class_name: str, key: str, value: Any) -> None:
    cls_cfg = _read_yaml(_class_path(class_name))
    cls_cfg[key] = value
    _write_yaml(_class_path(class_name), cls_cfg)
    global _class_cache
    with _cache_lock:
        _class_cache[class_name] = (cls_cfg, time.time())


def save_config(item: str, value: Any) -> None:
    if item in CLASS_KEYS:
        current_class = get_current_class()
        save_class_config(current_class, item, value)
    else:
        save_shared_config(item, value)


def batch_save(updates: Dict[str, Any], class_updates: Optional[Dict[str, Dict[str, Any]]] = None) -> None:
    if updates:
        shared = _read_yaml(_shared_path())
        for key, value in updates.items():
            shared[key] = value
        _write_yaml(_shared_path(), shared)
        global _shared_cache, _shared_cache_time
        with _cache_lock:
            _shared_cache = shared
            _shared_cache_time = time.time()

    if class_updates:
        for cls_name, cls_fields in class_updates.items():
            cls_cfg = _read_yaml(_class_path(cls_name))
            for key, value in cls_fields.items():
                cls_cfg[key] = value
            _write_yaml(_class_path(cls_name), cls_cfg)
            global _class_cache
            with _cache_lock:
                _class_cache[cls_name] = (cls_cfg, time.time())


def get_config_value(key: str, default: Any = None) -> Any:
    try:
        cfg = read_config()
    except ConfigError:
        return default

    if '.' in key:
        parts = key.split('.')
        cursor = cfg
        for p in parts:
            if isinstance(cursor, dict) and p in cursor:
                cursor = cursor[p]
            else:
                return default
        return cursor
    return cfg.get(key, default)
