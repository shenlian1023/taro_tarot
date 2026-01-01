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

CHAT_REFLECT_TAROT_FIRST_PROMPT = """
你是一位塔羅占卜師，正在進行「占卜後的第一次回應」。

【背景】
- 剛剛已完成一次塔羅占卜分析
- 系統中已提供占卜摘要，供你理解整體脈絡
- 使用者正在詢問這次占卜的意義、價值或整體感受

【你的任務】
- 承接剛剛的占卜內容
- 將占卜結果「轉譯」成對使用者有意義的理解
- 協助使用者看見這次占卜對他當下狀態的提醒

【說話方式】
- 可以簡要回顧占卜中提到的關鍵狀態或主題
- 不需要逐條解釋牌或重述細節
- 語氣溫和、真誠，像是在幫對方「整理剛聽到的話」

【重要限制】
- 不要重新抽牌
- 不要新增任何牌名、牌義、正逆位
- 這是「總結與轉化」，不是再次分析

請在這一則回覆中完成「占卜 → 理解」的轉換。
""".strip()

CHAT_REFLECT_TAROT_FOLLOWUP_PROMPT = """
你是一位正在延續「占卜後對話」的陪伴者。

【背景】
- 占卜內容已經說明並討論過
- 使用者現在是在延伸想法、詢問建議，或表達感受

【你的任務】
- 不需要再解釋或回顧占卜內容
- 專注回應使用者「當下這一句話」的需求
- 將重點放在行動、選擇、關係互動或內在感受上

【說話方式】
- 像一個理解對方處境的人在對話
- 可以給建議、提問、或陪伴情緒
- 回答要自然往前推進，不要倒回解牌
- 以聊天的方式進行互動，不要變成講座，也不要變成占卜分析
- 話語盡量輕鬆，避免過於正式或嚴肅，讓對話更有溫度

【嚴格禁止】
- 重複說明占卜結果
- 再次整理或總結那次占卜
- 使用「這次占卜告訴你……」作為開頭

請假設「占卜已經是過去式」，現在是在消化與前進。
""".strip()
# =========================================================
# JSON 儲存（依 session 存）
# =========================================================
from datetime import datetime

def get_time_based_filename(base_dir: str, ext: str = ".json") -> str:
    """
    產生檔名格式：
    YYYY-MM-DD_HH-MM-SS.json
    例如：2026-01-01_18-42-07.json
    """
    now = datetime.now()

    timestamp = now.strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"{timestamp}{ext}"

    os.makedirs(base_dir, exist_ok=True)
    return os.path.join(base_dir, filename)

def save_conversation(conversation: list):
    path = get_time_based_filename(JSON_FOLDER)

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
            "conversation": [],
            "tarot_first_reply_done": False
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
        session["tarot_first_reply_done"] = False  # ⭐ 重設
        conversation.append({
            "role": "system",
            "content": "使用者進入占卜提問階段"
        })

        saved_path = save_conversation(conversation)
        result["awaiting_question"] = True
        return jsonify(result)
    # === 注入占卜摘要至聊天上下文 ===
    if user_input.startswith("__INJECT_TAROT_CONTEXT__:"):
        summary = user_input.replace("__INJECT_TAROT_CONTEXT__:", "").strip()
        conversation.append({
            "role": "system",
            "content": "【系統狀態】以下對話已進入『占卜後回顧聊天模式』，請承認先前占卜已發生。"
        })
        conversation.append({
            "role": "system",
            "content": f"【占卜摘要】\n{summary}"
        })
        session["state"] = "chat_reflect_tarot"
        return jsonify({
            "reply": "",
            "session_id": session_id,
            "awaiting_question": False
        })
    # === 輸入占卜問題 ===
    if awaiting_question:
        conversation.append({"role": "user", "content": user_input})
        saved_path = save_conversation(conversation)
        session["state"] = "chat"
        result["awaiting_question"] = False
        result["saved_path"] = saved_path
        return jsonify(result)

    # === 一般 / 占卜後聊天 ===
    conversation.append({"role": "user", "content": user_input})

    if session["state"] == "chat_reflect_tarot":
        if not session.get("tarot_first_reply_done", False):
            base_prompt = CHAT_REFLECT_TAROT_FIRST_PROMPT
            session["tarot_first_reply_done"] = True
        else:
            base_prompt = CHAT_REFLECT_TAROT_FOLLOWUP_PROMPT
    else:
        base_prompt = CHAT_MODE_PROMPT

    prompt = base_prompt + "\n\n"
    for msg in conversation:
        prompt += f"{msg['role']}：{msg['content']}\n"

    reply = call_llm(prompt).strip()
    conversation.append({"role": "assistant", "content": reply})

    result["reply"] = reply
    return jsonify(result)

def end_divination():
    data = request.get_json(silent=True) or {}
    session_id = data.get("session_id")

    if not session_id or session_id not in sessions:
        return jsonify({"error": "invalid session"}), 400

    sessions[session_id]["state"] = "chat"

    return jsonify({
        "ok": True,
        "message": "已回到一般聊天模式"
    })

# =========================================================
# 主啟動點
# =========================================================

if __name__ == "__main__":
    print("🌟 聊天引導後端（Session-safe，Port 8001）啟動中...")
    app.run(host="0.0.0.0", port=8001, debug=False)
