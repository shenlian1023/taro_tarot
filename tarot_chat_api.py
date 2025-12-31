import os
import json
import uuid
from typing import Optional
from flask import Flask, request, jsonify
from flask_cors import CORS
import urllib.request
import urllib.error

# ================= 設定區 =================
API_KEY_FILE = "APIKEY.txt"
JSON_FOLDER = "Chat_History"
MODEL_NAME = "gemma3:4b"
API_URL = "https://api-gateway.netdb.csie.ncku.edu.tw/api/generate"

MAX_TOKENS = 1024
TEMPERATURE = 0.5

# =========================================================
# 基礎工具
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
# Prompt（聊天模式）
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
# JSON 儲存（依 session 存）
# =========================================================

def save_conversation(session_id: str, conversation: list):
    filename = f"{session_id}.json"
    path = os.path.join(JSON_FOLDER, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(conversation, f, ensure_ascii=False, indent=2)
    return path

# =========================================================
# Flask 啟動
# =========================================================

app = Flask(__name__)
CORS(app)

# 所有使用者的 session 狀態
sessions = {}

def get_session(session_id: Optional[str]):
    if not session_id or session_id not in sessions:
        session_id = uuid.uuid4().hex
        sessions[session_id] = {
            "state": "chat",
            "conversation": []
        }
    return session_id, sessions[session_id]

@app.route("/normal_chat", methods=["POST"])
def normal_chat():
    data = request.get_json(silent=True) or {}
    user_input = data.get("user_input", "").strip()
    session_id = data.get("session_id")

    session_id, session = get_session(session_id)
    conversation = session["conversation"]
    awaiting_question = (session["state"] == "awaiting_question")

    result = {
        "reply": "",
        "session_id": session_id,
        "awaiting_question": awaiting_question,
        "saved_path": None
    }

    # === 使用者按下「開始提問」===
    if user_input == "__START_QUESTION__":
        session["state"] = "awaiting_question"
        conversation.append({
            "role": "system",
            "content": "使用者進入占卜提問階段"
        })

        saved_path = save_conversation(session_id, conversation)
        result["awaiting_question"] = True
        return jsonify(result)

    # === 輸入占卜問題 ===
    if awaiting_question:
        conversation.append({"role": "user", "content": user_input})
        saved_path = save_conversation(session_id, conversation)

        session["state"] = "chat"

        result["reply"] = f"問題已收到（已儲存），正在為您準備占卜..."
        result["awaiting_question"] = False
        result["saved_path"] = saved_path
        return jsonify(result)

    # === 一般聊天 ===
    conversation.append({"role": "user", "content": user_input})

    prompt = CHAT_MODE_PROMPT + "\n\n"
    for msg in conversation:
        prompt += f"{msg['role']}：{msg['content']}\n"

    reply = call_llm(prompt).strip()
    conversation.append({"role": "assistant", "content": reply})

    result["reply"] = reply
    return jsonify(result)

# =========================================================
# 主啟動點
# =========================================================

if __name__ == "__main__":
    print("🌟 聊天引導後端（Session-safe，Port 8001）啟動中...")
    app.run(host="0.0.0.0", port=8001, debug=False)
