import discord
from discord.ext import commands, tasks
import os
import threading
from datetime import datetime, date
from http.server import HTTPServer, BaseHTTPRequestHandler

# ==============================================================================
# 1. BACKGROUND WEB SERVER (Keep-Alive for Render)
# ==============================================================================
class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(b"Absent Bot is online and running 24/7!")

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), SimpleHTTPRequestHandler)
    server.serve_forever()

threading.Thread(target=run_web_server, daemon=True).start()

# ==============================================================================
# 2. DISCORD BOT SETUP & CONFIGURATION
# ==============================================================================
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# --- Admin Lists by Rank ---
PRESIDENT_ADMINS = {
    723800522947166218: "🔮",  # starfaii88 (President)
}

VP_ADMINS = {
    1253326811882979329: "💖",  # sweet_manis_ (Vice President)
    1400511932037070921: "🌸",  # aangel1325 (Vice President)
    1455238315405217893: "☻",    # tequila_qyla. (Vice President)
    626874233888440330: "🎀",  # inesfgguerreiro (Vice President - Red Ribbon)
    967001330361192520: "🍑",  # just2_peach (Vice President)
    1568673840744104136: "🦄",  # blossiq1212 (Vice President)
}

EXECUTIVE_ADMINS = {
    1527320411082068018: "🥃",  # fanaem00 (Executive)
    753681817776947282: "🐸",  # renzoor145 (Executive)
}

FLOATER_ADMINS = {
    741251553452752976: "🍙",  # cyan143 (Floater)
    795323523132293160: "💐",  # gwendita_zai (Floater)
    1332012068798206073: "😘",  # lincy_2003_73773 (Floater)
    848524697205342278: "🐥",  # maxx_712 (Floater)
    837199088922787850: "🌞",  # smolsanson (Floater)
    1322558573699403918: "⭐",  # fthestarss (Floater)
}

ALL_ADMINS = {**PRESIDENT_ADMINS, **VP_ADMINS, **EXECUTIVE_ADMINS, **FLOATER_ADMINS}
VP_AND_EXEC = {**VP_ADMINS, **EXECUTIVE_ADMINS}

# --- Official Shift Partners Mapping ---
SHIFT_PARTNERS = {
    "12PM-2PM": {"💖": "🔮", "🔮": "💖"},
    "6PM-8PM": {"🎀": "🐸", "🐸": "🎀"},
    "8PM-10PM": {"🥃": "🍑", "🍑": "🥃"},
}

# --- Time Slot Sorting Order ---
TIME_ORDER = {
    "12PM-2PM": 1,
    "2PM-4PM": 2,
    "4PM-6PM": 3,
    "6PM-8PM": 4,
    "8PM-10PM": 5,
    "10PM-12AM": 6
}

# --- Channel ID (Absent Info Channel) ---
ABSENT_CHANNEL_ID = 1372224968535834635

# --- Global Trackers ---
absent_message_id = None
absent_records = {}
active_covers_tracker = {}
bento_tracker = {}

MONTH_MAP = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12
}

def parse_date_str(date_str):
    try:
        parts = date_str.strip().split()
        if len(parts) >= 3:
            day = int(parts[0])
            month_str = parts[1][:3].upper()
            year = int(parts[2])
            month = MONTH_MAP.get(month_str, 1)
            return date(year, month, day)
    except Exception:
        pass
    return None

def get_next_available_id():
    existing_ids = set(absent_records.keys())
    candidate = 1
    while candidate in existing_ids:
        candidate += 1
    return candidate

@bot.event
async def on_ready():
    print(f"Absent Info Bot connected as {bot.user}")
    if not auto_cleanup_task.is_running():
        auto_cleanup_task.start()
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} slash command(s).")
    except Exception as e:
        print(f"Failed to sync slash commands: {e}")

