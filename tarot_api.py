# -*- coding: utf-8 -*-
"""
Tarot Narrative Pipeline - Final + JSON Export
---------------------------------------------
- 穩定對話式塔羅敘事
- 正逆位分流
- 每段至少 2 句
- Token 充足不截斷
- 每次自動輸出 JSON 結果檔
"""

import os
import json
import random
import re
import urllib.request
from datetime import datetime
from typing import List, Dict, Any, Optional
from flask import Flask, request, jsonify
from flask_cors import CORS

# ================= 基本設定 =================

API_KEY_FILE = "APIKEY.txt"
JSON_FOLDER = "cards_json"
OUTPUT_FOLDER = "outputs"
HISTORY_FOLDER = "Chat_History"
HISTORY_TAIL_MESSAGES = 30   # 只取最後 30 則訊息（可調

MODEL_NAME = "gemma3:4b"
API_URL = "https://api-gateway.netdb.csie.ncku.edu.tw/api/generate"

TEMP_SKELETON = 0.2
TEMP_DIALOGUE = 0.55
TEMP_ACTIONS = 0.4

TOKENS_SKELETON = 350
TOKENS_DIALOGUE = 320
TOKENS_ACTIONS = 220

os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# ================= 工具 =================
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

def load_api_key() -> Optional[str]:
    if not os.path.exists(API_KEY_FILE):
        return None
    with open(API_KEY_FILE, "r", encoding="utf-8") as f:
        return f.read().strip()


def load_tarot_database() -> List[Dict[str, Any]]:
    db = []
    if not os.path.isdir(JSON_FOLDER):
        return db
    for fn in os.listdir(JSON_FOLDER):
        if fn.endswith(".json"):
            try:
                with open(os.path.join(JSON_FOLDER, fn), "r", encoding="utf-8") as f:
                    data = json.load(f)
                if "name_zh" in data or "name_en" in data:
                    db.append(data)
            except:
                pass
    print(f"✅ 載入 {len(db)} 張塔羅牌")
    return db


# API_KEY = load_api_key()
API_KEY = load_api_key()
if not API_KEY:
    raise RuntimeError("❌ 找不到 APIKEY.txt")
TAROT_DB = load_tarot_database()
TAROT_ID_INDEX = {card["id"]: card for card in TAROT_DB if "id" in card}


def call_llm(prompt: str, temperature: float, num_predict: int) -> str:
    if not API_KEY:
        return ""
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
    except:
        return ""


def parse_dialogue_json(text: str) -> List[str]:
    if not text:
        return []
    match = re.search(r"\[\s*\{.*?\}\s*\]", text, re.DOTALL)
    if not match:
        return []
    try:
        arr = json.loads(match.group(0))
        return [x["message"].strip() for x in arr if "message" in x]
    except:
        return []

def load_history_by_session(session_id: str) -> Dict[str, Any]:
    """
    讀取 Chat_History/{session_id}.json
    你 chat_api 存的是 conversation list:
      [{"role":"user","content":"..."}, ...]
    也可能包含 system / assistant。
    """
    if not session_id:
        return {"found": False, "messages": [], "note": "missing session_id"}

    fp = os.path.join(HISTORY_FOLDER, f"{session_id}.json")
    if not os.path.exists(fp):
        return {"found": False, "messages": [], "note": f"history file not found: {fp}"}

    try:
        with open(fp, "r", encoding="utf-8") as f:
            data = json.load(f)
        # data 可能就是 list，也可能是 dict（你之後若換格式）
        if isinstance(data, list):
            msgs = data
        elif isinstance(data, dict) and "conversation" in data and isinstance(data["conversation"], list):
            msgs = data["conversation"]
        else:
            msgs = []
        return {"found": True, "messages": msgs, "path": fp}
    except Exception as e:
        return {"found": False, "messages": [], "note": f"history read error: {e}"}

