# cogs/stock.py
import os, json, random, asyncio, discord, io, datetime
import matplotlib.pyplot as plt
from discord.ext import commands, tasks

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
os.makedirs(DATA_DIR, exist_ok=True)
STOCK_PATH = os.path.join(DATA_DIR, "stocks.json")
PORT_PATH = os.path.join(DATA_DIR, "portfolios.json")
BAL_PATH = os.path.join(DATA_DIR, "balances.json")
_lock = asyncio.Lock()

# ───────────── 기본 상장 종목 ─────────────
DEFAULT_STOCKS = {
    "SAMSUNG":     71000,   # 삼성전자
    "HYUNDAI":     195000,  # 현대자동차
    "KAKAO":       43000,   # 카카오
    "NAVER":       185000,  # 네이버
    "LG":          93000,   # LG전자
    "SKHYNIX":     118000,  # SK하이닉스
    "POSCO":       5000000,  # 포스코홀딩스
    "HANWHA":      33000,   # 한화
    "LOTTE":       28000,   # 롯데지주
    "KT":          38000,   # KT
    "CJ":          110000,  # CJ제일제당
    "KORAIL":      25000,   # 코레일
    "DAEWOO":      19000,   # 대우건설
    "S-OIL":       85000,   # 에쓰오일
    "KIA":         89000    # 기아
}

# ───────────── 유틸 함수 ─────────────
async def _load_json(path, default):
    async with _lock:
        if not os.path.exists(path):
            with open(path, "w", encoding="utf-8") as f: json.dump(default, f, ensure_ascii=False, indent=2)
            return json.loads(json.dumps(default))
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

async def _save_json(path, data):
    async with _lock:
        with open(path, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=2)

def _ensure_bal(balances, uid, init=1000):
    if uid not in balances:
        balances[uid] = {"money": init}

