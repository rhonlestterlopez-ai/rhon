#!/usr/bin/env python3

import sqlite3
import requests
import time
import json

# ============================================================
# CONFIG
# ============================================================

BOT_TOKEN = "8542412067:AAHVQnk_uS2NG9AAlVkucPJuuu-s8ykEzZM"

BOT_USERNAME = "Rhonreferbot"

ADMIN_ID = 8726474142

ADMIN_PASSWORD = "RHONLESTTERLOPEZ"

CHANNEL_USERNAME = "PythonPrivateTools"
CHANNEL_LINK = "https://t.me/PythonPrivateTools"

DB_FILE = "referral.db"

API = f"https://api.telegram.org/bot{BOT_TOKEN}"


# ============================================================
# DATABASE
# ============================================================

class Database:

    def __init__(self):
        self.conn = sqlite3.connect(
            DB_FILE,
            check_same_thread=False
        )

        self.conn.execute(
            "PRAGMA journal_mode=WAL"
        )

        self.init_db()

    def init_db(self):

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                referred_by INTEGER,
                referral_count INTEGER DEFAULT 0,
                points INTEGER DEFAULT 0,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Automatic migration for old database
        columns = {
            row[1]
            for row in self.conn.execute(
                "PRAGMA table_info(users)"
            ).fetchall()
        }

        migrations = {
            "username": "TEXT",
            "first_name": "TEXT",
            "referred_by": "INTEGER",
            "referral_count": "INTEGER DEFAULT 0",
            "points": "INTEGER DEFAULT 0"
        }

        for column, definition in migrations.items():

            if column not in columns:

                self.conn.execute(
                    f"ALTER TABLE users "
                    f"ADD COLUMN {column} {definition}"
                )

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS referral_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                referrer_id INTEGER NOT NULL,
                referred_id INTEGER UNIQUE NOT NULL,
                referred_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        self.conn.commit()

    # ========================================================
    # USERS
    # ========================================================

    def get_user(self, user_id):

        row = self.conn.execute("""
            SELECT
                user_id,
                username,
                first_name,
                referred_by,
                referral_count,
                points
            FROM users
            WHERE user_id = ?
        """, (user_id,)).fetchone()

        if not row:
            return None

        return {
            "user_id": row[0],
            "username": row[1],
            "first_name": row[2],
            "referred_by": row[3],
            "referral_count": row[4] or 0,
            "points": row[5] or 0
        }

    def user_exists(self, user_id):

        return self.conn.execute(
            "SELECT 1 FROM users WHERE user_id = ?",
            (user_id,)
        ).fetchone() is not None

    # ========================================================
    # REGISTER
    # ========================================================

    def register_user(
        self,
        user_id,
        username,
        first_name,
        referrer_id=None
    ):

        if self.user_exists(user_id):
            return "existing"

        # Normal registration
        if not referrer_id:

            self.conn.execute("""
                INSERT INTO users (
                    user_id,
                    username,
                    first_name
                )
                VALUES (?, ?, ?)
            """, (
                user_id,
                username,
                first_name
            ))

            self.conn.commit()

            return "registered"

        # Self referral
        if referrer_id == user_id:

            self.conn.execute("""
                INSERT INTO users (
                    user_id,
                    username,
                    first_name
                )
                VALUES (?, ?, ?)
            """, (
                user_id,
                username,
                first_name
            ))

            self.conn.commit()

            return "self"

        # Referrer doesn't exist
        if not self.user_exists(referrer_id):

            self.conn.execute("""
                INSERT INTO users (
                    user_id,
                    username,
                    first_name
                )
                VALUES (?, ?, ?)
            """, (
                user_id,
                username,
                first_name
            ))

            self.conn.commit()

            return "invalid_referrer"

        # Atomic referral transaction
        try:

            self.conn.execute("BEGIN")

            self.conn.execute("""
                INSERT INTO users (
                    user_id,
                    username,
                    first_name,
                    referred_by
                )
                VALUES (?, ?, ?, ?)
            """, (
                user_id,
                username,
                first_name,
                referrer_id
            ))

            self.conn.execute("""
                INSERT INTO referral_log (
                    referrer_id,
                    referred_id
                )
                VALUES (?, ?)
            """, (
                referrer_id,
                user_id
            ))

            self.conn.execute("""
                UPDATE users
                SET
                    referral_count =
                        referral_count + 1,
                    points =
                        points + 1
                WHERE user_id = ?
            """, (referrer_id,))

            self.conn.commit()

            return "referred"

        except Exception as e:

            self.conn.rollback()

            print("Referral error:", e)

            return "error"

    # ========================================================
    # POINTS
    # ========================================================

    def add_points(self, user_id, amount):

        self.conn.execute("""
            UPDATE users
            SET points = points + ?
            WHERE user_id = ?
        """, (
            amount,
            user_id
        ))

        self.conn.commit()

    # ========================================================
    # STATS
    # ========================================================

    def get_stats(self):

        users = self.conn.execute(
            "SELECT COUNT(*) FROM users"
        ).fetchone()[0]

        referrals = self.conn.execute(
            "SELECT COUNT(*) FROM referral_log"
        ).fetchone()[0]

        points = self.conn.execute(
            "SELECT COALESCE(SUM(points), 0) FROM users"
        ).fetchone()[0]

        return users, referrals, points

    def get_top_referrers(self, limit=10):

        return self.conn.execute("""
            SELECT
                user_id,
                username,
                first_name,
                referral_count,
                points
            FROM users
            WHERE referral_count > 0
            ORDER BY referral_count DESC
            LIMIT ?
        """, (limit,)).fetchall()

    def get_users(self, limit=50):

        return self.conn.execute("""
            SELECT
                user_id,
                username,
                first_name,
                points,
                referral_count
            FROM users
            ORDER BY points DESC
            LIMIT ?
        """, (limit,)).fetchall()

    def get_all_user_ids(self):

        return self.conn.execute(
            "SELECT user_id FROM users"
        ).fetchall()


