#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RHONBOT — Premium BIN Vault
Bot: @Rhonreferbot
Password: RHONLESTTERLOPEZ
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
ADMIN_PASSWORD = "RHONLESTTERLOPEZ"
REDEEM_COST = 5

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
                referral_code TEXT UNIQUE,
                referrer_id INTEGER,
                points INTEGER DEFAULT 0,
                used_points INTEGER DEFAULT 0,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS referrals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                referrer_id INTEGER,
                referred_id INTEGER,
                referred_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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

    def add_user(self, user_id, username, first_name, referrer_code=None):
        self.cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        if self.cursor.fetchone():
            return self.get_user(user_id)

        code = self._generate_code()
        referrer_id = None
        if referrer_code:
            self.cursor.execute("SELECT user_id FROM users WHERE referral_code = ?", (referrer_code,))
            result = self.cursor.fetchone()
            if result:
                referrer_id = result[0]
                self.cursor.execute("UPDATE users SET points = points + 1 WHERE user_id = ?", (referrer_id,))
                self.cursor.execute("INSERT INTO referrals (referrer_id, referred_id) VALUES (?, ?)", (referrer_id, user_id))

        self.cursor.execute(
            "INSERT INTO users (user_id, username, first_name, referral_code, referrer_id) VALUES (?, ?, ?, ?, ?)",
            (user_id, username or "", first_name or "", code, referrer_id)
        )
        self.conn.commit()
        return self.get_user(user_id)

    def get_user(self, user_id):
        self.cursor.execute(
            "SELECT user_id, username, first_name, referral_code, referrer_id, points, used_points FROM users WHERE user_id = ?",
            (user_id,)
        )
        row = self.cursor.fetchone()
        if row:
            return {"user_id": row[0], "username": row[1], "first_name": row[2],
                    "referral_code": row[3], "referrer_id": row[4],
                    "points": row[5], "used_points": row[6]}
        return None

    def get_referrals(self, user_id):
        self.cursor.execute("SELECT COUNT(*) FROM referrals WHERE referrer_id = ?", (user_id,))
        return self.cursor.fetchone()[0]

    def get_available_points(self, user_id):
        user = self.get_user(user_id)
        if user:
            return user["points"] - user["used_points"]
        return 0

    def use_points(self, user_id, amount):
        available = self.get_available_points(user_id)
        if available < amount:
            return False
        self.cursor.execute("UPDATE users SET used_points = used_points + ? WHERE user_id = ?", (amount, user_id))
        self.conn.commit()
        return True

    def _generate_code(self):
        chars = string.ascii_uppercase + string.digits
        while True:
            code = "REF" + ''.join(random.choices(chars, k=6))
            self.cursor.execute("SELECT referral_code FROM users WHERE referral_code = ?", (code,))
            if not self.cursor.fetchone():
                return code

    def add_item(self, name, category, content, cost=REDEEM_COST):
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

    def add_redemption(self, user_id, item_id):
        self.cursor.execute("INSERT INTO redemptions (user_id, item_id) VALUES (?, ?)", (user_id, item_id))
        self.conn.commit()

    def get_stats(self):
        self.cursor.execute("SELECT COUNT(*) FROM users")
        total_users = self.cursor.fetchone()[0]
        self.cursor.execute("SELECT COUNT(*) FROM referrals")
        total_refs = self.cursor.fetchone()[0]
        self.cursor.execute("SELECT SUM(points) FROM users")
        total_points = self.cursor.fetchone()[0] or 0
        self.cursor.execute("SELECT COUNT(*) FROM bin_items")
        total_items = self.cursor.fetchone()[0]
        return total_users, total_refs, total_points, total_items

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

def send_document(chat_id, file_path, caption=""):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"
    try:
        with open(file_path, "rb") as f:
            files = {"document": f}
            data = {"chat_id": chat_id, "caption": caption, "parse_mode": "Markdown"}
            requests.post(url, files=files, data=data, timeout=30)
    except Exception as e:
        print(f"Error sending document: {e}")

# ─── ADMIN SESSIONS ────────────────────────────────────────────────────

admin_sessions = {}  # user_id: True

# ─── HANDLERS ──────────────────────────────────────────────────────────

def handle_start(chat_id, user_id, username, first_name, args):
    referrer_code = args[0] if args else None
    user_data = db.add_user(user_id, username, first_name, referrer_code)

    if referrer_code and user_data.get("referrer_id"):
        referrer = db.get_user(user_data["referrer_id"])
        if referrer:
            send_message(
                chat_id,
                f"✅ You were invited by {referrer.get('first_name', 'Someone')}!\n\n"
                f"🔗 Your referral code: `{user_data['referral_code']}`\n\n"
                f"Use /menu to start!"
            )
            return

    send_message(
        chat_id,
        f"🏦 *Welcome to Premium BIN Vault!*\n\n"
        f"Invite friends → earn points → redeem BINs.\n\n"
        f"🔗 Your referral link:\n"
        f"`https://t.me/{BOT_USERNAME}?start={user_data['referral_code']}`\n\n"
        f"📊 Points: {user_data['points']}\n"
        f"Use /menu to start."
    )

