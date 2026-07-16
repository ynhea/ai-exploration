import json
from datetime import datetime

# 한 줄씩 append해서 누적하기 위해 jsonl 선택
LOG_FILE = "logs.jsonl"

def log_usage(question: str, prompt_tokens: int, completion_tokens: int, cost: float):
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "question": question,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
        "cost_usd": round(cost, 6)
    }
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")