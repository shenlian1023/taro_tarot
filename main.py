# main.py
# ===============================
# 啟動整個塔羅占卜系統（聊天 + 占卜）
# ===============================

import multiprocessing
import sys


def run_chat_server():
    """啟動聊天模式後端（Port 8001）"""
    import tarot_chat_api
    tarot_chat_api.app.run(
        host="0.0.0.0",
        port=8001,
        debug=False,
        use_reloader=False
    )


def run_tarot_server():
    """啟動正式占卜後端（Port 5005）"""
    import tarot_api
    tarot_api.app.run(
        host="0.0.0.0",
        port=5005,
        debug=False,
        use_reloader=False
    )


if __name__ == "__main__":
    print("啟動塔羅占卜系統中...")
    print("聊天模式後端：http://localhost:8001")
    print("占卜分析後端：http://localhost:5005")
    print("（Ctrl+C 可同時關閉所有服務）\n")

    try:
        chat_process = multiprocessing.Process(target=run_chat_server)
        tarot_process = multiprocessing.Process(target=run_tarot_server)

        chat_process.start()
        tarot_process.start()

        chat_process.join()
        tarot_process.join()

    except KeyboardInterrupt:
        print("\n收到中斷指令，關閉所有服務...")
        sys.exit(0)
