import discord
from discord.ext import commands, tasks
import aiosqlite
import datetime
import zoneinfo

# Setup bot
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Your specific channel ID where the bot should send the daily poll
CHANNEL_ID = 1504065666171277454

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

# --- THE POLL BUTTONS ---
# --- THE POLL BUTTONS ---
class DSAPoll(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def update_score(self, interaction: discord.Interaction, points: int, message: str):
        user_id = interaction.user.id
        async with aiosqlite.connect("dsa_tracker.db") as db:
            await db.execute("""
                INSERT INTO users (user_id, solved) VALUES (?, ?)
                ON CONFLICT(user_id) DO UPDATE SET solved = solved + ?
            """, (user_id, points, points))
            await db.commit()

        # Responds with the custom funny message for that specific tier!
        await interaction.response.send_message(message, ephemeral=True)

    @discord.ui.button(label="0 (Dont want intern 😴)", style=discord.ButtonStyle.secondary, custom_id="btn_0", row=0)
    async def btn_0(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.update_score(interaction, 0, "Taking a break? No worries, rest up and come back stronger tomorrow! 🌱")

    @discord.ui.button(label="1 (Honest Work 🌾)", style=discord.ButtonStyle.primary, custom_id="btn_1", row=0)
    async def btn_1(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.update_score(interaction, 1, "1 question down! Keep that streak alive. 🐢")

    @discord.ui.button(label="2 (Getting There 🚶)", style=discord.ButtonStyle.primary, custom_id="btn_2", row=0)
    async def btn_2(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.update_score(interaction, 2, "2 questions! Great job today, consistency is key.")

    @discord.ui.button(label="3 (On a Roll 🎳)", style=discord.ButtonStyle.success, custom_id="btn_3", row=0)
    async def btn_3(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.update_score(interaction, 3, "3 questions! Okay, we see you cooking now! 👨‍🍳")

    @discord.ui.button(label="5 (Locked In 🔒)", style=discord.ButtonStyle.success, custom_id="btn_5", row=1)
    async def btn_5(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.update_score(interaction, 5, "5 questions?! Absolute locked-in behavior. 🧠")

    @discord.ui.button(label="8 (Demon Time 😈)", style=discord.ButtonStyle.danger, custom_id="btn_8", row=1)
    async def btn_8(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.update_score(interaction, 8, "8 questions! Leave some LeetCode for the rest of us... 🔥")

    @discord.ui.button(label="10+ (Almost as locked in jyotirya)", style=discord.ButtonStyle.danger, custom_id="btn_10", row=1)
    async def btn_10(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.update_score(interaction, 10, "10 questions?! Please go outside and touch grass immediately. (Points added!) 🌲")

# --- DAILY REMINDER TASK ---
# Set the time you want the reminder to go off (UTC time)
ist_tz = zoneinfo.ZoneInfo("Asia/Kolkata")
poll_time = datetime.time(hour=22, minute=0, tzinfo=ist_tz)

@tasks.loop(time=poll_time)
async def daily_reminder():
    channel = bot.get_channel(CHANNEL_ID)
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

    embed = discord.Embed(title="🏆 DSA Leaderboard 🏆", description=description, color=discord.Color.gold())
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

# Run the bot (Replace with your actual token)
bot.run('MTUwNDA1OTQwMzgxOTU0ODcyMg.G9Qf9Z.fAi7CuZFSO3kqObvvZmISXcLVe5Wvi3mY2Fm8g')
