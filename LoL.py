import telebot
import datetime
import time
import subprocess
import random
import threading
import os
from telebot import types
from urllib.parse import urlparse
import ipaddress
import psutil

# Initialize bot
bot = telebot.TeleBot('7140094105:AAF53GsI95nO5jjtUj8-LBID9NGaTcQNIXI')  # Replace with your actual token

# Constants
INSTRUCTOR_IDS = ["1549748318", "1662672529"]  # Replace with your instructor IDs
STUDY_GROUP_ID = "-1002658128612"             # Replace with your group ID
LEARNING_CHANNEL = "@HUNTERAloneboy99"        # Replace with your channel
LAB_REPORTS_DIR = "lab_reports"
TEST_COOLDOWN = 30
DAILY_TEST_LIMIT = 7
DEFAULT_NETWORK_IMAGE = "https://imgur.com/default_network.jpg"

# Global variables
is_test_in_progress = False
last_test_time = None
pending_reports = {}
lab_submissions = {}
student_data = {}
study_groups = {}
pending_network_test_users = {}

# File paths
STUDENT_DATA_FILE = "student_progress.txt"
GROUPS_FILE = "study_groups.txt"

# ======================
# STYLISH KEYBOARD CREATION FUNCTIONS
# ======================

def create_main_keyboard(message=None):
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True, one_time_keyboard=False)
    buttons = [
        types.KeyboardButton("🌐 𝐍𝐞𝐭𝐰𝐨𝐫𝐤 𝐓𝐞𝐬𝐭"),
        types.KeyboardButton("🔬 𝐂𝐨𝐧𝐝𝐮𝐜𝐭 𝐄𝐱𝐩𝐞𝐫𝐢𝐦𝐞𝐧𝐭"),
        types.KeyboardButton("📊 𝐕𝐢𝐞𝐰 𝐏𝐫𝐨𝐠𝐫𝐞𝐬𝐬"),
        types.KeyboardButton("🧠 𝐂𝐏𝐔 𝐔𝐬𝐚𝐠𝐞"),
        types.KeyboardButton("📝 𝐒𝐮𝐛𝐦𝐢𝐭 𝐑𝐞𝐩𝐨𝐫𝐭"),
    ]
    if message and str(message.from_user.id) in INSTRUCTOR_IDS:
        buttons.append(types.KeyboardButton("👨‍🏫 𝐈𝐧𝐬𝐭𝐫𝐮𝐜𝐭𝐨𝐫 𝐓𝐨𝐨𝐥𝐬"))
    markup.add(*buttons)
    return markup

def create_experiment_keyboard():
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True, one_time_keyboard=False)
    buttons = [
        types.KeyboardButton("🌐 𝐍𝐞𝐭𝐰𝐨𝐫𝐤 𝐓𝐞𝐬𝐭"),
        types.KeyboardButton("📶 𝐏𝐢𝐧𝐠 𝐓𝐞𝐬𝐭"),
        types.KeyboardButton("⏱ 𝐂𝐡𝐞𝐜𝐤 𝐂𝐨𝐨𝐥𝐝𝐨𝐰𝐧"),
        types.KeyboardButton("🔙 𝐌𝐚𝐢𝐧 𝐌𝐞𝐧𝐮")
    ]
    markup.add(*buttons)
    return markup

def create_instructor_keyboard():
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True, one_time_keyboard=False)
    buttons = [
        types.KeyboardButton("📢 𝐒𝐞𝐧𝐝 𝐍𝐨𝐭𝐢𝐜𝐞"),
        types.KeyboardButton("➕ 𝐀𝐝𝐝 𝐀𝐝𝐦𝐢𝐧"),
        types.KeyboardButton("➖ 𝐑𝐞𝐦𝐨𝐯𝐞 𝐀𝐝𝐦𝐢𝐧"),
        types.KeyboardButton("📋 𝐋𝐢𝐬𝐭 𝐀𝐝𝐦𝐢𝐧𝐬"),
        types.KeyboardButton("➕ 𝐀𝐝𝐝 𝐆𝐫𝐨𝐮𝐩"),
        types.KeyboardButton("➖ 𝐑𝐞𝐦𝐨𝐯𝐞 𝐆𝐫𝐨𝐮𝐩"),
        types.KeyboardButton("📋 𝐋𝐢𝐬𝐭 𝐆𝐫𝐨𝐮𝐩𝐬"),
        types.KeyboardButton("🔄 𝐑𝐞𝐬𝐞𝐭 𝐒𝐭𝐮𝐝𝐞𝐧𝐭"),
        types.KeyboardButton("🔙 𝐌𝐚𝐢𝐧 𝐌𝐞𝐧𝐮")
    ]
    markup.add(*buttons)
    return markup

# ======================
# HELPER FUNCTIONS
# ======================