db = Database()


# ============================================================
# ADMIN SESSIONS
# ============================================================

admin_sessions = set()


# ============================================================
# TELEGRAM API
# ============================================================

def telegram(method, data=None):

    try:

        response = requests.post(
            f"{API}/{method}",
            data=data or {},
            timeout=30
        )

        result = response.json()

        if not result.get("ok"):
            print(
                "Telegram API error:",
                result
            )

        return result

    except Exception as e:

        print(
            "Telegram request error:",
            e
        )

        return None


def send_message(
    chat_id,
    text,
    reply_markup=None
):

    data = {
        "chat_id": chat_id,
        "text": text
    }

    if reply_markup:
        data["reply_markup"] = json.dumps(
            reply_markup
        )

    return telegram(
        "sendMessage",
        data
    )


def answer_callback(
    callback_id,
    text=None
):

    data = {
        "callback_query_id": callback_id
    }

    if text:
        data["text"] = text

    return telegram(
        "answerCallbackQuery",
        data
    )


def edit_message(
    chat_id,
    message_id,
    text,
    reply_markup=None
):

    data = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text
    }

    if reply_markup:
        data["reply_markup"] = json.dumps(
            reply_markup
        )

    return telegram(
        "editMessageText",
        data
    )


# ============================================================
# CHANNEL MEMBERSHIP
# ============================================================

def is_member(user_id):

    result = telegram(
        "getChatMember",
        {
            "chat_id": f"@{CHANNEL_USERNAME}",
            "user_id": user_id
        }
    )

    if not result or not result.get("ok"):
        return False

    status = result["result"].get(
        "status",
        ""
    )

    return status in [
        "member",
        "administrator",
        "creator"
    ]


def join_keyboard():

    return {
        "inline_keyboard": [
            [
                {
                    "text": "📢 Join Channel",
                    "url": CHANNEL_LINK
                }
            ],
            [
                {
                    "text": "✅ I've Joined",
                    "callback_data": "check_join"
                }
            ]
        ]
    }


# ============================================================
# MAIN MENU
# ============================================================

def menu_keyboard():

    return {
        "inline_keyboard": [
            [
                {
                    "text": "📢 Referrals",
                    "callback_data": "referrals"
                }
            ],
            [
                {
                    "text": "📊 My Stats",
                    "callback_data": "stats"
                }
            ],
            [
                {
                    "text": "👑 Admin Panel",
                    "callback_data": "admin_panel"
                }
            ]
        ]
    }


def send_menu(chat_id, user_id):

    user = db.get_user(user_id)

    if not user:
        send_message(
            chat_id,
            "❌ Please use /start first."
        )
        return

    send_message(
        chat_id,
        f"🏦 *Referral Bot*\n\n"
        f"👤 {user['first_name'] or 'User'}\n"
        f"⭐ Points: {user['points']}\n"
        f"👥 Referrals: {user['referral_count']}\n\n"
        f"Invite friends to earn points.",
        reply_markup=menu_keyboard()
    )


# ============================================================
# /START
# ============================================================