# ==============================================================================
# 3. BACKGROUND TASK: AUTO-DELETE PAST DATES
# ==============================================================================
@tasks.loop(hours=1)
async def auto_cleanup_task():
    global absent_records
    if not absent_records:
        return
    
    today = date.today()
    expired_ids = []
    
    for rid, data in absent_records.items():
        parsed_date = parse_date_str(data["date"])
        if parsed_date and parsed_date < today:
            expired_ids.append(rid)
            
    if expired_ids:
        for rid in expired_ids:
            absent_records.pop(rid, None)
            active_covers_tracker.pop(rid, None)
                
        for guild in bot.guilds:
            channel = guild.get_channel(ABSENT_CHANNEL_ID)
            if channel:
                await update_absent_board(guild)
                break

# ==============================================================================
# 4. BEAUTIFIED ABSENT BOARD RENDERER (EMBED DESIGN)
# ==============================================================================
async def update_absent_board(guild):
    global absent_message_id
    channel = guild.get_channel(ABSENT_CHANNEL_ID)
    if not channel:
        return

    # Warna Embed yang elegan (Dark Gold / Warm Amber)
    embed = discord.Embed(
        title="🌟  P.I.Z.Z.I.N  •  ABSENT & COVER SCHEDULE", 
        color=discord.Color.from_rgb(255, 193, 7)
    )
    
    # Bahagian 1: Jadual Absent & Cover yang disusun rapi
    if not absent_records:
        schedule_text = "```yaml\n✨ No upcoming leave or absent records. Great job everyone!\n```"
    else:
        dates_group = {}
        for rid, data in sorted(absent_records.items()):
            d = data["date"]
            if d not in dates_group:
                dates_group[d] = {}
            t = data["time"]
            if t not in dates_group[d]:
                dates_group[d][t] = []
            dates_group[d][t].append((rid, data))
            
        schedule_lines = []
        for date_str in sorted(dates_group.keys(), key=lambda x: (parse_date_str(x) or date.max)):
            schedule_lines.append(f"📌 **[{date_str}]**")
            
            sorted_times = sorted(dates_group[date_str].keys(), key=lambda x: TIME_ORDER.get(x, 99))
            
            for time_slot in sorted_times:
                items = dates_group[date_str][time_slot]
                
                record_ids = [str(item[0]) for item in items]
                ids_str = ", ".join(record_ids)
                
                absent_emojis = []
                cover_emojis = []
                
                for _, data in items:
                    ae = data['absent_emoji']
                    for part in ae.split("&"):
                        p_clean = part.strip()
                        if p_clean and p_clean not in absent_emojis:
                            absent_emojis.append(p_clean)
                            
                    covers = data.get('cover_emoji', [])
                    if not isinstance(covers, list):
                        covers = [covers] if covers else []
                    for c in covers:
                        if c not in cover_emojis:
                            cover_emojis.append(c)

                emoji_display = " & ".join(absent_emojis)
                cover_display = f"【{' & '.join(cover_emojis)}】" if cover_emojis else "【 ⏳ Looking for cover 】"
                
                # Menggunakan blockquote (>) supaya nampak terletak dalam kotak/jalur kemas
                schedule_lines.append(f"> ` ID: {ids_str} ` {emoji_display}  ──►  **{time_slot}**  {cover_display}")
            
            schedule_lines.append("") # Jarak kosong antara tarikh
            
        schedule_text = "\n".join(schedule_lines)

    embed.add_field(name="📋 ACTIVE SHIFT STATUS", value=schedule_text, inline=False)

    # Bahagian 2: Bento Leaderboard yang lebih teratur
    if bento_tracker:
        bento_list = []
        for uid, info in bento_tracker.items():
            if info["count"] <= 0 and not info["logs"]:
                continue
            emoji = VP_AND_EXEC.get(uid, "🍱")
            count = info["count"]
            paid_status = "✅ `Paid`" if info["paid"] else "❌ `Unpaid`"
            
            bento_item = f"• {emoji} <@{uid}>  •  **{count}** Bento(s)  {paid_status}"
            if info["logs"]:
                logs_str = " • ".join(info["logs"])
                bento_item += f"\n   └ 🕒 *{logs_str}*"
            bento_list.append(bento_item)
            
        bento_text = "\n".join(bento_list) if bento_list else "_No Bento rewards claimed yet._"
    else:
        bento_text = "_No Bento rewards claimed yet._"
        
    embed.add_field(name="🍱 BENTO REWARDS LEADERBOARD (VP & Exec)", value=bento_text, inline=False)
    
    # Footer yang ringkas & profesional
    embed.set_footer(text="💡 Commands: /absent  |  /cover  |  /pay_bento  |  /clear_paid_bento  |  /delete_record")

    if absent_message_id:
        try:
            msg = await channel.fetch_message(absent_message_id)
            await msg.edit(embed=embed)
            return
        except discord.NotFound:
            pass
            
    msg = await channel.send(embed=embed)
    absent_message_id = msg.id

