"""Детерминированные «порчи» снимков для сравнения OCR и предобработки.
Условия имитируют то, что в кейсе названо плохими снимками: наклон до 30°, тени, блики, низкое разрешение."""
from __future__ import annotations

import zlib

import cv2
import numpy as np

WHITE = (255, 255, 255)


def rotate_expand(img: np.ndarray, angle: float) -> np.ndarray:
    """Поворот на angle градусов (против часовой) без обрезки краёв; фон белый."""
    h, w = img.shape[:2]
    m = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    cos, sin = abs(m[0, 0]), abs(m[0, 1])
    nw, nh = int(h * sin + w * cos), int(h * cos + w * sin)
    m[0, 2] += nw / 2 - w / 2
    m[1, 2] += nh / 2 - h / 2
    return cv2.warpAffine(img, m, (nw, nh), flags=cv2.INTER_CUBIC, borderValue=WHITE)


def blur(img: np.ndarray, sigma: float = 2.0) -> np.ndarray:
    return cv2.GaussianBlur(img, (0, 0), sigma)


def lowres(img: np.ndarray, width: int = 560) -> np.ndarray:
    k = width / img.shape[1]
    return cv2.resize(img, None, fx=k, fy=k, interpolation=cv2.INTER_AREA)


def shadow(img: np.ndarray, darkest: float = 0.45) -> np.ndarray:
    """Диагональный градиент освещённости: слева-сверху темно, справа-снизу светло."""
    h, w = img.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w]
    mult = darkest + (1 - darkest) * ((xx / w + yy / h) / 2)
    return np.clip(img.astype(np.float32) * mult[..., None], 0, 255).astype(np.uint8)


def glare(img: np.ndarray, peak: float = 140.0) -> np.ndarray:
    """Блик: гауссово пятно света, осветляющее и обесцвечивающее участок страницы."""
    h, w = img.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w]
    cx, cy, s = 0.35 * w, 0.38 * h, 0.14 * w
    blob = np.exp(-(((xx - cx) ** 2 + (yy - cy) ** 2) / (2 * s * s)))
    return np.clip(img.astype(np.float32) + peak * blob[..., None], 0, 255).astype(np.uint8)


def noise(img: np.ndarray, sigma: float, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return np.clip(img.astype(np.float32) + rng.normal(0, sigma, img.shape), 0, 255).astype(np.uint8)


def jpeg(img: np.ndarray, quality: int) -> np.ndarray:
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, quality])
    return cv2.imdecode(buf, cv2.IMREAD_COLOR)


CONDITIONS = {
    "clean": lambda im, seed: im,
    "rot5": lambda im, seed: rotate_expand(im, 5),
    "rot15": lambda im, seed: rotate_expand(im, -15),
    "rot30": lambda im, seed: rotate_expand(im, 30),
    "blur": lambda im, seed: blur(im, 2.0),
    "lowres": lambda im, seed: lowres(im, 560),
    "shadow": lambda im, seed: shadow(im, 0.45),
    "glare": lambda im, seed: glare(im, 140),
    "jpeg": lambda im, seed: jpeg(noise(im, 10, seed), 25),
    # «фото с телефона»: наклон + тень + лёгкая размытость + шум + сжатие
    "photo": lambda im, seed: jpeg(noise(blur(shadow(rotate_expand(im, 7), 0.55), 1.2), 8, seed), 40),
}


def apply(name: str, img: np.ndarray, key: str = "") -> np.ndarray:
    """key (например, document_id) делает шум воспроизводимым для каждого документа."""
    return CONDITIONS[name](img, zlib.crc32(key.encode()) & 0xFFFF)