def handle_start(message):

    user = message["from"]

    user_id = user["id"]

    username = user.get(
        "username",
        ""
    )

    first_name = user.get(
        "first_name",
        "User"
    )

    # Must join channel first
    if not is_member(user_id):

        send_message(
            user_id,
            f"🔐 *Channel Required*\n\n"
            f"You must join @{CHANNEL_USERNAME} "
            f"before using the bot.\n\n"
            f"1. Click Join Channel\n"
            f"2. Join the channel\n"
            f"3. Click I've Joined",
            reply_markup=join_keyboard()
        )

        return

    # Parse referral parameter
    text = message.get(
        "text",
        ""
    )

    parts = text.split(
        maxsplit=1
    )

    referrer_id = None

    if len(parts) == 2:

        try:

            referrer_id = int(
                parts[1].strip()
            )

        except ValueError:

            referrer_id = None

    # Existing user
    existing = db.get_user(user_id)

    if existing:

        send_menu(
            user_id,
            user_id
        )

        return

    # Register
    result = db.register_user(
        user_id,
        username,
        first_name,
        referrer_id
    )

    # Successful referral
    if result == "referred":

        send_message(
            user_id,
            "🎉 *Welcome!*\n\n"
            "You joined through a referral link."
        )

        referrer = db.get_user(
            referrer_id
        )

        if referrer:

            send_message(
                referrer_id,
                f"🎉 *New Referral!*\n\n"
                f"{first_name} joined using "
                f"your referral link.\n\n"
                f"👥 Referrals: "
                f"{referrer['referral_count']}\n"
                f"⭐ Points: "
                f"{referrer['points']}"
            )

    else:

        send_message(
            user_id,
            f"🎉 *Welcome, {first_name}!*\n\n"
            f"Invite friends to earn points."
        )

    send_menu(
        user_id,
        user_id
    )


# ============================================================
# REFERRAL PAGE
# ============================================================

def handle_referrals(
    chat_id,
    user_id
):

    user = db.get_user(user_id)

    if not user:
        send_message(
            chat_id,
            "❌ Use /start first."
        )
        return

    link = (
        f"https://t.me/"
        f"{BOT_USERNAME}"
        f"?start={user_id}"
    )

    send_message(
        chat_id,
        f"🎁 *Referral Stats*\n\n"
        f"👥 Referrals: "
        f"{user['referral_count']}\n"
        f"⭐ Points: "
        f"{user['points']}\n\n"
        f"🔗 *Your referral link:*\n"
        f"{link}\n\n"
        f"Share it with your friends!"
    )


# ============================================================
# ADMIN PANEL
# ============================================================

def admin_keyboard():

    return {
        "inline_keyboard": [
            [
                {
                    "text": "📊 Statistics",
                    "callback_data": "admin_stats"
                }
            ],
            [
                {
                    "text": "🏆 Top Referrers",
                    "callback_data": "admin_top"
                }
            ],
            [
                {
                    "text": "👥 Users",
                    "callback_data": "admin_users"
                }
            ],
            [
                {
                    "text": "⭐ Add Points",
                    "callback_data": "admin_addpoints"
                }
            ],
            [
                {
                    "text": "📢 Broadcast",
                    "callback_data": "admin_broadcast"
                }
            ],
            [
                {
                    "text": "🚪 Logout",
                    "callback_data": "admin_logout"
                }
            ]
        ]
    }


def show_admin_panel(chat_id):

    send_message(
        chat_id,
        "👑 *ADMIN PANEL*\n\n"
        "Choose an action:",
        reply_markup=admin_keyboard()
    )


# ============================================================
# ADMIN COMMAND
# ============================================================

def handle_admin_command(
    chat_id,
    user_id
):

    if user_id != ADMIN_ID:

        send_message(
            chat_id,
            "❌ Unauthorized."
        )

        return

    if user_id in admin_sessions:

        show_admin_panel(
            chat_id
        )

    else:

        send_message(
            chat_id,
            "🔐 *Admin Login*\n\n"
            "Send the admin password."
        )


# ============================================================
# CALLBACKS
# ============================================================

