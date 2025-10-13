import os, asyncio, traceback, discord
from dotenv import load_dotenv
from discord.ext import commands

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
PREFIX = os.getenv("BOT_PREFIX", "!")
OPENAI_KEY = os.getenv("OPENAI_API_KEY", "")
OWNER_ID = os.getenv("OWNER_ID")

if not TOKEN:
    raise SystemExit("❌ DISCORD_TOKEN이 설정되지 않았습니다. .env를 확인하세요.")

INTENTS = discord.Intents.default()
INTENTS.message_content = True
INTENTS.members = True
INTENTS.guilds = True
INTENTS.reactions = True
INTENTS.voice_states = True

bot = commands.Bot(command_prefix=PREFIX, intents=INTENTS, help_command=None)
bot.config = {
    "prefix": PREFIX,
    "openai_api_key": (OPENAI_KEY or "").strip(),
    "owner_id": int(OWNER_ID) if OWNER_ID and OWNER_ID.isdigit() else None
}

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")
    await bot.change_presence(activity=discord.Game(name=f"{PREFIX}도움말 / {PREFIX}help"))

async def load_cogs():
    exts = (
        # 기본/유틸
        "cogs.basic","cogs.chat","cogs.announce","cogs.admin","cogs.profile",
        # 경제/게임
        "cogs.economy","cogs.gamble","cogs.minigames","cogs.level","cogs.stock","cogs.economy_plus","cogs.shop","cogs.lottery",
        # 음악
        "cogs.music",
        # 운영/보안/자동화
        "cogs.ticket","cogs.logger","cogs.reminder","cogs.moderation","cogs.stats","cogs.welcome","cogs.gpttoggle","cogs.help",
    )
    for ext in exts:
        try:
            await bot.load_extension(ext)
            print("Loaded cog:", ext)
        except Exception as e:
            print("Failed:", ext, e); traceback.print_exc()

async def main():
    async with bot:
        await load_cogs()
        await bot.start(TOKEN)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("🛑 Bot stopped.")
