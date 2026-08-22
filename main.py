#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
REFERRAL BOT — Full Working Version
Bot: @Rhomreferbot
Channel: https://t.me/PythonPrivateTools
Admin: 8726474142
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
BOT_USERNAME = "Rhomreferbot"
CHANNEL_LINK = "https://t.me/PythonPrivateTools"
CHANNEL_USERNAME = "PythonPrivateTools"
ADMINS = [8726474142]
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
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS redemptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                item_id INTEGER,
                redeemed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
    data = {"timeout": 60, "allowed_updates": ["message", "callback_query"]}
    if offset:
        data["offset"] = offset
    try:
        r = requests.post(url, data=data, timeout=65)
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

def handle_start(chat_id, user_id, username, first_name, args):
    if not is_member(user_id):
        keyboard = {
            "inline_keyboard": [
                [{"text": "📢 Join Premium BIN Vault", "url": CHANNEL_LINK}],
                [{"text": "✅ I've Joined!", "callback_data": "check_join"}],
            ]
        }
        send_message(
            chat_id,
            f"⚠️ *You must join the channel first!*\n\n"
            f"Click below to join, then press 'I've Joined!'",
            reply_markup=keyboard
        )
        return

    referrer_code = args[0] if args else None
    user_data = db.add_user(user_id, username, first_name, referrer_code)

    if referrer_code and user_data.get("referrer_id"):
        referrer = db.get_user(user_data["referrer_id"])
        if referrer:
            send_message(
                chat_id,
                f"✅ You were invited by *{referrer.get('first_name', 'Someone')}*!\n\n"
                f"They earned 1 point.\n\n"
                f"🔗 Your referral code: `{user_data['referral_code']}`\n\n"
                f"Use /menu to start."
            )
            return

    send_message(
        chat_id,
        f"🎯 *Welcome to Premium BIN Vault!*\n\n"
        f"Invite friends → earn points → redeem BINs & tools.\n\n"
        f"🔗 Your referral link:\n"
        f"`https://t.me/{BOT_USERNAME}?start={user_data['referral_code']}`\n\n"
        f"📊 Points: {user_data['points']}\n"
        f"📦 Available: {user_data['points'] - user_data['used_points']}\n"
        f"💡 {REDEEM_COST} points = 1 redeem\n\n"
        f"Use /menu to start."
    )

def handle_menu(chat_id, user_id):
    if not is_member(user_id):
        keyboard = {
            "inline_keyboard": [
                [{"text": "📢 Join Premium BIN Vault", "url": CHANNEL_LINK}],
                [{"text": "✅ I've Joined!", "callback_data": "check_join"}],
            ]
        }
        send_message(
            chat_id,
            f"⚠️ *You must join the channel first!*\n\n"
            f"Click below to join, then press 'I've Joined!'",
            reply_markup=keyboard
        )
        return

    user_data = db.get_user(user_id)
    if not user_data:
        send_message(chat_id, "❌ Please use /start first.")
        return

    referrals = db.get_referrals(user_id)
    available = user_data["points"] - user_data["used_points"]

    keyboard = {
        "inline_keyboard": [
            [{"text": "📦 Redeem BINs & Tools", "callback_data": "redeem"}],
            [{"text": "📊 My Stats", "callback_data": "stats"}],
            [{"text": "🔗 My Referral Link", "callback_data": "referral"}],
            [{"text": "👥 My Referrals", "callback_data": "myrefs"}],
            [{"text": "📤 Invite Friends", "callback_data": "invite"}],
        ]
    }
    send_message(
        chat_id,
        f"📋 *Main Menu*\n\n"
        f"👤 {user_data.get('first_name', 'User')}\n"
        f"👥 Referrals: {referrals}\n"
        f"⭐ Points: {user_data['points']}\n"
        f"📦 Available: {available}\n\n"
        f"💡 {REDEEM_COST} points = 1 redeem",
        reply_markup=keyboard
    )

