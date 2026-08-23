#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
✦ PREMIUM BIN VAULT ✦
Bot: @Rhonreferbot
Channel: @PythonPrivateTools
Referral: Share @Rhonreferbot
Proof: DM @Masitassss
"""

import os
import json
import sqlite3
import random
import string
import time
from datetime import datetime
import requests

# ─── CONFIG ──────────────────────────────────────────────────────────────
BOT_TOKEN = "8542412067:AAHVQnk_uS2NG9AAlVkucPJuuu-s8ykEzZM"
BOT_USERNAME = "Rhonreferbot"
CHANNEL_LINK = "https://t.me/PythonPrivateTools"
CHANNEL_USERNAME = "PythonPrivateTools"
ADMIN_PASSWORD = "RHONLESTTERLOPEZ"
VERIFIER = "Masitassss"

# ─── DATABASE ──────────────────────────────────────────────────────────

class Database:
    def __init__(self, db_path="referral.db"):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self._init_db()

    def _init_db(self):
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                points INTEGER DEFAULT 0,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS bin_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                category TEXT,
                content TEXT,
                cost INTEGER DEFAULT 5,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        self.conn.commit()

    def add_user(self, user_id, username, first_name):
        self.cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        if self.cursor.fetchone():
            return self.get_user(user_id)
        self.cursor.execute(
            "INSERT INTO users (user_id, username, first_name) VALUES (?, ?, ?)",
            (user_id, username or "", first_name or "")
        )
        self.conn.commit()
        return self.get_user(user_id)

    def get_user(self, user_id):
        self.cursor.execute(
            "SELECT user_id, username, first_name, points FROM users WHERE user_id = ?",
            (user_id,)
        )
        row = self.cursor.fetchone()
        if row:
            return {"user_id": row[0], "username": row[1], "first_name": row[2], "points": row[3]}
        return None

    def add_points(self, user_id, amount):
        self.cursor.execute("UPDATE users SET points = points + ? WHERE user_id = ?", (amount, user_id))
        self.conn.commit()

    def add_item(self, name, category, content, cost=5):
        self.cursor.execute(
            "INSERT INTO bin_items (name, category, content, cost) VALUES (?, ?, ?, ?)",
            (name, category, content, cost)
        )
        self.conn.commit()
        return self.cursor.lastrowid

    def get_items(self):
        self.cursor.execute("SELECT id, name, category, cost FROM bin_items ORDER BY id DESC")
        return self.cursor.fetchall()

    def get_item(self, item_id):
        self.cursor.execute("SELECT id, name, category, content, cost FROM bin_items WHERE id = ?", (item_id,))
        return self.cursor.fetchone()

    def delete_item(self, item_id):
        self.cursor.execute("DELETE FROM bin_items WHERE id = ?", (item_id,))
        self.conn.commit()

    def delete_all_items(self):
        self.cursor.execute("DELETE FROM bin_items")
        self.conn.commit()

    def get_stats(self):
        self.cursor.execute("SELECT COUNT(*) FROM users")
        total_users = self.cursor.fetchone()[0]
        self.cursor.execute("SELECT COUNT(*) FROM bin_items")
        total_items = self.cursor.fetchone()[0]
        return total_users, total_items

    def close(self):
        self.conn.close()

db = Database()

# ─── TELEGRAM API ──────────────────────────────────────────────────────

def send_message(chat_id, text, reply_markup=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    if reply_markup:
        data["reply_markup"] = json.dumps(reply_markup)
    try:
        requests.post(url, data=data, timeout=30)
    except Exception as e:
        print(f"Error: {e}")

def edit_message(chat_id, message_id, text, reply_markup=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/editMessageText"
    data = {"chat_id": chat_id, "message_id": message_id, "text": text, "parse_mode": "Markdown"}
    if reply_markup:
        data["reply_markup"] = json.dumps(reply_markup)
    try:
        requests.post(url, data=data, timeout=30)
    except Exception:
        pass

def answer_callback(callback_id, text=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/answerCallbackQuery"
    data = {"callback_query_id": callback_id}
    if text:
        data["text"] = text
    try:
        requests.post(url, data=data, timeout=15)
    except Exception:
        pass

def get_updates(offset=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
    data = {"timeout": 10, "allowed_updates": ["message", "callback_query"]}
    if offset:
        data["offset"] = offset
    try:
        r = requests.post(url, data=data, timeout=15)
        return r.json().get("result", [])
    except Exception:
        return []

# ─── CHECK CHANNEL MEMBERSHIP ─────────────────────────────────────────

def is_member(user_id):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getChatMember"
    data = {"chat_id": f"@{CHANNEL_USERNAME}", "user_id": user_id}
    try:
        r = requests.post(url, data=data, timeout=10)
        if r.status_code == 200:
            result = r.json()
            if result.get("ok"):
                status = result.get("result", {}).get("status", "")
                return status in ["member", "administrator", "creator"]
    except Exception:
        pass
    return False

# ─── HANDLERS ──────────────────────────────────────────────────────────

admin_sessions = {}

def handle_start(chat_id, user_id, username, first_name, args):
    # ─── ⭐ CHANNEL VERIFICATION ⭐ ──────────────────────────────────
    if not is_member(user_id):
        keyboard = {
            "inline_keyboard": [
                [{"text": "📢 Join Channel", "url": CHANNEL_LINK}],
                [{"text": "✅ I've Joined!", "callback_data": "check_join"}],
            ]
        }
        send_message(
            chat_id,
            f"🔐 *Join Our Channel First*\n\n"
            f"Click below to join @{CHANNEL_USERNAME}, then press 'I've Joined!'",
            reply_markup=keyboard
        )
        return

    user_data = db.add_user(user_id, username, first_name)

    keyboard = {
        "inline_keyboard": [
            [{"text": "📦 Redeem BINs", "callback_data": "redeem"}],
            [{"text": "📊 My Stats", "callback_data": "stats"}],
            [{"text": "👑 Owner Panel", "callback_data": "owner_login"}],
        ]
    }
    send_message(
        chat_id,
        f"🏦 *Premium BIN Vault*\n\n"
        f"💰 GET BINs:\n"
        f"1️⃣ Invite 5 people to @{BOT_USERNAME}\n"
        f"2️⃣ Screenshot proof\n"
        f"3️⃣ DM @{VERIFIER}\n"
        f"4️⃣ Get BIN!\n\n"
        f"📊 Points: {user_data['points']}\n"
        f"💡 5 points = 1 BIN",
        reply_markup=keyboard
    )

def handle_menu(chat_id, user_id):
    if not is_member(user_id):
        keyboard = {
            "inline_keyboard": [
                [{"text": "📢 Join Channel", "url": CHANNEL_LINK}],
                [{"text": "✅ I've Joined!", "callback_data": "check_join"}],
            ]
        }
        send_message(
            chat_id,
            f"🔐 *Join Our Channel First*",
            reply_markup=keyboard
        )
        return

    user_data = db.get_user(user_id)
    if not user_data:
        send_message(chat_id, "❌ Use /start first.")
        return

    keyboard = {
        "inline_keyboard": [
            [{"text": "📦 Redeem BINs", "callback_data": "redeem"}],
            [{"text": "📊 My Stats", "callback_data": "stats"}],
            [{"text": "👑 Owner Panel", "callback_data": "owner_login"}],
        ]
    }
    send_message(
        chat_id,
        f"📋 *Menu*\n\n"
        f"👤 {user_data.get('first_name', 'User')}\n"
        f"📊 Points: {user_data['points']}\n"
        f"💡 5 points = 1 BIN",
        reply_markup=keyboard
    )

def show_owner_panel(chat_id):
    keyboard = {
        "inline_keyboard": [
            [{"text": "📦 Add BIN", "callback_data": "admin_add"}],
            [{"text": "📋 List BINs", "callback_data": "admin_list"}],
            [{"text": "🗑️ Delete BIN", "callback_data": "admin_delete"}],
            [{"text": "🗑️ Delete ALL", "callback_data": "admin_delete_all"}],
            [{"text": "⭐ Add Points", "callback_data": "admin_addpoints"}],
            [{"text": "📊 Bot Stats", "callback_data": "admin_stats"}],
            [{"text": "🔙 Back", "callback_data": "menu_back"}],
        ]
    }
    send_message(chat_id, f"👑 *Owner Panel*", reply_markup=keyboard)

def handle_callback(query):
    callback_id = query["id"]
    chat_id = query["message"]["chat"]["id"]
    message_id = query["message"]["message_id"]
    data = query["data"]
    user_id = query["from"]["id"]

    # ─── ⭐ CHECK JOIN ⭐ ────────────────────────────────────────────
    if data == "check_join":
        if is_member(user_id):
            answer_callback(callback_id, "✅ Joined!")
            edit_message(
                chat_id,
                message_id,
                "✅ *You've joined!*\n\nNow use /start to access the bot."
            )
        else:
            answer_callback(callback_id, "❌ Not joined yet.")
            edit_message(
                chat_id,
                message_id,
                f"⚠️ *You still need to join the channel.*\n\n"
                f"Click below to join @{CHANNEL_USERNAME}",
                reply_markup={
                    "inline_keyboard": [
                        [{"text": "📢 Join Channel", "url": CHANNEL_LINK}],
                        [{"text": "✅ I've Joined!", "callback_data": "check_join"}],
                    ]
                }
            )
        return

    user_data = db.get_user(user_id)
    if not user_data:
        answer_callback(callback_id, "Use /start first.")
        return

    answer_callback(callback_id)

    if data == "owner_login":
        send_message(chat_id, f"👑 Enter password:")
        return

    admin_actions = ["admin_add", "admin_list", "admin_delete", "admin_delete_all", "admin_addpoints", "admin_stats"]
    if data in admin_actions and user_id not in admin_sessions:
        send_message(chat_id, "❌ Login first. Click 'Owner Panel' and enter password.")
        return

    if data == "admin_add":
        send_message(chat_id, f"📦 Send: `/additem Name Category 5 Content`")
    elif data == "admin_list":
        items = db.get_items()
        if not items:
            send_message(chat_id, "📦 No items.")
            return
        msg = "📦 *BINs*\n\n"
        for item_id, name, category, cost in items:
            msg += f"• {name} ({category}) — {cost} pts [ID: {item_id}]\n"
        send_message(chat_id, msg)
    elif data == "admin_delete":
        send_message(chat_id, f"🗑️ Send: `/delitem <item_id>`")
    elif data == "admin_delete_all":
        keyboard = {
            "inline_keyboard": [
                [{"text": "⚠️ YES DELETE ALL", "callback_data": "confirm_delete_all"}],
                [{"text": "🔙 Cancel", "callback_data": "admin_back"}],
            ]
        }
        send_message(chat_id, f"⚠️ Delete ALL BINs?", reply_markup=keyboard)
    elif data == "confirm_delete_all":
        db.delete_all_items()
        send_message(chat_id, f"🗑️ All BINs deleted.")
    elif data == "admin_addpoints":
        send_message(chat_id, f"⭐ Send: `/addpoints <user_id> <amount>`")
    elif data == "admin_stats":
        stats = db.get_stats()
        send_message(chat_id, f"📊 Users: {stats[0]}, Items: {stats[1]}")
    elif data == "admin_back":
        show_owner_panel(chat_id)
    elif data == "menu_back":
        handle_menu(chat_id, user_id)
    elif data == "stats":
        send_message(chat_id, f"📊 Points: {user_data['points']}")
    elif data == "redeem":
        items = db.get_items()
        if not items:
            send_message(chat_id, "📦 No BINs.")
            return
        available = user_data["points"]
        keyboard = {"inline_keyboard": []}
        for item_id, name, category, cost in items:
            status = "🔓" if available >= cost else "🔒"
            keyboard["inline_keyboard"].append([{"text": f"{status} {name} ({category}) — {cost} pts", "callback_data": f"redeem_item_{item_id}"}])
        keyboard["inline_keyboard"].append([{"text": "🔙 Back", "callback_data": "menu_back"}])
        send_message(chat_id, f"📦 Available: {available} points", reply_markup=keyboard)
    elif data.startswith("redeem_item_"):
        item_id = int(data.split("_")[2])
        item = db.get_item(item_id)
        if not item:
            send_message(chat_id, "❌ Not found.")
            return
        item_id, name, category, content, cost = item
        available = user_data["points"]
        if available < cost:
            send_message(chat_id, f"❌ Need {cost} points, you have {available}")
            return
        keyboard = {
            "inline_keyboard": [
                [{"text": "✅ Confirm", "callback_data": f"confirm_redeem_{item_id}"}],
                [{"text": "🔙 Cancel", "callback_data": "redeem"}],
            ]
        }
        send_message(chat_id, f"🔓 Confirm: {name} ({cost} pts)", reply_markup=keyboard)
    elif data.startswith("confirm_redeem_"):
        item_id = int(data.split("_")[2])
        item = db.get_item(item_id)
        if not item:
            send_message(chat_id, "❌ Not found.")
            return
        item_id, name, category, content, cost = item
        available = user_data["points"]
        if available < cost:
            send_message(chat_id, "❌ Not enough points.")
            return
        db.add_points(user_id, -cost)
        send_message(chat_id, f"✅ *{name}*\n```\n{content}\n```\nBalance: {available - cost}")

# ─── MAIN ──────────────────────────────────────────────────────────────

def main():
    print("🤖 Bot started: @Rhonreferbot")
    print(f"📢 Channel: {CHANNEL_LINK}")
    print("👑 Password: RHONLESTTERLOPEZ")
    print("="*50)
    last_update = 0

    while True:
        try:
            updates = get_updates(last_update + 1 if last_update else None)
            for update in updates:
                last_update = update["update_id"]

                if "message" in update:
                    msg = update["message"]
                    chat_id = msg["chat"]["id"]
                    user_id = msg["from"]["id"]
                    username = msg["from"].get("username", "")
                    first_name = msg["from"].get("first_name", "")
                    text = msg.get("text", "")

                    if text.upper() == ADMIN_PASSWORD:
                        admin_sessions[user_id] = True
                        show_owner_panel(chat_id)
                    elif text == "/start":
                        handle_start(chat_id, user_id, username, first_name, [])
                    elif text == "/menu":
                        handle_menu(chat_id, user_id)
                    elif text.startswith("/additem") and user_id in admin_sessions:
                        parts = text.split()
                        if len(parts) < 5:
                            send_message(chat_id, "Usage: /additem Name Category 5 Content")
                        else:
                            try:
                                name = parts[1]
                                category = parts[2]
                                cost = int(parts[3])
                                content = " ".join(parts[4:])
                                db.add_item(name, category, content, cost)
                                send_message(chat_id, f"✅ Added: {name}")
                            except:
                                send_message(chat_id, "❌ Error.")
                    elif text.startswith("/delitem") and user_id in admin_sessions:
                        parts = text.split()
                        if len(parts) != 2:
                            send_message(chat_id, "Usage: /delitem <id>")
                        else:
                            try:
                                item_id = int(parts[1])
                                db.delete_item(item_id)
                                send_message(chat_id, f"✅ Deleted ID: {item_id}")
                            except:
                                send_message(chat_id, "❌ Invalid ID.")
                    elif text.startswith("/deleteallbins") and user_id in admin_sessions:
                        db.delete_all_items()
                        send_message(chat_id, "🗑️ All BINs deleted.")
                    elif text.startswith("/addpoints") and user_id in admin_sessions:
                        parts = text.split()
                        if len(parts) != 3:
                            send_message(chat_id, "Usage: /addpoints <user_id> <amount>")
                        else:
                            try:
                                target_id = int(parts[1])
                                points = int(parts[2])
                                db.add_points(target_id, points)
                                send_message(chat_id, f"✅ Added {points} points to {target_id}")
                            except:
                                send_message(chat_id, "❌ Invalid.")

                elif "callback_query" in update:
                    handle_callback(update["callback_query"])

        except Exception as e:
            print(f"Error: {e}")
            time.sleep(2)

if __name__ == "__main__":
    main()