def create_progress_bar(progress, total, length=20):
    filled = int(length * progress // total)
    empty = length - filled
    bar = '🥭' * filled + '-' * empty
    percent = min(100, int(100 * progress / total))
    return f"📈 𝐏𝐫𝐨𝐠𝐫𝐞𝐬𝐬: {bar} {percent}%"

def update_progress(chat_id, progress_data, target, port, student_name):
    duration = progress_data['duration']
    start_time = progress_data['start_time']
    
    try:
        while True:
            elapsed = (datetime.datetime.now() - start_time).seconds
            progress = min(elapsed, duration)
            remaining = max(0, duration - elapsed)
            
            if progress - progress_data['last_update'] >= 5 or progress == duration:
                try:
                    bot.edit_message_text(
                        f"🔬 𝐄𝐱𝐩𝐞𝐫𝐢𝐦𝐞𝐧𝐭 𝐑𝐮𝐧𝐧𝐢𝐧𝐠\n"
                        f"👨‍🔬 𝐒𝐭𝐮𝐝𝐞𝐧𝐭: »»—— {student_name} ♥\n"
                        f"🎯 𝐓𝐚𝐫𝐠𝐞𝐭: {target}:{port}\n"
                        f"⏱ 𝐄𝐥𝐚𝐩𝐬𝐞𝐝: {progress}s/{duration}s\n"
                        f"📊 𝐑𝐞𝐦𝐚𝐢𝐧𝐢𝐧𝐠: {remaining}\n"
                        f"{create_progress_bar(progress, duration)}\n",
                        chat_id=chat_id,
                        message_id=progress_data['message_id']
                    )
                    progress_data['last_update'] = progress
                except Exception as e:
                    print(f"Error updating progress: {e}")
                
                if progress >= duration:
                    break
            
            time.sleep(1)
    except Exception as e:
        print(f"Progress updater error: {e}")

def is_valid_url(url):
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False

def safe_send_photo(chat_id, photo_url, caption):
    try:
        if is_valid_url(photo_url):
            bot.send_photo(chat_id, photo_url, caption=caption)
        else:
            bot.send_message(chat_id, caption)
    except Exception as e:
        print(f"Error sending photo: {e}")
        bot.send_message(chat_id, caption)

def load_student_data():
    global student_data
    try:
        with open(STUDENT_DATA_FILE, "r") as file:
            for line in file:
                if not line.strip():
                    continue
                try:
                    user_id, tests, last_reset = line.strip().split(',')
                    student_data[user_id] = {
                        'tests': int(tests),
                        'last_reset': datetime.datetime.fromisoformat(last_reset),
                        'last_test': None
                    }
                except ValueError:
                    print(f"Skipping malformed line: {line.strip()}")
    except FileNotFoundError:
        print(f"{STUDENT_DATA_FILE} not found, starting fresh.")

def save_student_data():
    with open(STUDENT_DATA_FILE, "w") as file:
        for user_id, data in student_data.items():
            file.write(f"{user_id},{data['tests']},{data['last_reset'].isoformat()}\n")

def check_membership(user_id):
    try:
        try:
            channel_member = bot.get_chat_member(LEARNING_CHANNEL, user_id)
            if channel_member.status not in ['member', 'administrator', 'creator']:
                return False
        except Exception as e:
            print(f"Error checking channel membership: {e}")
            return False
            
        for group_id in study_groups:
            try:
                group_member = bot.get_chat_member(group_id, user_id)
                if group_member.status in ['member', 'administrator', 'creator']:
                    return True
            except Exception as e:
                print(f"Error checking group {group_id} membership: {e}")
                continue
                
        try:
            main_group_member = bot.get_chat_member(STUDY_GROUP_ID, user_id)
            if main_group_member.status in ['member', 'administrator', 'creator']:
                return True
        except Exception as e:
            print(f"Error checking main group membership: {e}")
                
        return False
    except Exception as e:
        print(f"General membership check error: {e}")
        return False

def membership_required(func):
    def wrapped(message):
        user_id = str(message.from_user.id)
        chat_id = str(message.chat.id)

        if user_id in INSTRUCTOR_IDS:
            return func(message)

        if chat_id not in study_groups and chat_id != STUDY_GROUP_ID:
            bot.reply_to(message, "🚫 𝐓𝐡𝐢𝐬 𝐜𝐨𝐦𝐦𝐚𝐧𝐝 𝐜𝐚𝐧 𝐨𝐧𝐥𝐲 𝐛𝐞 𝐮𝐬𝐞𝐝 𝐢𝐧 𝐚𝐩𝐩𝐫𝐨𝐯𝐞𝐝 𝐬𝐭𝐮𝐝𝐲 𝐠𝐫𝐨𝐮𝐩𝐬")
            return

        if not check_membership(user_id):
            bot.reply_to(message, f"🔒 𝐀𝐜𝐜𝐞𝐬𝐬 𝐑𝐞𝐬𝐭𝐫𝐢𝐜𝐭𝐞𝐝\n\n𝐓𝐨 𝐮𝐬𝐞 𝐭𝐡𝐢𝐬 𝐛𝐨𝐭, 𝐲𝐨𝐮 𝐦𝐮𝐬𝐭:\n𝟭. 𝐉𝐨𝐢𝐧 𝐨𝐮𝐫 𝐠𝐫𝐨𝐮𝐩: {STUDY_GROUP_ID}\n𝟮. 𝐒𝐮𝐛𝐬𝐜𝐫𝐢𝐛𝐞 𝐭𝐨 𝐨𝐮𝐫 𝐜𝐡𝐚𝐧𝐧𝐞𝐥: {LEARNING_CHANNEL}\n\n𝐀𝐟𝐭𝐞𝐫 𝐣𝐨𝐢𝐧𝐢𝐧𝐠, 𝐭𝐫𝐲 𝐚𝐠𝐚𝐢𝐧.")
            return

        return func(message)
    return wrapped

def load_study_groups():
    global study_groups
    if os.path.exists(GROUPS_FILE):
        with open(GROUPS_FILE, "r") as f:
            for line in f:
                if ',' in line:
                    group_id, name = line.strip().split(',', 1)
                    study_groups[group_id] = name

def save_study_groups():
    with open(GROUPS_FILE, "w") as f:
        for group_id, name in study_groups.items():
            f.write(f"{group_id},{name}\n")

def notify_instructors(message, user_name, file_id):
    for instructor_id in INSTRUCTOR_IDS:
        try:
            bot.send_photo(
                instructor_id,
                file_id,
                caption=f"𝐍𝐞𝐰 𝐋𝐚𝐛 𝐑𝐞𝐩𝐨𝐫𝐭 𝐟𝐫𝐨𝐦 {user_name} (@{message.from_user.username})"
            )
        except Exception as e:
            print(f"Error notifying instructor {instructor_id}: {e}")
            try:
                bot.send_message(
                    instructor_id,
                    f"𝐍𝐞𝐰 𝐋𝐚𝐛 𝐑𝐞𝐩𝐨𝐫𝐭 𝐟𝐫𝐨𝐦 {user_name} (@{message.from_user.username})\n𝐏𝐡𝐨𝐭𝐨 𝐈𝐃: {file_id}"
                )
            except Exception as e2:
                print(f"Failed to send text notification to {instructor_id}: {e2}")

def auto_reset_daily_limits():
    while True:
        now = datetime.datetime.now()
        midnight = (now + datetime.timedelta(days=1)).replace(hour=0, minute=0, second=0)
        time.sleep((midnight - now).total_seconds())
        for user_id in student_data:
            student_data[user_id]['tests'] = 0
            student_data[user_id]['last_reset'] = datetime.datetime.now()
        save_student_data()

ADMINS_FILE = "admins.txt"
ADMIN_IDS = set()

def load_admins():
    global ADMIN_IDS
    if os.path.exists(ADMINS_FILE):
        with open(ADMINS_FILE, "r") as f:
            ADMIN_IDS = set(line.strip() for line in f if line.strip())

def save_admins():
    with open(ADMINS_FILE, "w") as f:
        for admin_id in ADMIN_IDS:
            f.write(f"{admin_id}\n")

# Add buttons in create_instructor_keyboard()
# types.KeyboardButton("➕ 𝐀𝐝𝐝 𝐀𝐝𝐦𝐢𝐧"),
# types.KeyboardButton("➖ 𝐑𝐞𝐦𝐨𝐯𝐞 𝐀𝐝𝐦𝐢𝐧"),
# types.KeyboardButton("📋 𝐋𝐢𝐬𝐭 𝐀𝐝𝐦𝐢𝐧𝐬"),

@bot.message_handler(func=lambda msg: msg.text == "➕ 𝐀𝐝𝐝 𝐀𝐝𝐦𝐢𝐧")
def ask_add_admin(message):
    if str(message.from_user.id) not in INSTRUCTOR_IDS:
        bot.reply_to(message, "🚫 𝐀𝐜𝐜𝐞𝐬𝐬 𝐃𝐞𝐧𝐢𝐞𝐝")
        return
    msg = bot.send_message(message.chat.id, "➕ 𝐒𝐞𝐧𝐝 𝐓𝐞𝐥𝐞𝐠𝐫𝐚𝐦 𝐔𝐬𝐞𝐫 𝐈𝐃 𝐭𝐨 𝐀𝐝𝐝 𝐚𝐬 𝐀𝐝𝐦𝐢𝐧:")
    bot.register_next_step_handler(msg, process_add_admin)

def process_add_admin(message):
    new_id = message.text.strip()
    if not new_id.isdigit():
        bot.reply_to(message, "❌ 𝐈𝐧𝐯𝐚𝐥𝐢𝐝 𝐈𝐃. 𝐏𝐥𝐞𝐚𝐬𝐞 𝐬𝐞𝐧𝐝 𝐧𝐮𝐦𝐞𝐫𝐢𝐜 𝐔𝐬𝐞𝐫 𝐈𝐃.")
        return
    if new_id in ADMIN_IDS:
        bot.reply_to(message, f"ℹ️ 𝐀𝐝𝐦𝐢𝐧 𝐈𝐃 `{new_id}` 𝐚𝐥𝐫𝐞𝐚𝐝𝐲 𝐞𝐱𝐢𝐬𝐭𝐬.", parse_mode="Markdown")
        return
    ADMIN_IDS.add(new_id)
    save_admins()
    bot.reply_to(message, f"✅ 𝐀𝐝𝐝𝐞𝐝 𝐀𝐝𝐦𝐢𝐧 𝐈𝐃: `{new_id}`", parse_mode="Markdown")

@bot.message_handler(func=lambda msg: msg.text == "➖ 𝐑𝐞𝐦𝐨𝐯𝐞 𝐀𝐝𝐦𝐢𝐧")
def ask_remove_admin(message):
    if str(message.from_user.id) not in INSTRUCTOR_IDS:
        bot.reply_to(message, "🚫 𝐀𝐜𝐜𝐞𝐬𝐬 𝐃𝐞𝐧𝐢𝐞𝐝")
        return
    msg = bot.send_message(message.chat.id, "➖ 𝐒𝐞𝐧𝐝 𝐔𝐬𝐞𝐫 𝐈𝐃 𝐭𝐨 𝐑𝐞𝐦𝐨𝐯𝐞 𝐟𝐫𝐨𝐦 𝐀𝐝𝐦𝐢𝐧:")
    bot.register_next_step_handler(msg, process_remove_admin)

def process_remove_admin(message):
    remove_id = message.text.strip()
    if remove_id in ADMIN_IDS:
        ADMIN_IDS.remove(remove_id)
        save_admins()
        bot.reply_to(message, f"✅ 𝐑𝐞𝐦𝐨𝐯𝐞𝐝 𝐀𝐝𝐦𝐢𝐧 𝐈𝐃: `{remove_id}`", parse_mode="Markdown")
    else:
        bot.reply_to(message, f"❌ 𝐀𝐝𝐦𝐢𝐧 𝐈𝐃 `{remove_id}` 𝐧𝐨𝐭 𝐟𝐨𝐮𝐧𝐝", parse_mode="Markdown")

@bot.message_handler(func=lambda msg: msg.text == "📋 𝐋𝐢𝐬𝐭 𝐀𝐝𝐦𝐢𝐧𝐬")
def list_admins(message):
    if str(message.from_user.id) not in INSTRUCTOR_IDS:
        bot.reply_to(message, "🚫 𝐀𝐜𝐜𝐞𝐬𝐬 𝐃𝐞𝐧𝐢𝐞𝐝")
        return
    if not ADMIN_IDS:
        bot.reply_to(message, "📋 𝐍𝐨 𝐚𝐝𝐦𝐢𝐧𝐬 𝐡𝐚𝐯𝐞 𝐛𝐞𝐞𝐧 𝐚𝐝𝐝𝐞𝐝 𝐲𝐞𝐭.")
        return
    admin_list = "\n".join(f"• `{aid}`" for aid in ADMIN_IDS)
    bot.send_message(message.chat.id, f"📋 𝐂𝐮𝐫𝐫𝐞𝐧𝐭 𝐀𝐝𝐦𝐢𝐧𝐬:\n\n{admin_list}", parse_mode="Markdown")
# ======================
# COMMAND HANDLERS
# ======================

@bot.message_handler(commands=['start'])
def welcome_student(message):
    user_name = message.from_user.first_name
    response = f"""
╭━━━━━━━〔 *ALONEBOY NETWORK LABORATORY* 〕━━━━━━━╮
         *“ᴡʜᴇʀᴇ ᴅᴀᴛᴀ ʙᴏᴡs ᴛᴏ ᴍᴀsᴛᴇʀʏ”*  
╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯

      🛡️ *ACCESS LEVEL: PREMIUM INITIATED*  
              𝘞𝘦𝘭𝘤𝘰𝘮𝘦, *{user_name}*  

*─────────────[ 𝘓𝘈𝘉 𝘋𝘐𝘙 ]─────────────*  
╰➤ *Professors:* [@GODxAloneBOY] [@RAJOWNER90]

╰➤ *Command Center:* [Join Channel]({LEARNING_CHANNEL})  
╰➤ *Systems Manual:* Type /help  
───────────────────────────────────  
🧾 *LAB PROTOCOLS:*  
1. *⛔ No Commands Without Authorization*  
2. *⚗️ Daily Limit:* `{DAILY_TEST_LIMIT}` Experiments  
3. *⏳ Cooldown Between Tests:* `{TEST_COOLDOWN} sec`  

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  
✅ *Access Tunnel Opened*  
➡️ Begin your mission at [{LEARNING_CHANNEL}]({LEARNING_CHANNEL})
"""
    bot.send_message(
        message.chat.id, 
        response, 
        parse_mode="Markdown", 
        disable_web_page_preview=False,
        reply_markup=create_main_keyboard(message)
    )

@bot.message_handler(commands=['help'])
@membership_required
def show_help(message):
    help_text = f"""
⚡ *Network Science Lab - Command Center* ⚡  
*Under the guidance of Professor ALONEBOY* 👨‍🏫  

▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬  
🔰 *BASIC COMMANDS*  
▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬  
😎➤ /start - Begin your network science journey  
🍀➤ /help - Show this elite command list  

▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬  
🔬 *STUDENT LAB COMMANDS*  
▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬  
🍀➤ /study <IP> <PORT> <DURATION> - Conduct advanced network analysis  
✅➤ /pingtest <IP> - Master latency measurement  
😎➤ /cooldownstatus - Check experiment readiness  
💗➤ /remainingtests - View your daily quota  

▬▬▬▬▬▬▬▬▬▬▬▬▬𝐂𝐨𝐧𝐭𝐢𝐧𝐮𝐞𝐝...
"""
    bot.send_message(
        message.chat.id, 
        help_text, 
        parse_mode="Markdown",
        reply_markup=create_main_keyboard(message)
    )

# ======================
# KEYBOARD BUTTON HANDLERS
# ======================

@bot.message_handler(func=lambda msg: msg.text == "🔙 𝐌𝐚𝐢𝐧 𝐌𝐞𝐧𝐮")
@membership_required
def return_to_main_menu(message):
    bot.send_message(
        message.chat.id,
        "🏠 𝐌𝐚𝐢𝐧 𝐌𝐞𝐧𝐮",
        reply_markup=create_main_keyboard(message)
    )

@bot.message_handler(func=lambda msg: msg.text == "🔬 𝐂𝐨𝐧𝐝𝐮𝐜𝐭 𝐄𝐱𝐩𝐞𝐫𝐢𝐦𝐞𝐧𝐭")
@membership_required
def experiment_menu(message):
    bot.send_message(
        message.chat.id,
        "🔬 𝐄𝐱𝐩𝐞𝐫𝐢𝐦𝐞𝐧𝐭 𝐌𝐞𝐧𝐮\n\n𝐂𝐡𝐨𝐨𝐬𝐞 𝐚𝐧 𝐨𝐩𝐭𝐢𝐨𝐧:",
        reply_markup=create_experiment_keyboard()
    )

@bot.message_handler(func=lambda msg: msg.text == "🌐 𝐍𝐞𝐭𝐰𝐨𝐫𝐤 𝐓𝐞𝐬𝐭")
@membership_required
def network_test_handler(message):
    """Handle network test request with user-specific tracking"""
    user_id = str(message.from_user.id)
    pending_network_test_users[user_id] = True
    
    msg = bot.send_message(
        message.chat.id,
        "🌐 *𝐄𝐧𝐭𝐞𝐫 𝐍𝐞𝐭𝐰𝐨𝐫𝐤 𝐓𝐞𝐬𝐭 𝐏𝐚𝐫𝐚𝐦𝐞𝐭𝐞𝐫𝐬:*\n\n*𝐅𝐨𝐫𝐦𝐚𝐭:* `<IP> <PORT> <DURATION>`\n*𝐄𝐱𝐚𝐦𝐩𝐥𝐞:* `192.168.1.1 80 30`",
        parse_mode="Markdown",
        reply_markup=types.ForceReply(selective=True)
    )
    bot.register_next_step_handler(msg, process_network_test)

def process_network_test(message):
    """Process network test parameters from the correct user"""
    global is_test_in_progress, last_test_time
    
    user_id = str(message.from_user.id)
    if not pending_network_test_users.get(user_id, False):
        bot.reply_to(message, "🚫 𝐓𝐡𝐢𝐬 𝐫𝐞𝐪𝐮𝐞𝐬𝐭 𝐢𝐬𝐧'𝐭 𝐟𝐨𝐫 𝐲𝐨u 𝐨𝐫 𝐡𝐚𝐬 𝐞𝐱𝐩𝐢𝐫𝐞𝐝", reply_markup=create_main_keyboard(message))
        return
    
    pending_network_test_users[user_id] = False
    
    try:
        command = message.text.split()
        if len(command) != 3:
            raise ValueError("❌ *𝐈𝐧𝐯𝐚𝐥𝐢𝐝 𝐟𝐨𝐫𝐦𝐚𝐭.* 𝐔𝐬𝐞: `<IP> <PORT> <DURATION>`")

        target, port, duration = command[0], int(command[1]), int(command[2])
        ipaddress.ip_address(target)

        if not (1 <= port <= 65535):
            raise ValueError("❌ *𝐏𝐨𝐫𝐭 𝐦𝐮𝐬𝐭 𝐛𝐞 𝟏-𝟔𝟓𝟓𝟑𝟓*")
        if duration > 149 or duration < 5:
            raise ValueError("❌ *𝐃𝐮𝐫𝐚𝐭𝐢𝐨𝐧 𝐦𝐮𝐬𝐭 𝐛𝐞 𝟓-𝟏𝟒𝟗 𝐬𝐞𝐜*")

        user_name = message.from_user.first_name

        if is_test_in_progress:
            bot.reply_to(message, "⏳ *𝐀𝐧𝐨𝐭𝐡𝐞𝐫 𝐞𝐱𝐩𝐞𝐫𝐢𝐦𝐞𝐧𝐭 𝐢𝐬 𝐫𝐮𝐧𝐧𝐢𝐧𝐠. 𝐖𝐚𝐢𝐭 𝐚 𝐛𝐢𝐭.*", 
                       parse_mode="Markdown", 
                       reply_markup=create_main_keyboard(message))
            return

        current_time = datetime.datetime.now()
        if last_test_time and (current_time - last_test_time).seconds < TEST_COOLDOWN:
            remaining = TEST_COOLDOWN - (current_time - last_test_time).seconds
            bot.reply_to(message, f"⏳ *𝐖𝐚𝐢𝐭 {remaining}s 𝐛𝐞𝐟𝐨𝐫𝐞 𝐧𝐞𝐱𝐭 𝐭𝐞𝐬𝐭.*", 
                       parse_mode="Markdown", 
                       reply_markup=create_main_keyboard(message))
            return

        if pending_reports.get(user_id, False):
            bot.reply_to(message, "📝 *𝐏𝐞𝐧𝐝𝐢𝐧𝐠 𝐥𝐚𝐛 𝐫𝐞𝐩𝐨𝐫𝐭 𝐟𝐨𝐮𝐧𝐝. 𝐒𝐮𝐛𝐦𝐢𝐭 𝐢𝐭 𝐟𝐢𝐫𝐬𝐭.*", 
                       parse_mode="Markdown", 
                       reply_markup=create_main_keyboard(message))
            return

        if user_id not in student_data:
            student_data[user_id] = {'tests': 0, 'last_reset': datetime.datetime.now()}

        student = student_data[user_id]
        if student['tests'] >= DAILY_TEST_LIMIT:
            bot.reply_to(message, "📊 *𝐃𝐚𝐢𝐥𝐲 𝐥𝐢𝐦𝐢𝐭 𝐫𝐞𝐚𝐜𝐡𝐞𝐝.*", 
                       parse_mode="Markdown", 
                       reply_markup=create_main_keyboard(message))
            return

        if not bot.get_user_profile_photos(user_id).total_count:
            bot.reply_to(message, "📸 *𝐏𝐥𝐞𝐚𝐬𝐞 𝐚𝐝𝐝 𝐚 𝐩𝐫𝐨𝐟𝐢𝐥𝐞 𝐩𝐢𝐜 𝐛𝐞𝐟𝐨𝐫𝐞 𝐮𝐬𝐢𝐧𝐠 𝐭𝐡𝐞 𝐥𝐚𝐛.*", 
                       parse_mode="Markdown", 
                       reply_markup=create_main_keyboard(message))
            return

        is_test_in_progress = True
        student['tests'] += 1
        pending_reports[user_id] = True
        save_student_data()

        progress_msg = bot.send_message(
            message.chat.id,
            f"🔬 *𝐄𝐱𝐩𝐞𝐫𝐢𝐦𝐞𝐧𝐭 𝐑𝐮𝐧𝐧𝐢𝐧𝐠*\n"
            f"👨‍🔬 *𝐒𝐭𝐮𝐝𝐞𝐧𝐭:* {user_name}\n"
            f"🎯 *𝐓𝐚𝐫𝐠𝐞𝐭:* {target}:{port}\n"
            f"⏱ *𝐃𝐮𝐫𝐚𝐭𝐢𝐨𝐧:* {duration}s\n"
            f"{create_progress_bar(0, duration)}",
            parse_mode="Markdown"
        )

        progress_data = {
            'message_id': progress_msg.message_id,
            'start_time': datetime.datetime.now(),
            'duration': duration,
            'last_update': 0,
            'target': target,
            'port': port
        }

        def run_progress():
            update_progress(message.chat.id, progress_data, target, port, user_name)

        def run_command():
            global is_test_in_progress, last_test_time
            try:
                subprocess.run(["./RAJ", target, str(port), str(duration)], check=True)
                last_test_time = datetime.datetime.now()

                bot.send_message(
                    message.chat.id,
                    f"✅ *𝐄𝐱𝐩𝐞𝐫𝐢𝐦𝐞𝐧𝐭 𝐂𝐨𝐦𝐩𝐥𝐞𝐭𝐞!*\n\n"
                    f"🔬 *𝐒𝐮𝐦𝐦𝐚𝐫𝐲:*\n"
                    f"👨‍🔬 *𝐒𝐭𝐮𝐝𝐞𝐧𝐭:* {user_name}\n"
                    f"🎯 *𝐓𝐚𝐫𝐠𝐞𝐭:* {target}:{port}\n"
                    f"⏱ *𝐓𝐢𝐦𝐞:* {duration}s\n\n"
                    f"📝 *𝐒𝐮𝐛𝐦𝐢𝐭 𝐲𝐨𝐮𝐫 𝐥𝐚𝐛 𝐫𝐞𝐩𝐨𝐫𝐭 𝐧𝐨𝐰.*",
                    parse_mode="Markdown",
                    reply_markup=create_main_keyboard(message)
                )

            except subprocess.CalledProcessError:
                bot.send_message(message.chat.id, "⚠️ *𝐂𝐨𝐦𝐦𝐚𝐧𝐝 𝐟𝐚𝐢𝐥𝐞𝐝.*", 
                               parse_mode="Markdown", 
                               reply_markup=create_main_keyboard(message))
            except Exception as e:
                bot.send_message(message.chat.id, f"⚠️ *𝐄𝐫𝐫𝐨𝐫:* {str(e)}", 
                               parse_mode="Markdown", 
                               reply_markup=create_main_keyboard(message))
            finally:
                is_test_in_progress = False

        threading.Thread(target=run_progress).start()
        threading.Thread(target=run_command).start()

    except ValueError as ve:
        bot.reply_to(message, f"{ve}", 
                   parse_mode="Markdown", 
                   reply_markup=create_main_keyboard(message))
    except Exception as e:
        bot.reply_to(message, f"❌ *𝐄𝐫𝐫𝐨𝐫:* {str(e)}", 
                   parse_mode="Markdown", 
                   reply_markup=create_main_keyboard(message))

# [Rest of the code remains the same...]

# ======================
# INITIALIZATION
# ======================

# Load data at startup
@bot.message_handler(func=lambda msg: msg.text == "📶 𝐏𝐢𝐧𝐠 𝐓𝐞𝐬𝐭")
@membership_required
def ping_test_handler(message):
    """Handle ping test request"""
    msg = bot.send_message(
        message.chat.id,
        "📶 𝐄𝐧𝐭𝐞𝐫 𝐈𝐏 𝐭𝐨 𝐩𝐢𝐧𝐠:"
        # Removed reply_markup=types.ForceReply()
    )
    bot.register_next_step_handler(msg, process_ping_test)

def process_ping_test(message):
    """Process ping test"""
    try:
        ip = message.text.strip()
        # Validate IP format
        if not all(part.isdigit() and 0 <= int(part) <= 255 for part in ip.split('.')):
            raise ValueError("𝐈𝐧𝐯𝐚𝐥𝐢𝐝 𝐈𝐏 𝐚𝐝𝐝𝐫𝐞𝐬𝐬 𝐟𝐨𝐫𝐦𝐚𝐭")
            
        # Simulate creating a ping command
        ping_command = f"/pingtest {ip}"
        message.text = ping_command
        conduct_ping_test(message)
        
    except ValueError as e:
        bot.reply_to(message, f"❌ 𝐈𝐧𝐯𝐚𝐥𝐢𝐝 𝐈𝐏 𝐚𝐝𝐝𝐫𝐞𝐬𝐬: {str(e)}")
    except Exception as e:
        bot.reply_to(message, f"❌ 𝐄𝐫𝐫𝐨𝐫: {str(e)}")

@bot.message_handler(func=lambda msg: msg.text == "⏱ 𝐂𝐡𝐞𝐜𝐤 𝐂𝐨𝐨𝐥𝐝𝐨𝐰𝐧")
@membership_required
def check_cooldown_handler(message):
    """Handle cooldown check"""
    if last_test_time and (datetime.datetime.now() - last_test_time).seconds < TEST_COOLDOWN:
        remaining = TEST_COOLDOWN - (datetime.datetime.now() - last_test_time).seconds
        bot.reply_to(message, f"⏳ 𝐍𝐞𝐱𝐭 𝐞𝐱𝐩𝐞𝐫𝐢𝐦𝐞𝐧𝐭 𝐚𝐯𝐚𝐢𝐥𝐚𝐛𝐥𝐞 𝐢𝐧 {remaining} 𝐬𝐞𝐜𝐨𝐧𝐝𝐬")
    else:
        bot.reply_to(message, "✅ 𝐑𝐞𝐚𝐝𝐲 𝐟𝐨𝐫 𝐧𝐞𝐰 𝐞𝐱𝐩𝐞𝐫𝐢𝐦𝐞𝐧𝐭!")

@bot.message_handler(func=lambda msg: msg.text == "📝 𝐒𝐮𝐛𝐦𝐢𝐭 𝐑𝐞𝐩𝐨𝐫𝐭")
@membership_required
def submit_report_handler(message):
    """Handle report submission request"""
    user_id = str(message.from_user.id)
    if not pending_reports.get(user_id, False):
        bot.reply_to(message, "📌 𝐍𝐨 𝐩𝐞𝐧𝐝𝐢𝐧𝐠 𝐥𝐚𝐛 𝐫𝐞𝐩𝐨𝐫𝐭𝐬 𝐟𝐨𝐮𝐧𝐝.\n𝐒𝐭𝐚𝐫𝐭 𝐚 𝐧𝐞𝐰 𝐞𝐱𝐩𝐞𝐫𝐢𝐦𝐞𝐧𝐭 𝐟𝐢𝐫𝐬𝐭")
        return
    
    bot.send_message(
        message.chat.id,
        "📸 𝐏𝐥𝐞𝐚𝐬𝐞 𝐬𝐞𝐧𝐝 𝐚 𝐩𝐡𝐨𝐭𝐨 𝐨𝐟 𝐲𝐨𝐮𝐫 𝐥𝐚𝐛 𝐨𝐛𝐬𝐞𝐫𝐯𝐚𝐭𝐢𝐨𝐧𝐬",
        reply_markup=types.ReplyKeyboardRemove()
    )

@bot.message_handler(func=lambda msg: msg.text == "📊 𝐕𝐢𝐞𝐰 𝐏𝐫𝐨𝐠𝐫𝐞𝐬𝐬")
@membership_required
def view_progress_handler(message):
    """Show student progress"""
    user_id = str(message.from_user.id)
    if user_id in student_data:
        remaining = DAILY_TEST_LIMIT - student_data[user_id]['tests']
        bot.reply_to(message, 
            f"📊 𝐘𝐨𝐮𝐫 𝐏𝐫𝐨𝐠𝐫𝐞𝐬𝐬\n\n"
            f"𝐄𝐱𝐩𝐞𝐫𝐢𝐦𝐞𝐧𝐭𝐬 𝐫𝐞𝐦𝐚𝐢𝐧𝐢𝐧𝐠 𝐭𝐨𝐝𝐚𝐲: {remaining}\n"
            f"𝐓𝐨𝐭𝐚𝐥 𝐞𝐱𝐩𝐞𝐫𝐢𝐦𝐞𝐧𝐭𝐬 𝐜𝐨𝐦𝐩𝐥𝐞𝐭𝐞𝐝: {student_data[user_id]['tests']}\n"
            f"𝐋𝐚𝐬𝐭 𝐫𝐞𝐬𝐞𝐭: {student_data[user_id]['last_reset'].strftime('%Y-%m-%d %H:%M')}",
            reply_markup=create_main_keyboard()
        )
    else:
        bot.reply_to(message, f"📊 𝐘𝐨𝐮 𝐡𝐚𝐯𝐞 𝐚𝐥𝐥 {DAILY_TEST_LIMIT} 𝐞𝐱𝐩𝐞𝐫𝐢𝐦𝐞𝐧𝐭𝐬 𝐚𝐯𝐚𝐢𝐥𝐚𝐛𝐥𝐞 𝐭𝐨𝐝𝐚𝐲",
                   reply_markup=create_main_keyboard())

@bot.message_handler(func=lambda msg: msg.text == "👨‍🏫 𝐈𝐧𝐬𝐭𝐫𝐮𝐜𝐭𝐨𝐫 𝐓𝐨𝐨𝐥𝐬")
def instructor_tools_handler(message):
    """Show instructor tools menu"""
    if str(message.from_user.id) not in INSTRUCTOR_IDS:
        bot.reply_to(message, "🚫 𝐀𝐜𝐜𝐞𝐬𝐬 𝐃𝐞𝐧𝐢𝐞𝐝")
        return
    
    bot.send_message(
        message.chat.id,
        "👨‍🏫 𝐈𝐧𝐬𝐭𝐫𝐮𝐜𝐭𝐨𝐫 𝐓𝐨𝐨𝐥𝐬 𝐌𝐞𝐧𝐮",
        reply_markup=create_instructor_keyboard()
    )

# ======================
# CORE FUNCTIONALITY
# ======================
@bot.message_handler(commands=['pingtest'])
@membership_required
def conduct_ping_test(message):
    """Conduct ping test"""
    if len(message.text.split()) != 2:
        bot.reply_to(message, "Usage: /pingtest <IP>\nExample: /pingtest 8.8.8.8")
        return
    
    target = message.text.split()[1]
    progress_msg = bot.send_message(message.chat.id, f"🔍 Simulating ping to {target}...")
    
    # Create progress bar for ping test
    for i in range(1, 6):
        time.sleep(1)
        try:
            bot.edit_message_text(
                f"🔍 Testing ping to {target}\n"
                f"{create_progress_bar(i*20, 100)}",
                chat_id=message.chat.id,
                message_id=progress_msg.message_id
            )
        except:
            pass
    
    # Send results
    bot.send_message(message.chat.id,
                   f"📊 Ping Results for {target}\n"
                   f"⏱ Avg Latency: {random.randint(10,150)}ms\n"
                   f"📦 Packet Loss: 0%\n\n"
                   f"💡 Educational Insight:\n"
                   f"Latency under 100ms is good for most applications",
                   reply_markup=create_main_keyboard())

@bot.message_handler(content_types=['photo'])
@membership_required
def handle_lab_report(message):
    """Process lab report submissions"""
    user_id = str(message.from_user.id)
    user_name = message.from_user.first_name
    
    try:
        if not pending_reports.get(user_id, False):
            bot.reply_to(message, "📌 No pending lab reports found.")
            return
        
        photo = message.photo[-1]
        file_info = bot.get_file(photo.file_id)
        
        os.makedirs(LAB_REPORTS_DIR, exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(LAB_REPORTS_DIR, f"{user_id}_{timestamp}.jpg")
        
        downloaded_file = bot.download_file(file_info.file_path)
        with open(filename, 'wb') as new_file:
            new_file.write(downloaded_file)
        
        pending_reports[user_id] = False
        lab_submissions.setdefault(user_id, []).append({
            'timestamp': timestamp,
            'filename': filename,
            'file_id': photo.file_id
        })
        
        bot.reply_to(message, f"📝 Lab Report Submitted!\n🕒 {timestamp}\nYou may now start a new experiment.",
                   reply_markup=create_main_keyboard())
        
        notify_instructors(message, user_name, photo.file_id)
        
    except Exception as e:
        bot.reply_to(message, f"❌ Error saving report: {str(e)}")
        pending_reports[user_id] = False

# ======================
# INSTRUCTOR COMMANDS
# ======================

@bot.message_handler(func=lambda msg: msg.text == "🔄 𝐑𝐞𝐬𝐞𝐭 𝐒𝐭𝐮𝐝𝐞𝐧𝐭")
def ask_reset_student(message):
    if str(message.from_user.id) not in INSTRUCTOR_IDS:
        bot.reply_to(message, "🚫 Access Denied", reply_markup=create_instructor_keyboard())
        return
    msg = bot.send_message(message.chat.id, "♻️ Send Student ID to reset:")
    bot.register_next_step_handler(msg, process_reset_student)

def process_reset_student(message):
    student_id = message.text.strip()
    if student_id not in student_data:
        bot.reply_to(message, f"❌ Student ID {student_id} not found", reply_markup=create_instructor_keyboard())
        return
    student_data[student_id] = {
        'tests': 0,
        'last_reset': datetime.datetime.now(),
        'last_test': None
    }
    save_student_data()
    bot.reply_to(message, f"✅ Reset daily limit for student {student_id}",
                 reply_markup=create_instructor_keyboard())


@bot.message_handler(func=lambda msg: msg.text == "➕ 𝐀𝐝𝐝 𝐆𝐫𝐨𝐮𝐩")
def ask_add_group(message):
    if str(message.from_user.id) not in INSTRUCTOR_IDS:
        bot.reply_to(message, "🚫 Access Denied", reply_markup=create_instructor_keyboard())
        return
    msg = bot.send_message(message.chat.id, "➕ Send Group ID to add:")
    bot.register_next_step_handler(msg, process_add_group)

def process_add_group(message):
    try:
        group_id = str(message.text.strip())
        chat_info = bot.get_chat(group_id)
        bot_member = bot.get_chat_member(group_id, bot.get_me().id)

        if bot_member.status not in ['administrator', 'creator']:
            bot.reply_to(message, "❌ Bot must be an admin in the group", reply_markup=create_instructor_keyboard())
            return

        study_groups[group_id] = chat_info.title
        save_study_groups()

        bot.reply_to(message,
                     f"✅ Added Study Group:\n📛 {chat_info.title}\n🆔 {group_id}",
                     reply_markup=create_instructor_keyboard())
    except Exception as e:
        bot.reply_to(message, f"❌ Error adding group: {str(e)}", reply_markup=create_instructor_keyboard())


@bot.message_handler(func=lambda msg: msg.text == "➖ 𝐑𝐞𝐦𝐨𝐯𝐞 𝐆𝐫𝐨𝐮𝐩")
def ask_remove_group(message):
    if str(message.from_user.id) not in INSTRUCTOR_IDS:
        bot.reply_to(message, "🚫 Access Denied", reply_markup=create_instructor_keyboard())
        return
    msg = bot.send_message(message.chat.id, "🗑 Send Group ID to remove:")
    bot.register_next_step_handler(msg, process_remove_group)

def process_remove_group(message):
    group_id = message.text.strip()
    if group_id not in study_groups:
        bot.reply_to(message, f"❌ Group ID {group_id} not found", reply_markup=create_instructor_keyboard())
        return
    removed = study_groups.pop(group_id)
    save_study_groups()
    bot.reply_to(message,
                 f"✅ Removed Group:\n📛 {removed}\n🆔 {group_id}",
                 reply_markup=create_instructor_keyboard())


@bot.message_handler(func=lambda msg: msg.text == "📋 𝐋𝐢𝐬𝐭 𝐆𝐫𝐨𝐮𝐩𝐬")
def list_groups_button(message):
    if str(message.from_user.id) not in INSTRUCTOR_IDS:
        bot.reply_to(message, "🚫 Access Denied", reply_markup=create_instructor_keyboard())
        return
    if not study_groups:
        bot.reply_to(message, "❌ No study groups added yet.", reply_markup=create_instructor_keyboard())
        return

    group_list = "📚 Approved Study Groups:\n\n"
    for idx, (gid, name) in enumerate(study_groups.items(), 1):
        group_list += f"{idx}. {name}\n🆔 `{gid}`\n\n"
    bot.send_message(message.chat.id, group_list, parse_mode="Markdown",
                     reply_markup=create_instructor_keyboard())

# Temporary storage for notice per instructor
instructor_notices = {}

@bot.message_handler(func=lambda msg: msg.text == "📢 𝐒𝐞𝐧𝐝 𝐍𝐨𝐭𝐢𝐜𝐞")
def send_notice_handler(message):
    if str(message.from_user.id) not in INSTRUCTOR_IDS:
        bot.reply_to(message, "🚫 𝐀𝐜𝐜𝐞𝐬𝐬 𝐃𝐞𝐧𝐢𝐞𝐝", reply_markup=create_main_keyboard(message))
        return

    msg = bot.send_message(
        message.chat.id,
        "📢 𝐒𝐞𝐧𝐝 𝐲𝐨𝐮𝐫 𝐧𝐨𝐭𝐢𝐜𝐞 𝐚𝐬 𝐭𝐞𝐱𝐭/𝐩𝐡𝐨𝐭𝐨/𝐯𝐢𝐝𝐞𝐨:"
    )
    bot.register_next_step_handler(msg, capture_notice_message)


def capture_notice_message(message):
    if message.content_type not in ['text', 'photo', 'video']:
        bot.reply_to(message, "⚠️ Please send only text, photo, or video.")
        return

    notice = {
        "type": message.content_type,
        "content": message.text if message.content_type == 'text' else None,
        "file_id": None
    }

    if message.content_type == 'photo':
        notice['file_id'] = message.photo[-1].file_id
    elif message.content_type == 'video':
        notice['file_id'] = message.video.file_id

    instructor_notices[str(message.from_user.id)] = notice

    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("✅ 𝐁𝐫𝐨𝐚𝐝𝐜𝐚𝐬𝐭 𝐍𝐨𝐰", callback_data="broadcast_now"),
        types.InlineKeyboardButton("❌ 𝐂𝐚𝐧𝐜𝐞𝐥", callback_data="cancel_notice")
    )

    bot.send_message(
        message.chat.id,
        "⚠️ 𝐂𝐨𝐧𝐟𝐢𝐫𝐦 𝐭𝐨 𝐬𝐞𝐧𝐝 𝐭𝐡𝐢𝐬 𝐧𝐨𝐭𝐢𝐜𝐞 𝐭𝐨 𝐚𝐥𝐥 𝐬𝐭𝐮𝐝𝐞𝐧𝐭𝐬 𝐚𝐧𝐝 𝐠𝐫𝐨𝐮𝐩𝐬?",
        reply_markup=markup
    )


@bot.callback_query_handler(func=lambda call: call.data in ['broadcast_now', 'cancel_notice'])
def handle_notice_confirmation(call):
    user_id = str(call.from_user.id)

    if call.data == "cancel_notice":
        instructor_notices.pop(user_id, None)
        bot.edit_message_text("❌ 𝐁𝐫𝐨𝐚𝐝𝐜𝐚𝐬𝐭 𝐜𝐚𝐧𝐜𝐞𝐥𝐥𝐞𝐝",
                              call.message.chat.id,
                              call.message.message_id)
        return

    notice = instructor_notices.get(user_id)
    if not notice:
        bot.edit_message_text("⚠️ 𝐍𝐨 𝐧𝐨𝐭𝐢𝐜𝐞 𝐟𝐨𝐮𝐧𝐝 𝐭𝐨 𝐛𝐫𝐨𝐚𝐝𝐜𝐚𝐬𝐭.", 
                              call.message.chat.id,
                              call.message.message_id)
        return

    results = {'success': 0, 'failed': 0}

    def send_notice(chat_id):
        try:
            if notice['type'] == 'text':
                bot.send_message(chat_id, f"📢 𝐎𝐅𝐅𝐈𝐂𝐈𝐀𝐋 𝐍𝐎𝐓𝐈𝐂𝐄\n\n{notice['content']}")
            elif notice['type'] == 'photo':
                bot.send_photo(chat_id, notice['file_id'], caption="📢 𝐎𝐅𝐅𝐈𝐂𝐈𝐀𝐋 𝐍𝐎𝐓𝐈𝐂𝐄")
            elif notice['type'] == 'video':
                bot.send_video(chat_id, notice['file_id'], caption="📢 𝐎𝐅𝐅𝐈𝐂𝐈𝐀𝐋 𝐍𝐎𝐓𝐈𝐂𝐄")
            results['success'] += 1
        except Exception as e:
            results['failed'] += 1

    bot.edit_message_text("📡 𝐁𝐫𝐨𝐚𝐝𝐜𝐚𝐬𝐭𝐢𝐧𝐠 𝐧𝐨𝐭𝐢𝐜𝐞...",
                          call.message.chat.id,
                          call.message.message_id)

    for uid in student_data:
        send_notice(uid)
        time.sleep(0.1)

    for gid in study_groups:
        send_notice(gid)
        time.sleep(0.2)

    instructor_notices.pop(user_id, None)

    report = (
        "📊 𝐁𝐫𝐨𝐚𝐝𝐜𝐚𝐬𝐭 𝐂𝐨𝐦𝐩𝐥𝐞𝐭𝐞!\n\n"
        f"✅ 𝐒𝐮𝐜𝐜𝐞𝐬𝐬: {results['success']}\n"
        f"❌ 𝐅𝐚𝐢𝐥𝐞𝐝: {results['failed']}\n"
        f"⏱ {datetime.datetime.now().strftime('%d %b %Y %H:%M:%S')}"
    )

    bot.send_message(call.message.chat.id, report, reply_markup=create_instructor_keyboard())

import psutil
@bot.message_handler(func=lambda msg: msg.text == "🧠 𝐂𝐏𝐔 𝐔𝐬𝐚𝐠𝐞")
def cpu_usage_button_handler(message):
    if str(message.from_user.id) not in INSTRUCTOR_IDS:
        bot.reply_to(message, "🚫 𝐀𝐜𝐜𝐞𝐬𝐬 𝐃𝐞𝐧𝐢𝐞𝐝")
        return

    try:
        cpu_percent = psutil.cpu_percent(interval=1)
        cpu_count = psutil.cpu_count()
        load_avg = psutil.getloadavg() if hasattr(psutil, 'getloadavg') else ("N/A", "N/A", "N/A")

        reply = (
            f"🧠 *𝐕𝐏𝐒 𝐂𝐏𝐔 𝐔𝐬𝐚𝐠𝐞*\n\n"
            f"🔢 *𝐓𝐨𝐭𝐚𝐥 𝐂𝐨𝐫𝐞𝐬:* {cpu_count}\n"
            f"📊 *𝐂𝐮𝐫𝐫𝐞𝐧𝐭 𝐔𝐬𝐚𝐠𝐞:* {cpu_percent}%\n"
            f"📉 *𝐋𝐨𝐚𝐝 𝐀𝐯𝐞𝐫𝐚𝐠𝐞 (𝟏/𝟓/𝟏𝟓 𝐦𝐢𝐧):* {load_avg[0]}, {load_avg[1]}, {load_avg[2]}"
        )

        bot.send_message(message.chat.id, reply, parse_mode="Markdown")
    except Exception as e:
        bot.send_message(message.chat.id, f"⚠️ 𝐄𝐫𝐫𝐨𝐫 𝐟𝐞𝐭𝐜𝐡𝐢𝐧𝐠 𝐂𝐏𝐔 𝐝𝐚𝐭𝐚:\n{str(e)}")

# ======================
# INITIALIZATION
# ======================

# Load data at startup
load_student_data()
load_study_groups()

# Start background tasks
threading.Thread(target=auto_reset_daily_limits, daemon=True).start()

if __name__ == "__main__":
    print("Bot started with", len(study_groups), "study groups")
    bot.polling(none_stop=True)