def format_history_for_rag(history_messages: List[Dict[str, Any]], tail: int = HISTORY_TAIL_MESSAGES) -> str:
    """
    把 history list 轉成可餵給 LLM 的短文本。
    - 只取最後 tail 則
    - 過長 content 做截斷
    """
    if not history_messages:
        return "（無聊天歷史可用）"

    tail_msgs = history_messages[-tail:] if len(history_messages) > tail else history_messages

    lines = []
    for m in tail_msgs:
        role = str(m.get("role", "unknown"))
        content = str(m.get("content", "")).strip()
        if len(content) > 300:
            content = content[:300] + "…(截斷)"
        lines.append(f"{role}: {content}")
    return "\n".join(lines)

def build_chat_summary(dialogue: list, actions: list) -> str:
    key_points = dialogue[:2]  # 只取前 1~2 句核心解讀
    action_points = actions[:2]

    lines = []
    for s in key_points:
        lines.append(f"- {s}")
    for a in action_points:
        lines.append(f"- 行動提醒：{a}")

    return "本次占卜重點如下：\n" + "\n".join(lines)
# ================= 抽牌 =================

def random_draw_three(db: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    picks = random.sample(db, 3)
    return [
        {
            "name": p.get("name_zh") or p.get("name_en"),
            "orientation": random.choice(["upright", "reversed"]),
            "position": pos
        }
        for p, pos in zip(picks, ["past", "present", "future"])
    ]


# ================= Prompt（沿用你現在穩定版） =================

CORE_PROMPT = """
你是一位成熟、可信任的塔羅占卜師。
塔羅呈現的是狀態與趨勢，不是命定。
禁止恐嚇、保證、貼標籤或教學。
""".strip()

PERSONA_PROMPT = """
語氣自然、清楚、有節奏，像真人對話。
不要使用「嗯…」「感覺…」「好像…」作為開頭。
""".strip()


def prompt_skeleton(question: str, rag_block: str) -> str:
    return f"""{CORE_PROMPT}
以下內容僅作為內部理解，請勿逐字提及。

{rag_block}

請只回傳 JSON，作為內部理解。
""".strip()


def prompt_phase(
    skeleton: str,
    card: Dict[str, Any],
    desc: str
) -> str:
    orientation = "正位" if card["orientation"] == "upright" else "逆位"
    return f"""{CORE_PROMPT}
{PERSONA_PROMPT}

你現在只談「{desc}」，並且必須緊扣使用者問題。

【目前的牌】
{card['position']}：{card['name']}（{orientation}）

【輸出格式】
JSON array：
[
  {{"message":"..."}}
]

【規則】
- 本段必須輸出 2～3 則訊息
- 第一則需自然提到牌名
- 正位只解正位，逆位才對照
- 這是對話，不是教學

【骨架】
{skeleton}
"""


def prompt_actions(skeleton: str) -> str:
    return f"""
{CORE_PROMPT}
{PERSONA_PROMPT}
請根據目前的理解，給出行動提醒。

【輸出格式】
JSON array：
[
  {{"message":"..."}}
]

【規則】
- 共 4 則
- 每則 ≤ 25 個中文字
【骨架】
{skeleton}
""".strip()

def load_selected_cards_meanings(cards: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    meanings = []
    for c in cards:
        name = c.get("name")
        orientation = c.get("orientation")
        meanings.append({
            "name": name,
            "orientation": orientation,
            "note": "牌意請依 cards_json 原始檔解讀"
        })
    return meanings

def build_rag_block(question: str, cards_meanings: List[Dict[str, Any]], history_text: str) -> str:
    return f"""
【使用者問題】
{question}

【聊天歷史摘要】
{history_text}

【三張牌牌意參考】
{json.dumps(cards_meanings, ensure_ascii=False, indent=2)}
""".strip()
# ================= Pipeline =================

def generate_dialogue(question: str, cards: List[Dict[str, Any]], session_id: str) -> Dict[str, Any]:
    # 1) 讀 history
    history_obj = load_history_by_session(session_id)
    history_text = format_history_for_rag(history_obj.get("messages", []))

    # 2) 讀三張牌的牌意 json
    cards_meanings = load_selected_cards_meanings(cards)

    # 3) 組 RAG block
    rag_block = build_rag_block(question, cards_meanings, history_text)

    # 4) skeleton
    skeleton = call_llm(prompt_skeleton(question, rag_block), TEMP_SKELETON, TOKENS_SKELETON)

    # 5) 三段解讀
    dialogue: List[str] = []
    for desc, card in zip(
        ["回顧過去的狀態", "目前卡住的狀態", "接下來可能的走向"],
        cards
    ):
        raw = call_llm(
            prompt_phase(skeleton, card, desc),
            TEMP_DIALOGUE,
            TOKENS_DIALOGUE
        )
        dialogue.extend(parse_dialogue_json(raw))

    # 6) 行動提醒
    actions = parse_dialogue_json(
        call_llm(prompt_actions(skeleton), TEMP_ACTIONS, TOKENS_ACTIONS)
    )

    return {
        "session_id": session_id,
        "question": question,
        "cards": cards,
        "rag": {
            "history_found": history_obj.get("found", False),
            "history_path": history_obj.get("path", None),
            "history_used_tail": HISTORY_TAIL_MESSAGES,
            "cards_meanings_included": True
        },
        "dialogue": dialogue,
        "actions": actions
    }

# ================= 輸出 JSON =================

def save_result_json(result: Dict[str, Any]):
    path = get_time_based_filename(OUTPUT_FOLDER)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"📄 已輸出占卜結果：{path}")
    return path


# ================= Terminal =================

def terminal_simulate(result: Dict[str, Any]):
    print("🔮 本次抽到的三張牌：")
    for c in result["cards"]:
        print(f"{c['position']}：{c['name']}（{'正位' if c['orientation']=='upright' else '逆位'}）")

    input("\n（Enter 開始占卜對話）")

    for i, msg in enumerate(result["dialogue"], 1):
        print(f"\n──────── Dialogue {i} ────────")
        print(f"占卜師：{msg}")
        input("（Enter 繼續）")

    print("\n========== 行動提醒 ==========")
    input("（Enter 繼續）")

    for i, msg in enumerate(result["actions"], 1):
        print(f"\n──────── Action {i} ────────")
        print(f"占卜師：{msg}")
        input("（Enter 繼續）")
        
def translate_frontend_input_to_v3_cards(
    card_ids: List[int],
    orientations: List[int]
) -> List[Dict[str, Any]]:
    """
    將前端輸入的 (card_ids, orientations)
    轉譯成 v3 使用的 cards JSON 結構
    """
    cards = []

    for cid, ori, pos in zip(
        card_ids,
        orientations,
        ["past", "present", "future"]
    ):
        card_data = TAROT_ID_INDEX.get(cid, {})

        card_name = (
            card_data.get("name_zh")
            or card_data.get("name_en")
            or "未知牌"
        )

        cards.append({
            "name": card_name,
            "orientation": "upright" if ori == 1 else "reversed",
            "position": pos
        })

    return cards

# ================= Flask =================

app = Flask(__name__)
CORS(app) # 允許跨網域請求

@app.route('/analyze_tarot', methods=['POST'])
def analyze_tarot():
    try:
        data = request.get_json(silent=True) or {}

        session_id = data.get("session_id")
        if not session_id:
            return jsonify({"error": "missing session_id"}), 400

        question = data.get("question", "")
        card_ids = data.get("card_ids")
        orientations = data.get("orientations")

        # 基本防呆
        if not isinstance(card_ids, list) or not isinstance(orientations, list):
            return jsonify({"error": "invalid card data"}), 400
        if len(card_ids) != 3 or len(orientations) != 3:
            return jsonify({"error": "card data length must be 3"}), 400

        cards = translate_frontend_input_to_v3_cards(card_ids, orientations)
        result = generate_dialogue(question, cards, session_id)

        # 儲存占卜結果（與聊天共用 session_id）
        saved_path = save_result_json(result)

        full_messages = result.get("dialogue", []) + result.get("actions", [])
        summary = build_chat_summary(result.get("dialogue", []), result.get("actions", []))
        return jsonify({
            "session_id": session_id,
            "messages": full_messages,
            "summary": summary,
            "saved_path": saved_path
        })

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    print("🌟 塔羅後端伺服器啟動中：http://localhost:5005")
    app.run(host='0.0.0.0', port=5005, debug=False)

    