# ==============================================================================
# 5. SLASH COMMANDS
# ==============================================================================
@bot.tree.command(name="absent", description="Report leave/absence for yourself or another admin")
async def absent(
    interaction: discord.Interaction, 
    date: str, 
    time_slot: str, 
    target_admin: discord.Member = None
):
    await interaction.response.defer(ephemeral=True)
    user_id = interaction.user.id
    
    if user_id not in ALL_ADMINS:
        await interaction.followup.send("❌ You are not registered as an admin.", ephemeral=True)
        return
        
    admin_to_record = target_admin.id if target_admin else user_id
    
    if admin_to_record not in ALL_ADMINS:
        await interaction.followup.send("❌ The specified user is not a registered admin.", ephemeral=True)
        return
        
    my_emoji = ALL_ADMINS[admin_to_record]
    target_date = date.upper()
    target_time = time_slot.upper()
    
    existing_record_id = None
    for rid, data in absent_records.items():
        if data["date"] == target_date and data["time"] == target_time:
            existing_record_id = rid
            break

    if existing_record_id:
        current_data = absent_records[existing_record_id]
        current_emojis = [e.strip() for e in current_data['absent_emoji'].split('&')]
        if my_emoji not in current_emojis:
            current_emojis.append(my_emoji)
            current_data['absent_emoji'] = " & ".join(current_emojis)
            
        target_name = target_admin.display_name if target_admin else "yourself"
        await interaction.followup.send(f"✅ Added {target_name} to existing shift record (ID: `{existing_record_id}`).", ephemeral=True)
        await update_absent_board(interaction.guild)
        return

    current_id = get_next_available_id()
    
    absent_records[current_id] = {
        "date": target_date,
        "time": target_time,
        "absent_emoji": my_emoji,
        "cover_emoji": []
    }
    
    target_name = target_admin.display_name if target_admin else "yourself"
    await interaction.followup.send(f"✅ Absent record added for {target_name}! (Record ID: `{current_id}`)", ephemeral=True)
    await update_absent_board(interaction.guild)

@bot.tree.command(name="edit_record", description="Edit an existing absent record's date or time slot")
async def edit_record(
    interaction: discord.Interaction, 
    record_id: int, 
    new_date: str = None, 
    new_time_slot: str = None
):
    await interaction.response.defer(ephemeral=True)
    user_id = interaction.user.id
    
    if user_id not in ALL_ADMINS:
        await interaction.followup.send("❌ You are not registered as an admin.", ephemeral=True)
        return
        
    if record_id not in absent_records:
        await interaction.followup.send("❌ Invalid record ID!", ephemeral=True)
        return
        
    if not new_date and not new_time_slot:
        await interaction.followup.send("❌ Please provide a new date or time slot to update.", ephemeral=True)
        return
        
    record_data = absent_records[record_id]
    old_date = record_data["date"]
    old_time = record_data["time"]
    
    changes = []
    if new_date:
        record_data["date"] = new_date.upper()
        changes.append(f"Date -> {new_date.upper()}")
    if new_time_slot:
        record_data["time"] = new_time_slot.upper()
        changes.append(f"Time -> {new_time_slot.upper()}")
        
    new_date_str = record_data["date"]
    new_time_str = record_data["time"]
    new_log = f"{new_date_str} ({new_time_str})"
    old_log = f"{old_date} ({old_time})"
    
    if record_id in active_covers_tracker:
        for admin_id, logged_msg in list(active_covers_tracker[record_id].items()):
            if admin_id in bento_tracker and old_log in bento_tracker[admin_id]["logs"]:
                bento_tracker[admin_id]["logs"].remove(old_log)
                bento_tracker[admin_id]["logs"].append(new_log)
                active_covers_tracker[record_id][admin_id] = new_log

    await interaction.followup.send(f"✏️ Record ID `{record_id}` updated! ({', '.join(changes)})", ephemeral=True)
    await update_absent_board(interaction.guild)

