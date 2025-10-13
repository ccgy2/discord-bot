import os, json, asyncio, math, time, discord
from discord.ext import commands

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
os.makedirs(DATA_DIR, exist_ok=True)
XP_PATH = os.path.join(DATA_DIR, "xp.json")
_lock = asyncio.Lock()

async def _load():
    async with _lock:
        if not os.path.exists(XP_PATH):
            with open(XP_PATH,"w",encoding="utf-8") as f: json.dump({},f,ensure_ascii=False,indent=2)
            return {}
        with open(XP_PATH,"r",encoding="utf-8") as f: return json.load(f)
async def _save(d):
    async with _lock:
        with open(XP_PATH,"w",encoding="utf-8") as f: json.dump(d,f,ensure_ascii=False,indent=2)

class Level(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.cool: dict[tuple[int,int], float] = {}

    def _level_of(self, xp: int) -> int:
        # 간단 공식: level = floor(sqrt(xp/50))
        return int(math.sqrt(max(0, xp)/50))

    @commands.Cog.listener()
    async def on_message(self, msg: discord.Message):
        if not msg.guild or msg.author.bot: return
        key=(msg.guild.id,msg.author.id); now=time.time()
        if self.cool.get(key,0) > now: return
        self.cool[key]=now+60  # 60초 쿨다운
        data = await _load(); g=str(msg.guild.id); u=str(msg.author.id)
        data.setdefault(g,{}); stat=data[g].setdefault(u,{"xp":0})
        stat["xp"]+=10
        before = self._level_of(stat["xp"]-10)
        after  = self._level_of(stat["xp"])
        await _save(data)
        if after>before:
            try: await msg.channel.send(f"🎉 {msg.author.mention} 레벨업! **Lv.{after}**")
            except Exception: pass

    @commands.command(name="레벨", aliases=["level"])
    async def my_level(self, ctx):
        data = await _load(); g=str(ctx.guild.id); u=str(ctx.author.id)
        xp=data.get(g,{}).get(u,{"xp":0})["xp"]; lv=self._level_of(xp)
        await ctx.reply(f"🧪 XP: **{xp}** / 레벨: **{lv}**")

    @commands.command(name="랭킹", aliases=["rank"])
    async def ranking(self, ctx):
        data = await _load(); g=str(ctx.guild.id); guild=data.get(g,{})
        rows=[(int(u),v["xp"]) for u,v in guild.items()]
        rows.sort(key=lambda x:x[1], reverse=True)
        lines=[]
        for i,(uid,xp) in enumerate(rows[:10],start=1):
            lv=self._level_of(xp); lines.append(f"{i}. <@{uid}> — Lv.{lv} ({xp}xp)")
        await ctx.reply("🏆 상위 랭킹\n" + ("\n".join(lines) if lines else "데이터 없음"))

async def setup(bot): await bot.add_cog(Level(bot))
