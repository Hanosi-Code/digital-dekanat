from dekanat.core.config import load_doc_types, load_settings
from dekanat.core.extract.fields import extract_card
from dekanat.core.ocr import Line
import numpy as np


def L(t, y):
    return Line(t, (0, y, 500, y + 20), 0.95)


def test_extract_basic_fields():
    lines = [
        L("СПРАВКА № 123/24", 10),
        L("Выдана 05.09.2024", 40),
        L("Период обучения: с 01.09.2022 по 30.06.2024", 70),
        L("Форма обучения: очная", 100),
    ]
    img = np.full((600, 800, 3), 255, np.uint8)
    card = extract_card(load_doc_types()["study_certificate"], lines, img, load_settings())
    assert card.fields["issue_number"].value == "123/24"
    assert card.fields["issue_date"].value == "05.09.2024"
    assert card.fields["study_period"].value == "01.09.2022 – 30.06.2024"
    assert card.fields["study_form"].value == "очная"
    assert not card.fields["program"].found          # нет на документе -> «не найдено»
    assert card.fields["stamp"].value is False        # пустой белый лист
