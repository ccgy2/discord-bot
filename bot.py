import os
import json
import asyncio
import traceback
import discord
from discord.ext import commands
from dotenv import load_dotenv

# .env 로드
load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
DEFAULT_PREFIX = os.getenv("BOT_PREFIX", "!")
OPENAI_KEY = os.getenv("OPENAI_API_KEY", "")
OWNER_ID = os.getenv("OWNER_ID")

if not TOKEN:
    raise SystemExit("❌ DISCORD_TOKEN이 설정되지 않았습니다. .env 파일을 확인하세요.")

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(DATA_DIR, exist_ok=True)
PREFIX_PATH = os.path.join(DATA_DIR, "prefixes.json")

def load_prefix_map():
    if not os.path.exists(PREFIX_PATH):
        return {}
    try:
        with open(PREFIX_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def get_prefix(bot, message):
    # DM 이면 기본 접두사
    if not message.guild:
        return DEFAULT_PREFIX
    mp = load_prefix_map()
    return mp.get(str(message.guild.id), DEFAULT_PREFIX)

INTENTS = discord.Intents.default()
INTENTS.message_content = True
INTENTS.guilds = True
INTENTS.members = True
INTENTS.messages = True
INTENTS.voice_states = True

bot = commands.Bot(command_prefix=get_prefix, intents=INTENTS, help_command=None)
bot.config = {
    "default_prefix": DEFAULT_PREFIX,
    "openai_api_key": OPENAI_KEY,
    "owner_id": int(OWNER_ID) if OWNER_ID and OWNER_ID.isdigit() else None
}

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")

@bot.event
async def load_cogs():
    # 필요한 코그를 등록하세요. (추가/삭제 자유)
    for ext in (
        "cogs.basic",
        "cogs.chat",
        "cogs.announce",
        "cogs.gamble",
        "cogs.music",
        "cogs.quiz",            # 있으면 유지, 없으면 자동 무시
        "cogs.economy",
        "cogs.economy_plus",
        "cogs.stock",
        "cogs.shop",
        "cogs.lottery",
        "cogs.prefix",          # ← 접두사 관리
        "cogs.help",            # ← 자동 도움말
    ):
        try:
            await bot.load_extension(ext)
            print(f"Loaded cog: {ext}")
        except Exception as e:
            print(f"Failed to load {ext}: {e}")
            traceback.print_exc()

async def main():
    async with bot:
        await load_cogs()
        await bot.start(TOKEN)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("🛑 Bot stopped.")
