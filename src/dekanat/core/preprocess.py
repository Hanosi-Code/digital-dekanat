"""Предобработка плохих снимков (OpenCV). Каждый шаг включается флагом из settings.yaml,
чтобы можно было измерить вклад шага в качество OCR."""
from __future__ import annotations

import cv2
import numpy as np


def estimate_skew_angle(gray: np.ndarray) -> float:
    """Угол наклона текста в градусах (±45). 0.0, если уверенно определить не удалось."""
    inv = cv2.bitwise_not(gray)
    thr = cv2.threshold(inv, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]
    coords = np.column_stack(np.where(thr > 0))
    if len(coords) < 500:
        return 0.0
    angle = cv2.minAreaRect(coords[:, ::-1].astype(np.float32))[-1]
    # приводим к диапазону (-45, 45]
    if angle > 45:
        angle -= 90
    elif angle < -45:
        angle += 90
    return float(angle)


def rotate(img: np.ndarray, angle: float) -> np.ndarray:
    h, w = img.shape[:2]
    m = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    return cv2.warpAffine(img, m, (w, h), flags=cv2.INTER_CUBIC,
                          borderMode=cv2.BORDER_REPLICATE)


def preprocess(img: np.ndarray, cfg: dict) -> np.ndarray:
    """Возвращает BGR-изображение (цвет нужен для поиска печати)."""
    if not cfg.get("enabled", True):
        return img
    out = img

    min_w = int(cfg.get("upscale_min_width", 0) or 0)
    if min_w and out.shape[1] < min_w:
        k = min_w / out.shape[1]
        out = cv2.resize(out, None, fx=k, fy=k, interpolation=cv2.INTER_CUBIC)

    if cfg.get("deskew", True):
        gray = cv2.cvtColor(out, cv2.COLOR_BGR2GRAY)
        angle = estimate_skew_angle(gray)
        if 0.3 < abs(angle) <= 35:
            out = rotate(out, angle)

    if cfg.get("denoise", True):
        out = cv2.fastNlMeansDenoisingColored(out, None, 5, 5, 7, 21)

    if cfg.get("clahe", True):
        lab = cv2.cvtColor(out, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        l = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(l)
        out = cv2.cvtColor(cv2.merge((l, a, b)), cv2.COLOR_LAB2BGR)

    if cfg.get("binarize", False):
        gray = cv2.cvtColor(out, cv2.COLOR_BGR2GRAY)
        bw = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                   cv2.THRESH_BINARY, 31, 15)
        out = cv2.cvtColor(bw, cv2.COLOR_GRAY2BGR)
    return out
