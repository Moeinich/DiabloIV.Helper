import os
import time
import ctypes
from typing import Tuple, Optional, Any
import pyautogui
import numpy as np
import cv2
from PIL import ImageGrab, Image
from math import sqrt

from helper import mouse_helper, logging_helper

_needle_cache = {}

_screenshot_cache = None
_screenshot_cache_time = 0.0
_SCREENSHOT_CACHE_TTL = 0.05


def _get_needle_image(path: str):
    if path not in _needle_cache:
        try:
            _needle_cache[path] = Image.open(path)
        except Exception:
            return None
    return _needle_cache[path]


def clear_needle_cache():
    _needle_cache.clear()


def clear_screenshot_cache():
    global _screenshot_cache, _screenshot_cache_time
    _screenshot_cache = None
    _screenshot_cache_time = 0.0


def _get_screenshot(region=None):
    global _screenshot_cache, _screenshot_cache_time
    now = time.monotonic()
    if region is None and _screenshot_cache is not None and (now - _screenshot_cache_time) < _SCREENSHOT_CACHE_TTL:
        return _screenshot_cache
    if region is not None:
        return ImageGrab.grab(bbox=region)
    img = ImageGrab.grab()
    _screenshot_cache = img
    _screenshot_cache_time = now
    return img


def _read_pixel(x: int, y: int) -> Tuple[int, int, int]:
    hdc = ctypes.windll.user32.GetDC(0)
    color = ctypes.windll.gdi32.GetPixel(hdc, int(x), int(y))
    ctypes.windll.user32.ReleaseDC(0, hdc)
    return (color & 0xFF, (color >> 8) & 0xFF, (color >> 16) & 0xFF)


def get_pixel_color_at_cursor() -> Tuple[int, int, int, int, int]:
    """
    Get the color of the pixel under the cursor.
    Returns:
        tuple: (x, y, r, g, b) - Cursor coordinates and pixel color.
    """
    try:
        x, y = mouse_helper.position()
        r, g, b = _read_pixel(x, y)
        return x, y, r, g, b
    except Exception as ex:
        logging_helper.log_debug(f"get_pixel_color_at_cursor failed: {ex}")
        return -1, -1, -1, -1, -1


def get_pixel_color_at_coords(x: int, y: int) -> Tuple[int, int, int]:
    """
    Get the color of the pixel at coordinates.
    Returns:
        tuple: (r, g, b) - Pixel color.
    """
    try:
        r, g, b = _read_pixel(x, y)
        return r, g, b
    except Exception as ex:
        logging_helper.log_debug(f"get_pixel_color_at_coords({x},{y}) failed: {ex}")
        return -1, -1, -1


def save_image(region: Tuple[int, int, int, int], name: str, path: str) -> None:
    """
    Save a screenshot of a specific region to a file.
    Parameters:
        region (tuple): (left, top, width, height) - The region to capture.
        name (str): Name of the saved file (without extension).
        path (str): Directory where the file will be saved.
    """
    try:
        os.makedirs(path, exist_ok=True)
        img = pyautogui.screenshot(region=region)
        filepath = os.path.join(path, f"{name}.png")
        img.save(filepath)
        logging_helper.log_debug(f"Saved image {filepath}")
    except Exception as ex:
        logging_helper.log_debug(f"save_image failed for {name} @ {path}: {ex}")


def get_image_at_cursor(ix: int = 10, iy: int = 10, name: str = 'default', path: str = './assets/skills/') -> Tuple[int, int]:
    """
    Capture an image centered around the cursor position.
    Returns cursor coordinates.
    """
    x, y = mouse_helper.position()
    save_image((x, y, ix, iy), name, path)
    return x, y


def get_image_from_coordinates(x: int, y: int, name: str = 'default', path: str = './assets/skills/') -> Tuple[int, int]:
    """
    Backward-compatible wrapper for the toolbox API.
    """
    return get_image_at_coords(x, y, name=name, path=path)


def get_image_at_coords(x: int, y: int, ix: int = 10, iy: int = 10, name: str = 'default', path: str = './assets/skills/') -> Tuple[int, int]:
    """
    Capture an image at specified coordinates (centered on x,y).
    Returns the provided coordinates.
    """
    save_image((x, y, ix, iy), name, path)
    return x, y


def pixel_matches_color(x: int, y: int, exR: int, exG: int, exB: int, tolerance: int = 25) -> bool:
    """
    Check if a pixel matches the expected RGB color within a tolerance.
    """
    try:
        hdc = ctypes.windll.user32.GetDC(0)
        color = ctypes.windll.gdi32.GetPixel(hdc, int(x), int(y))
        ctypes.windll.user32.ReleaseDC(0, hdc)
        r = color & 0xFF
        g = (color >> 8) & 0xFF
        b = (color >> 16) & 0xFF
        return all(abs(int(actual) - int(expected)) <= int(tolerance)
                   for actual, expected in zip((r, g, b), (exR, exG, exB)))
    except Exception as ex:
        logging_helper.log_debug(f"pixel_matches_color({x},{y}) failed: {ex}")
        return False

    
def _get_detect_region() -> Tuple[int, int, int, int]:
    try:
        from helper import config_helper
        cfg = config_helper.read_config() or {}
        val = cfg.get('region_detect')
        if val and isinstance(val, list) and len(val) == 4:
            x, y, w, h = val
            return (x, y, x + w, y + h)
    except Exception:
        pass
    return (600, 100, 2000, 1000)