def handle_callback(query):

    callback_id = query["id"]

    data = query["data"]

    user_id = query["from"]["id"]

    message = query.get(
        "message"
    )

    if not message:
        return

    chat_id = message["chat"]["id"]

    message_id = message["message_id"]

    # --------------------------------------------------------
    # JOIN CHECK
    # --------------------------------------------------------

    if data == "check_join":

        if is_member(user_id):

            answer_callback(
                callback_id,
                "✅ Membership verified!"
            )

            edit_message(
                chat_id,
                message_id,
                "✅ *Verified!*\n\n"
                "You can now use the bot.\n\n"
                "Send /start"
            )

        else:

            answer_callback(
                callback_id,
                "❌ You haven't joined yet."
            )

        return

    # --------------------------------------------------------
    # REFERRALS
    # --------------------------------------------------------

    if data == "referrals":

        answer_callback(
            callback_id
        )

        handle_referrals(
            chat_id,
            user_id
        )

        return

    # --------------------------------------------------------
    # USER STATS
    # --------------------------------------------------------

    if data == "stats":

        answer_callback(
            callback_id
        )

        user = db.get_user(
            user_id
        )

        if user:

            send_message(
                chat_id,
                f"📊 *Your Stats*\n\n"
                f"👥 Referrals: "
                f"{user['referral_count']}\n"
                f"⭐ Points: "
                f"{user['points']}"
            )

        return

    # --------------------------------------------------------
    # ADMIN PANEL
    # --------------------------------------------------------

    if data == "admin_panel":

        answer_callback(
            callback_id
        )

        if user_id != ADMIN_ID:

            send_message(
                chat_id,
                "❌ Unauthorized."
            )

            return

        if user_id not in admin_sessions:

            send_message(
                chat_id,
                "🔐 You are not logged in.\n\n"
                "Use /admin and enter the password."
            )

            return

        show_admin_panel(
            chat_id
        )

        return

    # --------------------------------------------------------
    # ADMIN AUTH CHECK
    # --------------------------------------------------------

    if user_id != ADMIN_ID:

        answer_callback(
            callback_id,
            "❌ Unauthorized."
        )

        return

    if user_id not in admin_sessions:

        answer_callback(
            callback_id,
            "🔐 Login required."
        )

        return

    answer_callback(
        callback_id
    )

    # --------------------------------------------------------
    # ADMIN STATS
    # --------------------------------------------------------

    if data == "admin_stats":

        users, referrals, points = (
            db.get_stats()
        )

        send_message(
            chat_id,
            f"📊 *ADMIN STATISTICS*\n\n"
            f"👤 Total Users: {users}\n"
            f"👥 Total Referrals: {referrals}\n"
            f"⭐ Total Points: {points}"
        )

    # --------------------------------------------------------
    # TOP REFERRERS
    # --------------------------------------------------------

    elif data == "admin_top":

        top = db.get_top_referrers(
            10
        )

        text = (
            "🏆 *TOP REFERRERS*\n\n"
        )

        if not top:

            text += "No referrals yet."

        else:

            for i, row in enumerate(
                top,
                1
            ):

                uid = row[0]
                username = row[1]
                first_name = row[2]
                refs = row[3]
                points = row[4]

                name = (
                    f"@{username}"
                    if username
                    else first_name or str(uid)
                )

                text += (
                    f"{i}. {name}\n"
                    f"   👥 {refs} referrals"
                    f" | ⭐ {points} points\n\n"
                )

        send_message(
            chat_id,
            text
        )

    # --------------------------------------------------------
    # USERS
    # --------------------------------------------------------

    elif data == "admin_users":

        users = db.get_users(
            50
        )

        text = (
            "👥 *USERS*\n\n"
        )

        for row in users:

            uid = row[0]
            username = row[1]
            first_name = row[2]
            points = row[3]
            refs = row[4]

            name = (
                f"@{username}"
                if username
                else first_name or str(uid)
            )

            text += (
                f"• {name}\n"
                f"  ID: {uid}\n"
                f"  ⭐ {points} pts"
                f" | 👥 {refs} refs\n\n"
            )

        send_message(
            chat_id,
            text[:4000]
        )

    # --------------------------------------------------------
    # ADD POINTS
    # --------------------------------------------------------

    elif data == "admin_addpoints":

        send_message(
            chat_id,
            "⭐ *Add Points*\n\n"
            "Send:\n"
            "`/addpoints USER_ID AMOUNT`\n\n"
            "Example:\n"
            "`/addpoints 123456789 5`"
        )

    # --------------------------------------------------------
    # BROADCAST
    # --------------------------------------------------------

    elif data == "admin_broadcast":

        send_message(
            chat_id,
            "📢 *Broadcast*\n\n"
            "Send:\n"
            "`/broadcast Your message here`"
        )

    # --------------------------------------------------------
    # LOGOUT
    # --------------------------------------------------------

    elif data == "admin_logout":

        admin_sessions.discard(
            user_id
        )

        send_message(
            chat_id,
            "🚪 Logged out."
        )


# ============================================================
# TEXT COMMANDS
# ============================================================

