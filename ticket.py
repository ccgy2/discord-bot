import discord, asyncio, os, json
from discord.ext import commands

def is_admin(ctx):
    p = ctx.author.guild_permissions
    return p.administrator or p.manage_channels or p.manage_guild

class Ticket(commands.Cog):
    def __init__(self, bot): self.bot = bot

    @commands.command(name="문의", aliases=["ticket","티켓"])
    async def create_ticket(self, ctx: commands.Context, *, reason: str = "문의"):
        g = ctx.guild
        name = f"ticket-{ctx.author.id}"
        overwrites = {
            g.default_role: discord.PermissionOverwrite(read_messages=False),
            ctx.author: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            g.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True)
        }
        ch = await g.create_text_channel(name, overwrites=overwrites, reason=reason)
        await ch.send(f"{ctx.author.mention} 문의가 접수되었습니다. 관리자가 곧 응답할게요. 종료: `!종료`")
        await ctx.reply(f"🎟️ {ch.mention} 채널을 생성했습니다.")

    @commands.command(name="종료", aliases=["closeticket","티켓종료"])
    async def close_ticket(self, ctx: commands.Context):
        if not ctx.channel.name.startswith("ticket-"): return await ctx.reply("티켓 채널에서만 사용 가능합니다.")
        await ctx.reply("채널을 3초 뒤 삭제합니다."); await asyncio.sleep(3)
        await ctx.channel.delete(reason="Ticket closed")

async def setup(bot): await bot.add_cog(Ticket(bot))
