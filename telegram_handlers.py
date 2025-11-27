import asyncio
from db import SessionLocal
from models import Discipline
import json

async def handle_telegram_commands(message, send_telegram_message_fn):
    """
    message: dict — payload message из Telegram webhook
    send_telegram_message_fn: async function(chat_id, text) -> send message
    """
    text = message.get("text") or ""
    chat = message.get("chat", {})
    chat_id = chat.get("id")
    if not text or not text.startswith("/"):
        return False  # не команда

    parts = text.strip().split()
    cmd = parts[0].lower()

    if cmd == "/disciplines":
        def _fn():
            db = SessionLocal()
            try:
                return db.query(Discipline).order_by(Discipline.title).all()
            finally:
                db.close()
        ds = await asyncio.to_thread(_fn)
        if not ds:
            await send_telegram_message_fn(chat_id, "Дисциплины не найдены. Добавьте через /admin или через веб-интерфейс.")
            return True
        msg = "Доступные дисциплины:\n" + "\n".join([f"{d.id}. {d.title} ({d.code})" for d in ds])
        msg += "\n\nВыберите дисциплину командой: /setdiscipline <id>"
        await send_telegram_message_fn(chat_id, msg)
        return True

    if cmd == "/setdiscipline" and len(parts) >= 2:
        try:
            discipline_id = int(parts[1])
        except ValueError:
            await send_telegram_message_fn(chat_id, "Неверный id дисциплины. Используйте /disciplines для списка.")
            return True
        def _fn_set():
            db = SessionLocal()
            try:
                # простая версия: сохраняем в таблицу chat_settings (используйте модель ChatSetting)
                from models import ChatSetting
                cs = db.query(ChatSetting).get(chat_id)
                if cs is None:
                    cs = ChatSetting(chat_id=chat_id, discipline_id=discipline_id)
                    db.add(cs)
                else:
                    cs.discipline_id = discipline_id
                db.commit()
                db.refresh(cs)
                return cs
            finally:
                db.close()
        await asyncio.to_thread(_fn_set)
        await send_telegram_message_fn(chat_id, f"Дисциплина установлена: id={discipline_id}")
        return True

    if cmd == "/currentdiscipline":
        def _fn():
            db = SessionLocal()
            try:
                from models import ChatSetting
                cs = db.query(ChatSetting).get(chat_id)
                return cs.discipline_id if cs else None
            finally:
                db.close()
        disc_id = await asyncio.to_thread(_fn)
        if not disc_id:
            await send_telegram_message_fn(chat_id, "Дисциплина не установлена. Используйте /disciplines для списка.")
        else:
            await send_telegram_message_fn(chat_id, f"Текущая дисциплина id={disc_id}")
        return True

    if cmd in ("/help", "/start"):
        await send_telegram_message_fn(chat_id, "Команды:\n/disciplines — список дисциплин\n/setdiscipline <id> — выбрать дисциплину\n/currentdiscipline — показать текущую")
        return True

    return False