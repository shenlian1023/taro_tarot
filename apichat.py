import os
import json
import uuid
from typing import Optional
import urllib.request
import urllib.error

# ================= 設定區 =================
API_KEY_FILE = "APIKEY.txt"
JSON_FOLDER = "Chat_History"
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

os.makedirs(JSON_FOLDER, exist_ok=True)

# =========================================================
# LLM 呼叫
# =========================================================

def call_llm(prompt: str) -> str:
    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False,
        "temperature": TEMPERATURE,
        "options": {"num_predict": MAX_TOKENS}
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
        return f"[ERROR] {e}"

# =========================================================
# Prompt 設定（嚴格聊天模式）
# =========================================================

CHAT_MODE_PROMPT = """
你是一位塔羅占卜師，但目前【只進行聊天模式】。

【嚴格禁止事項】
- 不得抽牌
- 不得提及任何牌名、牌陣、牌義、張數、位置
- 不得假設已經占卜
- 不得直接給出占卜結果

【你可以做的事】
- 傾聽使用者的困擾
- 幫助釐清問題
- 引導使用者把問題說清楚
- 安撫情緒、陪伴對話

語氣自然、真誠、像真人對談。
""".strip()

# =========================================================
# JSON 儲存
# =========================================================

def save_conversation(conversation: list):
    filename = f"{uuid.uuid4().hex}.json"
    path = os.path.join(JSON_FOLDER, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(conversation, f, ensure_ascii=False, indent=2)
    return path

# =========================================================
# 主程式（只聊天，存檔只在「提問」）
# =========================================================

if __name__ == "__main__":
    print("你好，有什麼煩惱呢？")

    conversation = []   # list of {role, content}
    awaiting_question = False  # 是否正在等「塔羅問題」

    while True:
        user_input = input("\n使用者： ").strip()

        if user_input.lower() in ["exit", "quit"]:
            break

        # === 使用者按下「開始提問」按鈕 ===
        if user_input == "__START_QUESTION__":
            system_msg = "請輸入您要問塔羅的問題"
            print("\n🔮 占卜師：")
            print(system_msg)

            conversation.append({
                "role": "system",
                "content": system_msg
            })

            awaiting_question = True
            continue

        # === 正在等待使用者輸入「占卜問題」===
        if awaiting_question:
            conversation.append({
                "role": "user",
                "content": user_input
            })

            saved_path = save_conversation(conversation)
            print(f"\n📁 對話已儲存：{saved_path}")

            # 重置狀態（或你也可以選擇 break）
            awaiting_question = False
            continue

        # === 一般聊天（不存檔）===
        conversation.append({
            "role": "user",
            "content": user_input
        })

        prompt = CHAT_MODE_PROMPT + "\n\n"
        for msg in conversation:
            prompt += f"{msg['role']}：{msg['content']}\n"

        reply = call_llm(prompt).strip()

        print("\n🔮 占卜師：")
        print(reply)

        conversation.append({
            "role": "assistant",
            "content": reply
        })