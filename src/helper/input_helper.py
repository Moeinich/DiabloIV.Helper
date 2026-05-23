from helper import logging_helper

_driver_available: bool | None = None
_context = None
_keyboard_device: int | None = None
_mouse_device: int | None = None

_SCANCODE_MAP = {
    'esc': 0x01, '1': 0x02, '2': 0x03, '3': 0x04, '4': 0x05,
    '5': 0x06, '6': 0x07, '7': 0x08, '8': 0x09, '9': 0x0A,
    '0': 0x0B, '-': 0x0C, '=': 0x0D, 'backspace': 0x0E, 'tab': 0x0F,
    'q': 0x10, 'w': 0x11, 'e': 0x12, 'r': 0x13, 't': 0x14,
    'y': 0x15, 'u': 0x16, 'i': 0x17, 'o': 0x18, 'p': 0x19,
    '[': 0x1A, ']': 0x1B, 'enter': 0x1C, 'ctrl': 0x1D, 'lctrl': 0x1D,
    'a': 0x1E, 's': 0x1F, 'd': 0x20, 'f': 0x21, 'g': 0x22,
    'h': 0x23, 'j': 0x24, 'k': 0x25, 'l': 0x26, ';': 0x27,
    "'": 0x28, '`': 0x29, 'shift': 0x2A, 'lshift': 0x2A,
    '\\': 0x2B, 'z': 0x2C, 'x': 0x2D, 'c': 0x2E, 'v': 0x2F,
    'b': 0x30, 'n': 0x31, 'm': 0x32, ',': 0x33, '.': 0x34,
    '/': 0x35, 'rshift': 0x36, 'numlock': 0x45,
    'space': 0x39, 'capslock': 0x3A, 'f1': 0x3B, 'f2': 0x3C,
    'f3': 0x3D, 'f4': 0x3E, 'f5': 0x3F, 'f6': 0x40, 'f7': 0x41,
    'f8': 0x42, 'f9': 0x43, 'f10': 0x44, 'f11': 0x57, 'f12': 0x58,
    'rctrl': 0x1D, 'ralt': 0x38, 'alt': 0x38,
    'up': 0x48, 'left': 0x4B, 'right': 0x4D, 'down': 0x50,
    'delete': 0x53, 'end': 0x4F, 'pageup': 0x49, 'pagedown': 0x51,
    'home': 0x47, 'insert': 0x52,
}

_VK_TO_SCANCODE_EXTENDED = {
    'rctrl': (0x1D, True),
    'ralt': (0x38, True),
    'up': (0x48, True),
    'left': (0x4B, True),
    'right': (0x4D, True),
    'down': (0x50, True),
    'delete': (0x53, True),
    'end': (0x4F, True),
    'pageup': (0x49, True),
    'pagedown': (0x51, True),
    'home': (0x47, True),
    'insert': (0x52, True),
}


def is_driver_installed() -> bool:
    global _driver_available
    if _driver_available is not None:
        return _driver_available
    try:
        from interception import ffi
        context = _get_context()
        _driver_available = (context is not None and context != ffi.NULL)
    except Exception:
        _driver_available = False
    return _driver_available


def _get_context():
    global _context, _keyboard_device, _mouse_device
    if _context is not None:
        return _context
    try:
        from interception import ffi, lib
        ctx = lib.interception_create_context()
        if ctx == ffi.NULL:
            return None
        _context = ctx
        for i in range(20):
            if _keyboard_device is None and lib.interception_is_keyboard(i):
                _keyboard_device = i
            if _mouse_device is None and lib.interception_is_mouse(i):
                _mouse_device = i
        return _context
    except Exception:
        return None


def _resolve_key(key: str):
    k = key.lower().strip()
    if k in _VK_TO_SCANCODE_EXTENDED:
        scancode, extended = _VK_TO_SCANCODE_EXTENDED[k]
        return scancode, extended
    if k in _SCANCODE_MAP:
        return _SCANCODE_MAP[k], False
    try:
        vk = int(k)
        return vk, False
    except ValueError:
        return ord(k.upper()), False


def _send_key(key: str, down: bool) -> None:
    from interception import ffi, lib
    ctx = _get_context()
    scancode, extended = _resolve_key(key)
    state = lib.INTERCEPTION_KEY_DOWN if down else lib.INTERCEPTION_KEY_UP
    if extended:
        state |= lib.INTERCEPTION_KEY_E0
    stroke = ffi.new('InterceptionKeyStroke *', {'code': scancode, 'state': state})
    lib.interception_send(ctx, _keyboard_device, stroke, 1)


def _send_mouse(flags: int, x: int = 0, y: int = 0, wheel: int = 0) -> None:
    from interception import ffi, lib
    ctx = _get_context()
    stroke = ffi.new('InterceptionMouseStroke *', {
        'state': flags,
        'flags': 0,
        'rolling': wheel,
        'x': x,
        'y': y,
        'information': 0,
    })
    lib.interception_send(ctx, _mouse_device, stroke, 1)


def keyDown(key: str) -> None:
    _send_key(key, down=True)


def keyUp(key: str) -> None:
    _send_key(key, down=False)


def press(key: str) -> None:
    keyDown(key)
    keyUp(key)


def leftClick(x: int = None, y: int = None) -> None:
    from interception import lib
    if x is not None and y is not None:
        moveTo(x, y)
    _send_mouse(lib.INTERCEPTION_MOUSE_LEFT_BUTTON_DOWN)
    from time import sleep
    sleep(0.01)
    _send_mouse(lib.INTERCEPTION_MOUSE_LEFT_BUTTON_UP)


def rightClick(x: int = None, y: int = None) -> None:
    from interception import lib
    if x is not None and y is not None:
        moveTo(x, y)
    _send_mouse(lib.INTERCEPTION_MOUSE_RIGHT_BUTTON_DOWN)
    from time import sleep
    sleep(0.01)
    _send_mouse(lib.INTERCEPTION_MOUSE_RIGHT_BUTTON_UP)


def mouseDown(button: str = 'left') -> None:
    from interception import lib
    flag = lib.INTERCEPTION_MOUSE_LEFT_BUTTON_DOWN if button == 'left' else lib.INTERCEPTION_MOUSE_RIGHT_BUTTON_DOWN
    _send_mouse(flag)


def mouseUp(button: str = 'left') -> None:
    from interception import lib
    flag = lib.INTERCEPTION_MOUSE_LEFT_BUTTON_UP if button == 'left' else lib.INTERCEPTION_MOUSE_RIGHT_BUTTON_UP
    _send_mouse(flag)


def moveTo(x: int, y: int, **kwargs) -> None:
    from interception import lib
    _send_mouse(lib.INTERCEPTION_MOUSE_MOVE_ABSOLUTE, x, y)


def position():
    import ctypes
    pt = ctypes.wintypes.POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
    return (pt.x, pt.y)
