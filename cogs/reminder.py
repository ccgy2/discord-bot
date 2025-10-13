import os, json, asyncio, discord
from datetime import datetime, timezone
from discord.ext import commands, tasks

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
os.makedirs(DATA_DIR, exist_ok=True)
REM_PATH = os.path.join(DATA_DIR, "reminders.json")
_lock = asyncio.Lock()

async def _load():
    async with _lock:
        if not os.path.exists(REM_PATH):
            with open(REM_PATH,"w",encoding="utf-8") as f: json.dump([],f,ensure_ascii=False,indent=2)
            return []
        with open(REM_PATH,"r",encoding="utf-8") as f: return json.load(f)

async def _save(d):
    async with _lock:
        with open(REM_PATH,"w",encoding="utf-8") as f: json.dump(d,f,ensure_ascii=False,indent=2)

class Reminder(commands.Cog):
    def __init__(self, bot):
        self.bot = bot; self.loop.start()

    @tasks.loop(seconds=30)
    async def loop(self):
        now = datetime.now(timezone.utc).timestamp()
        items = await _load(); changed = False
        keep = []
        for it in items:
            if it["at"] <= now:
                ch = self.bot.get_channel(it["channel_id"])
                if ch:
                    await ch.send(f"⏰ **알림**: {it['text']}")
                changed = True
            else:
                keep.append(it)
        if changed: await _save(keep)

    @commands.command(name="알림추가", aliases=["remind"])
    async def add(self, ctx: commands.Context, when: str, *, text: str):
        """
        사용: !알림추가 "2025-10-12 20:00" 내용
        시간은 서버 시간 기준(yyyy-mm-dd HH:MM)
        """
        try:
            dt = datetime.strptime(when, "%Y-%m-%d %H:%M")
            dt = dt.replace(tzinfo=timezone.utc)  # 간단화: UTC로 취급
        except Exception:
            return await ctx.reply('형식: `!알림추가 "YYYY-MM-DD HH:MM" 내용`')
        items = await _load()
        items.append({"channel_id": ctx.channel.id, "at": dt.timestamp(), "text": text})
        await _save(items)
        await ctx.reply("✅ 알림이 등록되었습니다.")

    @commands.command(name="알림목록", aliases=["reminds"])
    async def list(self, ctx):
        items = await _load()
        lines = [f"{i+1}. <#{it['channel_id']}> — {datetime.utcfromtimestamp(it['at']).strftime('%Y-%m-%d %H:%M')} — {it['text']}" for i,it in enumerate(items)]
        await ctx.reply("📋 알림 목록\n" + ("\n".join(lines) if lines else "비어 있음"))

async def setup(bot): await bot.add_cog(Reminder(bot))