def detect_lines(line_type: str = 'path') -> Optional[Tuple[int, int, int, int]]:
    """
    Detect narrow, curved lines of a given type ('path' or 'mob') by specified RGB color on the screen.
    Returns absolute bounding box (x, y, w, h) of the closest matching contour or None.
    """
    line_config = {
        'path': {
            'lower': np.array([254, 254, 254], dtype=np.uint8),
            'upper': np.array([255, 255, 255], dtype=np.uint8),
        },
        'mob': {
            'lower': np.array([155, 37, 1], dtype=np.uint8),
            'upper': np.array([168, 38, 1], dtype=np.uint8),
        }
    }

    if line_type not in line_config:
        logging_helper.log_debug(f"detect_lines: unknown line_type '{line_type}'")
        return None

    screen_box = _get_detect_region()
    left, top, width, height = screen_box
    cfg = line_config[line_type]

    try:
        # Grab region and convert to RGB for processing
        img = ImageGrab.grab(bbox=(left, top, width, height))
        np_img = np.array(img)
        rgb = cv2.cvtColor(np_img, cv2.COLOR_BGR2RGB)
        mask = cv2.inRange(rgb, cfg['lower'], cfg['upper'])
        edges = cv2.Canny(mask, 50, 150)

        # findContours: robust gegen verschiedene cv2-Versionen
        contours_info = cv2.findContours(edges.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        contours = contours_info[0] if len(contours_info) == 2 else contours_info[1]

        screen_center_x = left + (width // 2)
        screen_center_y = top + (height // 2)
        min_distance = float('inf')
        closest_contour: Optional[Tuple[int, int, int, int]] = None

        for contour in contours:
            #if cv2.contourArea(contour) < 20:
            #    continue  # Rauschen �berspringen

            epsilon = 0.01 * cv2.arcLength(contour, True)
            approx = cv2.approxPolyDP(contour, epsilon, True)
            x, y, w, h = cv2.boundingRect(contour)

            # Kontur-Koordinaten ins absolute Koordinatensystem umrechnen
            abs_x = left + x
            abs_y = top + y
            contour_center_x = abs_x + (w // 2)
            contour_center_y = abs_y + (h // 2)
            distance = sqrt((contour_center_x - screen_center_x) ** 2 + (contour_center_y - screen_center_y) ** 2)

            if line_type in ('path'):
                # Pfad ist typischerweise kurvig; wir erlauben kleine Konturen mit mehreren Punkten
                if len(approx) > 2 and distance < min_distance:
                    min_distance = distance
                    closest_contour = (abs_x, abs_y, w, h)
                    #cv2.imwrite(f"debug_{line_type}_hsv.png", rgb)  # Debug: save rgb image
                    #cv2.imwrite(f"debug_{line_type}_edges.png", edges)  # Debug: save edge image
                    logging_helper.log_debug(f"Detected curved line ('path') bbox {(abs_x, abs_y, w, h)}")
            elif line_type == 'mob':
                # Mob-Linien sind oft sehr schmal und lang; Filter nach minimaler Breite/H�he
                if w >= 20 and 1 <= h <= 6 and distance < min_distance:
                    min_distance = distance
                    closest_contour = (abs_x, abs_y, w, h)
                    #cv2.imwrite(f"debug_{line_type}_hsv.png", rgb)  # Debug: save rgb image
                    #cv2.imwrite(f"debug_{line_type}_edges.png", edges)  # Debug: save edge image
                    logging_helper.log_debug(f"Detected straight line ('mob') bbox {(abs_x, abs_y, w, h)}")

        if closest_contour:
            logging_helper.log_info(f"Closest contour to center: {closest_contour}")
            return closest_contour

    except Exception as ex:
        logging_helper.log_debug(f"detect_lines failed for type '{line_type}': {ex}")

    return None


def locate_needle(
    needle: str,
    haystack: Optional[str] = None,
    conf: float = 0.7,
    loctype: str = 'l',
    grayscale: bool = True,
    region: Optional[Tuple[int, int, int, int]] = None
) -> Any:
    def log_result(found: bool, context: str, result: Any = None) -> None:
        if found:
            logging_helper.log_debug(f"Found {context}: {needle} -> {result}")
        else:
            logging_helper.log_debug(f"Cannot find {context}: {needle}, conf={conf}, result={result}")

    try:
        if haystack:
            needle_img = _get_needle_image(needle)
            if needle_img is None:
                return (-1, -1)
            res = pyautogui.locate(needle_img, haystack, confidence=conf)
            if res:
                log_result(True, "needle in haystack", res)
                return res
            log_result(False, "needle in haystack")
            return (-1, -1)

        if loctype == 'l':
            needle_img = _get_needle_image(needle)
            if needle_img is None:
                return False
            haystack_img = _get_screenshot()
            if region is not None:
                left, top, rw, rh = region
                haystack_img = haystack_img.crop((left, top, left + rw, top + rh))
            res = pyautogui.locate(needle_img, haystack_img, confidence=conf, grayscale=grayscale)
            if res:
                log_result(True, "'l' image", res)
                return True
            log_result(False, "'l' image")
            return False

        if loctype == 'c':
            needle_img = _get_needle_image(needle)
            if needle_img is None:
                return (-1, -1)
            res = pyautogui.locateCenterOnScreen(needle_img, confidence=conf, region=region, grayscale=grayscale)
            if res:
                coords = (int(res.x), int(res.y)) if hasattr(res, 'x') else (int(res[0]), int(res[1]))
                log_result(True, "'c' image", coords)
                return coords
            log_result(False, "'c' image")
            return (-1, -1)

    except Exception as ex:
        msg = str(ex).strip()
        if msg:
            logging_helper.log_debug(f"locate_needle error for {needle}: {ex}")
        if loctype == 'c' or haystack:
            return (-1, -1)
        return False

    raise ValueError(f"Invalid loctype '{loctype}'. Must be 'l' or 'c'.")
