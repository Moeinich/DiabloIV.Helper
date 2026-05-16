from typing import Any, Dict, Optional
from yaml import safe_load, safe_dump
from pathlib import Path
import os
import time
import threading

from helper import logging_helper

_config_cache = None
_config_cache_time = 0.0
_config_cache_lock = threading.Lock()
_CACHE_TTL = 2.0

SKILL_SLOTS = ['skill1', 'skill2', 'skill3', 'skill4', 'skill5', 'skill6', 'pot', 'evade']

MACRO_KEYS_PER_SKILL = [
    '{key}_mode', '{key}_priority',
    '{key}_delay_min', '{key}_delay_max',
    '{key}_hp_min', '{key}_hp_max',
    '{key}_resource_min', '{key}_resource_max',
    '{key}_chain_next', '{key}_chain_delay',
]

CLASS_KEYS = []
for _slot in SKILL_SLOTS:
    CLASS_KEYS.append(_slot)
    CLASS_KEYS.append(f'{_slot}_pos')
    CLASS_KEYS.append(f'{_slot}_enabled')
    for _mk in MACRO_KEYS_PER_SKILL:
        CLASS_KEYS.append(_mk.format(key=_slot))

SHARED_KEYS = [
    'apptitle', 'class', 'rotation_hotkey',
    'hp_orb_center', 'hp_orb_radius', 'hp_orb_full_color', 'hp_orb_dark_color', 'hp_orb_tolerance',
    'resource_orb_center', 'resource_orb_radius', 'resource_orb_full_color', 'resource_orb_dark_color', 'resource_orb_tolerance',
    'region_detect',
]

ALL_CLASSES = ['Druid', 'Spiritborn', 'Barbarian', 'Necromancer', 'Sorceress', 'Rogue', 'Warlock', 'Paladin']

class ConfigError(Exception):
    """Spezielle Ausnahme fuer Konfigurationsfehler."""
    pass

def get_file_path() -> str:
    """
    Bestimmt den absoluten Pfad zur Konfigurationsdatei.
    Erwartet die Datei unter <project_root>/src/config.yml.
    """
    base_dir = Path(__file__).resolve().parents[1]
    return str(base_dir / "config.yml")

def ensure_config_exists(default: Optional[Dict[str, Any]] = None) -> None:
    """
    Stellt sicher, dass die Konfigurationsdatei existiert. Legt bei Bedarf ein Verzeichnis an
    und schreibt eine Default-Konfiguration (leeres Dict oder uebergebenes Default).
    """
    config_path = Path(get_file_path())
    try:
        if not config_path.exists():
            config_path.parent.mkdir(parents=True, exist_ok=True)
            data = default or {}
            write_config(data)
            logging_helper.log_info(f"Created default config at {config_path}")
    except Exception as ex:
        logging_helper.log_error(f"Failed to ensure config exists: {ex}")
        raise ConfigError(f"Failed to ensure config exists: {ex}")

def read_config() -> Dict[str, Any]:
    global _config_cache, _config_cache_time
    with _config_cache_lock:
        now = time.time()
        if _config_cache is not None and (now - _config_cache_time) < _CACHE_TTL:
            return _config_cache

        config_path = Path(get_file_path())
        if not config_path.exists():
            raise ConfigError(f"Configuration file not found at: {config_path}")

        try:
            with open(config_path, 'r', encoding='utf8') as infile:
                data = safe_load(infile) or {}
                if not isinstance(data, dict):
                    logging_helper.log_debug(f"Config file parsed to {type(data).__name__}, coercing to dict.")
                    data = {}
                if 'classes' not in data:
                    _config_cache_lock.release()
                    try:
                        data = _migrate_to_nested(data)
                    finally:
                        _config_cache_lock.acquire()
                else:
                    data = _migrate_color_keys(data)
                    data = _ensure_macro_defaults(data)
                    if data.get('_needs_write'):
                        del data['_needs_write']
                        _config_cache_lock.release()
                        try:
                            write_config(data)
                        finally:
                            _config_cache_lock.acquire()
                _config_cache = data
                _config_cache_time = time.time()
                return data
        except ConfigError:
            raise
        except Exception as ex:
            logging_helper.log_error(f"Failed to read config: {ex}")
            raise ConfigError(f"Failed to read config: {ex}")

def write_config(data: Dict[str, Any]) -> None:
    global _config_cache, _config_cache_time
    config_path = Path(get_file_path())
    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        yaml_text = safe_dump(data, default_flow_style=False, allow_unicode=True)
        with open(config_path, 'w', encoding='utf8') as f:
            f.write(yaml_text)
        with _config_cache_lock:
            _config_cache = data
            _config_cache_time = time.time()
        logging_helper.log_debug(f"Wrote config to {config_path}")
    except Exception as ex:
        logging_helper.log_error(f"Failed to write config: {ex}")
        raise ConfigError(f"Failed to write config: {ex}")

