import asyncio
import datetime
import os
import zoneinfo
import logging
import aiosqlite
import discord
import httpx
from discord import app_commands
from discord.ext import commands, tasks
from dotenv import load_dotenv

import leetcode_graphql as lc
import codeforces_api as cf
import geeksforgeeks_api as gfg

load_dotenv()

log = logging.getLogger(__name__)

MAIN_CHANNEL_ID = int(os.getenv("MAIN_CHANNEL_ID", "1504071059073405019"))
BOT_TOKEN = os.getenv("BOT_ID")
DB_PATH = "dsa_tracker.db"
IST = zoneinfo.ZoneInfo("Asia/Kolkata")

MORNING_TITLE = "Start the day strong"
MORNING_BODY = "Good morning — time to warm up with DSA. Pick a problem and get moving."

REMINDER_TITLE = "DSA reminder"
REMINDER_BODY = "How is practice going? Keep the streak alive — solve something if you have not yet."

GOODNIGHT_TITLE = "Good night"
GOODNIGHT_BODY = "Wrap up, rest well, and we will see you tomorrow for more practice."

LB_FOOTER = (
    "Counts are accepted (AC) submissions per UTC day across linked LeetCode, "
    "Codeforces, and GeeksforGeeks profiles. "
    f"LeetCode uses the recent AC list (up to {lc.RECENT_AC_FETCH_LIMIT} in the window)."
)

SCHEDULE_TIMES = [
    datetime.time(6, 0, tzinfo=IST),
    datetime.time(12, 0, tzinfo=IST),
    datetime.time(18, 0, tzinfo=IST),
    datetime.time(22, 0, tzinfo=IST),
    datetime.time(0, 0, tzinfo=IST),
]


def _parse_admin_ids() -> set[int]:
    raw = os.getenv("ADMIN_USER_IDS", "")
    out: set[int] = set()
    for part in raw.split(","):
        part = part.strip()
        if part.isdigit():
            out.add(int(part))
    return out


ADMIN_IDS = _parse_admin_ids()


def _norm_leetcode_username(s: str) -> str:
    s = s.strip()
    if s.startswith("@"):
        s = s[1:]
    return s


