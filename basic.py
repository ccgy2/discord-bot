import discord
from discord.ext import commands

class Basic(commands.Cog):
    def __init__(self, bot): self.bot = bot

    @commands.command(name="ping", aliases=["핑"])
    async def ping(self, ctx: commands.Context):
        msg = await ctx.reply("핑 테스트 중...")
        diff_ms = int((msg.created_at - ctx.message.created_at).total_seconds() * 1000)
        await msg.edit(content=f"Pong! API {round(self.bot.latency * 1000)}ms | RTT {diff_ms}ms")

    # ❗ 기존 help/도움 명령어는 제거했습니다.
    # 관리자 도움말(요약)은 그대로 유지해도 됩니다.
    @commands.command(name="adminhelp", aliases=["관리자도움말","관리자","관리"])
    @commands.has_permissions(administrator=True)
    async def admin_help(self, ctx: commands.Context):
        p = self.bot.config.get("prefix", "!")
        e = discord.Embed(title="🛠️ 관리자 전용 요약", color=0xe67e22)
        e.add_field(name="자세한 전체 도움말", value=f"`{p}도움` 을 사용하세요.", inline=False)
        await ctx.reply(embed=e)

async def setup(bot): await bot.add_cog(Basic(bot))
