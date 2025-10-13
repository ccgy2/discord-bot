import os, json, asyncio, random, discord, contextlib
from datetime import datetime, timezone, timedelta
from discord.ext import commands, tasks

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
os.makedirs(DATA_DIR, exist_ok=True)

BAL_PATH   = os.path.join(DATA_DIR, "balances.json")
LOG_PATH   = os.path.join(DATA_DIR, "transactions.json")
LOTTO_PATH = os.path.join(DATA_DIR, "lottery.json")
_lock = asyncio.Lock()

async def _load(path, default):
    async with _lock:
        if not os.path.exists(path):
            with open(path,"w",encoding="utf-8") as f:
                json.dump(default,f,ensure_ascii=False,indent=2)
                return json.loads(json.dumps(default))
        with open(path,"r",encoding="utf-8") as f: return json.load(f)

async def _save(path, data):
    async with _lock:
        with open(path,"w",encoding="utf-8") as f:
            json.dump(data,f,ensure_ascii=False,indent=2)

def _ensure_bal(b, uid, init=1000):
    if uid not in b: b[uid]={"money":init}

def _log(uid: str, desc: str, amt: int):
    return {"user": uid, "desc": desc, "amount": amt, "time": datetime.now().strftime("%Y-%m-%d %H:%M")}

