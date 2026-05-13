import discord
from discord.ext import commands, tasks
import aiosqlite
import datetime
import zoneinfo
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

MAIN_CHANNEL_ID = int(os.getenv("MAIN_CHANNEL_ID", "1504071059073405019"))
BOT_ID = os.getenv("BOT_ID")

# Setup bot
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# --- DATABASE SETUP ---
async def setup_db():
    async with aiosqlite.connect("dsa_tracker.db") as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                solved INTEGER DEFAULT 0
            )
        """)
        await db.commit()

# --- THE CUSTOM INPUT POP-UP (MODAL) ---
class CustomScoreModal(discord.ui.Modal, title='Enter Exact Score'):
    questions_solved = discord.ui.TextInput(
        label='How many questions did you solve?',
        placeholder='e.g., 6, 7, 12...',
        style=discord.TextStyle.short,
        required=True,
        max_length=3
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            points = int(self.questions_solved.value)
            if points < 0:
                await interaction.response.send_message("You can't solve negative questions! 🤨", ephemeral=True)
                return
        except ValueError:
            await interaction.response.send_message("Please enter a valid number! 🔢", ephemeral=True)
            return

        user_id = interaction.user.id

        # 1. Update Database and Fetch New Total
        async with aiosqlite.connect("dsa_tracker.db") as db:
            await db.execute("""
                INSERT INTO users (user_id, solved) VALUES (?, ?)
                ON CONFLICT(user_id) DO UPDATE SET solved = solved + ?
            """, (user_id, points, points))

            async with db.execute("SELECT solved FROM users WHERE user_id = ?", (user_id,)) as cursor:
                total_solved = (await cursor.fetchone())[0]

            await db.commit()

        # 2. Quiet confirmation to the user
        await interaction.response.send_message("Points successfully logged! 🚀", ephemeral=True)

        # 3. PUBLIC HYPE ANNOUNCEMENT!
        if points >= 15:
            public_msg = f"**GOD TIER!** <@{user_id}> just dropped an insane **{points}** questions! (Total: {total_solved})"
        elif points >= 8:
            public_msg = f"**BEAST MODE!** <@{user_id}> just crushed **{points}** questions! (Total: {total_solved})"
        elif points >= 5:
            public_msg = f"**LOCKED IN!** <@{user_id}> put away **{points}** questions! (Total: {total_solved})"
        else:
            public_msg = f"@{user_id} logged **{points}** questions! (Total: {total_solved})"

        # Sends it publicly to the group chat
        await interaction.channel.send(public_msg)

# --- THE POLL BUTTONS ---
class DSAPoll(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def update_score(self, interaction: discord.Interaction, points: int, custom_msg: str):
        user_id = interaction.user.id

        # 1. Update Database and Fetch New Total
        async with aiosqlite.connect("dsa_tracker.db") as db:
            await db.execute("""
                INSERT INTO users (user_id, solved) VALUES (?, ?)
                ON CONFLICT(user_id) DO UPDATE SET solved = solved + ?
            """, (user_id, points, points))

            async with db.execute("SELECT solved FROM users WHERE user_id = ?", (user_id,)) as cursor:
                total_solved = (await cursor.fetchone())[0]

            await db.commit()

        # 2. Quiet confirmation to the user who clicked
        await interaction.response.send_message(f"✅ Successfully logged {points} questions!", ephemeral=True)

        # 3. PUBLIC ANNOUNCEMENT (Preserving your exact if-else structure!)
        if points == 0:
            public_msg = f"<@{user_id}> is taking a rest day today. (Total: {total_solved})\n"
        elif points >= 5:
            public_msg = f"**LOCKED IN!** <@{user_id}> just crushed **{points}** questions! Almost as locked in as jyotirya. (Total: {total_solved})\n"
        else:
            public_msg = f"<@{user_id}> logged **{points}** questions! (Total: {total_solved})\n"

        # Sends it publicly to the group chat
        await interaction.channel.send(public_msg)

    # --- ROW 1 (The Mortals) ---
    @discord.ui.button(label="0 (Rest Day 😴)", style=discord.ButtonStyle.secondary, custom_id="btn_0", row=0)
    async def btn_0(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.update_score(interaction, 0, "Taking a break? No worries, rest up and come back stronger tomorrow! 🌱")

    @discord.ui.button(label="1 (Honest Work 🌾)", style=discord.ButtonStyle.primary, custom_id="btn_1", row=0)
    async def btn_1(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.update_score(interaction, 1, "1 exact question down! Keep that streak alive. 🐢")

    @discord.ui.button(label="2 (Getting There 🚶)", style=discord.ButtonStyle.primary, custom_id="btn_2", row=0)
    async def btn_2(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.update_score(interaction, 2, "2 exact questions! Great job today.")

    @discord.ui.button(label="3 (On a Roll 🎳)", style=discord.ButtonStyle.success, custom_id="btn_3", row=0)
    async def btn_3(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.update_score(interaction, 3, "3 exact questions! Okay, we see you cooking now! 👨‍🍳")

    # --- ROW 2 (The Tryhards & The Custom Input) ---
    @discord.ui.button(label="4 (Solid 🧱)", style=discord.ButtonStyle.success, custom_id="btn_4", row=1)
    async def btn_4(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.update_score(interaction, 4, "4 exact questions! Putting in the heavy work. 💪")

    @discord.ui.button(label="5 (Locked In 🔒)", style=discord.ButtonStyle.success, custom_id="btn_5", row=1)
    async def btn_5(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.update_score(interaction, 5, "5 exact questions! Absolute locked-in behavior. 🧠")

    # THE NEW MAGIC BUTTON
    @discord.ui.button(label="Custom Amount ⌨️", style=discord.ButtonStyle.danger, custom_id="btn_custom", row=1)
    async def btn_custom(self, interaction: discord.Interaction, button: discord.ui.Button):
        # This tells Discord to pop up our custom text box!
        await interaction.response.send_modal(CustomScoreModal())

# --- DAILY REMINDER TASK ---
# Set the time you want the reminder to go off (UTC time)
ist_tz = zoneinfo.ZoneInfo("Asia/Kolkata")
poll_time = datetime.time(hour=22, minute=0, tzinfo=ist_tz)

@tasks.loop(time=poll_time)
async def daily_reminder():
    channel = bot.get_channel(MAIN_CHANNEL_ID)
    if channel:
        embed = discord.Embed(
            title="Daily DSA Check-in! 🚀",
            description="How many questions did you solve today? Be honest!",
            color=discord.Color.blue()
        )
        await channel.send(embed=embed, view=DSAPoll())

# --- LEADERBOARD COMMAND ---
@bot.command()
async def leaderboard(ctx):
    async with aiosqlite.connect("dsa_tracker.db") as db:
        async with db.execute("SELECT user_id, solved FROM users ORDER BY solved DESC LIMIT 10") as cursor:
            rows = await cursor.fetchall()

    if not rows:
        await ctx.send("The leaderboard is empty. Start grinding!")
        return

    description = ""
    for rank, (user_id, solved) in enumerate(rows, 1):
        # Fetching the user mention to display in the Discord message
        description += f"**{rank}.** <@{user_id}> - {solved} questions\n"

    embed = discord.Embed(title="🏆 DSA Leaderboard", description=description, color=discord.Color.gold())
    await ctx.send(embed=embed)

# --- MANUAL TEST COMMAND ---
@bot.command()
async def testpoll(ctx):
    # This lets you manually trigger the poll anytime to test it
    embed = discord.Embed(
        title="Daily DSA Check-in! 🚀",
        description="How many questions did you solve today? Be honest!",
        color=discord.Color.blue()
    )
    await ctx.send(embed=embed, view=DSAPoll())

# --- BOT EVENTS ---
@bot.event
async def on_ready():
    await setup_db()
    # Add the view to the bot so buttons persist through bot restarts
    bot.add_view(DSAPoll())
    daily_reminder.start()
    print(f'Logged in as {bot.user}!')

# Run the bot
bot.run(BOT_ID)
