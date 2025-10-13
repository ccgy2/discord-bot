import os, json, asyncio, discord
from discord.ext import commands

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
os.makedirs(DATA_DIR, exist_ok=True)

BAL_PATH  = os.path.join(DATA_DIR, "balances.json")
SHOP_PATH = os.path.join(DATA_DIR, "shop.json")
INV_PATH  = os.path.join(DATA_DIR, "inventories.json")
LOG_PATH  = os.path.join(DATA_DIR, "transactions.json")
_lock = asyncio.Lock()

async def _load(path, default):
    async with _lock:
        if not os.path.exists(path):
            with open(path, "w", encoding="utf-8") as f:
                json.dump(default, f, ensure_ascii=False, indent=2)
                return json.loads(json.dumps(default))
        with open(path, "r", encoding="utf-8") as f: return json.load(f)

async def _save(path, data):
    async with _lock:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

def _ensure_bal(b, uid, init=1000):
    if uid not in b: b[uid] = {"money": init}

def _log(uid: str, desc: str, amt: int):
    from datetime import datetime
    return {"user": uid, "desc": desc, "amount": amt, "time": datetime.now().strftime("%Y-%m-%d %H:%M")}

class Shop(commands.Cog):
    """역할/아이템 상점"""
    def __init__(self, bot): self.bot = bot

    # ───────── 상점 조회
    @commands.command(name="상점", aliases=["shop","상점목록"])
    async def list_shop(self, ctx):
        shop = await _load(SHOP_PATH, {})
        items = shop.get(str(ctx.guild.id), [])
        if not items:
            return await ctx.reply("🛒 상점이 비어 있어요. `!상점추가`로 등록해 주세요.")
        lines = []
        for it in items:
            if it["type"] == "role":
                role = ctx.guild.get_role(int(it["role_id"]))
                rtxt = role.mention if role else f"(삭제됨:{it['role_id']})"
                lines.append(f"**{it['name']}** — {it['price']:,}원 · 역할: {rtxt}")
            else:
                lines.append(f"**{it['name']}** — {it['price']:,}원 · 아이템")
        await ctx.reply("🛍️ **상점 목록**\n" + "\n".join(lines))

    # ───────── 구매
    @commands.command(name="구매", aliases=["buy","역할구매"])
    async def buy_item(self, ctx, *, item_name: str):
        shop = await _load(SHOP_PATH, {})
        items = shop.get(str(ctx.guild.id), [])
        item = next((i for i in items if i["name"].lower() == item_name.lower()), None)
        if not item:
            return await ctx.reply("해당 아이템이 상점에 없습니다. `!상점`으로 이름을 확인해 주세요.")

        bal = await _load(BAL_PATH, {}); uid = str(ctx.author.id); _ensure_bal(bal, uid)
        price = int(item["price"])
        if bal[uid]["money"] < price:
            return await ctx.reply(f"잔액 부족! 필요 {price:,}원 / 보유 {bal[uid]['money']:,}원")

        # 결제
        bal[uid]["money"] -= price
        await _save(BAL_PATH, bal)

        # 지급
        if item["type"] == "role":
            role = ctx.guild.get_role(int(item["role_id"]))
            if not role:
                return await ctx.reply("역할이 존재하지 않습니다. 관리자에게 문의하세요.")
            try:
                await ctx.author.add_roles(role, reason="Shop purchase")
            except discord.Forbidden:
                return await ctx.reply("봇 권한/역할 위치가 낮아 역할을 줄 수 없습니다.")
            await ctx.reply(f"✅ {ctx.author.mention} — {role.mention} 역할을 구매했습니다! (-{price:,}원)")
        else:
            inv = await _load(INV_PATH, {})
            g = inv.setdefault(str(ctx.guild.id), {})
            uinv = g.setdefault(uid, {})
            uinv[item["name"]] = uinv.get(item["name"], 0) + 1
            await _save(INV_PATH, inv)
            await ctx.reply(f"🎁 {item['name']} 아이템을 1개 구매했습니다! (-{price:,}원)")

        # 거래 로그
        logs = await _load(LOG_PATH, [])
        logs.insert(0, _log(uid, f"상점 구매: {item['name']}", -price))
        if len(logs) > 300: logs = logs[:300]
        await _save(LOG_PATH, logs)

    # ───────── 인벤토리
    @commands.command(name="인벤토리", aliases=["inventory","아이템"])
    async def inventory(self, ctx, member: discord.Member = None):
        m = member or ctx.author
        inv = await _load(INV_PATH, {})
        uinv = inv.get(str(ctx.guild.id), {}).get(str(m.id), {})
        if not uinv:
            return await ctx.reply(f"{m.display_name}님의 인벤토리가 비어 있어요.")
        lines = [f"- {k} × {v}" for k, v in uinv.items()]
        await ctx.reply(f"🎒 **{m.display_name} 인벤토리**\n" + "\n".join(lines))

    # ───────── 관리자: 아이템/역할 등록/삭제
    @commands.command(name="상점추가", aliases=["shopadd"])
    @commands.has_permissions(manage_guild=True)
    async def add_item(self, ctx, target: str, price: int, *, name: str = None):
        """
        역할 등록:  !상점추가 @역할 5000 이름
        아이템 등록: !상점추가 item 2000 힐링포션
        """
        shop = await _load(SHOP_PATH, {})
        arr = shop.setdefault(str(ctx.guild.id), [])

        if target.lower() == "item":
            if not name: return await ctx.reply("아이템 이름을 입력하세요. 예: `!상점추가 item 2000 힐링포션`")
            arr.append({"type":"item","name":name,"price":int(price)})
            await _save(SHOP_PATH, shop)
            return await ctx.reply(f"🆕 아이템 등록: **{name}** — {int(price):,}원")

        # 역할
        if not ctx.message.role_mentions:
            return await ctx.reply("역할을 멘션해주세요. 예: `!상점추가 @VIP 10000 VIP`")
        role = ctx.message.role_mentions[0]
        disp_name = name or role.name
        arr.append({"type":"role","name":disp_name,"role_id":role.id,"price":int(price)})
        await _save(SHOP_PATH, shop)
        await ctx.reply(f"🆕 역할 등록: {role.mention} — {int(price):,}원 (이름: {disp_name})")

    @commands.command(name="상점삭제", aliases=["shopdel"])
    @commands.has_permissions(manage_guild=True)
    async def del_item(self, ctx, *, name: str):
        shop = await _load(SHOP_PATH, {})
        arr = shop.get(str(ctx.guild.id), [])
        new_arr = [x for x in arr if x["name"].lower() != name.lower()]
        if len(arr) == len(new_arr):
            return await ctx.reply("해당 이름의 상점 항목을 찾을 수 없습니다.")
        shop[str(ctx.guild.id)] = new_arr
        await _save(SHOP_PATH, shop)
        await ctx.reply(f"🗑️ `{name}` 항목을 삭제했습니다.")

async def setup(bot): await bot.add_cog(Shop(bot))