class Lottery(commands.Cog):
    """복권/랜덤 이벤트 — 티켓 구매 후 정해진 시간에 자동 추첨"""
    def __init__(self, bot):
        self.bot = bot
        self.auto_draw.start()

    # ───── 기본 상태 보장
    async def _ensure_pool(self, guild_id: int):
        data = await _load(LOTTO_PATH, {})
        g = data.setdefault(str(guild_id), {
            "ticket_price": 500,
            "jackpot": 10000,
            "tickets": [],  # [{user_id, count}]
            "next_draw": (datetime.now(timezone.utc) + timedelta(hours=6)).timestamp()
        })
        await _save(LOTTO_PATH, data)
        return g, data

    # ───── 상태 확인
    @commands.command(name="복권", aliases=["lotto","로또"])
    async def status(self, ctx):
        g, _ = await self._ensure_pool(ctx.guild.id)
        total_tickets = sum(t["count"] for t in g["tickets"])
        left = max(0, int(g["next_draw"] - datetime.now(timezone.utc).timestamp()))
        m = left // 60
        await ctx.reply(
            f"🎟️ **복권 현황**\n"
            f"- 티켓 가격: {g['ticket_price']:,}원\n"
            f"- 잭팟(최소 상금): {g['jackpot']:,}원\n"
            f"- 판매된 티켓: {total_tickets}장\n"
            f"- 다음 추첨까지: ~{m}분"
        )

    # ───── 티켓 구매
    @commands.command(name="복권구매", aliases=["buyticket","티켓구매"])
    async def buy(self, ctx, count: int = 1):
        g, data = await self._ensure_pool(ctx.guild.id)
        count = max(1, min(100, int(count)))
        price = g["ticket_price"] * count

        bal = await _load(BAL_PATH, {}); uid = str(ctx.author.id); _ensure_bal(bal, uid)
        if bal[uid]["money"] < price:
            return await ctx.reply(f"잔액 부족! 필요 {price:,}원 / 보유 {bal[uid]['money']:,}원")

        bal[uid]["money"] -= price
        await _save(BAL_PATH, bal)

        # add ticket
        found = next((t for t in g["tickets"] if t["user_id"] == uid), None)
        if found: found["count"] += count
        else:     g["tickets"].append({"user_id": uid, "count": count})
        await _save(LOTTO_PATH, data)

        logs = await _load(LOG_PATH, [])
        logs.insert(0, _log(uid, f"복권 티켓 구매 x{count}", -price))
        if len(logs) > 300: logs = logs[:300]
        await _save(LOG_PATH, logs)

        await ctx.reply(f"✅ 복권 티켓 **{count}장** 구매 완료! (-{price:,}원)")

    # ───── 관리자 설정
    @commands.command(name="복권설정", aliases=["lottoset"])
    @commands.has_permissions(manage_guild=True)
    async def set_lotto(self, ctx, ticket_price: int, jackpot: int, hours: int = 6):
        g, data = await self._ensure_pool(ctx.guild.id)
        g["ticket_price"] = max(1, ticket_price)
        g["jackpot"] = max(0, jackpot)
        g["next_draw"] = (datetime.now(timezone.utc) + timedelta(hours=max(1, hours))).timestamp()
        await _save(LOTTO_PATH, data)
        await ctx.reply(f"⚙️ 설정 완료 — 가격 {g['ticket_price']:,}원 / 잭팟 {g['jackpot']:,}원 / {hours}시간마다 추첨")

    # ───── 수동 추첨
    @commands.command(name="복권추첨", aliases=["draw","추첨"])
    @commands.has_permissions(manage_guild=True)
    async def draw(self, ctx):
        await self._draw_guild(ctx.guild, manual_channel=ctx.channel)

    # ───── 자동 추첨 루프 (6시간 기본)
    @tasks.loop(minutes=1)
    async def auto_draw(self):
        data = await _load(LOTTO_PATH, {})
        now = datetime.now(timezone.utc).timestamp()
        changed = False
        for gid, g in list(data.items()):
            if now >= g.get("next_draw", 0):
                guild = self.bot.get_guild(int(gid))
                if guild:
                    with contextlib.suppress(Exception):
                        ch = guild.system_channel or next((c for c in guild.text_channels if c.permissions_for(guild.me).send_messages), None)
                        await self._draw_guild(guild, manual_channel=ch)
                # next draw 예약
                g["next_draw"] = (datetime.now(timezone.utc) + timedelta(hours=6)).timestamp()
                changed = True
        if changed: await _save(LOTTO_PATH, data)

    @auto_draw.before_loop
    async def before(self):
        await self.bot.wait_until_ready()

    # ───── 실제 추첨 로직
    async def _draw_guild(self, guild: discord.Guild, manual_channel: discord.abc.Messageable | None):
        import contextlib
        g, data = await self._ensure_pool(guild.id)
        tickets = g["tickets"]
        total_tickets = sum(t["count"] for t in tickets)
        if total_tickets == 0:
            if manual_channel:
                await manual_channel.send("🎟️ 판매된 티켓이 없어 이번 회차는 무효입니다.")
            return

        # 상금: 잭팟 + 판매금의 70% (가벼운 기본 룰)
        pool_money = sum(t["count"] for t in tickets) * g["ticket_price"]
        prize = g["jackpot"] + int(pool_money * 0.7)

        # 가중 랜덤
        bag = []
        for t in tickets:
            bag.extend([t["user_id"]] * int(t["count"]))
        winner_uid = random.choice(bag)

        # 지급
        bal = await _load(BAL_PATH, {})
        _ensure_bal(bal, winner_uid)
        bal[winner_uid]["money"] += prize
        await _save(BAL_PATH, bal)

        # 로그
        logs = await _load(LOG_PATH, [])
        logs.insert(0, _log(winner_uid, f"복권 당첨", prize))
        if len(logs) > 300: logs = logs[:300]
        await _save(LOG_PATH, logs)

        # 공지
        user = guild.get_member(int(winner_uid))
        uname = user.mention if user else f"User#{winner_uid}"
        if manual_channel:
            await manual_channel.send(f"🎉 **복권 추첨 결과!** 당첨자: {uname} — **+{prize:,}원** 🥳")

        # 초기화
        g["tickets"] = []
        g["jackpot"] = max(0, int(g["jackpot"] * 0.5))  # 잭팟 일부 유지 (재밌게)
        g["next_draw"] = (datetime.now(timezone.utc) + timedelta(hours=6)).timestamp()
        await _save(LOTTO_PATH, data)

async def setup(bot): await bot.add_cog(Lottery(bot))
