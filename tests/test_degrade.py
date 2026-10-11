import cv2
import numpy as np

from dekanat.bench.degrade import CONDITIONS, apply, rotate_expand
from dekanat.core.ocr.base import cluster_line_ids


def img():
    im = np.full((400, 300, 3), 255, np.uint8)
    cv2.putText(im, "Test 123", (20, 200), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 0), 2)
    return im


def test_all_conditions_return_valid_images_and_are_deterministic():
    for name in CONDITIONS:
        a, b = apply(name, img(), "open-001"), apply(name, img(), "open-001")
        assert a.ndim == 3 and a.shape[2] == 3 and a.dtype == np.uint8, name
        assert np.array_equal(a, b), f"{name} недетерминирован"


def test_rotation_expands_canvas_and_keeps_all_ink():
    im = img()
    r = rotate_expand(im, 30)
    assert r.shape[0] > im.shape[0] and r.shape[1] > im.shape[1]
    assert (r < 128).sum() > 0.9 * (im < 128).sum()          # текст не обрезан


def test_noise_differs_between_documents():
    assert not np.array_equal(apply("jpeg", img(), "open-001"), apply("jpeg", img(), "open-002"))


def test_cluster_line_ids_groups_fragments_on_same_line():
    boxes = [(500, 100, 800, 130), (50, 102, 400, 133),      # одна строка, порядок «наоборот»
             (50, 200, 400, 230), (460, 198, 700, 228)]      # вторая строка
    ids = cluster_line_ids(boxes)
    assert ids[0] == ids[1] and ids[2] == ids[3] and ids[0] != ids[2]