def handle_menu(chat_id, user_id):
    user_data = db.get_user(user_id)
    if not user_data:
        send_message(chat_id, "❌ Please use /start first.")
        return

    referrals = db.get_referrals(user_id)
    available = user_data["points"] - user_data["used_points"]

    keyboard = {
        "inline_keyboard": [
            [{"text": "📦 Redeem BINs", "callback_data": "redeem"}],
            [{"text": "📊 My Stats", "callback_data": "stats"}],
            [{"text": "🔗 My Referral Link", "callback_data": "referral"}],
            [{"text": "👑 Owner Login", "callback_data": "owner_login"}],
        ]
    }
    send_message(
        chat_id,
        f"📋 *Premium Menu*\n\n"
        f"👤 {user_data.get('first_name', 'User')}\n"
        f"👥 Referrals: {referrals}\n"
        f"⭐ Points: {user_data['points']}\n"
        f"📦 Available: {available}\n\n"
        f"💡 {REDEEM_COST} points = 1 redeem",
        reply_markup=keyboard
    )

def handle_owner_login(chat_id, user_id, text):
    if text.upper() == ADMIN_PASSWORD:
        admin_sessions[user_id] = True
        keyboard = {
            "inline_keyboard": [
                [{"text": "📦 Add BIN", "callback_data": "admin_add"}],
                [{"text": "📋 List BINs", "callback_data": "admin_list"}],
                [{"text": "🗑️ Delete BIN", "callback_data": "admin_delete"}],
                [{"text": "📢 Broadcast", "callback_data": "admin_broadcast"}],
                [{"text": "📊 Bot Stats", "callback_data": "admin_stats"}],
                [{"text": "👥 All Users", "callback_data": "admin_users"}],
                [{"text": "📦 Backup DB", "callback_data": "admin_backup"}],
                [{"text": "🔙 Back to Menu", "callback_data": "menu_back"}],
            ]
        }
        send_message(
            chat_id,
            f"👑 *Owner Panel Unlocked!*\n\n"
            f"Welcome back, master.\n\n"
            f"Select an option:",
            reply_markup=keyboard
        )
    else:
        send_message(chat_id, "❌ *Wrong Password!* Access denied.")

