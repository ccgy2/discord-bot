import os, json, asyncio, random, contextlib, discord
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

def _ensure_pool(data, guild_id: int):
    g = data.setdefault(str(guild_id), {
        "ticket_price": 500,
        "jackpot": 10000,
        "tickets": [],  # [{user_id, count}]
        "next_draw": (datetime.now(timezone.utc) + timedelta(hours=6)).timestamp(),
        "announce_channel_id": None,  # ← 공지 채널
    })
    return g

def _log(uid: str, desc: str, amt: int):
    return {"user": uid, "desc": desc, "amount": amt, "time": datetime.now().strftime("%Y-%m-%d %H:%M")}

class Lottery(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.auto_draw.start()

    # ───── 공지 채널 설정/확인
    @commands.command(name="복권채널설정", aliases=["lottosetch", "복권채널"])
    @commands.has_permissions(manage_guild=True)
    async def set_channel(self, ctx, channel: discord.TextChannel):
        data = await _load(LOTTO_PATH, {})
        g = _ensure_pool(data, ctx.guild.id)
        g["announce_channel_id"] = channel.id
        await _save(LOTTO_PATH, data)
        await ctx.reply(f"📢 복권 당첨 공지 채널을 {channel.mention} 로 설정했습니다.")

    @commands.command(name="복권채널확인", aliases=["lottogetch"])
    async def get_channel(self, ctx):
        data = await _load(LOTTO_PATH, {})
        g = _ensure_pool(data, ctx.guild.id)
        ch = ctx.guild.get_channel(g.get("announce_channel_id") or 0)
        if ch:
            return await ctx.reply(f"📢 현재 당첨 공지 채널: {ch.mention}")
        await ctx.reply("📢 당첨 공지 채널이 아직 설정되지 않았습니다. `!복권채널설정 #채널`")

    # ───── 상태 확인
    @commands.command(name="복권", aliases=["lotto","로또"])
    async def status(self, ctx):
        data = await _load(LOTTO_PATH, {})
        g = _ensure_pool(data, ctx.guild.id)
        total = sum(t["count"] for t in g["tickets"])
        left = max(0, int(g["next_draw"] - datetime.now(timezone.utc).timestamp()))
        m = left // 60
        ch = ctx.guild.get_channel(g.get("announce_channel_id") or 0)
        ch_txt = ch.mention if ch else "미설정"
        await ctx.reply(
            f"🎟️ **복권 현황**\n"
            f"- 티켓 가격: {g['ticket_price']:,}원\n"
            f"- 잭팟(최소 상금): {g['jackpot']:,}원\n"
            f"- 판매된 티켓: {total}장\n"
            f"- 다음 추첨까지: ~{m}분\n"
            f"- 당첨 공지 채널: {ch_txt}"
        )

    # ───── 티켓 구매
    @commands.command(name="복권구매", aliases=["buyticket","티켓구매"])
    async def buy(self, ctx, count: int = 1):
        data = await _load(LOTTO_PATH, {})
        g = _ensure_pool(data, ctx.guild.id)
        count = max(1, min(100, int(count)))
        price = g["ticket_price"] * count

        bal = await _load(BAL_PATH, {}); uid = str(ctx.author.id)
        if uid not in bal: bal[uid] = {"money": 1000}
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
        data = await _load(LOTTO_PATH, {})
        g = _ensure_pool(data, ctx.guild.id)
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

    # ───── 자동 추첨 루프
    @tasks.loop(minutes=1)
    async def auto_draw(self):
        data = await _load(LOTTO_PATH, {})
        now = datetime.now(timezone.utc).timestamp()
        changed = False
        for gid, g in list(data.items()):
            if now >= g.get("next_draw", 0):
                guild = self.bot.get_guild(int(gid))
                if guild:
                    ch = None
                    if g.get("announce_channel_id"):
                        ch = guild.get_channel(int(g["announce_channel_id"]))
                    if not ch:
                        # 마지막 보루: 시스템 채널이나 발언 가능한 텍스트 채널
                        ch = guild.system_channel or next(
                            (c for c in guild.text_channels if c.permissions_for(guild.me).send_messages), None
                        )
                    with contextlib.suppress(Exception):
                        await self._draw_guild(guild, manual_channel=ch)
                # 다음 회차 예약
                g["next_draw"] = (datetime.now(timezone.utc) + timedelta(hours=6)).timestamp()
                changed = True
        if changed: await _save(LOTTO_PATH, data)

    @auto_draw.before_loop
    async def before(self):
        await self.bot.wait_until_ready()

    # ───── 실제 추첨 로직
    async def _draw_guild(self, guild: discord.Guild, manual_channel: discord.abc.Messageable | None):
        data = await _load(LOTTO_PATH, {})
        g = _ensure_pool(data, guild.id)
        tickets = g["tickets"]
        total_tickets = sum(t["count"] for t in tickets)
        if total_tickets == 0:
            if manual_channel:
                await manual_channel.send("🎟️ 판매된 티켓이 없어 이번 회차는 무효입니다.")
            return

        pool_money = sum(t["count"] for t in tickets) * g["ticket_price"]
        prize = g["jackpot"] + int(pool_money * 0.7)

        bag = []
        for t in tickets:
            bag.extend([t["user_id"]] * int(t["count"]))
        winner_uid = random.choice(bag)

        # 지급
        bal = await _load(BAL_PATH, {})
        if winner_uid not in bal: bal[winner_uid] = {"money": 1000}
        bal[winner_uid]["money"] += prize
        await _save(BAL_PATH, bal)

        # 로그
        logs = await _load(LOG_PATH, [])
        logs.insert(0, _log(winner_uid, f"복권 당첨", prize))
        if len(logs) > 300: logs = logs[:300]
        await _save(LOG_PATH, logs)

        # 공지 채널 결정
        ch = None
        if g.get("announce_channel_id"):
            ch = guild.get_channel(int(g["announce_channel_id"]))
        if not ch:
            ch = manual_channel

        # 공지
        user = guild.get_member(int(winner_uid))
        uname = user.mention if user else f"User#{winner_uid}"
        if ch:
            await ch.send(f"🎉 **복권 추첨 결과!** 당첨자: {uname} — **+{prize:,}원** 🥳")

        # 초기화
        g["tickets"] = []
        g["jackpot"] = max(0, int(g["jackpot"] * 0.5))  # 잭팟 일부 유지
        g["next_draw"] = (datetime.now(timezone.utc) + timedelta(hours=6)).timestamp()
        await _save(LOTTO_PATH, data)

async def setup(bot): await bot.add_cog(Lottery(bot))
