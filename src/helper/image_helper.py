import os
import time
import ctypes
from typing import Tuple, Optional, Any
from pathlib import Path
import pyautogui
import numpy as np
import cv2
from PIL import ImageGrab, Image
from math import sqrt

from helper import mouse_helper, logging_helper

_needle_cache = {}
_needle_gray_cache = {}

_skill_bar_bbox = None
_screenshot_cache = None
_screenshot_cache_time = 0.0
_SCREENSHOT_CACHE_TTL = 0.05


def _get_needle_image(path: str):
    if path not in _needle_cache:
        try:
            img = Image.open(path).convert('RGB')
            _needle_cache[path] = img
            arr = np.array(img)
            gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
            _needle_gray_cache[path] = gray
        except Exception:
            return None
    return _needle_cache[path]


def _get_needle_gray(path: str):
    if path not in _needle_gray_cache:
        _get_needle_image(path)
    return _needle_gray_cache.get(path)


def set_skill_bar_region(bbox):
    global _skill_bar_bbox
    _skill_bar_bbox = bbox
    clear_screenshot_cache()


def get_skill_bar_region():
    return _skill_bar_bbox


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
    if _skill_bar_bbox is not None:
        img = ImageGrab.grab(bbox=_skill_bar_bbox)
    else:
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


_DEFAULT_SKILL_PATH = str(Path(__file__).resolve().parents[1] / "assets" / "skills") + os.sep


def get_image_at_cursor(ix: int = 10, iy: int = 10, name: str = 'default', path: str = None) -> Tuple[int, int]:
    """
    Capture an image centered around the cursor position.
    Returns cursor coordinates.
    """
    path = path or _DEFAULT_SKILL_PATH
    x, y = mouse_helper.position()
    save_image((x, y, ix, iy), name, path)
    return x, y


def get_image_from_coordinates(x: int, y: int, name: str = 'default', path: str = None) -> Tuple[int, int]:
    """
    Backward-compatible wrapper for the toolbox API.
    """
    return get_image_at_coords(x, y, name=name, path=path)


def get_image_at_coords(x: int, y: int, ix: int = 10, iy: int = 10, name: str = 'default', path: str = None) -> Tuple[int, int]:
    """
    Capture an image at specified coordinates (centered on x,y).
    Returns the provided coordinates.
    """
    path = path or _DEFAULT_SKILL_PATH
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
            needle_gray = _get_needle_gray(needle)
            haystack_img = _get_screenshot()
            if region is not None:
                left, top, rw, rh = region
                offset_x = _skill_bar_bbox[0] if _skill_bar_bbox else 0
                offset_y = _skill_bar_bbox[1] if _skill_bar_bbox else 0
                haystack_img = haystack_img.crop((left - offset_x, top - offset_y, left - offset_x + rw, top - offset_y + rh))
            if needle_gray is not None:
                hay_arr = np.array(haystack_img)
                hay_gray = cv2.cvtColor(hay_arr, cv2.COLOR_RGB2GRAY)
                n_h, n_w = needle_gray.shape
                result = cv2.matchTemplate(hay_gray, needle_gray, cv2.TM_CCOEFF_NORMED)
                _, max_val, _, _ = cv2.minMaxLoc(result)
                if max_val >= conf:
                    log_result(True, "'l' image (cv2)", f"conf={max_val:.3f}")
                    return True
                log_result(False, "'l' image (cv2)", f"best={max_val:.3f}")
                return False
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


def read_orb_fill_percentage(center_x: int, center_y: int, radius: int,
                             full_r: int, full_g: int, full_b: int,
                             dark_r: int, dark_g: int, dark_b: int,
                             tolerance: int = 45) -> float:
    if radius <= 0:
        logging_helper.log_debug("read_orb_fill_percentage: invalid radius")
        return 0.5
    try:
        left = center_x - radius
        top = center_y - radius
        diam = radius * 2
        img = ImageGrab.grab(bbox=(left, top, left + diam, top + diam))
        arr = np.array(img)
        total_pixels = 0
        filled_pixels = 0
        r2 = radius * radius
        for row_y in range(diam):
            dy = row_y - radius
            hw_sq = r2 - (dy * dy)
            if hw_sq < 0:
                continue
            hw = int(hw_sq ** 0.5)
            if hw <= 0:
                continue
            cx = radius
            row = arr[row_y, max(0, cx - hw):min(diam, cx + hw + 1)]
            if len(row) == 0:
                continue
            total_pixels += len(row)
            r_vals = row[:, 0].astype(int)
            g_vals = row[:, 1].astype(int)
            b_vals = row[:, 2].astype(int)
            bright_mask = ((np.abs(r_vals - full_r) <= tolerance) &
                           (np.abs(g_vals - full_g) <= tolerance) &
                           (np.abs(b_vals - full_b) <= tolerance))
            dark_mask = ((np.abs(r_vals - dark_r) <= tolerance) &
                         (np.abs(g_vals - dark_g) <= tolerance) &
                         (np.abs(b_vals - dark_b) <= tolerance))
            filled_pixels += np.sum(bright_mask | dark_mask)
        if total_pixels == 0:
            return 0.5
        return filled_pixels / total_pixels
    except Exception as ex:
        logging_helper.log_debug(f"read_orb_fill_percentage error: {ex}")
        return 0.5


def sample_pixel_color(x: int, y: int) -> Tuple[int, int, int]:
    try:
        img = ImageGrab.grab(bbox=(x, y, x + 1, y + 1))
        px = img.getpixel((0, 0))
        return (px[0], px[1], px[2])
    except Exception as ex:
        logging_helper.log_debug(f"sample_pixel_color error: {ex}")
        return (0, 0, 0)


def read_pixel_brightness(x: int, y: int) -> float:
    try:
        hdc = ctypes.windll.user32.GetDC(0)
        color = ctypes.windll.gdi32.GetPixel(hdc, int(x), int(y))
        ctypes.windll.user32.ReleaseDC(0, hdc)
        r = color & 0xFF
        g = (color >> 8) & 0xFF
        b = (color >> 16) & 0xFF
        return (r + g + b) / 3.0
    except Exception:
        return 255.0


def classify_skill_state(calibration: Optional[dict] = None) -> str:
    if not calibration or 'pixel1_x' not in calibration:
        return 'ready'

    t1 = calibration.get('pixel1_brightness', 100) * 0.6
    t2 = calibration.get('pixel2_brightness', 100) * 0.6

    b1 = read_pixel_brightness(calibration['pixel1_x'], calibration['pixel1_y'])
    b2 = read_pixel_brightness(calibration['pixel2_x'], calibration['pixel2_y'])

    if b1 < t1 or b2 < t2:
        return 'cooldown'
    return 'ready'
