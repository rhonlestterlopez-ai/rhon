import os
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
# DELETE OLD DATABASE
# ============================================================

if os.path.exists(DB_FILE):
    print("🗑️ Deleting old database...")
    os.remove(DB_FILE)

print("🆕 Creating fresh database...")


# ============================================================
# DATABASE
# ============================================================

class Database:

    def __init__(self):

        self.conn = sqlite3.connect(
            DB_FILE,
            check_same_thread=False
        )

        self.init_db()

    def init_db(self):

        self.conn.execute("""
            CREATE TABLE users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                referred_by INTEGER,
                referral_count INTEGER DEFAULT 0,
                points INTEGER DEFAULT 0,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        self.conn.execute("""
            CREATE TABLE referral_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                referrer_id INTEGER NOT NULL,
                referred_id INTEGER UNIQUE NOT NULL,
                referred_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        self.conn.commit()

    # --------------------------------------------------------
    # USER
    # --------------------------------------------------------

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
            "referral_count": row[4],
            "points": row[5]
        }

    def user_exists(self, user_id):

        row = self.conn.execute("""
            SELECT user_id
            FROM users
            WHERE user_id = ?
        """, (user_id,)).fetchone()

        return row is not None

    # --------------------------------------------------------
    # REGISTER USER
    # --------------------------------------------------------

    def register_user(
        self,
        user_id,
        username,
        first_name,
        referrer_id=None
    ):

        # Already registered
        if self.user_exists(user_id):
            return "existing"

        # Anti-self-referral
        if referrer_id == user_id:
            referrer_id = None

        # Referrer must exist
        valid_referrer = False

        if referrer_id:

            valid_referrer = self.user_exists(
                referrer_id
            )

        try:

            self.conn.execute("BEGIN")

            # Create user
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
                username or "",
                first_name or "",
                referrer_id
                if valid_referrer
                else None
            ))

            # Referral reward
            if valid_referrer:

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
                """, (
                    referrer_id,
                ))

            self.conn.commit()

            if valid_referrer:
                return "referred"

            if referrer_id:
                return "invalid_referrer"

            return "registered"

        except Exception as e:

            self.conn.rollback()

            print(
                "REGISTER ERROR:",
                e
            )

            return "error"

    # --------------------------------------------------------
    # POINTS
    # --------------------------------------------------------

    def add_points(
        self,
        user_id,
        amount
    ):

        self.conn.execute("""
            UPDATE users
            SET points = points + ?
            WHERE user_id = ?
        """, (
            amount,
            user_id
        ))

        self.conn.commit()

    # --------------------------------------------------------
    # STATS
    # --------------------------------------------------------

    def stats(self):

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

    def top_referrers(self):

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
            LIMIT 10
        """).fetchall()

    def all_users(self):

        return self.conn.execute("""
            SELECT
                user_id,
                username,
                first_name,
                points,
                referral_count
            FROM users
            ORDER BY points DESC
            LIMIT 50
        """).fetchall()

    def all_user_ids(self):

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

def api(method, data=None):

    try:

        r = requests.post(
            f"{API}/{method}",
            data=data or {},
            timeout=30
        )

        result = r.json()

        if not result.get("ok"):

            print(
                "Telegram error:",
                result
            )

        return result

    except Exception as e:

        print(
            "API ERROR:",
            e
        )

        return None


def send_message(
    chat_id,
    text,
    keyboard=None
):

    data = {
        "chat_id": chat_id,
        "text": text
    }

    if keyboard:

        data["reply_markup"] = json.dumps(
            keyboard
        )

    return api(
        "sendMessage",
        data
    )


def answer_callback(
    callback_id,
    text=None
):

    data = {
        "callback_query_id":
            callback_id
    }

    if text:
        data["text"] = text

    return api(
        "answerCallbackQuery",
        data
    )


# ============================================================
# CHANNEL CHECK
# ============================================================

def is_member(user_id):

    result = api(
        "getChatMember",
        {
            "chat_id":
                f"@{CHANNEL_USERNAME}",
            "user_id":
                user_id
        }
    )

    if not result:
        return False

    if not result.get("ok"):
        return False

    status = result[
        "result"
    ].get(
        "status",
        ""
    )

    return status in (
        "member",
        "administrator",
        "creator"
    )


def join_keyboard():

    return {
        "inline_keyboard": [

            [
                {
                    "text":
                        "📢 Join Channel",
                    "url":
                        CHANNEL_LINK
                }
            ],

            [
                {
                    "text":
                        "✅ I've Joined",
                    "callback_data":
                        "check_join"
                }
            ]

        ]
    }


# ============================================================
# USER MENU
# ============================================================

def menu_keyboard():

    return {
        "inline_keyboard": [

            [
                {
                    "text":
                        "📢 My Referrals",
                    "callback_data":
                        "referrals"
                }
            ],

            [
                {
                    "text":
                        "📊 My Stats",
                    "callback_data":
                        "stats"
                }
            ],

            [
                {
                    "text":
                        "👑 Admin Panel",
                    "callback_data":
                        "admin_panel"
                }
            ]

        ]
    }


