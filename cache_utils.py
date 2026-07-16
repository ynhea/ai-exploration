import json
import os

CACHE_FILE = "cache.json"

def load_cache():
    if not os.path.exists(CACHE_FILE):
        return {}
    with open(CACHE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_cache(cache: dict):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

def get_cache_key(question: str, top_k: int) -> str:
    # TODO: question과 top_k를 조합해서 하나의 문자열 key로 만들기
    key = f"질문: {question}, top_k: {top_k}"
    return key