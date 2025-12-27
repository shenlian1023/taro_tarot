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
# prompt設定
# =========================================================

PERSONAL_PROMPT = """
語氣自然、清楚、有節奏，像真人對話。
不要使用「嗯…」「感覺…」「好像…」作為開頭。
""".strip()

CHAT_MODE_PROMPT = """
你是一位塔羅占卜師，但目前處於【聊天模式】。

【嚴格規則（必須遵守）】
- 現在尚未抽牌
- 禁止提及任何牌名、牌陣、張數、牌位
- 禁止說「我會用某某牌陣」「抽三張牌」「這張牌代表」
- 禁止假設已經抽牌
- 只能進行一般聊天、傾聽、安撫與引導
- 若使用者想占卜，只能詢問是否要抽牌，不能直接占卜
""".strip()

TAROT_MODE_PROMPT = """
你是一位成熟、可信任的塔羅占卜師。

塔羅呈現的是狀態與趨勢，不是命定。
禁止恐嚇、保證、貼標籤或教學。

現在已經完成抽牌，可以根據指定的牌與問題進行解釋牌義。
請只解釋牌義，不延伸未抽到的牌。
""".strip()


DRAW_QUESTION_TEXT = "\n要不要抽三張塔羅牌來看看呢？這樣我能更好的回答你的問題。"
QUESTION_ASK_TEXT = "那我們這次要占卜的問題是什麼呢？請用一句話描述。"

# =========================================================
# 狀態定義
# =========================================================
STATE_CHAT = "chat"
STATE_CONFIRM_QUESTION = "confirm_question"
STATE_DRAWING = "drawing"

state = STATE_CHAT
current_question = None
conversation = ""

# =========================================================
# 主程式
# =========================================================

if __name__ == "__main__": 
    print("對話開始")

    while True:
        user_input = input("\n使用者： ").strip()
        if user_input.lower() in ["exit", "quit"]:
            break
        # ================= 狀態 1：一般聊天 ================= 
        if state == STATE_CHAT: 
            if user_input in ["是", "好", "要", "我要抽牌"]:
                print("\n🔮 占卜師：")
                print(QUESTION_ASK_TEXT)
                state = STATE_CONFIRM_QUESTION
                continue
            # 不抽牌進一般聊天
            conversation += f"\n使用者：{user_input}\n"
            chat_prompt = (
                CHAT_MODE_PROMPT + "\n\n"
                + PERSONAL_PROMPT + "\n\n"
                + conversation
            )
            reply = call_llm(chat_prompt, TEMPERATURE, MAX_TOKENS).strip()
            reply += DRAW_QUESTION_TEXT
            print("\n🤖 占卜師：")
            print(reply)
            conversation += reply + "\n"
        # ================= 狀態 2：確認占卜問題 =================
        elif state == STATE_CONFIRM_QUESTION:
            current_question = user_input.strip()
            print("\n🤖 占卜師：")
            print("好，請點選右方抽牌鍵開始抽牌!")
            state = STATE_DRAWING 
        # ================= 狀態 3：抽牌並解牌 =================
        elif state == STATE_DRAWING:
            # 目前先假抽牌，之後可接 JSON
            drawn_card = "戀人（正位）"

            tarot_prompt = f"""
{TAROT_MODE_PROMPT}

【占卜問題】
{current_question}

【抽到的牌】
{drawn_card}

請針對上面的問題進行解釋牌義。
""".strip()

            reply = call_llm(tarot_prompt, TEMPERATURE, MAX_TOKENS).strip()

            print("\n🔮 占卜師：")
            print(reply)

            conversation += f"\n【占卜問題】：{current_question}\n"
            conversation += f"【抽到的牌】：{drawn_card}\n"
            conversation += reply + "\n"

            current_question = None
            state = STATE_CHAT