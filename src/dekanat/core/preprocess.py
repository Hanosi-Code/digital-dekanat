"""Предобработка плохих снимков (OpenCV). Каждый шаг включается флагом из settings.yaml,
чтобы можно было измерить вклад шага в качество OCR."""
from __future__ import annotations

import cv2
import numpy as np


def _row_score(mask: np.ndarray, angle: float) -> float:
    h, w = mask.shape
    m = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    rot = cv2.warpAffine(mask, m, (w, h), flags=cv2.INTER_NEAREST)
    prof = rot.sum(axis=1, dtype=np.float64) / 255.0
    return float(np.sum(prof * prof))              # максимум, когда строки текста горизонтальны


def estimate_skew_angle(gray: np.ndarray, max_angle: float = 35.0) -> float:
    """Угол поворота (градусы), который нужно применить к снимку, чтобы строки стали горизонтальными.

    Метод профиля проекций по компонентам размера «буква»: крупные объекты (печать, рамки, тени)
    отбрасываются, поэтому они не сбивают оценку. 0.0, если текст уже ровный или оценка ненадёжна."""
    h, w = gray.shape[:2]
    k = 900.0 / max(h, w)
    small = cv2.resize(gray, None, fx=k, fy=k, interpolation=cv2.INTER_AREA) if k < 1 else gray
    inv = cv2.bitwise_not(small)
    bw = cv2.threshold(inv, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]
    n, labels, stats, _ = cv2.connectedComponentsWithStats(bw, connectivity=8)
    H, W = bw.shape
    keep_ids = (stats[:, cv2.CC_STAT_HEIGHT] < 0.06 * H) & (stats[:, cv2.CC_STAT_WIDTH] < 0.15 * W) \
        & (stats[:, cv2.CC_STAT_AREA] >= 4)
    keep_ids[0] = False
    mask = (keep_ids[labels].astype(np.uint8)) * 255
    if mask.sum() / 255 < 200:
        return 0.0

    base = _row_score(mask, 0.0)
    coarse = max(((_row_score(mask, a), a) for a in np.arange(-max_angle, max_angle + 0.01, 1.0)))
    fine = max(((_row_score(mask, a), a) for a in np.arange(coarse[1] - 1.0, coarse[1] + 1.01, 0.2)))
    best_score, best_angle = fine
    if best_score < base * 1.02:                    # улучшения нет -> считаем текст ровным
        return 0.0
    return float(best_angle)


def rotate(img: np.ndarray, angle: float) -> np.ndarray:
    h, w = img.shape[:2]
    m = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    return cv2.warpAffine(img, m, (w, h), flags=cv2.INTER_CUBIC,
                          borderMode=cv2.BORDER_REPLICATE)


def flatten_illumination(img: np.ndarray) -> np.ndarray:
    """Убирает тени и неравномерное освещение: оцениваем «фон страницы» (морфологическое закрытие стирает
    тёмный текст) и делим на него. Цвет сохраняется (множитель общий для каналов), поэтому печать
    остаётся синей. Фон считаем на уменьшенной копии: быстро и достаточно точно."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    k = 0.25
    small = cv2.resize(gray, None, fx=k, fy=k, interpolation=cv2.INTER_AREA)
    size = max(15, int(min(small.shape) / 12) | 1)
    bg = cv2.morphologyEx(small, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (size, size)))
    bg = cv2.GaussianBlur(bg, (0, 0), size / 2)
    bg = cv2.resize(bg, (w, h), interpolation=cv2.INTER_LINEAR).astype(np.float32)
    gain = 255.0 / np.maximum(bg, 60.0)                     # 60: не раздуваем почти чёрные области
    return np.clip(img.astype(np.float32) * gain[..., None], 0, 255).astype(np.uint8)


def sharpness(gray: np.ndarray) -> float:
    """Дисперсия лапласиана на фиксированной ширине 1000 px: чем меньше, тем размытее снимок."""
    k = 1000.0 / gray.shape[1]
    g = cv2.resize(gray, None, fx=k, fy=k, interpolation=cv2.INTER_AREA)
    return float(cv2.Laplacian(g, cv2.CV_64F).var())


def unsharp(img: np.ndarray, amount: float = 1.6, sigma: float = 1.6) -> np.ndarray:
    blur = cv2.GaussianBlur(img, (0, 0), sigma)
    return cv2.addWeighted(img, 1 + amount, blur, -amount, 0)


def preprocess(img: np.ndarray, cfg: dict) -> np.ndarray:
    """Возвращает BGR-изображение (цвет нужен для поиска печати)."""
    if not cfg.get("enabled", True):
        return img
    out = img

    min_w = int(cfg.get("upscale_min_width", 0) or 0)
    if min_w and out.shape[1] < min_w:
        k = min_w / out.shape[1]
        out = cv2.resize(out, None, fx=k, fy=k, interpolation=cv2.INTER_CUBIC)

    if cfg.get("flatten_illumination", True):      # до оценки наклона: тени ломают бинаризацию
        out = flatten_illumination(out)

    if cfg.get("deskew", True):
        gray = cv2.cvtColor(out, cv2.COLOR_BGR2GRAY)
        angle = estimate_skew_angle(gray)
        if 0.5 < abs(angle) <= 35:
            out = rotate(out, angle)

    sharp_thr = cfg.get("sharpen_below", 0)        # 0 = выключено; иначе резкость усиливаем только у размытых
    if sharp_thr and sharpness(cv2.cvtColor(out, cv2.COLOR_BGR2GRAY)) < sharp_thr:
        out = unsharp(out)

    if cfg.get("denoise", True):
        if cfg.get("denoise_method", "bilateral") == "nlm":
            out = cv2.fastNlMeansDenoisingColored(out, None, 5, 5, 7, 21)   # ~10 с на страницу: только для экспериментов
        else:
            out = cv2.bilateralFilter(out, 5, 40, 40)                       # ~0.1 с, сохраняет края букв

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