def _migrate_to_nested(data: Dict[str, Any]) -> Dict[str, Any]:
    """Migrate flat config to nested per-class structure."""
    if 'classes' in data:
        return data

    shared = {}
    class_data = {}

    for key in SHARED_KEYS:
        if key in data:
            shared[key] = data.pop(key)

    current_class = shared.get('class', 'Paladin')

    class_data[current_class] = {}
    for key in CLASS_KEYS:
        if key in data:
            class_data[current_class][key] = data.pop(key)

    for cls_name in ALL_CLASSES:
        if cls_name not in class_data:
            class_data[cls_name] = {}

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
    }

    result = {
        'classes': class_data,
        **shared
    }

    skill6_defaults = {
        'skill6': 'rightclick',
        'skill6_pos': [980, 45, 60, 60],
        'skill6_enabled': True,
    }
    for cls_name in ALL_CLASSES:
        for k, v in skill6_defaults.items():
            if k not in result['classes'][cls_name]:
                result['classes'][cls_name][k] = v

        for slot, slot_defaults in _MACRO_DEFAULTS.items():
            for mk, mv in slot_defaults.items():
                key = f'{slot}_{mk}'
                if key not in result['classes'][cls_name]:
                    result['classes'][cls_name][key] = mv
            for mk, mv in _SHARED_MACRO_DEFAULTS.items():
                key = f'{slot}_{mk}'
                if key not in result['classes'][cls_name]:
                    result['classes'][cls_name][key] = mv

    write_config(result)
    logging_helper.log_info("Migrated config from flat to nested per-class structure")
    return result

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
}

def _migrate_color_keys(data: Dict[str, Any]) -> Dict[str, Any]:
    renames = {
        'hp_orb_empty_color': 'hp_orb_full_color',
        'resource_orb_empty_color': 'resource_orb_full_color',
    }
    changed = False
    for old_key, new_key in renames.items():
        if old_key in data and new_key not in data:
            data[new_key] = data.pop(old_key)
            changed = True
    if changed:
        data['_needs_write'] = True
    return data

def _ensure_macro_defaults(data: Dict[str, Any]) -> Dict[str, Any]:
    if 'classes' not in data:
        return data
    needs_write = False
    for cls_name, cls_cfg in data['classes'].items():
        if not isinstance(cls_cfg, dict):
            continue
        for slot, slot_defaults in _MACRO_DEFAULTS.items():
            for mk, mv in slot_defaults.items():
                key = f'{slot}_{mk}'
                if key not in cls_cfg:
                    cls_cfg[key] = mv
                    needs_write = True
            for mk, mv in _SHARED_MACRO_DEFAULTS.items():
                key = f'{slot}_{mk}'
                if key not in cls_cfg:
                    cls_cfg[key] = mv
                    needs_write = True
    if needs_write:
        data['_needs_write'] = True
    return data

def get_current_class() -> str:
    """Returns the currently selected class name."""
    try:
        data = read_config()
    except ConfigError:
        return 'Paladin'
    if 'classes' in data:
        return data.get('class', 'Paladin')
    return 'Paladin'

def get_shared_config(key: str, default: Any = None) -> Any:
    """Get a shared (global) config value."""
    try:
        data = read_config()
        if 'classes' in data:
            return data.get(key, default)
        return data.get(key, default)
    except ConfigError:
        return default

def save_shared_config(key: str, value: Any) -> None:
    """Save a shared (global) config value."""
    try:
        data = read_config()
    except ConfigError:
        data = {}
    if 'classes' not in data:
        data = _migrate_to_nested(data)
    data[key] = value
    write_config(data)

def get_class_config(class_name: str) -> Dict[str, Any]:
    """Get the full config dict for a specific class, migrating if needed."""
    try:
        data = read_config()
    except ConfigError:
        data = {}
    if 'classes' not in data:
        data = _migrate_to_nested(data)
    return data.get('classes', {}).get(class_name, {})

def get_class_value(class_name: str, key: str, default: Any = None) -> Any:
    """Get a class-specific config value."""
    try:
        data = read_config()
    except ConfigError:
        return default
    if 'classes' not in data:
        return default
    cls_cfg = data.get('classes', {}).get(class_name, {})
    return cls_cfg.get(key, default)

def save_class_config(class_name: str, key: str, value: Any) -> None:
    """Save a class-specific config value."""
    try:
        data = read_config()
    except ConfigError:
        data = {}
    if 'classes' not in data:
        data = _migrate_to_nested(data)

    if 'classes' not in data:
        data['classes'] = {}
    if class_name not in data['classes']:
        data['classes'][class_name] = {}

    data['classes'][class_name][key] = value
    write_config(data)

def save_config(item: str, value: Any) -> None:
    """
    Setzt oder aktualisiert einen einzelnen Key in der Konfiguration und schreibt die Datei.
    Example: save_config('evade', 'space')
    For class-specific keys, uses the currently selected class.
    """
    try:
        cfg = read_config()
    except ConfigError:
        cfg = {}
    if not isinstance(cfg, dict):
        cfg = {}

    if 'classes' in cfg:
        current_class = cfg.get('class', 'Paladin')
        if item in CLASS_KEYS:
            save_class_config(current_class, item, value)
            return

    cfg[item] = value
    write_config(cfg)

def batch_save(updates: Dict[str, Any], class_updates: Optional[Dict[str, Dict[str, Any]]] = None) -> None:
    try:
        data = read_config()
    except ConfigError:
        data = {}
    if 'classes' not in data:
        data = _migrate_to_nested(data)

    for key, value in updates.items():
        data[key] = value

    if class_updates:
        for cls_name, cls_fields in class_updates.items():
            if cls_name not in data.get('classes', {}):
                data.setdefault('classes', {})[cls_name] = {}
            cls_cfg = data['classes'][cls_name]
            for key, value in cls_fields.items():
                cls_cfg[key] = value

    write_config(data)

def get_config_value(key: str, default: Any = None) -> Any:
    """
    Liefert einen Konfigurationswert. Unterstuetzt verschachtelte Keys mit Punkt-Notation:
    z.B. get_config_value('graphics.fullscreen', False)
    """
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
