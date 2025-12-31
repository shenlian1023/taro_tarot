# 計算理論期末專案_🔮 結合LLM的塔羅占卜

一個結合 **前端互動式塔羅抽牌介面** 與 **後端 AI 敘事引擎** 的塔羅占卜系統。  
使用者可先與占卜師聊天釐清問題，接著抽三張牌，最後由 AI 根據牌面與正逆位生成占卜解讀。

---

## 專案簡介

本專案模擬真實塔羅占卜流程，分為「聊天階段」與「正式占卜階段」：

- 聊天階段：  
  占卜師僅負責傾聽與引導問題，不進行任何抽牌或解牌。
- 占卜階段：  
  使用者提出明確問題後，抽取三張塔羅牌，由 AI 生成對應的敘事式解讀與行動提醒。

整個系統可作為：
- AI 互動式應用展示
- 塔羅占卜 Demo
- 前後端整合與 LLM 應用範例

---

## 專案結構說明

```text
.
├── Chat_room_ui.html        # 前端：聊天主畫面
├── Draw_cards_ui.html       # 前端：抽牌桌畫面
│
├── tarot_chat_api.py        # 後端：聊天模式 API（Flask，port 8001）
├── tarot_api.py             # 後端：正式占卜 API（Flask，port 5005）
│
├── tarot_chat_source.py     # 聊天模式核心邏輯（可獨立執行）
├── tarot_source.py          # 塔羅敘事 pipeline 核心
│
├── APIKEY.txt               # LLM API Key
├── Card_back.png            # 塔羅牌背面圖片
├── outputs/                 # 占卜結果 JSON 輸出資料夾
├── Chat_History/            # 聊天紀錄 JSON
├── cards_json/              # 78張塔羅牌的牌義解說 JSON
├── cards_pic/               # 78張塔羅牌的圖片檔  
└── README.md
