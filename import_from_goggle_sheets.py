#!/usr/bin/env python3
import os
import logging
from typing import Optional

import gspread
from google.oauth2.service_account import Credentials

from db import SessionLocal, init_db
from models import Discipline, Question, Submission

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("gs-importer")

def get_gspread_client():
    sa_file = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE")
    if not sa_file:
        raise RuntimeError("GOOGLE_SERVICE_ACCOUNT_FILE env var not set")
    scopes = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
    creds = Credentials.from_service_account_file(sa_file, scopes=scopes)
    return gspread.Client(auth=creds)

def import_voprosi(ws):
    records = ws.get_all_records()
    logger.info("Voprosi rows: %d", len(records))
    session = SessionLocal()
    created_q = 0
    try:
        for row in records:
            row_lower = {k.lower(): v for k, v in row.items()}
            key = None; prompt = None; ideal = None; discipline_title = None
            for kname in row.keys():
                lk = kname.lower()
                val = row[kname]
                if any(s in lk for s in ("ключ", "key", "id")) and val:
                    key = str(val).strip()
                if any(s in lk for s in ("вопрос", "question", "prompt")) and val:
                    prompt = str(val).strip()
                if any(s in lk for s in ("идеаль", "идеальный", "ответ", "answer", "ideal")) and val:
                    ideal = str(val).strip()
                if any(s in lk for s in ("дисцип", "course", "subject")) and val:
                    discipline_title = str(val).strip()
            if not discipline_title:
                discipline_title = os.getenv("DEFAULT_DISCIPLINE_TITLE", "Imported")
            d = session.query(Discipline).filter(Discipline.title == discipline_title).first()
            if not d:
                d = Discipline(code=discipline_title.lower().replace(" ", "_")[:50], title=discipline_title, description="Imported from Voprosi sheet")
                session.add(d); session.commit(); session.refresh(d)
            q = None
            if key:
                q = session.query(Question).filter(Question.discipline_id == d.id, Question.code == key).first()
            if not q and prompt:
                q = session.query(Question).filter(Question.discipline_id == d.id, Question.prompt_text == prompt).first()
            if q:
                q.ideal_text = ideal or q.ideal_text
                q.prompt_text = prompt or q.prompt_text
            else:
                q = Question(discipline_id=d.id, code=key, prompt_text=prompt or "", ideal_text=ideal or "")
                session.add(q)
            session.commit()
            created_q += 1
    finally:
        session.close()
    logger.info("Imported/updated %d questions", created_q)

def import_otveti(ws):
    records = ws.get_all_records()
    logger.info("Otveti rows: %d", len(records))
    session = SessionLocal()
    created = 0
    try:
        for row in records:
            lookup = {k.strip(): v for k, v in row.items()}
            discipline_title = lookup.get("Название дисциплины") or lookup.get("название дисциплины") or lookup.get("discipline")
            fio = lookup.get("ФИО студента")
            ticket = lookup.get("Номер билета")
            otvet = lookup.get("Ответ на билет")
            ocen = lookup.get("Оценка")
            student_id = lookup.get("ID студента")
            if not discipline_title:
                discipline_title = os.getenv("DEFAULT_DISCIPLINE_TITLE", "Imported")
            d = session.query(Discipline).filter(Discipline.title == discipline_title).first()
            if not d:
                d = Discipline(code=discipline_title.lower().replace(" ", "_")[:50], title=discipline_title, description="Imported from Otveti")
                session.add(d); session.commit(); session.refresh(d)
            q = None
            if ticket:
                q = session.query(Question).filter(Question.discipline_id == d.id, Question.code == str(ticket)).first()
            s = Submission(
                user_id=str(student_id) if student_id is not None else None,
                chat_id=None,
                question_id=q.id if q else None,
                audio_path=None,
                transcript_raw=otvet if otvet else None,
                transcript_norm=None,
                translated_text=None,
                score=float(ocen) if ocen and str(ocen).strip() != "" else None,
                details={"import_source": "Otveti_sheet"}
            )
            session.add(s); session.commit()
            created += 1
    finally:
        session.close()
    logger.info("Imported %d submissions", created)

def main():
    init_db()
    client = get_gspread_client()
    voprosi_id = os.getenv("VOPROSI_SHEET_ID")
    otveti_id = os.getenv("OTVETI_SHEET_ID")
    if not voprosi_id and not otveti_id:
        raise RuntimeError("Set VOPROSI_SHEET_ID and/or OTVETI_SHEET_ID env vars")
    if voprosi_id:
        sh = client.open_by_key(voprosi_id); ws = sh.sheet1
        import_voprosi(ws)
    if otveti_id:
        sh2 = client.open_by_key(otveti_id); ws2 = sh2.sheet1
        import_otveti(ws2)

if __name__ == "__main__":
    main()