import os, json, asyncio, discord
from discord.ext import commands

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
os.makedirs(DATA_DIR, exist_ok=True)
BAL_PATH = os.path.join(DATA_DIR, "balances.json")
XP_PATH  = os.path.join(DATA_DIR, "xp.json")
_lock = asyncio.Lock()

async def _load(path, default):
    async with _lock:
        if not os.path.exists(path):
            with open(path,"w",encoding="utf-8") as f: json.dump(default,f,ensure_ascii=False,indent=2)
            return default
        with open(path,"r",encoding="utf-8") as f: return json.load(f)

class Profile(commands.Cog):
    def __init__(self, bot): self.bot=bot

    @commands.command(name="프로필", aliases=["profile","내정보"])
    async def profile(self, ctx, member: discord.Member=None):
        m = member or ctx.author
        bal = await _load(BAL_PATH,{})
        xp  = await _load(XP_PATH,{})
        money = bal.get(str(m.id),{}).get("money",0)
        user_xp = xp.get(str(ctx.guild.id),{}).get(str(m.id),{"xp":0})["xp"]

        embed = discord.Embed(title=f"👤 {m.display_name} 프로필", color=0x1abc9c)
        embed.set_thumbnail(url=m.display_avatar.url)
        embed.add_field(name="잔액", value=f"{money}원")
        embed.add_field(name="XP", value=str(user_xp))
        embed.add_field(name="가입일", value=m.joined_at.strftime("%Y-%m-%d") if m.joined_at else "알 수 없음")
        await ctx.reply(embed=embed)

async def setup(bot): await bot.add_cog(Profile(bot))
