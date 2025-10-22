import os, json, discord
from discord.ext import commands

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
os.makedirs(DATA_DIR, exist_ok=True)
PREFIX_PATH = os.path.join(DATA_DIR, "prefixes.json")

def _load_map():
    if not os.path.exists(PREFIX_PATH):
        return {}
    try:
        with open(PREFIX_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _save_map(data: dict):
    with open(PREFIX_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

class Prefix(commands.Cog):
    """서버별 접두사 설정"""
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="접두사", aliases=["prefix","프리픽스"])
    @commands.has_permissions(manage_guild=True)
    async def set_prefix(self, ctx: commands.Context, new_prefix: str):
        """서버 접두사 변경 (예: !접두사 ?)"""
        new_prefix = new_prefix.strip()
        if not new_prefix:
            return await ctx.reply("빈 접두사는 사용할 수 없습니다.")
        mp = _load_map()
        mp[str(ctx.guild.id)] = new_prefix
        _save_map(mp)
        await ctx.reply(f"✅ 이 서버의 접두사가 `{new_prefix}` 로 변경되었습니다.\n"
                        f"예: `{new_prefix}도움`, `{new_prefix}재생`")

    @commands.command(name="접두사확인", aliases=["prefixget","프리픽스확인"])
    async def get_prefix(self, ctx: commands.Context):
        """현재 서버 접두사 확인"""
        mp = _load_map()
        cur = mp.get(str(ctx.guild.id), self.bot.config.get("default_prefix", "!"))
        await ctx.reply(f"현재 접두사: `{cur}`")

async def setup(bot):
    await bot.add_cog(Prefix(bot))