def handle_callback(query):
    callback_id = query["id"]
    chat_id = query["message"]["chat"]["id"]
    message_id = query["message"]["message_id"]
    data = query["data"]
    user_id = query["from"]["id"]

    if data == "check_join":
        if is_member(user_id):
            answer_callback(callback_id, "✅ Joined! Now use /start again.")
            edit_message(
                chat_id,
                message_id,
                "✅ *You've joined!*\n\nNow use /start to access the bot."
            )
        else:
            answer_callback(callback_id, "❌ You haven't joined yet.")
            edit_message(
                chat_id,
                message_id,
                "⚠️ *You still need to join the channel.*\n\n"
                f"Click below to join, then press 'I've Joined!'",
                reply_markup={
                    "inline_keyboard": [
                        [{"text": "📢 Join Premium BIN Vault", "url": CHANNEL_LINK}],
                        [{"text": "✅ I've Joined!", "callback_data": "check_join"}],
                    ]
                }
            )
        return

    user_data = db.get_user(user_id)
    if not user_data:
        answer_callback(callback_id, "Please use /start first.")
        return

    answer_callback(callback_id)

    if data == "stats":
        referrals = db.get_referrals(user_id)
        available = user_data["points"] - user_data["used_points"]
        edit_message(
            chat_id,
            message_id,
            f"📊 *Your Stats*\n\n"
            f"👤 Name: {user_data.get('first_name', 'Unknown')}\n"
            f"🔗 Code: `{user_data['referral_code']}`\n"
            f"👥 Referrals: {referrals}\n"
            f"⭐ Total Points: {user_data['points']}\n"
            f"📦 Available: {available}\n"
            f"💡 Redeem cost: {REDEEM_COST} pts"
        )

    elif data == "referral":
        keyboard = {
            "inline_keyboard": [
                [{"text": "📤 Share Link", "url": f"https://t.me/share/url?url=https://t.me/{BOT_USERNAME}?start={user_data['referral_code']}&text=Join Premium BIN Vault for premium BINs and tools!"}]
            ]
        }
        edit_message(
            chat_id,
            message_id,
            f"🔗 *Your Referral Link*\n\n"
            f"`https://t.me/{BOT_USERNAME}?start={user_data['referral_code']}`\n\n"
            f"Share it! You get **1 point** per referral.",
            reply_markup=keyboard
        )

    elif data == "myrefs":
        refs = db.get_referrals(user_id)
        if refs == 0:
            edit_message(chat_id, message_id, "📊 You haven't invited anyone yet.")
            return
        edit_message(chat_id, message_id, f"👥 *Your Referrals*\n\nTotal: {refs}\n\nKeep inviting to earn more points!")

    elif data == "invite":
        keyboard = {
            "inline_keyboard": [
                [{"text": "📤 Share Link", "url": f"https://t.me/share/url?url=https://t.me/{BOT_USERNAME}?start={user_data['referral_code']}&text=Join Premium BIN Vault for premium BINs and tools!"}]
            ]
        }
        edit_message(
            chat_id,
            message_id,
            f"📤 *Invite Friends*\n\n"
            f"Share your link:\n`https://t.me/{BOT_USERNAME}?start={user_data['referral_code']}`\n\n"
            f"✅ You get **1 point** per referral!\n"
            f"💡 {REDEEM_COST} points = 1 redeem",
            reply_markup=keyboard
        )

    elif data == "redeem":
        items = db.get_items()
        if not items:
            edit_message(chat_id, message_id, "📦 No BINs or tools available yet. Check back later!")
            return

        available = user_data["points"] - user_data["used_points"]
        keyboard = {"inline_keyboard": []}
        for item_id, name, category, cost in items:
            status = "🔓" if available >= cost else "🔒"
            keyboard["inline_keyboard"].append([{"text": f"{status} {name} ({category}) — {cost} pts", "callback_data": f"redeem_item_{item_id}"}])
        keyboard["inline_keyboard"].append([{"text": "🔙 Back", "callback_data": "menu_back"}])

        edit_message(
            chat_id,
            message_id,
            f"📦 *Redeem BINs & Tools*\n\n"
            f"Available points: {available}\n"
            f"Each redeem costs {REDEEM_COST} points.\n\n"
            f"Select an item:",
            reply_markup=keyboard
        )

    elif data.startswith("redeem_item_"):
        item_id = int(data.split("_")[2])
        item = db.get_item(item_id)
        if not item:
            edit_message(chat_id, message_id, "❌ Item not found.")
            return

        item_id, name, category, content, cost = item
        available = user_data["points"] - user_data["used_points"]

        if available < cost:
            edit_message(
                chat_id,
                message_id,
                f"❌ *Not enough points!*\n\n"
                f"Item: {name}\n"
                f"Cost: {cost} points\n"
                f"Available: {available}\n\n"
                f"Invite more people to earn points."
            )
            return

        keyboard = {
            "inline_keyboard": [
                [{"text": "✅ Confirm Redeem", "callback_data": f"confirm_redeem_{item_id}"}],
                [{"text": "🔙 Cancel", "callback_data": "redeem"}],
            ]
        }
        edit_message(
            chat_id,
            message_id,
            f"🔓 *Confirm Redeem*\n\n"
            f"Item: {name}\n"
            f"Category: {category}\n"
            f"Cost: {cost} points\n"
            f"Available: {available}\n\n"
            f"⚠️ This will deduct {cost} points from your balance.",
            reply_markup=keyboard
        )

    elif data.startswith("confirm_redeem_"):
        item_id = int(data.split("_")[2])
        item = db.get_item(item_id)
        if not item:
            edit_message(chat_id, message_id, "❌ Item not found.")
            return

        item_id, name, category, content, cost = item
        available = user_data["points"] - user_data["used_points"]

        if available < cost:
            edit_message(chat_id, message_id, "❌ Not enough points!")
            return

        if db.use_points(user_id, cost):
            db.add_redemption(user_id, item_id)
            edit_message(
                chat_id,
                message_id,
                f"✅ *Redeemed!*\n\n"
                f"📦 {name}\n"
                f"📂 Category: {category}\n\n"
                f"🔑 *Content:*\n```\n{content}\n```\n\n"
                f"Balance remaining: {available - cost} points"
            )
        else:
            edit_message(chat_id, message_id, "❌ Failed to redeem. Try again.")

    elif data == "menu_back":
        handle_menu(chat_id, user_id)

