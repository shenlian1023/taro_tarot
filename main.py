from flask import Flask, send_from_directory
from flask_cors import CORS
import threading
from tarot_api import app as tarot_app
from tarot_chat_api import app as chat_app
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__, static_folder=BASE_DIR)
CORS(app)

# ===== 前端 =====
@app.route("/")
def index():
    return send_from_directory(BASE_DIR, "Chat_room_ui.html")

@app.route("/<path:path>")
def static_files(path):
    return send_from_directory(BASE_DIR, path)

# ===== 啟動兩個後端 =====
def run_chat():
    chat_app.run(port=8001, debug=False, use_reloader=False)

def run_tarot():
    tarot_app.run(port=5005, debug=False, use_reloader=False)

if __name__ == "__main__":
    threading.Thread(target=run_chat).start()
    threading.Thread(target=run_tarot).start()
    print("🌟 前端 + 後端整合啟動：http://localhost:8080")
    app.run(port=8080, debug=False)