def handle_callback(query):
    callback_id = query["id"]
    chat_id = query["message"]["chat"]["id"]
    message_id = query["message"]["message_id"]
    data = query["data"]
    user_id = query["from"]["id"]

    user_data = db.get_user(user_id)
    if not user_data:
        answer_callback(callback_id, "Please use /start first.")
        return

    answer_callback(callback_id)

    # ─── OWNER LOGIN ──────────────────────────────────────────────────
    if data == "owner_login":
        send_message(
            chat_id,
            "👑 *Enter Owner Password:*\n\n"
            "Type the password to unlock admin commands."
        )
        return

    # ─── ADMIN PANEL ──────────────────────────────────────────────────
    if user_id not in admin_sessions:
        send_message(chat_id, "❌ *Please login first.*\n\nClick 'Owner Login' and enter the password.")
        return

    # ─── ADMIN: Add BIN ──────────────────────────────────────────────
    if data == "admin_add":
        send_message(
            chat_id,
            "📦 *Add BIN/Tool*\n\n"
            "Send: `/additem Name Category 5 Content`\n\n"
            "Example:\n"
            "`/additem Netflix BINs 5 BIN: 4753950x27xx92x0`"
        )

    # ─── ADMIN: List BINs ────────────────────────────────────────────
    elif data == "admin_list":
        items = db.get_items()
        if not items:
            send_message(chat_id, "📦 No items.")
            return
        msg = "📦 *Items*\n\n"
        for item_id, name, category, cost in items:
            msg += f"• {name} ({category}) — {cost} pts [ID: {item_id}]\n"
        send_message(chat_id, msg)

    # ─── ADMIN: Delete BIN ───────────────────────────────────────────
    elif data == "admin_delete":
        send_message(
            chat_id,
            "🗑️ *Delete BIN*\n\n"
            "Send: `/delitem <item_id>`"
        )

    # ─── ADMIN: Broadcast ────────────────────────────────────────────
    elif data == "admin_broadcast":
        send_message(
            chat_id,
            "📢 *Broadcast*\n\n"
            "Send: `/broadcast <message>`"
        )

    # ─── ADMIN: Stats ────────────────────────────────────────────────
    elif data == "admin_stats":
        stats = db.get_stats()
        send_message(
            chat_id,
            f"📊 *Bot Stats*\n\n"
            f"👥 Total Users: {stats[0]}\n"
            f"🔗 Total Referrals: {stats[1]}\n"
            f"⭐ Total Points: {stats[2]}\n"
            f"📦 Total Items: {stats[3]}"
        )

    # ─── ADMIN: All Users ────────────────────────────────────────────
    elif data == "admin_users":
        db.cursor.execute("SELECT user_id, username, first_name, points FROM users ORDER BY points DESC")
        users = db.cursor.fetchall()
        if not users:
            send_message(chat_id, "📊 No users yet.")
            return
        msg = "👥 *All Users*\n\n"
        for uid, username, first_name, points in users[:50]:
            name = first_name or username or f"User_{uid}"
            msg += f"• {name} — {points} pts [ID: {uid}]\n"
        if len(users) > 50:
            msg += f"\n... and {len(users) - 50} more"
        send_message(chat_id, msg)

    # ─── ADMIN: Backup ───────────────────────────────────────────────
    elif data == "admin_backup":
        if os.path.exists("referral.db"):
            size = os.path.getsize("referral.db") / 1024
            stats = db.get_stats()
            caption = (
                f"📦 *Database Backup*\n\n"
                f"📅 Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"📊 Size: {size:.2f} KB\n"
                f"👥 Users: {stats[0]}\n"
                f"🔗 Referrals: {stats[1]}\n"
                f"⭐ Points: {stats[2]}\n"
                f"📦 Items: {stats[3]}"
            )
            send_document(chat_id, "referral.db", caption)
        else:
            send_message(chat_id, "❌ Database file not found.")

    # ─── Back to Menu ────────────────────────────────────────────────
    elif data == "menu_back":
        handle_menu(chat_id, user_id)

    # ─── Stats ────────────────────────────────────────────────────────
    elif data == "stats":
        referrals = db.get_referrals(user_id)
        available = user_data["points"] - user_data["used_points"]
        send_message(
            chat_id,
            f"📊 *Your Stats*\n\n"
            f"👤 Name: {user_data.get('first_name', 'Unknown')}\n"
            f"🔗 Code: `{user_data['referral_code']}`\n"
            f"👥 Referrals: {referrals}\n"
            f"⭐ Total Points: {user_data['points']}\n"
            f"📦 Available: {available}\n"
            f"💡 Redeem cost: {REDEEM_COST} pts"
        )

    # ─── Referral Link ──────────────────────────────────────────────
    elif data == "referral":
        keyboard = {
            "inline_keyboard": [
                [{"text": "📤 Share Link", "url": f"https://t.me/share/url?url=https://t.me/{BOT_USERNAME}?start={user_data['referral_code']}&text=Join Premium BIN Vault for premium BINs and tools!"}]
            ]
        }
        send_message(
            chat_id,
            f"🔗 *Your Referral Link*\n\n"
            f"`https://t.me/{BOT_USERNAME}?start={user_data['referral_code']}`\n\n"
            f"Share it! You get **1 point** per referral.",
            reply_markup=keyboard
        )

    # ─── Redeem ──────────────────────────────────────────────────────
    elif data == "redeem":
        items = db.get_items()
        if not items:
            send_message(chat_id, "📦 No BINs available yet.")
            return

        available = user_data["points"] - user_data["used_points"]
        keyboard = {"inline_keyboard": []}
        for item_id, name, category, cost in items:
            status = "🔓" if available >= cost else "🔒"
            keyboard["inline_keyboard"].append([{"text": f"{status} {name} ({category}) — {cost} pts", "callback_data": f"redeem_item_{item_id}"}])
        keyboard["inline_keyboard"].append([{"text": "🔙 Back", "callback_data": "menu_back"}])

        send_message(
            chat_id,
            f"📦 *Redeem BINs*\n\n"
            f"Available points: {available}\n"
            f"Select an item:",
            reply_markup=keyboard
        )

    # ─── Redeem Item ──────────────────────────────────────────────────
    elif data.startswith("redeem_item_"):
        item_id = int(data.split("_")[2])
        item = db.get_item(item_id)
        if not item:
            send_message(chat_id, "❌ Item not found.")
            return

        item_id, name, category, content, cost = item
        available = user_data["points"] - user_data["used_points"]

        if available < cost:
            send_message(
                chat_id,
                f"❌ *Not enough points!*\n\n"
                f"Item: {name}\n"
                f"Cost: {cost} points\n"
                f"Available: {available}"
            )
            return

        keyboard = {
            "inline_keyboard": [
                [{"text": "✅ Confirm", "callback_data": f"confirm_redeem_{item_id}"}],
                [{"text": "🔙 Cancel", "callback_data": "redeem"}],
            ]
        }
        send_message(
            chat_id,
            f"🔓 *Confirm Redeem*\n\n"
            f"Item: {name}\n"
            f"Cost: {cost} points\n"
            f"Available: {available}",
            reply_markup=keyboard
        )

    elif data.startswith("confirm_redeem_"):
        item_id = int(data.split("_")[2])
        item = db.get_item(item_id)
        if not item:
            send_message(chat_id, "❌ Item not found.")
            return

        item_id, name, category, content, cost = item
        available = user_data["points"] - user_data["used_points"]

        if available < cost:
            send_message(chat_id, "❌ Not enough points!")
            return

        if db.use_points(user_id, cost):
            db.add_redemption(user_id, item_id)
            send_message(
                chat_id,
                f"✅ *Redeemed!*\n\n"
                f"📦 {name}\n"
                f"🔑 *Content:*\n```\n{content}\n```\n\n"
                f"Balance: {available - cost} points"
            )
        else:
            send_message(chat_id, "❌ Failed to redeem.")