def handle_message(message):

    user = message["from"]

    user_id = user["id"]

    chat_id = message["chat"]["id"]

    text = message.get(
        "text",
        ""
    ).strip()

    # --------------------------------------------------------
    # ADMIN PASSWORD
    # --------------------------------------------------------

    if (
        user_id == ADMIN_ID
        and text == ADMIN_PASSWORD
    ):

        admin_sessions.add(
            user_id
        )

        show_admin_panel(
            chat_id
        )

        return

    # --------------------------------------------------------
    # START
    # --------------------------------------------------------

    if text.startswith(
        "/start"
    ):

        handle_start(
            message
        )

        return

    # --------------------------------------------------------
    # REFERRALS
    # --------------------------------------------------------

    if text == "/referrals":

        if not is_member(user_id):

            send_message(
                chat_id,
                "🔐 Please join the channel first.",
                reply_markup=join_keyboard()
            )

            return

        handle_referrals(
            chat_id,
            user_id
        )

        return

    # --------------------------------------------------------
    # STATS
    # --------------------------------------------------------

    if text == "/stats":

        user = db.get_user(
            user_id
        )

        if not user:

            send_message(
                chat_id,
                "❌ Use /start first."
            )

            return

        send_message(
            chat_id,
            f"📊 *Your Stats*\n\n"
            f"👥 Referrals: "
            f"{user['referral_count']}\n"
            f"⭐ Points: "
            f"{user['points']}"
        )

        return

    # --------------------------------------------------------
    # ADMIN
    # --------------------------------------------------------

    if text == "/admin":

        handle_admin_command(
            chat_id,
            user_id
        )

        return

    # --------------------------------------------------------
    # ADD POINTS
    # --------------------------------------------------------

    if text.startswith(
        "/addpoints"
    ):

        if user_id != ADMIN_ID:
            return

        if user_id not in admin_sessions:

            send_message(
                chat_id,
                "❌ Login first."
            )

            return

        parts = text.split()

        if len(parts) != 3:

            send_message(
                chat_id,
                "Usage:\n"
                "/addpoints USER_ID AMOUNT"
            )

            return

        try:

            target_id = int(
                parts[1]
            )

            amount = int(
                parts[2]
            )

            db.add_points(
                target_id,
                amount
            )

            send_message(
                chat_id,
                f"✅ Added {amount} points "
                f"to {target_id}."
            )

        except ValueError:

            send_message(
                chat_id,
                "❌ Invalid numbers."
            )

        return

    # --------------------------------------------------------
    # BROADCAST
    # --------------------------------------------------------

    if text.startswith(
        "/broadcast"
    ):

        if user_id != ADMIN_ID:
            return

        if user_id not in admin_sessions:

            send_message(
                chat_id,
                "❌ Login first."
            )

            return

        broadcast_text = text[
            len("/broadcast"):
        ].strip()

        if not broadcast_text:

            send_message(
                chat_id,
                "Usage:\n"
                "/broadcast Your message"
            )

            return

        users = db.get_all_user_ids()

        sent = 0

        for row in users:

            target_id = row[0]

            result = send_message(
                target_id,
                f"📢 *Announcement*\n\n"
                f"{broadcast_text}"
            )

            if result and result.get("ok"):

                sent += 1

            time.sleep(0.05)

        send_message(
            chat_id,
            f"✅ Broadcast finished.\n\n"
            f"Sent: {sent}\n"
            f"Total users: {len(users)}"
        )

        return


# ============================================================
# UPDATE LOOP
# ============================================================

def get_updates(offset=None):

    data = {
        "timeout": 30,
        "allowed_updates": '["message","callback_query"]'
    }

    if offset is not None:

        data["offset"] = offset

    return telegram(
        "getUpdates",
        data
    )


def main():

    print(
        "======================================"
    )

    print(
        "🤖 REFERRAL BOT STARTED"
    )

    print(
        f"Bot: @{BOT_USERNAME}"
    )

    print(
        f"Channel: @{CHANNEL_USERNAME}"
    )

    print(
        "======================================"
    )

    offset = None

    while True:

        try:

            result = get_updates(
                offset
            )

            if not result:
                time.sleep(2)
                continue

            updates = result.get(
                "result",
                []
            )

            for update in updates:

                offset = (
                    update["update_id"] + 1
                )

                try:

                    if "message" in update:

                        handle_message(
                            update["message"]
                        )

                    elif "callback_query" in update:

                        handle_callback(
                            update["callback_query"]
                        )

                except Exception as e:

                    print(
                        "Update error:",
                        e
                    )

        except KeyboardInterrupt:

            print(
                "Bot stopped."
            )

            break

        except Exception as e:

            print(
                "Main loop error:",
                e
            )

            time.sleep(3)


if __name__ == "__main__":
    main()