def send_menu(
    chat_id,
    user_id
):

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

        f"🏦 *Referral Bot*\n\n"

        f"👤 "
        f"{user['first_name'] or 'User'}\n"

        f"⭐ Points: "
        f"{user['points']}\n"

        f"👥 Referrals: "
        f"{user['referral_count']}\n\n"

        f"Invite friends using "
        f"your referral link.",

        menu_keyboard()
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

    # --------------------------------------------------------
    # CHANNEL REQUIREMENT
    # --------------------------------------------------------

    if not is_member(user_id):

        send_message(

            user_id,

            f"🔐 *Channel Required*\n\n"

            f"You must join "
            f"@{CHANNEL_USERNAME} "
            f"before using this bot.\n\n"

            f"1️⃣ Join the channel\n"
            f"2️⃣ Click I've Joined\n"
            f"3️⃣ Use /start",

            join_keyboard()
        )

        return

    # --------------------------------------------------------
    # GET REFERRAL ID
    # --------------------------------------------------------

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

    print(
        f"START user={user_id} "
        f"referrer={referrer_id}"
    )

    # --------------------------------------------------------
    # ALREADY REGISTERED
    # --------------------------------------------------------

    if db.user_exists(
        user_id
    ):

        send_menu(
            user_id,
            user_id
        )

        return

    # --------------------------------------------------------
    # REGISTER
    # --------------------------------------------------------

    result = db.register_user(

        user_id,

        username,

        first_name,

        referrer_id
    )

    print(
        "Registration result:",
        result
    )

    # --------------------------------------------------------
    # SUCCESSFUL REFERRAL
    # --------------------------------------------------------

    if result == "referred":

        referrer = db.get_user(
            referrer_id
        )

        send_message(

            user_id,

            "🎉 *Welcome!*\n\n"

            "You joined using "
            "a referral link.\n\n"

            "Your referrer received "
            "+1 point."
        )

        if referrer:

            send_message(

                referrer_id,

                f"🎉 *New Referral!*\n\n"

                f"{first_name} joined "
                f"using your link.\n\n"

                f"👥 Referrals: "
                f"{referrer['referral_count']}\n"

                f"⭐ Points: "
                f"{referrer['points']}"
            )

    elif result == "invalid_referrer":

        send_message(

            user_id,

            "⚠️ The referral link is "
            "invalid or the referrer "
            "is not registered.\n\n"

            "Your account was still "
            "created normally."
        )

    else:

        send_message(

            user_id,

            f"🎉 *Welcome, "
            f"{first_name}!*\n\n"

            "You are now registered."
        )

    send_menu(
        user_id,
        user_id
    )


# ============================================================
# REFERRAL PAGE
# ============================================================

def show_referrals(
    chat_id,
    user_id
):

    user = db.get_user(
        user_id
    )

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

        f"🎁 *Your Referral Stats*\n\n"

        f"👥 Referrals: "
        f"{user['referral_count']}\n"

        f"⭐ Points: "
        f"{user['points']}\n\n"

        f"🔗 *Your referral link:*\n"
        f"{link}\n\n"

        f"Share this link with "
        f"your friends!"
    )


# ============================================================
# ADMIN
# ============================================================

def admin_keyboard():

    return {
        "inline_keyboard": [

            [
                {
                    "text":
                        "📊 Statistics",
                    "callback_data":
                        "admin_stats"
                }
            ],

            [
                {
                    "text":
                        "🏆 Top Referrers",
                    "callback_data":
                        "admin_top"
                }
            ],

            [
                {
                    "text":
                        "👥 Users",
                    "callback_data":
                        "admin_users"
                }
            ],

            [
                {
                    "text":
                        "⭐ Add Points",
                    "callback_data":
                        "admin_addpoints"
                }
            ],

            [
                {
                    "text":
                        "📢 Broadcast",
                    "callback_data":
                        "admin_broadcast"
                }
            ],

            [
                {
                    "text":
                        "🚪 Logout",
                    "callback_data":
                        "admin_logout"
                }
            ]

        ]
    }


def admin_panel(
    chat_id
):

    send_message(

        chat_id,

        "👑 *ADMIN PANEL*\n\n"
        "Choose an option:",

        admin_keyboard()
    )


# ============================================================
# CALLBACK HANDLER
# ============================================================