async def setup_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                leetcode_username TEXT
            )
            """
        )
        async with db.execute("PRAGMA table_info(users)") as cur:
            cols = [row[1] for row in await cur.fetchall()]
        if cols and "leetcode_username" not in cols:
            await db.execute("ALTER TABLE users ADD COLUMN leetcode_username TEXT")
        if cols and "codeforces_handle" not in cols:
            await db.execute("ALTER TABLE users ADD COLUMN codeforces_handle TEXT")
        if cols and "geeksforgeeks_handle" not in cols:
            await db.execute("ALTER TABLE users ADD COLUMN geeksforgeeks_handle TEXT")
        if cols and "solved" in cols:
            try:
                await db.execute("ALTER TABLE users DROP COLUMN solved")
            except aiosqlite.OperationalError:
                pass
        await db.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_users_leetcode_username "
            "ON users(leetcode_username) WHERE leetcode_username IS NOT NULL"
        )
        await db.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_users_codeforces_handle "
            "ON users(codeforces_handle) WHERE codeforces_handle IS NOT NULL"
        )
        await db.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_users_geeksforgeeks_handle "
            "ON users(geeksforgeeks_handle) WHERE geeksforgeeks_handle IS NOT NULL"
        )
        await db.commit()


async def fetch_linked_users() -> list[tuple[int, str | None, str | None, str | None]]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT user_id, leetcode_username, codeforces_handle, geeksforgeeks_handle FROM users "
            "WHERE (leetcode_username IS NOT NULL AND leetcode_username != '') "
            "   OR (codeforces_handle IS NOT NULL AND codeforces_handle != '')"
            "   OR (geeksforgeeks_handle IS NOT NULL AND geeksforgeeks_handle != '')"
        ) as cur:
            return [(int(r[0]), r[1] if r[1] else None, r[2] if r[2] else None, r[3] if r[3] else None) for r in await cur.fetchall()]


async def fetch_stats_for_all(
    http: httpx.AsyncClient,
    rows: list[tuple[int, str | None, str | None, str | None]],
) -> list[tuple[int, int | None, int | None]]:
    sem = asyncio.Semaphore(4)

    async def one(uid: int, lc_name: str | None, cf_name: str | None, gfg_name: str | None) -> tuple[int, int | None, int | None]:
        async with sem:
            lc_t, lc_w = None, None
            cf_t, cf_w = None, None
            gfg_t, gfg_w = None, None
            
            if lc_name:
                lc_t, lc_w = await lc.fetch_stats_today_and_week(http, lc_name)
            if cf_name:
                cf_t, cf_w = await cf.fetch_stats_today_and_week(http, cf_name)
            if gfg_name:
                gfg_t, gfg_w = await gfg.fetch_stats_today_and_week(http, gfg_name)
            
            t = (lc_t or 0) + (cf_t or 0) + (gfg_t or 0)
            w = (lc_w or 0) + (cf_w or 0) + (gfg_w or 0)
            
            if lc_t is None and cf_t is None and gfg_t is None:
                t = None
            if lc_w is None and cf_w is None and gfg_w is None:
                w = None

            return uid, t, w

    return list(await asyncio.gather(*[one(u, l, c, g) for u, l, c, g in rows]))


def _sort_leaderboard(
    stats: list[tuple[int, int | None, int | None]],
) -> list[tuple[int, int | None, int | None]]:
    def key(r: tuple[int, int | None, int | None]) -> tuple[int, int]:
        _, t, w = r
        return (
            -(w if w is not None else -1),
            -(t if t is not None else -1),
        )

    return sorted(stats, key=key)


def build_leaderboard_description(
    ranked: list[tuple[int, int | None, int | None]],
) -> str:
    lines: list[str] = []
    for i, (uid, t, w) in enumerate(ranked, 1):
        ts = str(t) if t is not None else "—"
        ws = str(w) if w is not None else "—"
        lines.append(f"**{i}.** <@{uid}> — this week: **{ws}** | today: **{ts}**")
    return "\n".join(lines) if lines else "_No linked users._"


async def build_leaderboard_embeds(
    http: httpx.AsyncClient,
) -> list[discord.Embed]:
    rows = await fetch_linked_users()
    if not rows:
        embed = discord.Embed(
            title="DSA Leaderboard",
            description="No one has linked a profile yet. Use `/leetcode set`, `/codeforces set`, or `/geeksforgeeks set`.",
            color=discord.Color.dark_blue(),
        )
        embed.set_footer(text=LB_FOOTER)
        return [embed]

    stats = await fetch_stats_for_all(http, rows)
    ranked = _sort_leaderboard(stats)
    desc = build_leaderboard_description(ranked)
    embed = discord.Embed(
        title="DSA Leaderboard",
        description=desc,
        color=discord.Color.gold(),
    )
    embed.set_footer(text=LB_FOOTER)
    return [embed]


leetcode_group = app_commands.Group(
    name="leetcode",
    description="Link your LeetCode profile for daily leaderboards",
)


@leetcode_group.command(name="set", description="Save your LeetCode username")
@app_commands.describe(username="Your LeetCode username (as in your profile URL)")
async def leetcode_set(interaction: discord.Interaction, username: str) -> None:
    bot = interaction.client
    if not isinstance(bot, DSABot):
        return
    name = _norm_leetcode_username(username)
    if not name or len(name) > 64:
        await interaction.response.send_message(
            "Please provide a valid LeetCode username.",
            ephemeral=True,
        )
        return

    if not await lc.user_exists(bot.http_lc, name):
        await interaction.response.send_message(
            "Could not find that LeetCode user. Check the spelling (case-sensitive).",
            ephemeral=True,
        )
        return

    uid = interaction.user.id
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT user_id FROM users WHERE leetcode_username = ? AND user_id != ?",
            (name, uid),
        ) as cur:
            taken = await cur.fetchone()
        if taken:
            await interaction.response.send_message(
                f"That LeetCode account is already linked to <@{taken[0]}>.",
                ephemeral=True,
            )
            return
        await db.execute(
            """
            INSERT INTO users (user_id, leetcode_username) VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET leetcode_username = excluded.leetcode_username
            """,
            (uid, name),
        )
        await db.commit()

    await interaction.response.send_message(
        f"Linked LeetCode **{name}** to your Discord account.",
        ephemeral=True,
    )


@leetcode_group.command(name="clear", description="Remove your linked LeetCode username")
async def leetcode_clear(interaction: discord.Interaction) -> None:
    uid = interaction.user.id
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET leetcode_username = NULL WHERE user_id = ?",
            (uid,),
        )
        await db.commit()
    await interaction.response.send_message(
        "Your LeetCode link was removed.",
        ephemeral=True,
    )


@leetcode_group.command(name="show", description="Show your linked LeetCode username")
async def leetcode_show(interaction: discord.Interaction) -> None:
    uid = interaction.user.id
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT leetcode_username FROM users WHERE user_id = ?",
            (uid,),
        ) as cur:
            row = await cur.fetchone()
    lc_name = row[0] if row else None
    if not lc_name:
        await interaction.response.send_message(
            "You have not linked a LeetCode profile. Use `/leetcode set`.",
            ephemeral=True,
        )
        return
    await interaction.response.send_message(
        f"Your LeetCode username: **{lc_name}**",
        ephemeral=True,
    )


codeforces_group = app_commands.Group(
    name="codeforces",
    description="Link your Codeforces profile for daily leaderboards",
)


@codeforces_group.command(name="set", description="Save your Codeforces handle")
@app_commands.describe(handle="Your Codeforces handle")
async def codeforces_set(interaction: discord.Interaction, handle: str) -> None:
    bot = interaction.client
    if not isinstance(bot, DSABot):
        return
    name = _norm_leetcode_username(handle)
    if not name or len(name) > 64:
        await interaction.response.send_message(
            "Please provide a valid Codeforces handle.",
            ephemeral=True,
        )
        return

    if not await cf.user_exists(bot.http_lc, name):
        await interaction.response.send_message(
            "Could not find that Codeforces user. Check the spelling (case-sensitive).",
            ephemeral=True,
        )
        return

    uid = interaction.user.id
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT user_id FROM users WHERE codeforces_handle = ? AND user_id != ?",
            (name, uid),
        ) as cur:
            taken = await cur.fetchone()
        if taken:
            await interaction.response.send_message(
                f"That Codeforces account is already linked to <@{taken[0]}>.",
                ephemeral=True,
            )
            return
        await db.execute(
            """
            INSERT INTO users (user_id, codeforces_handle) VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET codeforces_handle = excluded.codeforces_handle
            """,
            (uid, name),
        )
        await db.commit()

    await interaction.response.send_message(
        f"Linked Codeforces **{name}** to your Discord account.",
        ephemeral=True,
    )


@codeforces_group.command(name="clear", description="Remove your linked Codeforces handle")
async def codeforces_clear(interaction: discord.Interaction) -> None:
    uid = interaction.user.id
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET codeforces_handle = NULL WHERE user_id = ?",
            (uid,),
        )
        await db.commit()
    await interaction.response.send_message(
        "Your Codeforces link was removed.",
        ephemeral=True,
    )


@codeforces_group.command(name="show", description="Show your linked Codeforces handle")
async def codeforces_show(interaction: discord.Interaction) -> None:
    uid = interaction.user.id
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT codeforces_handle FROM users WHERE user_id = ?",
            (uid,),
        ) as cur:
            row = await cur.fetchone()
    cf_name = row[0] if row else None
    if not cf_name:
        await interaction.response.send_message(
            "You have not linked a Codeforces profile. Use `/codeforces set`.",
            ephemeral=True,
        )
        return
    await interaction.response.send_message(
        f"Your Codeforces handle: **{cf_name}**",
        ephemeral=True,
    )


geeksforgeeks_group = app_commands.Group(
    name="geeksforgeeks",
    description="Link your GeeksforGeeks profile for daily leaderboards",
)


@geeksforgeeks_group.command(name="set", description="Save your GeeksforGeeks handle")
@app_commands.describe(handle="Your GeeksforGeeks handle")
async def geeksforgeeks_set(interaction: discord.Interaction, handle: str) -> None:
    bot = interaction.client
    if not isinstance(bot, DSABot):
        return
    name = _norm_leetcode_username(handle)
    if not name or len(name) > 64:
        await interaction.response.send_message(
            "Please provide a valid GeeksforGeeks handle.",
            ephemeral=True,
        )
        return

    if not await gfg.user_exists(bot.http_lc, name):
        await interaction.response.send_message(
            "Could not find that GeeksforGeeks user. Check the spelling.",
            ephemeral=True,
        )
        return

    uid = interaction.user.id
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT user_id FROM users WHERE geeksforgeeks_handle = ? AND user_id != ?",
            (name, uid),
        ) as cur:
            taken = await cur.fetchone()
        if taken:
            await interaction.response.send_message(
                f"That GeeksforGeeks account is already linked to <@{taken[0]}>.",
                ephemeral=True,
            )
            return
        await db.execute(
            """
            INSERT INTO users (user_id, geeksforgeeks_handle) VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET geeksforgeeks_handle = excluded.geeksforgeeks_handle
            """,
            (uid, name),
        )
        await db.commit()

    await interaction.response.send_message(
        f"Linked GeeksforGeeks **{name}** to your Discord account.",
        ephemeral=True,
    )


@geeksforgeeks_group.command(name="clear", description="Remove your linked GeeksforGeeks handle")
async def geeksforgeeks_clear(interaction: discord.Interaction) -> None:
    uid = interaction.user.id
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET geeksforgeeks_handle = NULL WHERE user_id = ?",
            (uid,),
        )
        await db.commit()
    await interaction.response.send_message(
        "Your GeeksforGeeks link was removed.",
        ephemeral=True,
    )


@geeksforgeeks_group.command(name="show", description="Show your linked GeeksforGeeks handle")
async def geeksforgeeks_show(interaction: discord.Interaction) -> None:
    uid = interaction.user.id
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT geeksforgeeks_handle FROM users WHERE user_id = ?",
            (uid,),
        ) as cur:
            row = await cur.fetchone()
    gfg_name = row[0] if row else None
    if not gfg_name:
        await interaction.response.send_message(
            "You have not linked a GeeksforGeeks profile. Use `/geeksforgeeks set`.",
            ephemeral=True,
        )
        return
    await interaction.response.send_message(
        f"Your GeeksforGeeks handle: **{gfg_name}**",
        ephemeral=True,
    )


intents = discord.Intents.default()
intents.message_content = True


class DSABot(commands.Bot):
    http_lc: httpx.AsyncClient

    def __init__(self) -> None:
        super().__init__(command_prefix="!", intents=intents)
        self.http_lc = httpx.AsyncClient(timeout=30.0)

    async def setup_hook(self) -> None:
        await setup_db()
        self.tree.add_command(leetcode_group)
        self.tree.add_command(codeforces_group)
        self.tree.add_command(geeksforgeeks_group)
        
        log.info(f"Registered command groups: {[cmd.name for cmd in self.tree.get_commands()]}")

        guild_id = os.getenv("GUILD_ID")
        if guild_id:
            guild = discord.Object(id=int(guild_id))
            self.tree.copy_global_to(guild=guild)
            log.info(f"Syncing commands to guild: {guild_id}")
            synced = await self.tree.sync(guild=guild)
            log.info(f"Synced {len(synced)} commands to guild {guild_id}")
        else:
            log.info("Syncing commands globally")
            synced = await self.tree.sync()
            log.info(f"Synced {len(synced)} commands globally")
        if not ist_schedule.is_running():
            ist_schedule.start()

    async def close(self) -> None:
        await self.http_lc.aclose()
        await super().close()


bot = DSABot()


@bot.check
async def restrict_prefix_commands(ctx: commands.Context) -> bool:
    return ctx.channel.id == MAIN_CHANNEL_ID


@bot.tree.interaction_check
async def restrict_slash_commands(interaction: discord.Interaction) -> bool:
    return interaction.channel_id == MAIN_CHANNEL_ID


@bot.tree.command(name="leaderboard", description="Show DSA today / 7-day stats leaderboard")
async def slash_leaderboard(interaction: discord.Interaction) -> None:
    await interaction.response.defer(thinking=True)
    embeds = await build_leaderboard_embeds(bot.http_lc)
    await interaction.followup.send(embeds=embeds)


@bot.tree.command(name="testcommand", description="Test command to verify command sync is working")
async def test_command(interaction: discord.Interaction) -> None:
    await interaction.response.send_message(
        "✅ Test command is working! This confirms the bot is syncing commands correctly.",
        ephemeral=True,
    )


@tasks.loop(time=SCHEDULE_TIMES)
async def ist_schedule() -> None:
    channel = bot.get_channel(MAIN_CHANNEL_ID)
    if not isinstance(channel, discord.TextChannel):
        return

    now = datetime.datetime.now(IST)
    hour = now.hour

    if hour == 6:
        embed = discord.Embed(
            title=MORNING_TITLE,
            description=MORNING_BODY,
            color=discord.Color.green(),
        )
        await channel.send(embed=embed)
    elif hour in (12, 18, 22):
        embed = discord.Embed(
            title=REMINDER_TITLE,
            description=REMINDER_BODY,
            color=discord.Color.blue(),
        )
        await channel.send(embed=embed)
    elif hour == 0:
        embed = discord.Embed(
            title=GOODNIGHT_TITLE,
            description=GOODNIGHT_BODY,
            color=discord.Color.dark_purple(),
        )
        await channel.send(embed=embed)

    # Always send the leaderboard after any scheduled message
    embeds = await build_leaderboard_embeds(bot.http_lc)
    await channel.send(embeds=embeds)


@ist_schedule.before_loop
async def before_ist_schedule() -> None:
    await bot.wait_until_ready()


@bot.command(name="leaderboard")
async def prefix_leaderboard(ctx: commands.Context) -> None:
    embeds = await build_leaderboard_embeds(bot.http_lc)
    await ctx.send(embeds=embeds)


@bot.command(name="testschedule")
async def testschedule(ctx: commands.Context) -> None:
    if not ADMIN_IDS or ctx.author.id not in ADMIN_IDS:
        await ctx.send("You do not have permission to use this command.")
        return
    channel = ctx.channel
    if not isinstance(channel, discord.TextChannel):
        return
    remind = discord.Embed(
        title=REMINDER_TITLE,
        description=REMINDER_BODY + "\n\n_(test run)_",
        color=discord.Color.blue(),
    )
    await channel.send(embed=remind)
    embeds = await build_leaderboard_embeds(bot.http_lc)
    await channel.send(embeds=embeds)


@bot.event
async def on_ready() -> None:
    log.info(f"Logged in as {bot.user} ({bot.user.id if bot.user else '?'})")


def main() -> None:
    if not BOT_TOKEN:
        raise SystemExit("Missing BOT_ID (Discord bot token) in environment.")
    # Tell discord.py to handle Python's root logger so our __main__ logs show up too
    bot.run(BOT_TOKEN, root_logger=True)


if __name__ == "__main__":
    main()
