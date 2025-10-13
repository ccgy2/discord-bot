import os, json, asyncio, aiohttp, random, discord
from discord.ext import commands

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
os.makedirs(DATA_DIR, exist_ok=True)
GPT_PATH = os.path.join(DATA_DIR, "gpt_channels.json")
_lock = asyncio.Lock()

async def _load():
    async with _lock:
        if not os.path.exists(GPT_PATH):
            with open(GPT_PATH,"w",encoding="utf-8") as f: json.dump([],f)
            return []
        with open(GPT_PATH,"r",encoding="utf-8") as f: return json.load(f)
async def _save(d):
    async with _lock:
        with open(GPT_PATH,"w",encoding="utf-8") as f: json.dump(d,f)

class GPTToggle(commands.Cog):
    def __init__(self, bot): self.bot=bot

    @commands.command(name="gpt켜기")
    @commands.has_permissions(manage_channels=True)
    async def enable(self, ctx):
        arr=await _load()
        if ctx.channel.id not in arr:
            arr.append(ctx.channel.id); await _save(arr)
        await ctx.reply("✅ 이 채널에서 AI 응답을 활성화했습니다.")

    @commands.command(name="gpt끄기")
    @commands.has_permissions(manage_channels=True)
    async def disable(self, ctx):
        arr=await _load()
        if ctx.channel.id in arr:
            arr.remove(ctx.channel.id); await _save(arr)
        await ctx.reply("⛔ 이 채널에서 AI 응답을 비활성화했습니다.")

    @commands.Cog.listener()
    async def on_message(self, msg: discord.Message):
        if msg.author.bot or not msg.guild: return
        arr=await _load()
        if msg.channel.id not in arr: return
        # 간단 로컬 답변 or OpenAI
        key = self.bot.config.get("openai_api_key","")
        if not key:
            if msg.content.startswith(("!","/")): return
            rep = random.choice(["오! 재밌네요 😄","그건 좋은 아이디어 같아요.","흠.. 한번 더 설명해줄래요?"])
            await msg.reply(rep); return
        try:
            headers={"Authorization":f"Bearer {key}","Content-Type":"application/json"}
            body={"model":"gpt-4o-mini","messages":[{"role":"system","content":"Be concise."},{"role":"user","content":msg.content}]}
            async with aiohttp.ClientSession() as s:
                async with s.post("https://api.openai.com/v1/chat/completions",headers=headers,json=body) as r:
                    data=await r.json()
            content=(data.get("choices") or [{}])[0].get("message",{}).get("content","")
            if content: await msg.reply(content[:1900])
        except Exception:
            pass

async def setup(bot): await bot.add_cog(GPTToggle(bot))
