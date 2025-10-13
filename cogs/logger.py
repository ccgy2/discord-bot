import os, json, asyncio, discord
from discord.ext import commands

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
os.makedirs(DATA_DIR, exist_ok=True)
LOG_PATH = os.path.join(DATA_DIR, "logger_settings.json")
_lock = asyncio.Lock()

async def _load():
    async with _lock:
        if not os.path.exists(LOG_PATH):
            with open(LOG_PATH,"w",encoding="utf-8") as f: json.dump({},f,ensure_ascii=False,indent=2)
            return {}
        with open(LOG_PATH,"r",encoding="utf-8") as f: return json.load(f)

async def _save(d):
    async with _lock:
        with open(LOG_PATH,"w",encoding="utf-8") as f: json.dump(d,f,ensure_ascii=False,indent=2)

def _is_admin(ctx):
    p = ctx.author.guild_permissions
    return p.administrator or p.manage_guild

class Logger(commands.Cog):
    def __init__(self, bot): self.bot = bot

    @commands.command(name="로그설정", aliases=["setlog"])
    async def setlog(self, ctx: commands.Context, channel: discord.TextChannel):
        if not _is_admin(ctx): return await ctx.reply("권한이 없습니다.")
        st = await _load(); st[str(ctx.guild.id)] = channel.id; await _save(st)
        await ctx.reply(f"✅ 로그 채널을 {channel.mention} 로 설정했습니다.")

    async def _send(self, guild: discord.Guild, text: str):
        st = await _load(); cid = st.get(str(guild.id))
        if not cid: return
        ch = guild.get_channel(cid)
        if ch: await ch.send(text)

    @commands.Cog.listener()
    async def on_message_delete(self, msg: discord.Message):
        if msg.guild and not msg.author.bot:
            await self._send(msg.guild, f"🗑️ `{msg.author}` 가 #{msg.channel} 에서 메시지 삭제: {msg.content[:150]}")

    @commands.Cog.listener()
    async def on_member_ban(self, guild, user):
        await self._send(guild, f"⛔ {user} 가 밴 당했습니다.")

    @commands.Cog.listener()
    async def on_member_join(self, member):
        await self._send(member.guild, f"➕ {member} 입장")

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        await self._send(member.guild, f"➖ {member} 퇴장")

async def setup(bot): await bot.add_cog(Logger(bot))
