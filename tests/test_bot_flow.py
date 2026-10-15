"""Симуляция Telegram: проверяем, что бот отвечает на КАЖДОЕ действие и не «замолкает»."""
import asyncio
import datetime
import itertools

import pytest

pytest.importorskip("aiogram")

from aiogram import Bot, Dispatcher  # noqa: E402
from aiogram.client.session.base import BaseSession  # noqa: E402
from aiogram.fsm.storage.memory import MemoryStorage, SimpleEventIsolation  # noqa: E402
from aiogram.methods import EditMessageText, GetFile, SendMessage  # noqa: E402
from aiogram.types import CallbackQuery, Chat, File, Message, PhotoSize, Update, User  # noqa: E402

from dekanat.bot import handlers  # noqa: E402

TYPES = [{"id": "study_certificate", "title": "Справка", "fields": [{"id": "seal_present", "label": "Печать вуза"}]},
         {"id": "academic_leave_application", "title": "Заявление", "fields": []}]
OK_RESP = {"card": {"doc_type": "study_certificate",
                    "fields": {"seal_present": {"value": False, "status": "found"}}, "raw_text": ""},
           "validation": {"status": "missing_fields", "missing_fields": ["seal_present"],
                          "sources": ["rule:3.3"]},
           "answer": {"question_id": None, "intent": "completeness", "answerable": True,
                      "value": "missing_fields", "answer": "Не хватает обязательных сведений: печать вуза.",
                      "sources": ["rule:3.3"]},
           "rule_texts": {"3.3": "Обязательна печать вуза."}}


class FakeSession(BaseSession):
    def __init__(self):
        super().__init__()
        self.sent = []

    async def close(self): ...

    async def stream_content(self, *a, **k):
        yield b"imagebytes"

    async def make_request(self, bot, method, timeout=None):
        self.sent.append(getattr(method, "text", None) or type(method).__name__)
        if isinstance(method, (SendMessage, EditMessageText)):
            return Message(message_id=1, date=datetime.datetime.now(), chat=Chat(id=1, type="private"), text="x").as_(bot)
        if isinstance(method, GetFile):
            return File(file_id="f", file_unique_id="u", file_path="p.jpg")
        return True


class FakeResp:
    def __init__(self, status, payload=None, text=""):
        self.status_code, self._p, self.text = status, payload, text

    def json(self):
        if self._p is None:
            raise ValueError("not json")
        return self._p


def fake_client(resp):
    class C:
        def __init__(self, *a, **k): ...
        async def __aenter__(self): return self
        async def __aexit__(self, *a): ...
        async def get(self, *a, **k): return FakeResp(200, TYPES)
        async def post(self, *a, **k): return resp
    return C


class Chatter:
    def __init__(self):
        self.session = FakeSession()
        self.bot = Bot("123:ABC", session=self.session)
        self.dp = Dispatcher(storage=MemoryStorage(), events_isolation=SimpleEventIsolation())
        handlers.router._parent_router = None   # роутер модульный: отвязываем от прошлого теста
        self.dp.include_router(handlers.router)
        self.u = User(id=1, is_bot=False, first_name="a")
        self.ch = Chat(id=1, type="private")
        self.n = itertools.count(1)

    def _m(self, message_id=None, **kw):
        i = message_id if message_id is not None else next(self.n)
        return Message(message_id=i, date=datetime.datetime.now(), chat=self.ch, from_user=self.u, **kw)

    async def send(self, upd):
        self.session.sent.clear()
        await self.dp.feed_update(self.bot, upd)
        return list(self.session.sent)

    async def text(self, t):
        return await self.send(Update(update_id=next(self.n), message=self._m(text=t)))

    async def photo(self, caption=None):
        ph = [PhotoSize(file_id="f", file_unique_id="u", width=10, height=10)]
        return await self.send(Update(update_id=next(self.n), message=self._m(photo=ph, caption=caption)))

    async def click(self, data, message_id=None, clear=True):
        cb = CallbackQuery(id=str(next(self.n)), from_user=self.u, chat_instance="c", data=data,
                           message=self._m(message_id=message_id, text="kb"))
        if clear:
            self.session.sent.clear()
        await self.dp.feed_update(self.bot, Update(update_id=next(self.n), callback_query=cb))
        return list(self.session.sent)


@pytest.fixture(autouse=True)
def patch_api(monkeypatch):
    async def types(): return TYPES
    monkeypatch.setattr(handlers, "_doc_types", types)
    monkeypatch.setattr(handlers.httpx, "AsyncClient", fake_client(FakeResp(200, OK_RESP)))


@pytest.mark.asyncio
async def test_buttons_work_repeatedly():
    c = Chatter()
    assert await c.text("/start")
    for data in ("dt:study_certificate", "dt:academic_leave_application", "dt:auto", "dt:study_certificate"):
        assert await c.click(data), f"нет отклика на {data}"          # баг: раньше молчал со 2-го раза


@pytest.mark.asyncio
async def test_rapid_type_button_clicks_reply_once():
    c = Chatter()
    c.session.sent.clear()
    await asyncio.gather(
        c.click("dt:study_certificate", message_id=100, clear=False),
        c.click("dt:academic_leave_application", message_id=100, clear=False),
    )
    assert c.session.sent.count("AnswerCallbackQuery") == 2
    assert sum("Пришлите фото" in sent for sent in c.session.sent) == 1


@pytest.mark.asyncio
async def test_button_after_restart_does_not_hang():
    c = Chatter()                                                       # состояние пустое, как после рестарта
    out = await c.click("dt:study_certificate")
    assert out                                                          # устаревшая кнопка тоже работает


@pytest.mark.asyncio
async def test_full_flow_and_followup():
    c = Chatter()
    await c.text("/start"); await c.click("dt:study_certificate")
    assert await c.text("привет")                                       # «нужен файл»
    assert await c.photo()                                              # «пришлите вопрос»
    out = await c.text("Хватит ли справки?")
    assert any("Не хватает" in s for s in out)
    assert await c.text("А какая печать?")                              # второй вопрос по тому же документу
    assert await c.photo("Хватит ли?")                                  # новый файл с подписью без /new


@pytest.mark.asyncio
async def test_api_500_without_json_is_reported(monkeypatch):
    monkeypatch.setattr(handlers.httpx, "AsyncClient", fake_client(FakeResp(500, None, "Internal Server Error")))
    c = Chatter()
    await c.text("/start"); await c.click("dt:study_certificate")
    out = await c.photo("Хватит ли?")
    assert any("Не получилось" in s for s in out)
    assert await c.text("/start")                                       # бот жив


@pytest.mark.asyncio
async def test_unknown_inputs_get_hint():
    c = Chatter()
    assert await c.text("что-то")                                       # без /start
    assert await c.text("/help")
    assert await c.click("bad:data")


@pytest.mark.asyncio
async def test_check_button_runs_completeness():
    c = Chatter()
    await c.text("/start"); await c.click("dt:study_certificate")
    await c.photo()                                                     # без подписи -> появляется кнопка
    out = await c.click("check")
    assert any("Не хватает" in s for s in out)


@pytest.mark.asyncio
async def test_check_button_without_file_does_not_hang():
    c = Chatter()
    assert await c.click("check")