# ─── MAIN LOOP ─────────────────────────────────────────────────────────

def main():
    print("🤖 Rhonbot started!")
    print(f"📱 Bot: @{BOT_USERNAME}")
    print(f"👑 Password: {ADMIN_PASSWORD}")
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

                    # ─── ⭐ PASSWORD CHECK ⭐ ──────────────────────────
                    if text.upper() == ADMIN_PASSWORD:
                        admin_sessions[user_id] = True
                        keyboard = {
                            "inline_keyboard": [
                                [{"text": "📦 Add BIN", "callback_data": "admin_add"}],
                                [{"text": "📋 List BINs", "callback_data": "admin_list"}],
                                [{"text": "🗑️ Delete BIN", "callback_data": "admin_delete"}],
                                [{"text": "📢 Broadcast", "callback_data": "admin_broadcast"}],
                                [{"text": "📊 Bot Stats", "callback_data": "admin_stats"}],
                                [{"text": "👥 All Users", "callback_data": "admin_users"}],
                                [{"text": "📦 Backup DB", "callback_data": "admin_backup"}],
                                [{"text": "🔙 Back to Menu", "callback_data": "menu_back"}],
                            ]
                        }
                        send_message(
                            chat_id,
                            f"👑 *Owner Panel Unlocked!*\n\n"
                            f"Welcome back, master.\n\n"
                            f"Select an option:",
                            reply_markup=keyboard
                        )
                    elif text == "/start":
                        args = text.split()[1:] if len(text.split()) > 1 else []
                        handle_start(chat_id, user_id, username, first_name, args)
                    elif text == "/menu":
                        handle_menu(chat_id, user_id)
                    elif text.startswith("/additem") and user_id in admin_sessions:
                        parts = text.split()
                        if len(parts) < 5:
                            send_message(chat_id, "❌ Usage: /additem <name> <category> <cost> <content>")
                        else:
                            try:
                                name = parts[1]
                                category = parts[2]
                                cost = int(parts[3])
                                content = " ".join(parts[4:])
                                db.add_item(name, category, content, cost)
                                send_message(chat_id, f"✅ Added: {name} ({category}) — {cost} pts")
                            except Exception as e:
                                send_message(chat_id, f"❌ Error: {e}")
                    elif text.startswith("/delitem") and user_id in admin_sessions:
                        parts = text.split()
                        if len(parts) != 2:
                            send_message(chat_id, "Usage: /delitem <item_id>")
                        else:
                            try:
                                item_id = int(parts[1])
                                db.delete_item(item_id)
                                send_message(chat_id, f"✅ Deleted item ID: {item_id}")
                            except:
                                send_message(chat_id, "❌ Invalid ID.")
                    elif text.startswith("/broadcast") and user_id in admin_sessions:
                        msg = text.replace("/broadcast", "", 1).strip()
                        if not msg:
                            send_message(chat_id, "Usage: /broadcast <message>")
                        else:
                            db.cursor.execute("SELECT user_id FROM users")
                            users = db.cursor.fetchall()
                            sent = 0
                            for (uid,) in users:
                                try:
                                    send_message(uid, f"📢 *Announcement*\n\n{msg}")
                                    sent += 1
                                    time.sleep(0.1)
                                except:
                                    pass
                            send_message(chat_id, f"✅ Broadcast sent to {sent} users.")

                elif "callback_query" in update:
                    handle_callback(update["callback_query"])

        except Exception as e:
            print(f"Error: {e}")
            time.sleep(2)

if __name__ == "__main__":
    main()