# ─── ADMIN COMMANDS ──────────────────────────────────────────────────

def handle_admin(chat_id, user_id, text):
    if user_id not in ADMINS:
        send_message(chat_id, "❌ Admin only.")
        return

    parts = text.split()
    if not parts:
        return
    
    cmd = parts[0].lower()

    if cmd == "/additem":
        try:
            if len(parts) < 5:
                send_message(chat_id, "❌ Usage: /additem <name> <category> <cost> <content>")
                return
            
            name = parts[1]
            category = parts[2]
            
            try:
                cost = int(parts[3])
            except ValueError:
                send_message(chat_id, "❌ Cost must be a number.")
                return
            
            content = " ".join(parts[4:])
            
            if not content:
                send_message(chat_id, "❌ Content cannot be empty.")
                return
            
            db.add_item(name, category, content, cost)
            send_message(chat_id, f"✅ Added: {name} ({category}) — {cost} pts")
            
        except Exception as e:
            send_message(chat_id, f"❌ Error: {e}")

    elif cmd == "/listitems":
        items = db.get_items()
        if not items:
            send_message(chat_id, "📦 No items.")
            return
        msg = "📦 *Items*\n\n"
        for item_id, name, category, cost in items:
            msg += f"• {name} ({category}) — {cost} pts [ID: {item_id}]\n"
        send_message(chat_id, msg)

    elif cmd == "/delitem" and len(parts) == 2:
        try:
            item_id = int(parts[1])
            db.delete_item(item_id)
            send_message(chat_id, f"✅ Deleted item ID: {item_id}")
        except ValueError:
            send_message(chat_id, "❌ Invalid ID.")

    elif cmd == "/backup":
        if os.path.exists("referral.db"):
            size = os.path.getsize("referral.db") / 1024
            stats = db.get_stats()
            caption = (
                f"📦 *Database Backup*\n\n"
                f"📅 Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"📊 Size: {size:.2f} KB\n"
                f"👥 Users: {stats[0]}\n"
                f"🔗 Referrals: {stats[1]}\n"
                f"⭐ Total Points: {stats[2]}\n"
                f"📦 Items: {stats[3]}"
            )
            send_document(chat_id, "referral.db", caption)
        else:
            send_message(chat_id, "❌ Database file not found.")

    elif cmd == "/broadcast":
        msg = text.replace("/broadcast", "", 1).strip()
        if not msg:
            send_message(chat_id, "Usage: /broadcast <message>")
            return
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

    elif cmd == "/addpoints" and len(parts) == 3:
        try:
            target_id = int(parts[1])
            points = int(parts[2])
            db.cursor.execute("UPDATE users SET points = points + ? WHERE user_id = ?", (points, target_id))
            db.conn.commit()
            send_message(chat_id, f"✅ Added {points} points to user {target_id}")
        except ValueError:
            send_message(chat_id, "❌ Invalid ID or points.")

    elif cmd == "/stats":
        stats = db.get_stats()
        send_message(
            chat_id,
            f"📊 *Bot Stats*\n\n"
            f"👥 Total Users: {stats[0]}\n"
            f"🔗 Total Referrals: {stats[1]}\n"
            f"⭐ Total Points: {stats[2]}\n"
            f"📦 Total Items: {stats[3]}"
        )

    else:
        send_message(
            chat_id,
            "🔧 *Admin Commands*\n\n"
            "/additem <name> <category> <cost> <content>\n"
            "/listitems\n"
            "/delitem <item_id>\n"
            "/backup\n"
            "/broadcast <msg>\n"
            "/addpoints <user_id> <points>\n"
            "/stats"
        )

# ─── MAIN LOOP ─────────────────────────────────────────────────────────

def main():
    print("🤖 Referral Bot started!")
    print(f"📱 Bot: @{BOT_USERNAME}")
    print(f"📢 Channel: {CHANNEL_LINK}")
    print(f"👤 Admin ID: {ADMINS[0]}")
    print("="*50)
    print("⏳ Waiting for messages...")
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

                    if text == "/start":
                        args = text.split()[1:] if len(text.split()) > 1 else []
                        handle_start(chat_id, user_id, username, first_name, args)
                    elif text == "/menu":
                        handle_menu(chat_id, user_id)
                    elif text.startswith("/"):
                        handle_admin(chat_id, user_id, text)

                elif "callback_query" in update:
                    handle_callback(update["callback_query"])

        except Exception as e:
            print(f"Error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