def callback_handler(query):

    callback_id = query["id"]

    data = query["data"]

    user_id = query[
        "from"
    ]["id"]

    message = query.get(
        "message"
    )

    if not message:
        return

    chat_id = message[
        "chat"
    ]["id"]

    # --------------------------------------------------------
    # CHECK JOIN
    # --------------------------------------------------------

    if data == "check_join":

        if is_member(
            user_id
        ):

            answer_callback(
                callback_id,
                "✅ Membership verified!"
            )

            send_message(

                chat_id,

                "✅ *Verified!*\n\n"
                "Now send /start."
            )

        else:

            answer_callback(
                callback_id,
                "❌ You haven't joined yet."
            )

        return

    # --------------------------------------------------------
    # USER REFERRALS
    # --------------------------------------------------------

    if data == "referrals":

        answer_callback(
            callback_id
        )

        show_referrals(
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
    # ADMIN AUTH
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
                "Use /admin."
            )

            return

        admin_panel(
            chat_id
        )

        return

    if user_id != ADMIN_ID:

        answer_callback(
            callback_id,
            "❌ Unauthorized."
        )

        return

    if user_id not in admin_sessions:

        answer_callback(
            callback_id,
            "❌ Login required."
        )

        return

    answer_callback(
        callback_id
    )

    # --------------------------------------------------------
    # ADMIN STATS
    # --------------------------------------------------------

    if data == "admin_stats":

        users, refs, points = db.stats()

        send_message(

            chat_id,

            f"📊 *BOT STATISTICS*\n\n"

            f"👤 Users: {users}\n"
            f"👥 Referrals: {refs}\n"
            f"⭐ Points: {points}"
        )

    # --------------------------------------------------------
    # TOP
    # --------------------------------------------------------

    elif data == "admin_top":

        top = db.top_referrers()

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
                    else first_name
                    or str(uid)
                )

                text += (
                    f"{i}. {name}\n"
                    f"👥 {refs} | "
                    f"⭐ {points}\n\n"
                )

        send_message(
            chat_id,
            text
        )

    # --------------------------------------------------------
    # USERS
    # --------------------------------------------------------

    elif data == "admin_users":

        users = db.all_users()

        text = "👥 *USERS*\n\n"

        for row in users:

            uid = row[0]

            username = row[1]

            first_name = row[2]

            points = row[3]

            refs = row[4]

            name = (
                f"@{username}"
                if username
                else first_name
                or str(uid)
            )

            text += (
                f"• {name}\n"
                f"ID: `{uid}`\n"
                f"⭐ {points} | "
                f"👥 {refs}\n\n"
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

            "Use:\n"
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

            "Use:\n"
            "`/broadcast Your message`"
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
# MESSAGE HANDLER
# ============================================================

def message_handler(message):

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

        send_message(
            chat_id,
            "✅ Admin login successful."
        )

        admin_panel(
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

        if not is_member(
            user_id
        ):

            send_message(

                chat_id,

                "🔐 Join the channel first.",

                join_keyboard()
            )

            return

        show_referrals(
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

        if user_id != ADMIN_ID:

            send_message(
                chat_id,
                "❌ Unauthorized."
            )

            return

        if user_id in admin_sessions:

            admin_panel(
                chat_id
            )

        else:

            send_message(

                chat_id,

                "🔐 *Admin Login*\n\n"
                "Send the admin password."
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

            target = int(
                parts[1]
            )

            amount = int(
                parts[2]
            )

            if not db.user_exists(
                target
            ):

                send_message(
                    chat_id,
                    "❌ User not found."
                )

                return

            db.add_points(
                target,
                amount
            )

            send_message(

                chat_id,

                f"✅ Added "
                f"{amount} points "
                f"to {target}."
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

        broadcast = text[
            len("/broadcast"):
        ].strip()

        if not broadcast:

            send_message(
                chat_id,
                "Usage: /broadcast message"
            )

            return

        users = db.all_user_ids()

        sent = 0

        for row in users:

            target = row[0]

            result = send_message(

                target,

                f"📢 *Announcement*\n\n"
                f"{broadcast}"
            )

            if result and result.get("ok"):

                sent += 1

            time.sleep(
                0.05
            )

        send_message(

            chat_id,

            f"✅ Broadcast complete.\n\n"
            f"Sent: {sent}\n"
            f"Users: {len(users)}"
        )


# ============================================================
# GET UPDATES
# ============================================================

def get_updates(
    offset=None
):

    data = {
        "timeout": 30,
        "allowed_updates":
            json.dumps([
                "message",
                "callback_query"
            ])
    }

    if offset is not None:

        data["offset"] = offset

    return api(
        "getUpdates",
        data
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print(
        "================================"
    )
    print(
        "🤖 RHON REFERRAL BOT"
    )
    print(
        "================================"
    )
    print(
        f"Bot: @{BOT_USERNAME}"
    )
    print(
        f"Channel: @{CHANNEL_USERNAME}"
    )
    print(
        f"Admin ID: {ADMIN_ID}"
    )
    print(
        "Database: FRESH"
    )
    print(
        "================================"
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

                        message_handler(
                            update["message"]
                        )

                    elif (
                        "callback_query"
                        in update
                    ):

                        callback_handler(
                            update[
                                "callback_query"
                            ]
                        )

                except Exception as e:

                    print(
                        "UPDATE ERROR:",
                        e
                    )

        except KeyboardInterrupt:

            print(
                "Bot stopped."
            )

            break

        except Exception as e:

            print(
                "MAIN ERROR:",
                e
            )

            time.sleep(3)


if __name__ == "__main__":
    main()
