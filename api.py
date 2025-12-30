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

MODEL_NAME = "gemma3:4b"
API_URL = "https://api-gateway.netdb.csie.ncku.edu.tw/api/generate"

TEMP_SKELETON = 0.2
TEMP_DIALOGUE = 0.55
TEMP_ACTIONS = 0.4

TOKENS_SKELETON = 350
TOKENS_DIALOGUE = 320   # 🔧 加大
TOKENS_ACTIONS = 220    # 🔧 加大

os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# ================= 工具 =================

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
API_KEY = "f84f4e9735f7b6cc351a61d41224a7a220947aebdfa37e62581fba3e4fc1fbfa"
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


def prompt_skeleton(question: str) -> str:
    return f"""
{CORE_PROMPT}
請只回傳 JSON，作為內部理解。

【問題】
{question}
""".strip()


def prompt_phase(skeleton: str, card: Dict[str, str], desc: str) -> str:
    orientation = "正位" if card["orientation"] == "upright" else "逆位"
    return f"""
{CORE_PROMPT}
{PERSONA_PROMPT}

你現在只談「{desc}」。

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
""".strip()


def prompt_actions(skeleton: str) -> str:
    return f"""
{CORE_PROMPT}
{PERSONA_PROMPT}

請給出行動提醒。

【輸出格式】
JSON array：
[
  {{"message":"..."}}
]

【規則】
- 共 4 則
- 每則 ≤ 25 個中文字
""".strip()


# ================= Pipeline =================

def generate_dialogue(question: str, cards: List[Dict[str, str]]) -> Dict[str, Any]:
    skeleton = call_llm(prompt_skeleton(question), TEMP_SKELETON, TOKENS_SKELETON)

    dialogue = []
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

    actions = parse_dialogue_json(
        call_llm(prompt_actions(skeleton), TEMP_ACTIONS, TOKENS_ACTIONS)
    )

    return {
        "question": question,
        "cards": cards,
        "dialogue": dialogue,
        "actions": actions
    }


# ================= 輸出 JSON =================

def save_result_json(result: Dict[str, Any]):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(OUTPUT_FOLDER, f"tarot_api_output.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"📄 已輸出結果檔：{path}")


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


# ================= Main =================

# if __name__ == "__main__":
#     question = "目前這段感情狀態，對我未來半年的影響是什麼？"

#     # 🔹 前端輸入
#     card_ids = [35, 33, 1]
#     orientations = [1, 0, 1]

#     # 🔹 轉譯成 v3 cards 結構
#     cards = translate_frontend_input_to_v3_cards(card_ids, orientations)

#     result = generate_dialogue(question, cards)

#     # save_result_json(result)
#     # terminal_simulate(result)




# ================= Flask =================

app = Flask(__name__)
CORS(app) # 允許跨網域請求

@app.route('/analyze_tarot', methods=['POST'])
def analyze_tarot():
    try:
        data = request.json
        question = data.get('question')
        card_ids = data.get('card_ids')
        orientations = data.get('orientations')

        # 這裡假設你的這些自定義函式運作正常
        cards = translate_frontend_input_to_v3_cards(card_ids, orientations)
        result = generate_dialogue(question, cards)
        
        # 確保 result["dialogue"] 和 result["actions"] 都是 list
        full_messages = result.get("dialogue", []) + result.get("actions", [])
        
        return jsonify({"messages": full_messages})
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    print("🌟 塔羅後端伺服器啟動中：http://localhost:5005")
    app.run(host='0.0.0.0', port=5005, debug=True)