@bot.tree.command(name="cover", description="Cover a shift, change covering admin, or remove cover status")
@discord.app_commands.choices(action=[
    discord.app_commands.Choice(name="Cover Shift (Assign/Update)", value="cover"),
    discord.app_commands.Choice(name="Remove Cover Status (Un-cover)", value="uncover")
])
async def cover(
    interaction: discord.Interaction, 
    record_id: int, 
    action: str = None, 
    target_admin: discord.Member = None
):
    await interaction.response.defer(ephemeral=True)
    user_id = interaction.user.id
    
    if user_id not in ALL_ADMINS:
        await interaction.followup.send("❌ You are not registered as an admin.", ephemeral=True)
        return
        
    if record_id not in absent_records:
        await interaction.followup.send("❌ Invalid record ID!", ephemeral=True)
        return
        
    chosen_action = action if action else "cover"
    covering_admin_id = target_admin.id if target_admin else user_id
    
    if covering_admin_id not in ALL_ADMINS:
        await interaction.followup.send("❌ The specified covering user is not a registered admin.", ephemeral=True)
        return
        
    my_emoji = ALL_ADMINS[covering_admin_id]
    record_data = absent_records[record_id]
    shift_date = record_data["date"]
    shift_time = record_data["time"]
    log_entry = f"{shift_date} ({shift_time})"

    if chosen_action == "uncover":
        covers = absent_records[record_id].get("cover_emoji", [])
        if not isinstance(covers, list):
            covers = [covers] if covers else []
            
        if my_emoji not in covers:
            await interaction.followup.send(f"⚠️ Record ID `{record_id}` does not have a cover assigned by this admin.", ephemeral=True)
            return
            
        covers.remove(my_emoji)
        absent_records[record_id]["cover_emoji"] = covers
        
        if record_id in active_covers_tracker and covering_admin_id in active_covers_tracker[record_id]:
            tracked_log = active_covers_tracker[record_id][covering_admin_id]
            if covering_admin_id in bento_tracker:
                if bento_tracker[covering_admin_id]["count"] > 0:
                    bento_tracker[covering_admin_id]["count"] -= 1
                if tracked_log in bento_tracker[covering_admin_id]["logs"]:
                    bento_tracker[covering_admin_id]["logs"].remove(tracked_log)
            del active_covers_tracker[record_id][covering_admin_id]
            
        await interaction.followup.send(f"🔄 Cover status removed for {my_emoji} from Record ID `{record_id}`.", ephemeral=True)
        await update_absent_board(interaction.guild)
        return

    covers = absent_records[record_id].get("cover_emoji", [])
    if not isinstance(covers, list):
        covers = [covers] if covers else []

    if len(covers) >= 2 and my_emoji not in covers:
        await interaction.followup.send("❌ This shift already has the maximum of 2 covering admins!", ephemeral=True)
        return

    is_vp_or_exec = covering_admin_id in VP_AND_EXEC
    absent_emoji_str = record_data["absent_emoji"]
    
    is_partner_cover = False
    if shift_time in SHIFT_PARTNERS:
        partner_map = SHIFT_PARTNERS[shift_time]
        for ae in absent_emoji_str.split("&"):
            ae_clean = ae.strip()
            if partner_map.get(ae_clean) == my_emoji:
                is_partner_cover = True
                break

    earned_bento = False
    if is_vp_or_exec and not is_partner_cover:
        if my_emoji not in covers:
            if covering_admin_id not in bento_tracker:
                bento_tracker[covering_admin_id] = {"count": 0, "logs": [], "paid": False}
            bento_tracker[covering_admin_id]["count"] += 1
            bento_tracker[covering_admin_id]["logs"].append(log_entry)
            
            if record_id not in active_covers_tracker:
                active_covers_tracker[record_id] = {}
            active_covers_tracker[record_id][covering_admin_id] = log_entry
            earned_bento = True

    if my_emoji not in covers:
        covers.append(my_emoji)
    absent_records[record_id]["cover_emoji"] = covers

    target_name = target_admin.display_name if target_admin else "You"

    if earned_bento:
        await interaction.followup.send(f"🍱 Congratulations! {target_name} covered this shift and earned 1 Bento 🍱.", ephemeral=True)
    elif is_partner_cover:
        await interaction.followup.send(f"🤝 Shift covered by partner {target_name}! (No Bento awarded for covering partners).", ephemeral=True)
    else:
        await interaction.followup.send(f"✅ {target_name} covered this shift!", ephemeral=True)
        
    await update_absent_board(interaction.guild)

