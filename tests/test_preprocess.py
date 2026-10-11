import cv2
import numpy as np

from dekanat.core.preprocess import estimate_skew_angle, preprocess, rotate
from dekanat.core.extract.stamp_signature import detect_signature, detect_stamp


def page(with_seal=True):
    img = np.full((1000, 1240, 3), 255, np.uint8)
    for i in range(10):
        cv2.putText(img, f"Line {i} text field value 2026", (70, 90 + i * 70),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.1, (0, 0, 0), 2)
    if with_seal:
        cv2.ellipse(img, (900, 800), (130, 110), 0, 0, 360, (200, 60, 30), 7)   # синяя печать (BGR)
    return img


def test_seal_does_not_cause_false_skew():
    g = cv2.cvtColor(page(True), cv2.COLOR_BGR2GRAY)
    assert estimate_skew_angle(g) == 0.0


def test_skew_is_recovered():
    tilted = rotate(page(True), 12.0)
    a = estimate_skew_angle(cv2.cvtColor(tilted, cv2.COLOR_BGR2GRAY))
    assert abs(a - (-12.0)) < 1.5                  # нужная коррекция — в обратную сторону
    fixed = preprocess(tilted, {"enabled": True, "deskew": True, "denoise": False, "clahe": False})
    left = estimate_skew_angle(cv2.cvtColor(fixed, cv2.COLOR_BGR2GRAY))
    assert abs(left) < 1.0


PAGE_BOXES = [(70, 55 + i * 70, 800, 105 + i * 70) for i in range(10)]   # рамки строк, как у OCR


def test_printed_signature_label_is_not_a_signature():
    img = page(False)
    boxes = PAGE_BOXES + [(70, 700, 400, 740)]     # OCR-рамки: строки страницы и слово «Подпись:»
    cv2.putText(img, "Podpis:", (70, 735), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (0, 0, 0), 2)
    assert detect_signature(img, 0.0002, [70, 700, 400, 740], boxes).value is False


def test_graphic_signature_is_detected():
    img = page(False)
    pts = np.array([[480, 800], [520, 770], [560, 820], [600, 760], [660, 815], [720, 780]], np.int32)
    cv2.polylines(img, [pts], False, (120, 40, 20), 4)
    boxes = PAGE_BOXES + [(70, 700, 400, 740)]
    assert detect_signature(img, 0.0002, [70, 700, 400, 740], boxes).value is True


def test_seal_detected_only_when_present():
    assert detect_stamp(page(True)).value is True
    assert detect_stamp(page(False)).value is False


def test_flat_signature_merged_with_underline_is_detected():
    """open-005: плоский росчерк (321x37), слитый с линейкой, не должен считаться линейкой."""
    img = np.full((1000, 1240, 3), 255, np.uint8)
    cv2.line(img, (440, 790), (700, 790), (170, 170, 170), 1)                 # линейка
    pts = np.array([[455, 785], [470, 765], [485, 785], [500, 762], [520, 788], [545, 766],
                    [570, 786], [595, 768], [615, 786]], np.int32)
    cv2.polylines(img, [pts], False, (120, 60, 20), 4)
    assert detect_signature(img, 0.0002, [70, 770, 400, 800], []).value is True


def test_underline_only_is_not_a_signature():
    img = np.full((1000, 1240, 3), 255, np.uint8)
    cv2.line(img, (440, 790), (700, 800), (150, 150, 150), 2)                 # слегка наклонная линейка
    assert detect_signature(img, 0.0002, [70, 770, 400, 800], []).value is False
