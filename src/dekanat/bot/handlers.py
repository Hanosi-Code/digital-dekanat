"""Диалог: /start -> тип документа -> файл -> вопрос -> ответ.
После ответа документ запоминается: можно задавать следующие вопросы (/new — новый документ)."""
from __future__ import annotations

import io
import os

import httpx
from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from .formatter import format_answer, format_card
from .keyboards import doc_type_keyboard

API_URL = os.environ.get("API_URL", "http://localhost:8000")
router = Router()


class Flow(StatesGroup):
    choose_type = State()
    wait_file = State()
    wait_question = State()


async def _doc_types() -> list[dict]:
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get(f"{API_URL}/doc-types")
        r.raise_for_status()
        return r.json()


async def _ask_for_type(message: Message, state: FSMContext) -> None:
    types = await _doc_types()
    await state.set_state(Flow.choose_type)
    await state.update_data(types=types)
    await message.answer(
        "Я цифровой секретарь деканата. Помогу проверить документ и отвечу по Положению.\n"
        "Какой документ вы хотите проверить?",
        reply_markup=doc_type_keyboard(types))


@router.message(CommandStart())
@router.message(Command("new"))
async def start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await _ask_for_type(message, state)


@router.callback_query(Flow.choose_type, F.data.startswith("dt:"))
async def chosen_type(cb: CallbackQuery, state: FSMContext) -> None:
    doc_type = cb.data.split(":", 1)[1]
    await state.update_data(doc_type=None if doc_type == "auto" else doc_type)
    await state.set_state(Flow.wait_file)
    await cb.message.answer("Пришлите фото, скан или PDF документа. "
                            "Вопрос можно написать в подписи к файлу.")
    await cb.answer()


@router.message(Flow.wait_file, F.photo | F.document)
async def got_file(message: Message, state: FSMContext, bot: Bot) -> None:
    if message.photo:
        file_id, name = message.photo[-1].file_id, "photo.jpg"   # самое большое разрешение
    else:
        file_id, name = message.document.file_id, message.document.file_name or "doc"
    await state.update_data(file_id=file_id, file_name=name)
    if message.caption:
        await _analyze(message, state, bot, message.caption)
    else:
        await state.set_state(Flow.wait_question)
        await message.answer("Принял. Теперь напишите вопрос, например: "
                             "«Хватит ли этой справки для перевода на 2 курс?»")


@router.message(Flow.wait_question, F.text & ~F.text.startswith("/"))
async def got_question(message: Message, state: FSMContext, bot: Bot) -> None:
    await _analyze(message, state, bot, message.text)


@router.message(Flow.wait_file)
async def wrong_input(message: Message) -> None:
    await message.answer("Нужен файл: фото, скан (JPG/PNG) или PDF.")


async def _analyze(message: Message, state: FSMContext, bot: Bot, question: str) -> None:
    data = await state.get_data()
    wait = await message.answer("Читаю документ…")
    buf = io.BytesIO()
    await bot.download(data["file_id"], destination=buf)
    try:
        async with httpx.AsyncClient(timeout=120) as c:
            r = await c.post(
                f"{API_URL}/analyze",
                files={"file": (data["file_name"], buf.getvalue())},
                data={"question": question, **({"doc_type": data["doc_type"]}
                                               if data.get("doc_type") else {})})
        if r.status_code != 200:
            await wait.edit_text(f"Не получилось обработать документ: {r.json().get('detail', r.text)}")
            return
        resp = r.json()
    except httpx.HTTPError:
        await wait.edit_text("Сервис временно недоступен, попробуйте позже.")
        return

    types = {t["id"]: t for t in data.get("types", [])} or {t["id"]: t for t in await _doc_types()}
    doc_type = types[resp["card"]["doc_type"]]
    await wait.edit_text(format_card(resp["card"], doc_type), parse_mode="HTML")
    await message.answer(format_answer(resp), parse_mode="HTML")
    await state.update_data(doc_type=resp["card"]["doc_type"])   # закрепляем найденный тип
    await state.set_state(Flow.wait_question)
    await message.answer("Можно задать ещё вопрос по этому документу или нажать /new.")
