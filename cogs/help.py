import inspect
from typing import List, Dict, Tuple

import discord
from discord.ext import commands


# ─────────────────────────────────────────────
# 고정 카테고리 순서 & 이름 매핑
# ─────────────────────────────────────────────
CATEGORY_ORDER = [
    "Basic",        # 기본/유틸
    "Music",        # 음악
    "Announce",     # 공지
    "Economy",      # 경제(잔액/은행/송금/랭킹)
    "Gamble",       # 도박
    "Quiz",         # 퀴즈
    "Stock",        # 주식
    "Shop",         # 상점/인벤토리
    "Lottery",      # 복권
    "Prefix",       # 접두사
    # 그 밖의 코그는 마지막 "기타"로
]

FRIENDLY_NAME = {
    "Basic": "🎯 기본 / 유틸",
    "Music": "🎵 음악",
    "Announce": "📢 공지",
    "Economy": "💰 경제",
    "Gamble": "🎲 도박",
    "Quiz": "🧩 퀴즈",
    "Stock": "📈 주식",
    "Shop": "🛍️ 상점 / 인벤토리",
    "Lottery": "🎟️ 복권",
    "Prefix": "⚙️ 접두사",
    "기타": "🧰 기타",
}


# ─────────────────────────────────────────────
# 유틸
# ─────────────────────────────────────────────
def _current_prefix(bot: commands.Bot, message: discord.Message) -> str:
    """동적 prefix 지원(get_prefix가 함수인 케이스 포함)."""
    p = bot.command_prefix
    if callable(p):
        p = p(bot, message)
    if isinstance(p, (list, tuple)):
        p = p[0]
    return str(p)


def _signature(prefix: str, cmd: commands.Command) -> str:
    """간단한 시그니처 문자열 생성."""
    parts = []
    for name, p in cmd.clean_params.items():
        if p.default is not inspect._empty:
            parts.append(f"[{name}]")
        else:
            parts.append(f"<{name}>")
    arg = " " + " ".join(parts) if parts else ""
    return f"`{prefix}{cmd.qualified_name}{arg}`"


# ─────────────────────────────────────────────
# 페이지용 뷰(버튼 + 카테고리 셀렉트)
# ─────────────────────────────────────────────
class HelpView(discord.ui.View):
    def __init__(self, author_id: int, pages: List[discord.Embed], labels: List[str]):
        super().__init__(timeout=120)
        self.author_id = author_id
        self.pages = pages
        self.labels = labels
        self.index = 0

        # 셀렉트에 카테고리 주입
        self.category_select.options = [
            discord.SelectOption(label=lbl, value=str(i)) for i, lbl in enumerate(labels)
        ]
        # 버튼 활성화 초기화
        self._refresh_buttons()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user and interaction.user.id == self.author_id

    def _refresh_buttons(self):
        single = len(self.pages) <= 1
        for b in (self.first_btn, self.prev_btn, self.next_btn, self.last_btn):
            b.disabled = single
        self.category_select.disabled = single

        self.first_btn.disabled = single or self.index == 0
        self.prev_btn.disabled = single or self.index == 0
        self.next_btn.disabled = single or self.index == len(self.pages) - 1
        self.last_btn.disabled = single or self.index == len(self.pages) - 1

    async def _update(self, interaction: discord.Interaction):
        self._refresh_buttons()
        await interaction.response.edit_message(embed=self.pages[self.index], view=self)

    @discord.ui.button(label="⏮ 처음", style=discord.ButtonStyle.secondary)
    async def first_btn(self, interaction: discord.Interaction, _: discord.ui.Button):
        self.index = 0
        await self._update(interaction)

    @discord.ui.button(label="◀ 이전", style=discord.ButtonStyle.secondary)
    async def prev_btn(self, interaction: discord.Interaction, _: discord.ui.Button):
        self.index = max(0, self.index - 1)
        await self._update(interaction)

    @discord.ui.button(label="다음 ▶", style=discord.ButtonStyle.secondary)
    async def next_btn(self, interaction: discord.Interaction, _: discord.ui.Button):
        self.index = min(len(self.pages) - 1, self.index + 1)
        await self._update(interaction)

    @discord.ui.button(label="마지막 ⏭", style=discord.ButtonStyle.secondary)
    async def last_btn(self, interaction: discord.Interaction, _: discord.ui.Button):
        self.index = len(self.pages) - 1
        await self._update(interaction)

    @discord.ui.select(placeholder="카테고리로 이동")
    async def category_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        self.index = int(select.values[0])
        await self._update(interaction)

    @discord.ui.button(label="🗑 닫기", style=discord.ButtonStyle.danger)
    async def close_btn(self, interaction: discord.Interaction, _: discord.ui.Button):
        await interaction.response.edit_message(content="(도움말 닫힘)", embed=None, view=None)
        self.stop()


