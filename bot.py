import discord
from discord.ext import commands
import os
import threading
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
    1455238315405217893: "☻",   # tequila_qyla. (Vice President)
    626874233888440330: "🎀",  # inesfgguerreiro (Vice President - Red Ribbon)
    967001330361192520: "🍑",  # just2_peach (Vice President)
    1384881169547530291: "🦄",  # blossiq12 (Vice President)
}

EXECUTIVE_ADMINS = {
    1527320411082068018: "🥃",  # fanaem00 (Executive)
    1322558573699403918: "⭐",  # fthestarss (Executive)
}

FLOATER_ADMINS = {
    741251553452752976: "🍙",  # cyan143 (Floater)
    795323523132293160: "💐",  # gwendita_zai (Floater)
    1332012068798206073: "😘",  # lincy_2003_73773 (Floater)
    848524697205342278: "🐥",  # maxx_712 (Floater)
    839186062240120833: "🐼",  # xpingux1 (Floater)
}

ALL_ADMINS = {**PRESIDENT_ADMINS, **VP_ADMINS, **EXECUTIVE_ADMINS, **FLOATER_ADMINS}
VP_AND_EXEC = {**VP_ADMINS, **EXECUTIVE_ADMINS}

# --- Official Shift Partners Mapping ---
SHIFT_PARTNERS = {
    "12PM-2PM": {"💖": "🔮", "🔮": "💖"},
    "6PM-8PM": {"🎀": "🥃", "🥃": "🎀"},
    "10PM-12AM": {"🦄": "⭐", "⭐": "🦄"},
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
bento_tracker = {}  # Tracks earned bentos: {user_id: count}
record_counter = 1

@bot.event
async def on_ready():
    print(f"Absent Info Bot connected as {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} slash command(s).")
    except Exception as e:
        print(f"Failed to sync slash commands: {e}")

# ==============================================================================
# 3. ABSENT BOARD RENDERER
# ==============================================================================
async def update_absent_board(guild):
    global absent_message_id
    channel = guild.get_channel(ABSENT_CHANNEL_ID)
    if not channel:
        return

    embed = discord.Embed(title="📋 ABSENT & COVER SHIFT INFO", color=discord.Color.gold())
    
    if not absent_records:
        embed.description = "No upcoming leave or absent records. Great job everyone!\n"
    else:
        dates_group = {}
        for rid, data in absent_records.items():
            d = data["date"]
            if d not in dates_group:
                dates_group[d] = {}
            t = data["time"]
            if t not in dates_group[d]:
                dates_group[d][t] = []
            dates_group[d][t].append((rid, data))
            
        text_content = ""
        for date_str in sorted(dates_group.keys()):
            text_content += f"\n**[{date_str}]**\n"
            
            sorted_times = sorted(dates_group[date_str].keys(), key=lambda x: TIME_ORDER.get(x, 99))
            
            for time_slot in sorted_times:
                items = dates_group[date_str][time_slot]
                
                paired_items = []
                single_items = list(items)
                
                if time_slot in SHIFT_PARTNERS and len(items) >= 2:
                    partner_map = SHIFT_PARTNERS[time_slot]
                    found_pair = False
                    for i in range(len(items)):
                        for j in range(i + 1, len(items)):
                            emoji_a = items[i][1]['absent_emoji']
                            emoji_b = items[j][1]['absent_emoji']
                            
                            if partner_map.get(emoji_a) == emoji_b:
                                paired_items = [items[i], items[j]]
                                single_items.remove(items[i])
                                single_items.remove(items[j])
                                found_pair = True
                                break
                        if found_pair:
                            break
                
                if paired_items:
                    ids_str = f"{paired_items[0][0]}, {paired_items[1][0]}"
                    emoji_display = f"{paired_items[0][1]['absent_emoji']} & {paired_items[1][1]['absent_emoji']}"
                    cover_status = paired_items[0][1]['cover_emoji'] or paired_items[1][1]['cover_emoji']
                    cover_display = f"【{cover_status}】" if cover_status else "【 】"
                    text_content += f"• (ID: `{ids_str}`) {emoji_display} ▷ {time_slot} {cover_display}\n"

                for rid, item in single_items:
                    cover_display = f"【{item['cover_emoji']}】" if item['cover_emoji'] else "【 】"
                    text_content += f"• (ID: `{rid}`) {item['absent_emoji']} ▷ {time_slot} {cover_display}\n"
                
        embed.description = text_content

    if bento_tracker:
        bento_list = []
        for uid, count in bento_tracker.items():
            emoji = VP_AND_EXEC.get(uid, "🍱")
            bento_list.append(f"{emoji} <@{uid}>: `{count}` Bento(s)")
        bento_text = "\n".join(bento_list)
    else:
        bento_text = "No Bento rewards claimed yet."
        
    embed.add_field(name="🍱 Bento Leaderboard (VP & Exec)", value=bento_text, inline=False)
    embed.set_footer(text="Use /absent | /cover | /edit_record | /delete_record")

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
# 4. SLASH COMMANDS (/absent, /cover, /edit_record, /delete_record)
# ==============================================================================
@bot.tree.command(name="absent", description="Report leave/absence for yourself or another admin")
async def absent(
    interaction: discord.Interaction, 
    date: str, 
    time_slot: str, 
    target_admin: discord.Member = None
):
    global record_counter
    user_id = interaction.user.id
    
    if user_id not in ALL_ADMINS:
        await interaction.response.send_message("❌ You are not registered as an admin.", ephemeral=True)
        return
        
    admin_to_record = target_admin.id if target_admin else user_id
    
    if admin_to_record not in ALL_ADMINS:
        await interaction.response.send_message("❌ The specified user is not a registered admin.", ephemeral=True)
        return
        
    my_emoji = ALL_ADMINS[admin_to_record]
    current_id = record_counter
    record_counter += 1
    
    absent_records[current_id] = {
        "date": date.upper(),
        "time": time_slot.upper(),
        "absent_emoji": my_emoji,
        "cover_emoji": None
    }
    
    target_name = target_admin.display_name if target_admin else "yourself"
    await interaction.response.send_message(f"✅ Absent record added for {target_name}! (Record ID: `{current_id}`)", ephemeral=True)
    await update_absent_board(interaction.guild)

@bot.tree.command(name="edit_record", description="Edit an existing absent record's date or time slot")
async def edit_record(
    interaction: discord.Interaction, 
    record_id: int, 
    new_date: str = None, 
    new_time_slot: str = None
):
    user_id = interaction.user.id
    
    if user_id not in ALL_ADMINS:
        await interaction.response.send_message("❌ You are not registered as an admin.", ephemeral=True)
        return
        
    if record_id not in absent_records:
        await interaction.response.send_message("❌ Invalid record ID!", ephemeral=True)
        return
        
    if not new_date and not new_time_slot:
        await interaction.response.send_message("❌ Please provide a new date or time slot to update.", ephemeral=True)
        return
        
    changes = []
    if new_date:
        absent_records[record_id]["date"] = new_date.upper()
        changes.append(f"Date -> {new_date.upper()}")
    if new_time_slot:
        absent_records[record_id]["time"] = new_time_slot.upper()
        changes.append(f"Time -> {new_time_slot.upper()}")
        
    await interaction.response.send_message(f"✏️ Record ID `{record_id}` updated! ({', '.join(changes)})", ephemeral=True)
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
    user_id = interaction.user.id
    
    if user_id not in ALL_ADMINS:
        await interaction.response.send_message("❌ You are not registered as an admin.", ephemeral=True)
        return
        
    if record_id not in absent_records:
        await interaction.response.send_message("❌ Invalid record ID!", ephemeral=True)
        return
        
    chosen_action = action if action else "cover"
    
    if chosen_action == "uncover":
        prev_cover_emoji = absent_records[record_id]["cover_emoji"]
        if not prev_cover_emoji:
            await interaction.response.send_message(f"⚠️ Record ID `{record_id}` doesn't have a cover assigned.", ephemeral=True)
            return
            
        covering_admin_id = target_admin.id if target_admin else user_id
        if covering_admin_id in bento_tracker and bento_tracker[covering_admin_id] > 0:
            bento_tracker[covering_admin_id] -= 1
            
        absent_records[record_id]["cover_emoji"] = None
        await interaction.response.send_message(f"🔄 Cover status removed from Record ID `{record_id}`.", ephemeral=True)
        await update_absent_board(interaction.guild)
        return

    covering_admin_id = target_admin.id if target_admin else user_id
    
    if covering_admin_id not in ALL_ADMINS:
        await interaction.response.send_message("❌ The specified covering user is not a registered admin.", ephemeral=True)
        return
        
    my_emoji = ALL_ADMINS[covering_admin_id]
    is_vp_or_exec = covering_admin_id in VP_AND_EXEC
    
    record_data = absent_records[record_id]
    shift_time = record_data["time"]
    absent_emoji = record_data["absent_emoji"]
    
    is_partner_cover = False
    if shift_time in SHIFT_PARTNERS:
        if absent_emoji in SHIFT_PARTNERS[shift_time]:
            partner_emoji = SHIFT_PARTNERS[shift_time][absent_emoji]
            if my_emoji == partner_emoji:
                is_partner_cover = True

    earned_bento = False
    if is_vp_or_exec and not is_partner_cover:
        bento_tracker[covering_admin_id] = bento_tracker.get(covering_admin_id, 0) + 1
        earned_bento = True

    absent_records[record_id]["cover_emoji"] = my_emoji
    target_name = target_admin.display_name if target_admin else "You"

    if earned_bento:
        await interaction.response.send_message(f"🍱 Congratulations! {target_name} covered this shift and earned 1 Bento 🍱.", ephemeral=True)
    elif is_partner_cover:
        await interaction.response.send_message(f"🤝 Shift covered by partner {target_name}! (No Bento awarded for covering partners).", ephemeral=True)
    else:
        await interaction.response.send_message(f"✅ {target_name} covered this shift!", ephemeral=True)
        
    await update_absent_board(interaction.guild)

@bot.tree.command(name="delete_record", description="Delete an absent record from the board without giving bentos")
async def delete_record(interaction: discord.Interaction, record_id: int):
    user_id = interaction.user.id
    
    if user_id not in ALL_ADMINS:
        await interaction.response.send_message("❌ You are not registered as an admin.", ephemeral=True)
        return
        
    if record_id not in absent_records:
        await interaction.response.send_message("❌ Invalid record ID!", ephemeral=True)
        return
        
    deleted_item = absent_records.pop(record_id)
    await interaction.response.send_message(f"🗑️ Record ID `{record_id}` ({deleted_item['date']} - {deleted_item['time']}) deleted.", ephemeral=True)
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
# 5. RUN BOT (UPDATED TOKEN)
# ==============================================================================
bot.run(os.environ.get("MTU2NjgyMDk1MDE5MDU5NjE2OQ.GPNGW6.3ytHEOL-ciSQk5gQnaf41q1Ghp_Kw90NhBIetA"))
