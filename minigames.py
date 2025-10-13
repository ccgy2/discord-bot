import random, os, json, asyncio, discord
from discord.ext import commands

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
os.makedirs(DATA_DIR, exist_ok=True)
BAL_PATH = os.path.join(DATA_DIR, "balances.json")
_lock = asyncio.Lock()

async def _load_bal():
    async with _lock:
        if not os.path.exists(BAL_PATH):
            with open(BAL_PATH,"w",encoding="utf-8") as f: json.dump({},f,ensure_ascii=False,indent=2)
            return {}
        with open(BAL_PATH,"r",encoding="utf-8") as f: return json.load(f)
async def _save_bal(d):
    async with _lock:
        with open(BAL_PATH,"w",encoding="utf-8") as f: json.dump(d,f,ensure_ascii=False,indent=2)
def _ensure(b,u): 
    if u not in b: b[u]={"money":1000}

class Mini(commands.Cog):
    def __init__(self, bot): self.bot=bot

    @commands.command(name="가위바위보", aliases=["rps"])
    async def rps(self, ctx, pick: str):
        pick = pick.strip().lower()
        mapping = {"가위":"s","바위":"r","보":"p","s":"s","r":"r","p":"p"}
        if pick not in mapping: return await ctx.reply("사용: `!가위바위보 가위|바위|보`")
        botp = random.choice(["r","p","s"])
        result_map = {("r","s"):"승",("p","r"):"승",("s","p"):"승",
                      ("s","r"):"패",("r","p"):"패",("p","s"):"패"}
        res = "무"
        if pick!=botp: res = result_map.get((mapping[pick],botp),"패")
        name = {"r":"바위","p":"보","s":"가위"}[botp]
        await ctx.reply(f"봇은 **{name}**! 결과: **{res}**")

    @commands.command(name="주사위", aliases=["dice"])
    async def dice(self, ctx):
        await ctx.reply(f"🎲 {random.randint(1,6)}")

    @commands.command(name="가챠", aliases=["gacha"])
    async def gacha(self, ctx, cost: int = 100):
        b = await _load_bal(); u=str(ctx.author.id); _ensure(b,u)
        if b[u]["money"] < cost: return await ctx.reply("잔액이 부족합니다.")
        b[u]["money"] -= cost
        # 확률: S 5%, A 20%, B 75%
        r = random.random()
        if r < 0.05: tier="S"; prize=cost*5
        elif r < 0.25: tier="A"; prize=cost*2
        else: tier="B"; prize=0
        b[u]["money"] += prize; await _save_bal(b)
        await ctx.reply(f"🎰 결과: **{tier}** 등급! {'+'+str(prize)+'원' if prize else '당첨 없음'} / 잔액 {b[u]['money']}원")

async def setup(bot): await bot.add_cog(Mini(bot))