# ─────────────────────────────────────────────
# Cog 본체
# ─────────────────────────────────────────────
class HelpCog(commands.Cog):
    """자동 갱신 도움말 (카테고리 고정 + 상세 페이지 + 페이지 네비)"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ------- 메인: !도움 [명령어] -------
    @commands.command(name="도움", aliases=["help", "도움말", "헬프"])
    async def help_command(self, ctx: commands.Context, *, query: str | None = None):
        """
        - `!도움` : 카테고리별 도움말(버튼/셀렉트로 페이지 전환)
        - `!도움 <명령>` : 해당 명령의 상세 페이지
        """
        if query:
            return await self._send_command_detail(ctx, query.strip())

        prefix = _current_prefix(self.bot, ctx.message)
        # 1) 사용 가능한 명령만 수집
        cat_map: Dict[str, List[Tuple[str, str]]] = {}  # {cog_name: [(display, raw_name), ...]}

        for cmd in sorted(self.bot.commands, key=lambda c: c.qualified_name.lower()):
            if cmd.hidden or not cmd.enabled:
                continue
            # 실행 가능 여부 필터(권한/채널 등)
            try:
                can = await cmd.can_run(ctx)
            except Exception:
                can = False
            if not can:
                continue

            # 항목 문자열
            sig = _signature(prefix, cmd)
            summary = (cmd.help or "설명 없음").strip().splitlines()[0]
            display = f"{sig} — {summary}"

            cog_name = cmd.cog_name or "기타"
            cat_map.setdefault(cog_name, []).append((display, cmd.qualified_name))

        # 2) 고정 순서에 맞게 페이지 생성
        ordered_keys = [k for k in CATEGORY_ORDER if k in cat_map]  # 미존재는 제외
        others = [k for k in cat_map.keys() if k not in CATEGORY_ORDER]
        if others:
            ordered_keys += sorted(others)
        if not ordered_keys:
            return await ctx.reply("표시할 명령어가 없습니다.")

        pages: List[discord.Embed] = []
        labels: List[str] = []

        for cog_name in ordered_keys:
            entries = cat_map[cog_name]
            # 너무 길어지면 1페이지에 15개씩 분할
            chunks = [entries[i:i+15] for i in range(0, len(entries), 15)]
            friendly = FRIENDLY_NAME.get(cog_name, FRIENDLY_NAME.get("기타", "기타"))

            for idx, chunk in enumerate(chunks, start=1):
                em = discord.Embed(
                    title=f"📖 {friendly}",
                    description=(f"접두사: `{prefix}`  |  카테고리: **{friendly}**\n"
                                 f"도움말 상세: `{prefix}도움 <명령어>`"),
                    color=0x58b9ff
                )
                body = "\n".join(f"- {d}" for d, _ in chunk)
                em.add_field(name="명령어 목록", value=body, inline=False)
                em.set_footer(text=f"{ctx.guild.name if ctx.guild else 'DM'} · 요청자: {ctx.author.display_name}",
                              icon_url=ctx.author.display_avatar.url)
                pages.append(em)

                # 라벨(카테고리 이름 + (분할 페이지 표시))
                label = friendly if len(chunks) == 1 else f"{friendly} · {idx}/{len(chunks)}"
                labels.append(label)

        view = HelpView(author_id=ctx.author.id, pages=pages, labels=labels)
        await ctx.reply(embed=pages[0], view=view)

    # ------- 상세 페이지: !도움 <명령> -------
    async def _send_command_detail(self, ctx: commands.Context, name: str):
        prefix = _current_prefix(self.bot, ctx.message)

        # 별칭 포함 검색
        cmd = self.bot.get_command(name)
        if not cmd:
            # 공백 포함한 이름(서브커맨드) 보정
            lowered = name.lower().strip()
            # try exact alias match
            for c in self.bot.commands:
                if lowered in [c.qualified_name.lower(), *[a.lower() for a in c.aliases]]:
                    cmd = c
                    break

        if not cmd:
            return await ctx.reply(f"`{name}` 명령을 찾을 수 없습니다. 정확한 이름을 입력해 주세요.")

        # 권한 체크 → 실행 불가면 상세 도움도 숨김
        try:
            can = await cmd.can_run(ctx)
        except Exception:
            can = False
        if not can:
            return await ctx.reply("이 명령은 현재 권한/환경에서 사용할 수 없습니다.")

        # 본문 구성
        sig = _signature(prefix, cmd)
        desc = (cmd.help or "설명 없음").strip()
        aliases = ", ".join(cmd.aliases) if cmd.aliases else "없음"
        category = FRIENDLY_NAME.get(cmd.cog_name or "기타", "기타")

        # 체크(권한) 간단 표기
        checks = []
        for check in getattr(cmd, "checks", []):
            txt = getattr(check, "__name__", "check")
            if "has_permissions" in txt:
                checks.append("권한 필요")
            elif "is_owner" in txt:
                checks.append("봇 소유자 전용")
            elif "has_guild_permissions" in txt:
                checks.append("서버 권한 필요")
            # (필요하면 더 추가)
        checks_text = ", ".join(checks) if checks else "특별 조건 없음"

        em = discord.Embed(title=f"🔎 명령 상세: {cmd.qualified_name}", color=0x00b894)
        em.add_field(name="사용법", value=sig, inline=False)
        em.add_field(name="설명", value=desc, inline=False)
        em.add_field(name="카테고리", value=category, inline=True)
        em.add_field(name="별칭", value=aliases, inline=True)
        em.add_field(name="실행 조건", value=checks_text, inline=False)
        em.set_footer(text=f"요청자: {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)

        # 간단 예시(파라미터 이름 기반 자동 예시)
        if cmd.clean_params:
            example_args = " ".join(f"<{n}>" for n in cmd.clean_params.keys())
            em.add_field(name="예시", value=f"`{prefix}{cmd.qualified_name} {example_args}`", inline=False)

        await ctx.reply(embed=em)


async def setup(bot: commands.Bot):
    await bot.add_cog(HelpCog(bot))
