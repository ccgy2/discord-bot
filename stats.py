import os, json, asyncio, discord
from discord.ext import commands

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
os.makedirs(DATA_DIR, exist_ok=True)
STAT_PATH = os.path.join(DATA_DIR, "stats.json")
_lock = asyncio.Lock()

async def _load():
    async with _lock:
        if not os.path.exists(STAT_PATH):
            with open(STAT_PATH,"w",encoding="utf-8") as f: json.dump({},f,ensure_ascii=False,indent=2)
            return {}
        with open(STAT_PATH,"r",encoding="utf-8") as f: return json.load(f)

async def _save(d):
    async with _lock:
        with open(STAT_PATH,"w",encoding="utf-8") as f: json.dump(d,f,ensure_ascii=False,indent=2)

class Stats(commands.Cog):
    def __init__(self, bot): self.bot=bot

    @commands.Cog.listener()
    async def on_message(self, msg: discord.Message):
        if not msg.guild or msg.author.bot: return
        st = await _load(); g=str(msg.guild.id); st.setdefault(g,{"messages":0,"joins":0})
        st[g]["messages"]+=1; await _save(st)

    @commands.Cog.listener()
    async def on_member_join(self, m: discord.Member):
        st = await _load(); g=str(m.guild.id); st.setdefault(g,{"messages":0,"joins":0})
        st[g]["joins"]+=1; await _save(st)

    @commands.command(name="통계", aliases=["stats"])
    async def show(self, ctx):
        st = await _load(); g=str(ctx.guild.id); s=st.get(g,{"messages":0,"joins":0})
        await ctx.reply(f"📊 통계 — 메시지: **{s['messages']}** / 신규가입: **{s['joins']}**")

async def setup(bot): await bot.add_cog(Stats(bot))
