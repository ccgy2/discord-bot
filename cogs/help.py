import inspect
import discord
from discord.ext import commands

def _command_signature(prefix: str, cmd: commands.Command) -> str:
    # 파라미터 간단 표기 (자세한 시그니처는 생략)
    params = []
    for name, p in cmd.clean_params.items():
        if p.default is not inspect._empty:
            params.append(f"[{name}]")
        else:
            params.append(f"<{name}>")
    arg = " ".join(params)
    return f"`{prefix}{cmd.qualified_name} {arg}`".strip()

class HelpCog(commands.Cog):
    """자동 갱신 도움말"""
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="도움", aliases=["help","도움말","헬프"])
    async def help_command(self, ctx: commands.Context):
        # 현재 서버 접두사 추출
        if callable(self.bot.command_prefix):
            prefix = self.bot.command_prefix(self.bot, ctx.message)
        else:
            prefix = self.bot.command_prefix
        if isinstance(prefix, (list, tuple)):
            prefix = prefix[0]
        prefix = str(prefix)

        is_dm = ctx.guild is None
        embed = discord.Embed(
            title="📖 야르봇 자동 도움말",
            description=f"모든 명령어는 `{prefix}` 로 시작합니다.\n"
                        f"예: `{prefix}도움`, `{prefix}재생 <노래>`\n\n"
                        f"※ 현재 당신이 **사용할 수 있는** 명령어만 표시됩니다.",
            color=0x58b9ff
        )

        # Cog별로 정렬
        # command.can_run(ctx) 평가로 사용 불가(권한X) 명령어는 숨김
        cog_map: dict[str, list[str]] = {}
        for cmd in sorted(self.bot.commands, key=lambda c: c.qualified_name):
            # 숨김/비활성/DM 전용/기타 제외
            if cmd.hidden or not cmd.enabled:
                continue
            if cmd.cog_name in ("Owner",):  # 필요 시 제외
                continue
            try:
                can = await cmd.can_run(ctx)
            except Exception:
                can = False
            if not can:
                continue

            # 하위 명령 그룹 등은 기본 커맨드만 표시
            if isinstance(cmd, commands.Group):
                # 그룹 자체 사용법만
                sig = _command_signature(prefix, cmd)
                entry = f"{sig} — {cmd.help or '그룹 명령어'}"
            else:
                sig = _command_signature(prefix, cmd)
                entry = f"{sig} — {cmd.help or '설명 없음'}"

            cat = cmd.cog_name or "기타"
            cog_map.setdefault(cat, []).append(entry)

        # 섹션 렌더링
        if not cog_map:
            embed.description += "\n\n표시할 명령어가 없습니다."
        else:
            for cat, entries in sorted(cog_map.items()):
                # 너무 길어지지 않게 상위 25개만 표시
                chunk = "\n".join(entries[:25])
                embed.add_field(name=f"**{cat}**", value=chunk, inline=False)

        embed.set_footer(text=f"요청자: {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)
        await ctx.reply(embed=embed)

async def setup(bot):
    await bot.add_cog(HelpCog(bot))
