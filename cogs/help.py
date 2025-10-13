import discord
from discord.ext import commands

class HelpCog(commands.Cog):
    """통합 도움말 시스템"""
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="도움", aliases=["help"])
    async def help_command(self, ctx):
        prefix = self.bot.config.get("prefix", "!")
        is_admin = ctx.author.guild_permissions.administrator

        embed = discord.Embed(
            title="📖 야르봇 통합 도움말",
            description=f"모든 명령어는 `{prefix}` 로 시작합니다.\n예: `{prefix}ping`, `{prefix}도박 1000`\n\n🟢 일반 유저용 | 🔴 관리자 전용",
            color=0x6cc644
        )

        # ──────────────── 일반 명령어 ────────────────
        embed.add_field(
            name="🎯 기본 / 유틸리티",
            value=(
                f"`{prefix}ping` — 봇 응답 속도 확인\n"
                f"`{prefix}chat <질문>` — AI 또는 기본 챗봇 대화\n"
                f"`{prefix}서버정보` — 서버 상태 보기\n"
                f"`{prefix}내정보` — 내 역할/가입일 표시\n"
            ),
            inline=False
        )

        embed.add_field(
            name="💰 경제 / 출석 / 도박 / 퀴즈",
            value=(
                f"`{prefix}출석` — 하루 1회 코인 수령\n"
                f"`{prefix}잔액` — 내 지갑 잔액 확인\n"
                f"`{prefix}도박 <금액>` — 랜덤 베팅 게임\n"
                f"`{prefix}퀴즈` — 랜덤 문제 참여 (이모지 반응)\n"
                f"`{prefix}송금 @유저 <금액>` — 다른 유저에게 송금\n"
                f"`{prefix}거래기록` — 최근 10개 거래 내역\n"
                f"`{prefix}예금 <금액>` / `{prefix}인출 <금액>` — 은행 입출금\n"
                f"`{prefix}은행잔액` — 은행 보관 금액 확인\n"
                f"`{prefix}부자랭킹` — 총 자산 순위 표시\n"
            ),
            inline=False
        )

        embed.add_field(
            name="📈 주식 / 배당",
            value=(
                f"`{prefix}주식목록` — 주식 시장 보기\n"
                f"`{prefix}매수 <회사> <개수>` — 주식 구매\n"
                f"`{prefix}매도 <회사> <개수>` — 주식 판매\n"
                f"`{prefix}주식그래프 <회사>` — 시세 그래프 표시\n"
                f"`{prefix}배당지급` — (관리자 전용) 주식 보유자에게 배당 지급\n"
            ),
            inline=False
        )

        embed.add_field(
            name="🛍️ 상점 / 인벤토리",
            value=(
                f"`{prefix}상점` — 상점 목록 보기\n"
                f"`{prefix}구매 <이름>` — 아이템/역할 구매\n"
                f"`{prefix}인벤토리` — 내 아이템 목록 보기\n"
            ),
            inline=False
        )

        embed.add_field(
            name="🎟️ 복권 / 랜덤 이벤트",
            value=(
                f"`{prefix}복권` — 현재 회차 정보 보기\n"
                f"`{prefix}복권구매 [개수]` — 복권 티켓 구매\n"
                f"`{prefix}복권추첨` — 수동 추첨 (관리자)\n"
                f"자동 추첨 — 설정된 시간마다 자동 진행\n"
            ),
            inline=False
        )

        embed.add_field(
            name="🎵 음악 재생",
            value=(
                f"`{prefix}재생 <노래/URL>` — 음악 재생\n"
                f"`{prefix}스킵` — 다음 곡으로 넘기기\n"
                f"`{prefix}정지` / `{prefix}나가` — 음악 중지 및 퇴장\n"
                f"`{prefix}반복 <one/all/off>` — 반복 모드 변경\n"
                f"`{prefix}볼륨 <수치>` — 볼륨 조절 및 저장\n"
                f"`{prefix}셔플` — 대기열 랜덤 재생\n"
                f"`{prefix}대기열` — 현재 재생 목록 확인\n"
            ),
            inline=False
        )

        embed.add_field(
            name="📢 공지 / 안내",
            value=(
                f"`{prefix}공지 #채널 제목 | 내용` — 공지 작성 (관리자만)\n"
                f"`{prefix}공지역할설정 @역할` — 공지 시 멘션되는 역할 설정\n"
            ),
            inline=False
        )

        # ──────────────── 관리자 전용 ────────────────
        if is_admin:
            embed.add_field(
                name="🛠️ 관리자 전용",
                value=(
                    f"`{prefix}청소 <개수>` — 최근 메시지 삭제\n"
                    f"`{prefix}역할지급 @유저 @역할` — 역할 추가\n"
                    f"`{prefix}역할삭제 @유저 @역할` — 역할 제거\n"
                    f"`{prefix}기본역할설정 @역할` — 서버 입장 시 자동 역할\n"
                    f"`{prefix}인증설정 #채널 @역할` — 인증 시스템 설정\n"
                    f"`{prefix}복권설정 <가격> <잭팟> [시간]` — 복권 회차 설정\n"
                    f"`{prefix}상점추가 @역할 5000 [이름]` — 상점 등록\n"
                    f"`{prefix}상점추가 item 2000 이름` — 아이템 등록\n"
                    f"`{prefix}상점삭제 <이름>` — 상점 삭제\n"
                    f"`{prefix}이자 <비율>` — 모든 은행 잔액에 이자 지급\n"
                    f"`{prefix}배당지급 <비율>` — 주식 보유자에게 배당 지급\n"
                ),
                inline=False
            )

        embed.set_footer(text=f"요청자: {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)
        await ctx.reply(embed=embed)

async def setup(bot):
    await bot.add_cog(HelpCog(bot))
