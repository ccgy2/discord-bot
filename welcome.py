import os, json, asyncio, discord
from discord.ext import commands

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
os.makedirs(DATA_DIR, exist_ok=True)
WEL_PATH = os.path.join(DATA_DIR, "welcome.json")
_lock = asyncio.Lock()

async def _load():
    async with _lock:
        if not os.path.exists(WEL_PATH):
            with open(WEL_PATH,"w",encoding="utf-8") as f: json.dump({},f,ensure_ascii=False,indent=2)
            return {}
        with open(WEL_PATH,"r",encoding="utf-8") as f: return json.load(f)

async def _save(d):
    async with _lock:
        with open(WEL_PATH,"w",encoding="utf-8") as f: json.dump(d,f,ensure_ascii=False,indent=2)

def _is_admin(ctx): 
    p=ctx.author.guild_permissions
    return p.administrator or p.manage_guild

class Welcome(commands.Cog):
    def __init__(self, bot): self.bot=bot

    @commands.command(name="환영설정")
    async def set_welcome(self, ctx, ch: discord.TextChannel):
        if not _is_admin(ctx): return await ctx.reply("권한이 없습니다.")
        st=await _load(); st.setdefault(str(ctx.guild.id),{})["welcome"]=ch.id; await _save(st)
        await ctx.reply(f"✅ 환영 채널: {ch.mention}")

    @commands.command(name="작별설정")
    async def set_leave(self, ctx, ch: discord.TextChannel):
        if not _is_admin(ctx): return await ctx.reply("권한이 없습니다.")
        st=await _load(); st.setdefault(str(ctx.guild.id),{})["leave"]=ch.id; await _save(st)
        await ctx.reply(f"✅ 작별 채널: {ch.mention}")

    @commands.Cog.listener()
    async def on_member_join(self, m: discord.Member):
        st=await _load(); ch_id=st.get(str(m.guild.id),{}).get("welcome")
        if ch_id: 
            ch=m.guild.get_channel(ch_id)
            if ch: await ch.send(f"🎉 {m.mention} 님, 환영합니다!")

    @commands.Cog.listener()
    async def on_member_remove(self, m: discord.Member):
        st=await _load(); ch_id=st.get(str(m.guild.id),{}).get("leave")
        if ch_id:
            ch=m.guild.get_channel(ch_id)
            if ch: await ch.send(f"👋 {m} 님이 서버를 떠났습니다.")

async def setup(bot): await bot.add_cog(Welcome(bot))
