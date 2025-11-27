import os
import re
import numpy as np
from typing import List, Dict
import httpx

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

def normalize_text(s: str) -> str:
    s = (s or "").lower().strip()
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"[«»\"'()—–\-]", "", s)
    return s

def keyword_score(normalized_text: str, keywords: List[str]) -> float:
    if not keywords:
        return 0.0
    found = 0
    for kw in keywords:
        if kw.lower() in normalized_text:
            found += 1
    return found / len(keywords)

def get_embedding_openai(text: str) -> List[float]:
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY not set")
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
    payload = {"model": "text-embedding-3-small", "input": text}
    with httpx.Client(timeout=30.0) as client:
        r = client.post("https://api.openai.com/v1/embeddings", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
        return data["data"][0]["embedding"]

def cosine(u, v):
    u = np.array(u); v = np.array(v)
    denom = (np.linalg.norm(u) * np.linalg.norm(v))
    return float(np.dot(u, v) / denom) if denom != 0 else 0.0

def compute_final_score(student_text: str, ideal_text: str, keywords: List[str] = None, weights: Dict = None) -> Dict:
    weights = weights or {"sem": 0.6, "key": 0.3, "ngram": 0.1}
    s_norm = normalize_text(student_text)
    i_norm = normalize_text(ideal_text)
    emb_s = get_embedding_openai(s_norm)
    emb_i = get_embedding_openai(i_norm)
    sem_sim = (cosine(emb_s, emb_i) + 1) / 2.0  # scale to [0,1]
    key_sc = keyword_score(s_norm, keywords or [])
    ngram_sc = 0.0
    final = weights["sem"] * sem_sim + weights["key"] * key_sc + weights["ngram"] * ngram_sc
    return {"final_score": final, "sem_sim": sem_sim, "key_score": key_sc, "ngram_score": ngram_sc}