# ───────────── 코그 ─────────────
class StockMarket(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.market_loop.start()

    # ───────────── 시세 자동 변동 ─────────────
    @tasks.loop(minutes=10)
    async def market_loop(self):
        stocks = await _load_json(STOCK_PATH, {})
        if not stocks:
            for name, price in DEFAULT_STOCKS.items():
                stocks[name] = {"price": price, "history": [price]}
        changed = []
        for name, info in stocks.items():
            p = int(info.get("price", 100))
            rate = random.uniform(-0.15, 0.15)
            new_p = max(10, int(p * (1 + rate)))
            stocks[name]["price"] = new_p
            hist = info.get("history", [])
            hist.append(new_p)
            if len(hist) > 50: hist.pop(0)
            stocks[name]["history"] = hist
            changed.append((name, p, new_p, rate))
        await _save_json(STOCK_PATH, stocks)

        # 콘솔 로그용
        print("📈 [Market Update]")
        for n, old, new, r in changed:
            diff = "▲" if new > old else "▼" if new < old else "→"
            print(f" {n}: {old} → {new} ({diff}{r*100:.1f}%)")

    @market_loop.before_loop
    async def before_market(self):
        await self.bot.wait_until_ready()

    # ───────────── 명령어 ─────────────
    @commands.group(name="주식", invoke_without_command=True)
    async def stock_main(self, ctx):
        """주식 관련 명령어 모음"""
        p = self.bot.config.get("prefix", "!")
        msg = (
            f"📊 **주식 시장 명령어**\n"
            f"- `{p}주식목록` 현재 모든 주식 가격 보기\n"
            f"- `{p}주식구매 <회사> <수량>` 주식 매수\n"
            f"- `{p}주식판매 <회사> <수량>` 주식 매도\n"
            f"- `{p}내주식` 내 포트폴리오 보기\n"
            f"- `{p}주식차트 <회사>` 최근 시세 그래프 보기\n"
            f"- `{p}주식추가 <이름> <시작가>` (관리자 전용)\n"
        )
        await ctx.reply(msg)

    @commands.command(name="주식목록")
    async def list_stocks(self, ctx):
        stocks = await _load_json(STOCK_PATH, DEFAULT_STOCKS)
        if isinstance(stocks, dict) and not stocks:
            stocks = {n: {"price": p, "history": [p]} for n, p in DEFAULT_STOCKS.items()}
        desc = []
        for name, info in stocks.items():
            desc.append(f"**{name}** — {info.get('price', 0):,}원")
        embed = discord.Embed(title="📈 현재 주식 시세", description="\n".join(desc), color=0x2ecc71)
        embed.set_footer(text="10분마다 자동 갱신")
        await ctx.reply(embed=embed)

    @commands.command(name="주식구매")
    async def buy_stock(self, ctx, name: str, amount: int):
        name = name.upper()
        stocks = await _load_json(STOCK_PATH, DEFAULT_STOCKS)
        if name not in stocks: return await ctx.reply("존재하지 않는 회사입니다.")
        price = int(stocks[name]["price"])
        total = price * amount

        balances = await _load_json(BAL_PATH, {})
        uid = str(ctx.author.id)
        _ensure_bal(balances, uid)
        if balances[uid]["money"] < total:
            return await ctx.reply(f"💸 잔액 부족! 필요: {total:,}원, 보유: {balances[uid]['money']:,}원")

        balances[uid]["money"] -= total
        ports = await _load_json(PORT_PATH, {})
        ports.setdefault(uid, {})
        ports[uid][name] = ports[uid].get(name, 0) + amount

        await _save_json(BAL_PATH, balances)
        await _save_json(PORT_PATH, ports)
        await ctx.reply(f"✅ {name} {amount}주 구매 완료! ({total:,}원 차감)")

    @commands.command(name="주식판매")
    async def sell_stock(self, ctx, name: str, amount: int):
        name = name.upper()
        stocks = await _load_json(STOCK_PATH, DEFAULT_STOCKS)
        ports = await _load_json(PORT_PATH, {})
        balances = await _load_json(BAL_PATH, {})

        uid = str(ctx.author.id)
        _ensure_bal(balances, uid)
        if uid not in ports or name not in ports[uid] or ports[uid][name] < amount:
            return await ctx.reply("보유한 주식이 부족합니다.")

        price = int(stocks[name]["price"])
        total = price * amount
        ports[uid][name] -= amount
        if ports[uid][name] <= 0: ports[uid].pop(name)
        balances[uid]["money"] += total

        await _save_json(PORT_PATH, ports)
        await _save_json(BAL_PATH, balances)
        await ctx.reply(f"💰 {name} {amount}주 판매 완료! ({total:,}원 수익)")

    @commands.command(name="내주식")
    async def my_stocks(self, ctx):
        uid = str(ctx.author.id)
        ports = await _load_json(PORT_PATH, {})
        stocks = await _load_json(STOCK_PATH, DEFAULT_STOCKS)
        if uid not in ports or not ports[uid]:
            return await ctx.reply("보유한 주식이 없습니다.")
        total_val = 0
        lines = []
        for name, count in ports[uid].items():
            price = int(stocks.get(name, {}).get("price", 0))
            val = price * count
            total_val += val
            lines.append(f"**{name}** — {count}주 (평가금 {val:,}원)")
        embed = discord.Embed(title=f"📊 {ctx.author.display_name}님의 포트폴리오", description="\n".join(lines), color=0x3498db)
        embed.add_field(name="총 평가금", value=f"{total_val:,}원")
        await ctx.reply(embed=embed)

    @commands.command(name="주식추가")
    @commands.has_permissions(administrator=True)
    async def add_stock(self, ctx, name: str, price: int):
        name = name.upper()
        stocks = await _load_json(STOCK_PATH, DEFAULT_STOCKS)
        if name in stocks:
            return await ctx.reply("이미 존재하는 종목입니다.")
        stocks[name] = {"price": price, "history": [price]}
        await _save_json(STOCK_PATH, stocks)
        await ctx.reply(f"✅ 새 종목 `{name}` 상장 완료! (시작가 {price:,}원)")

    @commands.command(name="주식차트")
    async def stock_chart(self, ctx, name: str):
        name = name.upper()
        stocks = await _load_json(STOCK_PATH, DEFAULT_STOCKS)
        if name not in stocks:
            return await ctx.reply("존재하지 않는 종목입니다.")

        hist = stocks[name].get("history", [])
        if len(hist) < 2:
            return await ctx.reply("차트를 그릴 데이터가 부족합니다.")

        plt.figure(figsize=(5,3))
        plt.plot(hist, marker="o", linestyle="-", color="green")
        plt.title(f"{name} 주가 변동")
        plt.xlabel("시간(단위 10분)")
        plt.ylabel("가격(원)")
        plt.grid(True)
        buf = io.BytesIO()
        plt.savefig(buf, format="png")
        buf.seek(0)
        plt.close()

        file = discord.File(buf, filename="chart.png")
        await ctx.reply(file=file)

async def setup(bot):
    await bot.add_cog(StockMarket(bot))
