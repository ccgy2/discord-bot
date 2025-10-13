import os, json, asyncio, time, discord
from discord.ext import commands
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
os.makedirs(DATA_DIR, exist_ok=True)

BAL_PATH = os.path.join(DATA_DIR, "balances.json")
BANK_PATH = os.path.join(DATA_DIR, "bank.json")
LOG_PATH = os.path.join(DATA_DIR, "transactions.json")
PORT_PATH = os.path.join(DATA_DIR, "portfolios.json")
STOCK_PATH = os.path.join(DATA_DIR, "stocks.json")

_lock = asyncio.Lock()

# -------- Utility: Load/Save --------
async def _load(path, default):
    async with _lock:
        if not os.path.exists(path):
            with open(path, "w", encoding="utf-8") as f:
                json.dump(default, f, ensure_ascii=False, indent=2)
                return json.loads(json.dumps(default))
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

async def _save(path, data):
    async with _lock:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

def _ensure(b, uid, init=1000):
    if uid not in b:
        b[uid] = {"money": init}

def _log(uid: str, desc: str, amount: int):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    return {"user": uid, "desc": desc, "amount": amount, "time": ts}

# -------- Cog Start --------
class EconomyPlus(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ===========================
    # 💰 은행 시스템
    # ===========================
    @commands.command(name="예금", aliases=["deposit"])
    async def deposit(self, ctx, amount: int):
        if amount <= 0:
            return await ctx.reply("금액은 0보다 커야 합니다.")
        uid = str(ctx.author.id)
        bal = await _load(BAL_PATH, {})
        bank = await _load(BANK_PATH, {})
        _ensure(bal, uid)
        _ensure(bank, uid, 0)
        if bal[uid]["money"] < amount:
            return await ctx.reply("지갑에 잔액이 부족합니다.")
        bal[uid]["money"] -= amount
        bank[uid]["money"] = bank[uid].get("money", 0) + amount
        await _save(BAL_PATH, bal)
        await _save(BANK_PATH, bank)
        await self._add_log(uid, f"예금", -amount)
        await ctx.reply(f"🏦 {amount:,}원을 은행에 예금했습니다.")

    @commands.command(name="인출", aliases=["withdraw"])
    async def withdraw(self, ctx, amount: int):
        if amount <= 0:
            return await ctx.reply("금액은 0보다 커야 합니다.")
        uid = str(ctx.author.id)
        bal = await _load(BAL_PATH, {})
        bank = await _load(BANK_PATH, {})
        _ensure(bal, uid)
        _ensure(bank, uid, 0)
        if bank[uid]["money"] < amount:
            return await ctx.reply("은행 잔액이 부족합니다.")
        bank[uid]["money"] -= amount
        bal[uid]["money"] += amount
        await _save(BANK_PATH, bank)
        await _save(BAL_PATH, bal)
        await self._add_log(uid, f"인출", amount)
        await ctx.reply(f"💸 {amount:,}원을 인출했습니다.")

    @commands.command(name="은행잔액", aliases=["bank"])
    async def bank_balance(self, ctx):
        uid = str(ctx.author.id)
        bank = await _load(BANK_PATH, {})
        money = bank.get(uid, {}).get("money", 0)
        await ctx.reply(f"🏦 현재 은행 잔액: **{money:,}원**")

    @commands.command(name="이자", aliases=["interest"])
    @commands.has_permissions(administrator=True)
    async def give_interest(self, ctx, rate: float = 1.0):
        bank = await _load(BANK_PATH, {})
        total = 0
        for uid, data in bank.items():
            bal = data.get("money", 0)
            if bal > 0:
                gain = int(bal * (rate / 100))
                data["money"] += gain
                total += gain
                await self._add_log(uid, f"은행 이자 {rate}%", gain)
        await _save(BANK_PATH, bank)
        await ctx.reply(f"💰 모든 유저에게 {rate}% 이자를 지급했습니다. 총 지급액: {total:,}원")

    # ===========================
    # 💸 송금 시스템
    # ===========================
    @commands.command(name="송금", aliases=["transfer"])
    async def transfer(self, ctx, member: discord.Member, amount: int):
        if amount <= 0:
            return await ctx.reply("송금 금액은 0보다 커야 합니다.")
        uid = str(ctx.author.id)
        tid = str(member.id)
        bal = await _load(BAL_PATH, {})
        _ensure(bal, uid)
        _ensure(bal, tid)
        if bal[uid]["money"] < amount:
            return await ctx.reply("잔액이 부족합니다.")
        tax = int(amount * 0.02)  # 2% 수수료
        net = amount - tax
        bal[uid]["money"] -= amount
        bal[tid]["money"] += net
        await _save(BAL_PATH, bal)
        await self._add_log(uid, f"송금 → {member.display_name}", -amount)
        await self._add_log(tid, f"송금 받음 ← {ctx.author.display_name}", net)
        await ctx.reply(f"💵 {member.mention}에게 {net:,}원을 송금했습니다. (세금 {tax:,}원)")

    # ===========================
    # 🧾 거래 기록
    # ===========================
    async def _add_log(self, uid: str, desc: str, amount: int):
        logs = await _load(LOG_PATH, [])
        logs.insert(0, _log(uid, desc, amount))
        if len(logs) > 300:
            logs = logs[:300]
        await _save(LOG_PATH, logs)

    @commands.command(name="거래기록", aliases=["log","logs"])
    async def logs(self, ctx):
        uid = str(ctx.author.id)
        logs = await _load(LOG_PATH, [])
        items = [x for x in logs if x["user"] == uid][:10]
        if not items:
            return await ctx.reply("📄 거래 기록이 없습니다.")
        lines = [f"[{x['time']}] {x['desc']} {'+' if x['amount']>0 else ''}{x['amount']:,}" for x in items]
        await ctx.reply("📊 최근 거래 기록:\n" + "\n".join(lines))

    # ===========================
    # 💹 배당 시스템
    # ===========================
    @commands.command(name="배당지급", aliases=["dividend"])
    @commands.has_permissions(administrator=True)
    async def give_dividend(self, ctx, rate: float = 2.0):
        stocks = await _load(STOCK_PATH, {})
        ports = await _load(PORT_PATH, {})
        balances = await _load(BAL_PATH, {})
        total_paid = 0
        for uid, userstocks in ports.items():
            gain = 0
            for name, count in userstocks.items():
                if name not in stocks:
                    continue
                price = stocks[name].get("price", 0)
                gain += int(price * count * (rate / 100))
            if gain > 0:
                _ensure(balances, uid)
                balances[uid]["money"] += gain
                await self._add_log(uid, f"주식 배당 ({rate}%)", gain)
                total_paid += gain
        await _save(BAL_PATH, balances)
        await ctx.reply(f"📈 배당률 {rate}%로 지급 완료! 총 {total_paid:,}원 분배됨.")

    # ===========================
    # 🏆 총자산 랭킹
    #  (⚠ level.py의 '랭킹' 명령어와 충돌 방지를 위해 '랭킹' 별칭은 사용하지 않음)
    # ===========================
    @commands.command(name="부자랭킹", aliases=["richrank","자산랭킹","부자순위"])
    async def rank(self, ctx):
        bal = await _load(BAL_PATH, {})
        bank = await _load(BANK_PATH, {})
        stocks = await _load(STOCK_PATH, {})
        ports = await _load(PORT_PATH, {})

        ranking = []
        for uid, b in bal.items():
            total = b.get("money", 0)
            total += bank.get(uid, {}).get("money", 0)
            if uid in ports:
                for name, c in ports[uid].items():
                    total += stocks.get(name, {}).get("price", 0) * c
            ranking.append((uid, total))

        ranking.sort(key=lambda x: x[1], reverse=True)
        lines = []
        for i, (uid, total) in enumerate(ranking[:10], start=1):
            user = ctx.guild.get_member(int(uid))
            name = user.display_name if user else f"User#{uid}"
            lines.append(f"{i}. {name} — {total:,}원")

        await ctx.reply("💰 **부자 랭킹 TOP 10** 💰\n" + "\n".join(lines))

async def setup(bot):
    await bot.add_cog(EconomyPlus(bot))
