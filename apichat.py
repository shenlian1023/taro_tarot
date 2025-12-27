import os
import json
import uuid
import random
import re
from typing import Any, Dict, List, Optional, Tuple
import urllib.request
import urllib.error
# ================= 設定區 =================
API_KEY_FILE = "APIKEY.txt"
JSON_FOLDER = "Card_Json"
MODEL_NAME = "gemma3:4b"
API_URL = "https://api-gateway.netdb.csie.ncku.edu.tw/api/generate"

MAX_TOKENS = 1024
TEMPERATURE = 0.5
# =========================================


# =========================================================
# 0) 基礎工具
# =========================================================

def load_api_key() -> Optional[str]:
    if not os.path.exists(API_KEY_FILE):
        return None
    with open(API_KEY_FILE, "r", encoding="utf-8") as f:
        return f.read().strip() or None


API_KEY = load_api_key()
if not API_KEY:
    raise RuntimeError("❌ 找不到 APIKEY.txt")
# =========================================================
# LLM 呼叫
# =========================================================

def call_llm(prompt: str, temperature: float, num_predict: int) -> str:
    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False,
        "temperature": temperature,
        "options": {"num_predict": num_predict}
    }

    req = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_KEY}"
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode()).get("response", "")
    except Exception as e:
        return f"\n[ERROR] {e}"


# =========================================================
# 主程式
# =========================================================

if __name__ == "__main__":
    print("對話開始")

    conversation = ""

    while True:
        user_input = input("\n使用者： ")
        if user_input.lower() in ["exit", "quit"]:
            break
        conversation += f"\n使用者：{user_input}\n"

        print("\n🤖 模型：", end="")
        reply = call_llm(conversation, TEMPERATURE, MAX_TOKENS)
        print(reply)

        conversation += reply + "\n"