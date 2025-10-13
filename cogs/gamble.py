import os
import json
import random
import asyncio
from typing import Dict, Any
from discord.ext import commands

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
os.makedirs(DATA_DIR, exist_ok=True)
BAL_PATH = os.path.join(DATA_DIR, "balances.json")
_file_lock = asyncio.Lock()

DEFAULT_BALANCE = 1000

async def _load_balances() -> Dict[str, Any]:
    async with _file_lock:
        if not os.path.exists(BAL_PATH):
            return {}
        try:
            with open(BAL_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

async def _save_balances(balances: Dict[str, Any]) -> None:
    async with _file_lock:
        with open(BAL_PATH, "w", encoding="utf-8") as f:
            json.dump(balances, f, ensure_ascii=False, indent=2)

def _ensure_user(balances: Dict[str, Any], user_id: str, default_amt: int) -> None:
    if user_id not in balances:
        balances[user_id] = {"money": default_amt}

class Gamble(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        try:
            self.default_amt = int(bot.config.get("default_currency", DEFAULT_BALANCE))
        except Exception:
            self.default_amt = DEFAULT_BALANCE

    @commands.group(name="gamble", aliases=["도박"], invoke_without_command=True)
    async def gamble(self, ctx: commands.Context):
        p = self.bot.config.get("prefix", "!")
        txt = (
            f"**도박 시스템 명령어**\n"
            f"- `{p}도박 잔액` / `{p}gamble balance` — 잔액 확인\n"
            f"- `{p}도박 동전 <금액>` / `{p}gamble coin <금액>` — 동전 던지기(50/50)\n"
            f"- `{p}도박 슬롯 <금액>` / `{p}gamble slot <금액>` — 슬롯머신\n"
            f"- (관리자) `{p}도박 지급 @유저 <금액>` / `{p}gamble give @user <금액>`\n"
            f"- (관리자) `{p}도박 설정 @유저 <금액>` / `{p}gamble set @user <금액>`\n"
        )
        await ctx.reply(txt)

    @gamble.command(name="balance", aliases=["잔액"])
    async def balance(self, ctx: commands.Context):
        balances = await _load_balances()
        uid = str(ctx.author.id)
        _ensure_user(balances, uid, self.default_amt)
        await _save_balances(balances)
        await ctx.reply(f"{ctx.author.mention} 현재 잔액: {balances[uid]['money']}원")

    @gamble.command(name="coin", aliases=["동전"])
    async def coin(self, ctx: commands.Context, amount: int = 0):
        if amount <= 0:
            return await ctx.reply("배팅 금액을 입력하세요. 예: `!도박 동전 100`")
        balances = await _load_balances()
        uid = str(ctx.author.id)
        _ensure_user(balances, uid, self.default_amt)

        if balances[uid]["money"] < amount:
            return await ctx.reply("잔액이 부족합니다.")

        win = random.random() < 0.5
        if win:
            balances[uid]["money"] += amount
            await _save_balances(balances)
            return await ctx.reply(f"🎉 동전 결과: **당첨!** {amount}원 획득. 현재 잔액: {balances[uid]['money']}원")
        else:
            balances[uid]["money"] -= amount
            await _save_balances(balances)
            return await ctx.reply(f"😢 동전 결과: **꽝** {amount}원 손실. 현재 잔액: {balances[uid]['money']}원")

    @gamble.command(name="slot", aliases=["슬롯"])
    async def slot(self, ctx: commands.Context, amount: int = 0):
        if amount <= 0:
            return await ctx.reply("배팅 금액을 입력하세요. 예: `!도박 슬롯 200`")
        balances = await _load_balances()
        uid = str(ctx.author.id)
        _ensure_user(balances, uid, self.default_amt)

        if balances[uid]["money"] < amount:
            return await ctx.reply("잔액이 부족합니다.")

        icons = ['🍒', '🍋', '🔔', '⭐', '7️⃣']
        a, b, c = random.choice(icons), random.choice(icons), random.choice(icons)
        line = f"{a} {b} {c}\n"

        if a == b == c:
            gain = amount * 5
            balances[uid]["money"] += gain
            line += f"🎉 **잭팟!** {gain}원 획득! 현재 잔액: {balances[uid]['money']}원"
        elif a == b or b == c or a == c:
            gain = int(amount * 1.5)
            balances[uid]["money"] += gain
            line += f"👍 부분 당첨: {gain}원 획득! 현재 잔액: {balances[uid]['money']}원"
        else:
            balances[uid]["money"] -= amount
            line += f"😢 꽝! {amount}원 손실. 현재 잔액: {balances[uid]['money']}원"

        await _save_balances(balances)
        await ctx.reply(line)

    @gamble.command(name="give", aliases=["지급"])
    async def give(self, ctx: commands.Context, member: commands.UserConverter = None, amount: int = None):
        is_owner = False
        try:
            owner_id = self.bot.config.get("owner_id")
            if owner_id and int(owner_id) == ctx.author.id:
                is_owner = True
        except Exception:
            pass
        if not (is_owner or ctx.author.guild_permissions.manage_guild or ctx.author.guild_permissions.administrator):
            return await ctx.reply("권한이 없습니다. (서버 관리자 또는 봇 오너 필요)")
        if member is None or amount is None:
            return await ctx.reply("사용법: `!도박 지급 @유저 1000`")

        balances = await _load_balances()
        tid = str(member.id)
        _ensure_user(balances, tid, self.default_amt)
        balances[tid]["money"] += int(amount)
        await _save_balances(balances)
        await ctx.reply(f"완료: {member.mention}에게 {amount}원 지급. 현재 잔액: {balances[tid]['money']}원")

    @gamble.command(name="set", aliases=["설정"])
    async def setbal(self, ctx: commands.Context, member: commands.UserConverter = None, amount: int = None):
        is_owner = False
        try:
            owner_id = self.bot.config.get("owner_id")
            if owner_id and int(owner_id) == ctx.author.id:
                is_owner = True
        except Exception:
            pass
        if not (is_owner or ctx.author.guild_permissions.manage_guild or ctx.author.guild_permissions.administrator):
            return await ctx.reply("권한이 없습니다. (서버 관리자 또는 봇 오너 필요)")
        if member is None or amount is None:
            return await ctx.reply("사용법: `!도박 설정 @유저 5000`")

        balances = await _load_balances()
        tid = str(member.id)
        _ensure_user(balances, tid, self.default_amt)
        balances[tid]["money"] = int(amount)
        await _save_balances(balances)
        await ctx.reply(f"완료: {member.mention} 잔액을 {amount}원으로 설정했습니다.")

async def setup(bot: commands.Bot):
    await bot.add_cog(Gamble(bot))
