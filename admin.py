import os
import json
import asyncio
from typing import Optional

import discord
from discord.ext import commands

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
os.makedirs(DATA_DIR, exist_ok=True)
ADMIN_PATH = os.path.join(DATA_DIR, "admin_settings.json")
_lock = asyncio.Lock()

async def _load_settings():
    async with _lock:
        if not os.path.exists(ADMIN_PATH):
            with open(ADMIN_PATH, "w", encoding="utf-8") as f:
                json.dump({}, f, ensure_ascii=False, indent=2)
            return {}
        with open(ADMIN_PATH, "r", encoding="utf-8") as f:
            return json.load(f)

async def _save_settings(data):
    async with _lock:
        with open(ADMIN_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

def _is_admin(bot: commands.Bot, ctx: commands.Context) -> bool:
    owner_id = bot.config.get("owner_id")
    if owner_id and int(owner_id) == ctx.author.id:
        return True
    p = ctx.author.guild_permissions
    return p.administrator or p.manage_guild or p.manage_roles

class Admin(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ============ 청소 ============
    @commands.command(name="청소", aliases=["purge","clear"])
    @commands.has_permissions(manage_messages=True)
    async def purge(self, ctx: commands.Context, count: Optional[int] = 10):
        count = max(1, min(200, int(count or 10)))
        deleted = await ctx.channel.purge(limit=count+1)  # 명령어 포함
        msg = await ctx.send(f"🧹 메시지 {len(deleted)-1}개 삭제 완료")
        await asyncio.sleep(2)
        with contextlib.suppress(Exception):
            await msg.delete()

    # ============ 인증 ============
    @commands.command(name="인증설정", aliases=["verifyset"])
    async def verify_set(self, ctx: commands.Context, channel: discord.TextChannel, role: discord.Role):
        if not _is_admin(self.bot, ctx):
            return await ctx.reply("권한이 없습니다.")
        st = await _load_settings()
        gid = str(ctx.guild.id)
        st.setdefault(gid, {})
        st[gid]["verify_channel_id"] = channel.id
        st[gid]["verify_role_id"] = role.id
        await _save_settings(st)
        await ctx.reply(f"✅ 인증 채널: {channel.mention}, 인증 역할: {role.mention}")

    @commands.command(name="인증", aliases=["verify"])
    async def verify(self, ctx: commands.Context):
        st = await _load_settings()
        conf = st.get(str(ctx.guild.id), {})
        ch_id = conf.get("verify_channel_id")
        role_id = conf.get("verify_role_id")
        if not ch_id or not role_id:
            return await ctx.reply("인증이 아직 설정되지 않았습니다. `!인증설정 #채널 @역할`")
        if ctx.channel.id != ch_id:
            return await ctx.reply("이 명령은 지정된 인증 채널에서만 사용할 수 있어요.")
        role = ctx.guild.get_role(role_id)
        if not role:
            return await ctx.reply("인증 역할이 존재하지 않습니다. 다시 설정하세요.")
        try:
            await ctx.author.add_roles(role, reason="Verification")
            await ctx.reply(f"✅ 인증 완료! {role.mention} 역할이 부여되었습니다.")
        except discord.Forbidden:
            await ctx.reply("역할을 부여할 권한이 부족합니다. 봇에 '역할 관리' 권한을 주세요.")

    # ============ 역할 지급/삭제 ============
    @commands.command(name="역할지급", aliases=["giverole"])
    @commands.has_permissions(manage_roles=True)
    async def give_role(self, ctx: commands.Context, member: discord.Member, role: discord.Role):
        try:
            await member.add_roles(role, reason=f"Given by {ctx.author}")
            await ctx.reply(f"✅ {member.mention} 에게 {role.mention} 지급")
        except discord.Forbidden:
            await ctx.reply("봇의 역할 위치/권한이 낮아 실패했습니다.")

    @commands.command(name="역할삭제", aliases=["removerole"])
    @commands.has_permissions(manage_roles=True)
    async def remove_role(self, ctx: commands.Context, member: discord.Member, role: discord.Role):
        try:
            await member.remove_roles(role, reason=f"Removed by {ctx.author}")
            await ctx.reply(f"🗑️ {member.mention} 의 {role.mention} 제거")
        except discord.Forbidden:
            await ctx.reply("봇의 역할 위치/권한이 낮아 실패했습니다.")

    # ============ 기본 역할 설정 + 자동 지급 ============
    @commands.command(name="기본역할설정", aliases=["defrole","defaultrole"])
    async def set_default_role(self, ctx: commands.Context, role: discord.Role):
        if not _is_admin(self.bot, ctx):
            return await ctx.reply("권한이 없습니다.")
        st = await _load_settings()
        st.setdefault(str(ctx.guild.id), {})
        st[str(ctx.guild.id)]["default_role_id"] = role.id
        await _save_settings(st)
        await ctx.reply(f"✅ 기본 역할을 {role.mention} 로 설정했습니다. (신규 입장 시 자동 지급)")

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        # 기본 역할 자동 지급
        st = await _load_settings()
        conf = st.get(str(member.guild.id), {})
        role_id = conf.get("default_role_id")
        if role_id:
            role = member.guild.get_role(role_id)
            if role:
                with contextlib.suppress(Exception):
                    await member.add_roles(role, reason="Default role on join")

import contextlib
async def setup(bot: commands.Bot):
    await bot.add_cog(Admin(bot))
