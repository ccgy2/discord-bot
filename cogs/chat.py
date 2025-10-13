import random
from datetime import datetime
import aiohttp
from discord.ext import commands

class Chat(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.api_key = (bot.config.get("openai_api_key") or "").strip()

    @commands.command(name="chat", aliases=["채팅", "대화"])
    async def chat(self, ctx: commands.Context, *, text: str = ""):
        if not text:
            return await ctx.reply("질문이나 대화를 입력하세요. 예: `!채팅 오늘 할 일`")

        # (선택) OpenAI 키가 있으면 AI 호출
        if self.api_key:
            try:
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "model": "gpt-4o-mini",
                    "messages": [
                        {"role": "system", "content": "You are a friendly assistant in a Discord server."},
                        {"role": "user", "content": text}
                    ],
                    "max_tokens": 400
                }
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as sess:
                    async with sess.post("https://api.openai.com/v1/chat/completions",
                                         headers=headers, json=payload) as resp:
                        data = await resp.json()
                content = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
                if content:
                    return await ctx.reply(content[:1900])
            except Exception:
                await ctx.reply("⚠️ AI 응답 오류로 로컬 모드로 전환합니다…")

        # 로컬 규칙형 응답
        lower = text.lower()
        if any(k in lower for k in ["안녕", "hello", "hi", "하이"]):
            return await ctx.reply("안녕하세요! 반가워요 😊")
        if "시간" in lower:
            return await ctx.reply(f"현재 서버 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        if "도움" in lower or "help" in lower:
            p = self.bot.config.get("prefix", "!")
            return await ctx.reply(f"사용 가능한 명령: `{p}채팅`, `{p}핑`, `{p}도움말`")

        replies = [
            "흥미롭네요! 좀 더 이야기해볼까요?",
            "좋은 질문이에요. 같이 생각해볼까요?",
            "음… 그건 제가 공부 중이에요 😅"
        ]
        return await ctx.reply(random.choice(replies))

async def setup(bot):
    await bot.add_cog(Chat(bot))
