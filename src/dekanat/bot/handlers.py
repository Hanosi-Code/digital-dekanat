"""Диалог: /start -> тип документа -> файл -> вопрос -> ответ.

Принципы устойчивости (чтобы бот не «замолкал»):
  * кнопки выбора типа работают в ЛЮБОМ состоянии и всегда получают answer() — иначе в Telegram
    бесконечно крутится «часики»;
  * файл принимается в любом состоянии (можно сменить документ без /new);
  * любое необработанное сообщение или нажатие получает понятный ответ, а не тишину;
  * любые ошибки (API недоступен, не-JSON ответ, сбой Telegram) ловятся и показываются
    пользователем текстом, а диалог остаётся рабочим.
"""
from __future__ import annotations

import io
import logging
import os

import httpx
from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, ErrorEvent, Message

from .formatter import format_answer, format_card
from .keyboards import check_keyboard, doc_type_keyboard

log = logging.getLogger(__name__)
API_URL = os.environ.get("API_URL", "http://localhost:8000")
router = Router()

CHECK_QUESTION = "Содержит ли документ все обязательные сведения по Положению?"
HINT = "Нажмите /start, чтобы выбрать тип документа, и пришлите фото или PDF."


class Flow(StatesGroup):
    wait_file = State()       # тип выбран, ждём файл
    wait_question = State()   # файл получен, ждём вопрос


async def _doc_types() -> list[dict]:
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get(f"{API_URL}/doc-types")
        r.raise_for_status()
        return r.json()


# ---------------------------------------------------------------- старт / новый документ
@router.message(CommandStart())
@router.message(Command("new"))
async def start(message: Message, state: FSMContext) -> None:
    await state.clear()
    try:
        types = await _doc_types()
    except httpx.HTTPError:
        await message.answer("Сервис проверки документов сейчас недоступен. Попробуйте чуть позже.")
        return
    await state.update_data(types=types)
    await message.answer(
        "Я цифровой секретарь деканата. Помогу проверить документ и отвечу по Положению.\n"
        "Какой документ вы хотите проверить?",
        reply_markup=doc_type_keyboard(types))


# ---------------------------------------------------------------- выбор типа (в любом состоянии)
@router.callback_query(F.data.startswith("dt:"))
async def chosen_type(cb: CallbackQuery, state: FSMContext) -> None:
    await cb.answer()                                  # сразу убираем «часики» на кнопке
    doc_type = cb.data.split(":", 1)[1]
    await state.update_data(doc_type=None if doc_type == "auto" else doc_type,
                            file_id=None, file_name=None)
    await state.set_state(Flow.wait_file)
    if cb.message:
        await cb.message.answer("Пришлите фото, скан или PDF документа. "
                                "Вопрос можно написать в подписи к файлу.")


# ---------------------------------------------------------------- файл (в любом состоянии)
@router.message(F.photo | F.document)
async def got_file(message: Message, state: FSMContext, bot: Bot) -> None:
    if message.photo:
        file_id, name = message.photo[-1].file_id, "photo.jpg"   # максимальное разрешение
    else:
        file_id, name = message.document.file_id, message.document.file_name or "doc"
    await state.update_data(file_id=file_id, file_name=name)
    if message.caption:
        await _analyze(message, state, bot, message.caption)
    else:
        await state.set_state(Flow.wait_question)
        await message.answer("Принял. Напишите вопрос, например: «Укажи значение поля «Дата выдачи»» "
                             "— или нажмите кнопку для проверки комплектности.",
                             reply_markup=check_keyboard())


# ---------------------------------------------------------------- вопрос
@router.message(StateFilter(Flow.wait_question), F.text & ~F.text.startswith("/"))
async def got_question(message: Message, state: FSMContext, bot: Bot) -> None:
    await _analyze(message, state, bot, message.text)


@router.message(StateFilter(Flow.wait_file), F.text & ~F.text.startswith("/"))
async def need_file(message: Message) -> None:
    await message.answer("Сначала пришлите документ: фото, скан (JPG/PNG) или PDF.")


# ---------------------------------------------------------------- анализ
async def _analyze(message: Message, state: FSMContext, bot: Bot, question: str) -> None:
    data = await state.get_data()
    if not data.get("file_id"):
        await message.answer(HINT)
        return

    wait = await message.answer("Читаю документ…")
    try:
        buf = io.BytesIO()
        await bot.download(data["file_id"], destination=buf)
        form = {"question": question}
        if data.get("doc_type"):
            form["doc_type"] = data["doc_type"]
        async with httpx.AsyncClient(timeout=120) as c:
            r = await c.post(f"{API_URL}/analyze",
                             files={"file": (data.get("file_name") or "doc", buf.getvalue())},
                             data=form)
    except httpx.HTTPError:
        await wait.edit_text("Сервис проверки недоступен, попробуйте позже.")
        return

    if r.status_code != 200:
        try:
            detail = r.json().get("detail", "")
        except ValueError:                     # 500 без JSON
            detail = ""
        log.error("API %s: %s", r.status_code, r.text[:300])
        extra = " Выберите тип документа вручную: /new." if r.status_code == 422 else ""
        await wait.edit_text(f"Не получилось обработать документ. {detail}{extra}".strip())
        return

    resp = r.json()
    types = {t["id"]: t for t in data.get("types", [])}
    if resp["card"]["doc_type"] not in types:   # после перезапуска бота список мог потеряться
        try:
            types = {t["id"]: t for t in await _doc_types()}
        except httpx.HTTPError:
            types = {}
    doc_type = types.get(resp["card"]["doc_type"],
                         {"title": resp["card"]["doc_type"], "fields": []})

    await wait.edit_text(format_card(resp["card"], doc_type), parse_mode="HTML")
    await message.answer(format_answer(resp, doc_type), parse_mode="HTML")
    await state.update_data(doc_type=resp["card"]["doc_type"])    # закрепляем найденный тип
    await state.set_state(Flow.wait_question)
    await message.answer("Можно задать ещё вопрос по этому документу или нажать /new.")


@router.callback_query(F.data == "check")
async def check_button(cb: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    await cb.answer()
    if cb.message:
        await _analyze(cb.message, state, bot, CHECK_QUESTION)


# ---------------------------------------------------------------- «ловушки»: никакой тишины
@router.callback_query()
async def stale_button(cb: CallbackQuery) -> None:
    await cb.answer("Эта кнопка устарела. Нажмите /start", show_alert=True)


@router.errors()
async def on_error(event: ErrorEvent) -> bool:
    log.exception("Ошибка в обработчике: %s", event.exception)
    upd = event.update
    target = (upd.message or (upd.callback_query.message if upd.callback_query else None))
    if upd.callback_query:
        try:
            await upd.callback_query.answer()
        except Exception:  # noqa: BLE001
            pass
    if target:
        try:
            await target.answer("Что-то пошло не так. Нажмите /start и попробуйте ещё раз.")
        except Exception:  # noqa: BLE001
            pass
    return True


@router.message()
async def fallback(message: Message) -> None:
    await message.answer(HINT)
