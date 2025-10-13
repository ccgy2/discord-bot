import os, json, asyncio, discord
from discord.ext import commands

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
os.makedirs(DATA_DIR, exist_ok=True)
ADMIN_PATH = os.path.join(DATA_DIR, "admin_settings.json")
_lock = asyncio.Lock()

async def _load():
    async with _lock:
        if not os.path.exists(ADMIN_PATH):
            with open(ADMIN_PATH,"w",encoding="utf-8") as f: json.dump({},f,ensure_ascii=False,indent=2)
            return {}
        with open(ADMIN_PATH,"r",encoding="utf-8") as f: return json.load(f)

async def _save(d):
    async with _lock:
        with open(ADMIN_PATH,"w",encoding="utf-8") as f: json.dump(d,f,ensure_ascii=False,indent=2)

def _is_admin(bot, ctx):
    oid = bot.config.get("owner_id")
    if oid and int(oid)==ctx.author.id: return True
    p = ctx.author.guild_permissions
    return p.administrator or p.manage_guild or p.manage_messages

class Announce(commands.Cog):
    def __init__(self, bot): self.bot = bot

    @commands.command(name="공지", aliases=["announce"])
    async def announce(self, ctx: commands.Context, *, text: str = ""):
        """
        사용법: !공지 [#채널] 제목 | 내용
        예시 : !공지 #공지사항 업데이트 | 내일 9시 점검
        멘션: !공지역할설정 으로 지정된 역할을 자동 멘션
        """
        if not text.strip(): return await ctx.reply("형식: `!공지 [#채널] 제목 | 내용`")
        target = ctx.channel
        if ctx.message.channel_mentions:
            target = ctx.message.channel_mentions[0]
            text = text.replace(f"<#{target.id}>","",1).strip()

        if "|" not in text: return await ctx.reply("제목과 내용을 `|`로 구분해 주세요.")
        title, body = [s.strip() for s in text.split("|",1)]

        st = await _load()
        gid = str(ctx.guild.id)
        role_id = st.get(gid,{}).get("announce_role_id")
        mention_text = ""
        allowed_mentions = discord.AllowedMentions.none()
        if role_id:
            role = ctx.guild.get_role(role_id)
            if role:
                mention_text = role.mention + "\n"
                allowed_mentions = discord.AllowedMentions(roles=True)

        embed = discord.Embed(title=title, description=body, color=0xf1c40f)
        embed.set_footer(text=f"by {ctx.author}", icon_url=ctx.author.display_avatar.url)
        await target.send(content=mention_text or None, embed=embed, allowed_mentions=allowed_mentions)
        await ctx.reply(f"📢 공지를 {target.mention} 에 전송했어요.")

    @commands.command(name="공지역할설정", aliases=["setannouncerole"])
    async def set_announce_role(self, ctx: commands.Context, role: discord.Role=None):
        """관리자: 공지 멘션 역할 지정/해제"""
        if not _is_admin(self.bot, ctx): return await ctx.reply("권한이 없습니다.")
        st = await _load(); gid = str(ctx.guild.id); st.setdefault(gid,{})
        if role:
            st[gid]["announce_role_id"] = role.id
            await ctx.reply(f"✅ 공지 멘션 역할을 {role.mention} 으로 설정했습니다.")
        else:
            st[gid].pop("announce_role_id", None)
            await ctx.reply("✅ 공지 멘션 역할을 해제했습니다.")
        await _save(st)

async def setup(bot): await bot.add_cog(Announce(bot))
