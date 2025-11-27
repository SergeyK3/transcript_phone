import os
import logging
import mimetypes
from pathlib import Path
from typing import Dict, Any, Optional

import aiofiles
import httpx
from fastapi import FastAPI, Request, BackgroundTasks

# Конфиг из окружения
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
UPLOADS_DIR = Path(os.getenv("UPLOADS_DIR", "uploads"))
TRANSCRIPTS_DIR = Path(os.getenv("TRANSCRIPTS_DIR", "transcripts"))

if TELEGRAM_BOT_TOKEN is None:
    raise RuntimeError("TELEGRAM_BOT_TOKEN not set")
if OPENAI_API_KEY is None:
    raise RuntimeError("OPENAI_API_KEY not set")

UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)

TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
TELEGRAM_FILE_API = f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}"
OPENAI_TRANSCRIPT_ENDPOINT = "https://api.openai.com/v1/audio/transcriptions"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tg-whisper-bot")

app = FastAPI(title="Telegram -> Whisper transcription bot (FastAPI)")

@app.post("/telegram/webhook")
async def telegram_webhook(request: Request, background_tasks: BackgroundTasks):
    update = await request.json()
    # быстро отвечаем Telegram, делаем работу в background
    background_tasks.add_task(handle_update, update)
    return {"ok": True}


async def handle_update(update: Dict[str, Any]) -> None:
    try:
        message = update.get("message") or update.get("edited_message")
        if not message:
            logger.debug("no message in update")
            return

        chat = message.get("chat", {})
        chat_id = chat.get("id")
        message_id = message.get("message_id")

        # Telegram может прислать voice (огг), audio (mp3), или document
        file_id = None
        file_name = None

        if "voice" in message:
            file_id = message["voice"]["file_id"]
            file_name = f"voice_{message_id}.ogg"
        elif "audio" in message:
            file_id = message["audio"]["file_id"]
            # try original filename
            file_name = message["audio"].get("file_name") or f"audio_{message_id}.mp3"
        elif "document" in message and message["document"].get("mime_type", "").startswith("audio"):
            file_id = message["document"]["file_id"]
            file_name = message["document"].get("file_name") or f"document_{message_id}"
        else:
            # если нет аудио — оповестим пользователя
            await send_telegram_message(chat_id, "Отправьте голосовое сообщение, аудиофайл или документ с аудио.")
            return

        # скачиваем файл
        saved_path = await download_telegram_file(file_id, file_name)
        logger.info(f"Saved uploaded file to {saved_path}")

        # транскрибируем через OpenAI Whisper API
        transcript_text = await transcribe_with_openai(saved_path)
        logger.info("Transcription finished")

        # нормализация базовая
        if transcript_text:
            normalized = " ".join(transcript_text.split()).strip()
        else:
            normalized = ""

        # сохраняем результат локально
        transcript_path = TRANSCRIPTS_DIR / (Path(saved_path).stem + ".txt")
        async with aiofiles.open(transcript_path, "w", encoding="utf-8") as f:
            await f.write(normalized)

        # отправляем результат обратно пользователю (частями если длинный)
        await send_long_message(chat_id, normalized)

        # отправляем файл как документ (полный текст)
        await send_document(chat_id, str(transcript_path))
    except Exception as e:
        logger.exception("Error in handle_update: %s", e)
        # если есть чат_id — уведомим пользователя
        try:
            chat = (update.get("message") or {}).get("chat", {})
            chat_id = chat.get("id")
            if chat_id:
                await send_telegram_message(chat_id, "Произошла ошибка при обработке аудио.")
        except Exception:
            pass


async def download_telegram_file(file_id: str, filename: str) -> str:
    # получаем file_path
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(f"{TELEGRAM_API}/getFile", params={"file_id": file_id})
        resp.raise_for_status()
        data = resp.json()
        file_path = data["result"]["file_path"]
        download_url = f"{TELEGRAM_FILE_API}/{file_path}"

        # скачиваем
        r = await client.get(download_url)
        r.raise_for_status()

        full_path = UPLOADS_DIR / filename
        async with aiofiles.open(full_path, "wb") as f:
            await f.write(r.content)
        return str(full_path)


async def transcribe_with_openai(file_path: str, language: Optional[str] = None) -> str:
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}
    # Формируем multipart/form-data. model=whisper-1 (OpenAI Whisper API)
    params = {"model": "whisper-1"}
    if language:
        params["language"] = language  # например "kk" или "ru" — опционально

    async with httpx.AsyncClient(timeout=300.0) as client:
        mime_type, _ = mimetypes.guess_type(file_path)
        if not mime_type:
            mime_type = "application/octet-stream"
        with open(file_path, "rb") as f:
            files = {"file": (Path(file_path).name, f, mime_type)}
            resp = await client.post("https://api.openai.com/v1/audio/transcriptions", headers=headers, data=params, files=files)
            resp.raise_for_status()
            data = resp.json()
            text = data.get("text") or data.get("transcript") or ""
            return text


async def send_telegram_message(chat_id: int, text: str) -> None:
    async with httpx.AsyncClient() as client:
        await client.post(f"{TELEGRAM_API}/sendMessage", json={"chat_id": chat_id, "text": text})


async def send_document(chat_id: int, file_path: str) -> None:
    async with httpx.AsyncClient(timeout=60.0) as client:
        with open(file_path, "rb") as f:
            files = {"document": (Path(file_path).name, f)}
            await client.post(f"{TELEGRAM_API}/sendDocument", data={"chat_id": chat_id}, files=files)


async def send_long_message(chat_id: int, text: str) -> None:
    # Telegram message limit ~4096 chars
    max_len = 4000
    if not text:
        await send_telegram_message(chat_id, "(пустой результат транскрипции)")
        return
    for i in range(0, len(text), max_len):
        chunk = text[i:i+max_len]
        await send_telegram_message(chat_id, chunk)