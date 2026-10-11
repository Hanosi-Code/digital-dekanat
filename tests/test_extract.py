import numpy as np

from dekanat.core.config import load_doc_types, load_settings
from dekanat.core.extract.fields import extract_card
from dekanat.core.ocr import Line

IMG = np.full((600, 800, 3), 255, np.uint8)       # пустой белый лист: подписи и печати нет


def L(t, y):
    return Line(t, (0, y, 500, y + 20), 0.95)


def run(dt_id, texts):
    lines = [L(t, 20 * i) for i, t in enumerate(texts)]
    return extract_card(load_doc_types()[dt_id], lines, IMG, load_settings())


def test_study_certificate():
    c = run("study_certificate", [
        "СПРАВКА № СП-2026/17",
        "Выдана 5 сентября 2026 года",
        "ФИО студента: Иванов Иван Иванович",
        "Название вуза: Университет «Меридиан»",
        "Форма обучения: очная",
        "Период обучения: с 01.09.2022 по 30.06.2026",
    ])
    f = {k: v.value for k, v in c.fields.items() if v.found}
    assert f["document_number"] == "СП-2026/17"
    assert f["issue_date"] == "2026-09-05"
    assert f["student_name"] == "Иванов Иван Иванович"
    assert f["study_start"] == "2022-09-01" and f["study_end"] == "2026-06-30"
    assert f["study_form"] == "очная"
    assert "program" not in f                       # нет на документе -> не найдено
    assert c.fields["seal_present"].value is False and c.fields["signature_present"].value is False


def test_leave_application_course_and_group():
    c = run("academic_leave_application", [
        "Заявление",
        "ФИО студента: Петрова Анна Сергеевна",
        "Учебная группа: ИС-21    Курс: 2",
        "Причина отпуска: по состоянию здоровья",
        "Дата начала отпуска: 01.10.2026",
        "Дата окончания отпуска: 01.10.2027",
        "Дата заявления: 25.09.2026",
    ])
    f = {k: v.value for k, v in c.fields.items() if v.found}
    assert f["group"] == "ИС-21"
    assert f["course"] == "2"
    assert f["leave_reason"] == "по состоянию здоровья"
    assert f["leave_start"] == "2026-10-01" and f["leave_end"] == "2027-10-01"
    assert f["application_date"] == "2026-09-25"
    assert "seal_present" not in c.fields           # у заявления печати нет (п. 4.3)


def test_empty_field_is_not_stolen_from_next_label():
    c = run("study_certificate", ["Дата выдачи:", "Номер справки: 123"])
    assert not c.fields["issue_date"].found


def test_application_date_not_taken_from_leave_dates():
    c = run("academic_leave_application", [
        "Дата начала отпуска: 01.10.2026", "Дата окончания отпуска: 01.10.2027",
        "Дата: 25.09.2026"])
    assert c.fields["application_date"].value == "2026-09-25"
    assert c.fields["leave_start"].value == "2026-10-01"


def test_empty_value_is_not_filled_with_rest_of_label():
    """Пустое поле «ФИО студента:» не должно дать значение «студента» (баг на open-005/015/025)."""
    c = run("study_certificate", [
        "ФИО студента:",
        "Название вуза: Учебная академия «Горизонт»",
        "Направление подготовки:",
        "Форма обучения:",
        "Номер справки: ОБ-1005",
    ])
    assert not c.fields["student_name"].found
    assert not c.fields["program"].found
    assert not c.fields["study_form"].found
    assert c.fields["university"].value == "Учебная академия «Горизонт»"
    assert c.fields["document_number"].value == "ОБ-1005"


def test_empty_leave_reason():
    c = run("academic_leave_application", ["Причина отпуска:", "Дата начала отпуска: 01.11.2026"])
    assert not c.fields["leave_reason"].found
    assert c.fields["leave_start"].value == "2026-11-01"


def test_student_name_not_taken_from_supervisor():
    """open-025: пустое «ФИО студента:» не должно подхватывать ФИО руководителя практики."""
    c = run("internship_certificate", [
        "ФИО студента:",
        "Название организации: Учебная организация «Спектр»",
        "ФИО руководителя практики: Кузнецова Мария Сергеевна",
    ])
    assert not c.fields["student_name"].found
    assert c.fields["supervisor_name"].value == "Кузнецова Мария Сергеевна"


def test_signature_label_requires_colon():
    from dekanat.core.extract.fields import _label_bbox
    from dekanat.core.ocr import Word

    def line(*words):
        ws = [Word(t, (x, 10, x + 80, 40), 0.95, 1) for t, x in words]
        return Line(" ".join(t for t, _ in words), (0, 10, 900, 40), 0.95, ws)

    assert _label_bbox(line(("Подпись", 100), ("сотрудника:", 200))) == [100, 10, 280, 40]
    # сноска без двоеточия не является меткой
    assert _label_bbox(line(("Подпись", 100), ("и", 200), ("печать", 300), ("являются", 400))) is None
