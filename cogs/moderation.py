import os, json, asyncio, time, discord
from discord.ext import commands

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
os.makedirs(DATA_DIR, exist_ok=True)
MOD_PATH = os.path.join(DATA_DIR, "moderation.json")
_lock = asyncio.Lock()

async def _load():
    async with _lock:
        if not os.path.exists(MOD_PATH):
            with open(MOD_PATH,"w",encoding="utf-8") as f: json.dump({},f,ensure_ascii=False,indent=2)
            return {}
        with open(MOD_PATH,"r",encoding="utf-8") as f: return json.load(f)

async def _save(d):
    async with _lock:
        with open(MOD_PATH,"w",encoding="utf-8") as f: json.dump(d,f,ensure_ascii=False,indent=2)

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.rate = {}  # (guild,user)->[timestamps]

    def _is_admin(self, ctx):
        p = ctx.author.guild_permissions
        return p.administrator or p.manage_messages or p.manage_guild

    @commands.command(name="금지어추가")
    async def add_bad(self, ctx, *, words: str):
        if not self._is_admin(ctx): return await ctx.reply("권한이 없습니다.")
        st = await _load(); g=str(ctx.guild.id); st.setdefault(g,{"bad":[]})
        st[g]["bad"].extend([w.strip().lower() for w in words.split(",") if w.strip()])
        st[g]["bad"] = sorted(set(st[g]["bad"]))
        await _save(st); await ctx.reply("✅ 금지어 추가 완료")

    @commands.command(name="금지어삭제")
    async def del_bad(self, ctx, *, word: str):
        if not self._is_admin(ctx): return await ctx.reply("권한이 없습니다.")
        st = await _load(); g=str(ctx.guild.id); st.setdefault(g,{"bad":[]})
        st[g]["bad"] = [w for w in st[g]["bad"] if w!=word.lower()]
        await _save(st); await ctx.reply("🗑️ 삭제 완료")

    @commands.command(name="금지어목록")
    async def list_bad(self, ctx):
        st = await _load(); g=str(ctx.guild.id); arr=st.get(g,{}).get("bad",[])
        await ctx.reply("🚫 금지어: " + (", ".join(arr) if arr else "없음"))

    @commands.Cog.listener()
    async def on_message(self, msg: discord.Message):
        if not msg.guild or msg.author.bot: return
        # 금지어
        st = await _load(); bad = st.get(str(msg.guild.id),{}).get("bad",[])
        low = msg.content.lower()
        if any(w in low for w in bad):
            try:
                await msg.delete()
                await msg.channel.send(f"{msg.author.mention} 금지어 사용으로 삭제되었습니다.", delete_after=3)
            except Exception: pass
            return
        # 간단 스팸(10초에 7회 이상)
        key=(msg.guild.id,msg.author.id); now=time.time()
        arr=self.rate.setdefault(key,[]); arr.append(now)
        self.rate[key]=[t for t in arr if now-t<10]
        if len(self.rate[key])>7:
            try:
                await msg.delete()
                await msg.channel.send(f"{msg.author.mention} 도배 감지로 메시지를 제한합니다.", delete_after=3)
            except Exception: pass

async def setup(bot): await bot.add_cog(Moderation(bot))