@bot.tree.command(name="pay_bento", description="Mark an admin's Bento status as Paid")
async def pay_bento(interaction: discord.Interaction, target_admin: discord.Member):
    await interaction.response.defer(ephemeral=True)
    if interaction.user.id not in ALL_ADMINS:
        await interaction.followup.send("❌ You are not authorized.", ephemeral=True)
        return
        
    if target_admin.id not in bento_tracker:
        await interaction.followup.send(f"❌ {target_admin.display_name} has no Bento records.", ephemeral=True)
        return
        
    bento_tracker[target_admin.id]["paid"] = True
    await interaction.followup.send(f"✅ Marked Bento status for {target_admin.display_name} as **Paid**.", ephemeral=True)
    await update_absent_board(interaction.guild)

@bot.tree.command(name="clear_paid_bento", description="Clear/Remove admins whose Bento have been paid")
async def clear_paid_bento(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    if interaction.user.id not in ALL_ADMINS:
        await interaction.followup.send("❌ You are not authorized.", ephemeral=True)
        return
        
    paid_users = [uid for uid, info in bento_tracker.items() if info["paid"]]
    for uid in paid_users:
        del bento_tracker[uid]
        
    await interaction.followup.send(f"🧹 Cleared {len(paid_users)} paid Bento record(s) from the leaderboard.", ephemeral=True)
    await update_absent_board(interaction.guild)

@bot.tree.command(name="delete_record", description="Delete an absent record from the board without giving bentos")
async def delete_record(interaction: discord.Interaction, record_id: int):
    await interaction.response.defer(ephemeral=True)
    user_id = interaction.user.id
    
    if user_id not in ALL_ADMINS:
        await interaction.followup.send("❌ You are not registered as an admin.", ephemeral=True)
        return
        
    if record_id not in absent_records:
        await interaction.followup.send("❌ Invalid record ID!", ephemeral=True)
        return
        
    deleted_item = absent_records.pop(record_id)
    active_covers_tracker.pop(record_id, None)

    await interaction.followup.send(f"🗑️ Record ID `{record_id}` ({deleted_item['date']} - {deleted_item['time']}) deleted.", ephemeral=True)
    await update_absent_board(interaction.guild)

@bot.command()
async def setup_absent(ctx):
    if ctx.author.id in ALL_ADMINS:
        await update_absent_board(ctx.guild)
        try:
            await ctx.message.delete()
        except discord.Forbidden:
            pass

# ==============================================================================
# 5. RUN BOT (DIRECT TOKEN)
# ==============================================================================
bot.run(os.environ.get("DISCORD_TOKEN"))
