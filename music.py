import os
import json
import random
import asyncio
import functools
import contextlib
import discord
from discord.ext import commands
from yt_dlp import YoutubeDL

# =========================
# YT-DLP / FFmpeg 설정
# =========================
YTDL_OPTS = {
    "format": "bestaudio/best",
    "quiet": True,
    "no_warnings": True,
    "noplaylist": True,
}
# 유튜브 스트림 끊김 대비 재연결 옵션
FFMPEG_BEFORE = "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"
FFMPEG_OPTS = {"before_options": FFMPEG_BEFORE, "options": "-vn"}
ytdl = YoutubeDL(YTDL_OPTS)

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
os.makedirs(DATA_DIR, exist_ok=True)
VOL_PATH = os.path.join(DATA_DIR, "volumes.json")


def _load_volume(guild_id: int) -> float:
    if not os.path.exists(VOL_PATH):
        return 0.5
    try:
        with open(VOL_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        v = float(data.get(str(guild_id), 0.5))
        return max(0.0, min(1.5, v))
    except Exception:
        return 0.5


def _save_volume(guild_id: int, v: float) -> None:
    try:
        data = {}
        if os.path.exists(VOL_PATH):
            with open(VOL_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
        data[str(guild_id)] = v
        with open(VOL_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


# =========================
# 플레이어
# =========================
class GuildPlayer:
    def __init__(self, bot: commands.Bot, guild: discord.Guild):
        self.bot = bot
        self.guild = guild
        self.voice: discord.VoiceClient | None = None
        self.queue: list[dict] = []  # ytdl info dict
        self.current: dict | None = None
        self.repeat = "off"  # off | one | all
        self.volume = _load_volume(guild.id)

    async def ensure_voice(self, channel: discord.abc.Connectable):
        """
        음성/스테이지 채널 연결/이동 (매우 견고)
        - 길드의 기존 voice_client 우선 사용
        - 실패 시 완전 분리 후 재연결
        - 최대 5회 재시도 (IndexError/Timeout 등 포함)
        - 스테이지 채널이면 발언 요청 시도
        """
        perms = channel.permissions_for(self.guild.me)
        if not perms.connect:
            raise PermissionError("봇에 '연결' 권한이 없습니다.")
        if not isinstance(channel, discord.StageChannel) and not perms.speak:
            raise PermissionError("봇에 '말하기' 권한이 없습니다.")

        async def _connect_or_move():
            vc = self.guild.voice_client
            if vc and vc.is_connected():
                self.voice = vc
                if vc.channel.id != channel.id:
                    await vc.move_to(channel)
            else:
                self.voice = await channel.connect(self_deaf=True, reconnect=True)

        last_err: Exception | None = None
        for attempt in range(5):
            try:
                await _connect_or_move()
                break
            except (IndexError, asyncio.TimeoutError, discord.ClientException, OSError) as e:
                last_err = e
                with contextlib.suppress(Exception):
                    if self.guild.voice_client:
                        await self.guild.voice_client.disconnect(force=True)
                    self.voice = None
                await asyncio.sleep(0.6 + attempt * 0.2)
            except Exception as e:
                last_err = e
                await asyncio.sleep(0.6 + attempt * 0.2)
        else:
            raise last_err if last_err else RuntimeError("음성 연결 실패(원인 불명)")

        if isinstance(channel, discord.StageChannel):
            stage_perms = channel.permissions_for(self.guild.me)
            with contextlib.suppress(Exception):
                if getattr(stage_perms, "request_to_speak", False):
                    await channel.guild.me.edit(suppress=False)

    async def extract(self, query: str) -> dict:
        """yt-dlp 추출 (스레드 풀) — 검색 0건/None 결과도 처리"""
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(
            None, functools.partial(ytdl.extract_info, query, download=False)
        )
        if not data:
            raise LookupError("추출 실패(콘텐츠를 가져올 수 없음)")
        if "entries" in data:
            entries = [e for e in (data.get("entries") or []) if e]
            if not entries:
                raise LookupError("검색 결과 없음")
            data = entries[0]
        # url이 없으면 무효
        if not data.get("url"):
            raise LookupError("유효한 스트림 URL이 없습니다.")
        return data

    async def play_next(self, *, ch: discord.abc.Messageable | None):
        if not self.voice or not self.voice.is_connected():
            return
        if not self.queue and not self.current:
            return

        # 다음 트랙 선택
        if self.current and self.repeat == "one":
            info = self.current
        else:
            if self.current and self.repeat == "all":
                self.queue.append(self.current)
            info = self.queue.pop(0) if self.queue else self.current

        self.current = info
        stream_url = info.get("url")

        # PCM + 볼륨 조절(오디오 소스는 Opus가 아니어야 함)
        source = discord.FFmpegPCMAudio(stream_url, **FFMPEG_OPTS)
        wrapped = discord.PCMVolumeTransformer(source, volume=self.volume)

        def _after(err: Exception | None):
            fut = asyncio.run_coroutine_threadsafe(self._after_inner(err, ch), self.bot.loop)
            try:
                fut.result()
            except Exception:
                pass

        self.voice.play(wrapped, after=_after)

        if ch:
            with contextlib.suppress(Exception):
                await ch.send(f"🎵 재생 중: **{info.get('title','?')}**")

    async def _after_inner(self, err: Exception | None, ch: discord.abc.Messageable | None):
        if err and ch:
            with contextlib.suppress(Exception):
                await ch.send(f"재생 오류: {type(err).__name__}: {err}")

        # 반복 처리
        if self.repeat == "one":
            pass
        elif self.repeat == "all":
            pass
        else:
            self.current = None

        # 다음 곡
        if self.repeat == "one":
            if self.voice and not self.voice.is_playing():
                await self.play_next(ch=ch)
            return

        if self.queue:
            if self.voice and not self.voice.is_playing():
                await self.play_next(ch=ch)
        else:
            await asyncio.sleep(60)
            if not self.queue and self.voice and self.voice.is_connected():
                with contextlib.suppress(Exception):
                    await self.voice.disconnect(force=True)
                self.voice = None


# =========================
# Cog
# =========================
class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.players: dict[int, GuildPlayer] = {}

    def player(self, guild: discord.Guild) -> GuildPlayer:
        if guild.id not in self.players:
            self.players[guild.id] = GuildPlayer(self.bot, guild)
        return self.players[guild.id]

    # --------- 진단 명령 ---------
    @commands.command(name="보이스디버그", aliases=["voicedebug"])
    async def voice_debug(self, ctx: commands.Context):
        vc = ctx.author.voice.channel if ctx.author.voice else None
        if not vc:
            return await ctx.reply("음성 채널에 먼저 들어가 주세요.")
        me = ctx.guild.me
        perms = vc.permissions_for(me)
        typ = "StageChannel" if isinstance(vc, discord.StageChannel) else "VoiceChannel"
        lines = [
            f"채널: {vc.name} ({typ})",
            f"권한 - connect:{perms.connect}, speak:{perms.speak}, request_to_speak:{getattr(perms, 'request_to_speak', False)}",
            f"봇 상태 - has_voice_client:{bool(ctx.guild.voice_client)}",
        ]
        await ctx.reply("🔎 보이스 디버그\n" + "\n".join(lines))

    # ───────────────── 재생 ─────────────────
    @commands.command(name="재생", aliases=["play"])
    async def cmd_play(self, ctx: commands.Context, *, query: str):
        if not ctx.author.voice or not ctx.author.voice.channel:
            return await ctx.reply("먼저 음성 채널에 들어가 주세요.")

        p = self.player(ctx.guild)

        # 음성 연결
        try:
            await p.ensure_voice(ctx.author.voice.channel)
        except PermissionError as e:
            return await ctx.reply(f"권한 오류: {e}")
        except discord.Forbidden:
            return await ctx.reply("봇에 음성 채널 **연결/말하기** 권한이 없어요.")
        except Exception:
            return await ctx.reply("음성 채널 연결에 실패했습니다. 다른 채널로 시도하거나 잠시 후 다시 시도해 주세요.")

        # 검색어 준비
        q = query.strip()
        if not q.startswith("http"):
            q = f"ytsearch5:{q}"

        # 정보 추출
        try:
            info = await p.extract(q)
        except LookupError as e:
            return await ctx.reply(f"{e}")
        except Exception as e:
            return await ctx.reply(f"검색/추출 실패: {type(e).__name__}: {e}")

        # 큐 추가
        p.queue.append(info)
        await ctx.reply(f"➕ 대기열 추가: **{info.get('title','(제목없음)')}**")

        # 재생 시작
        if p.voice and not p.voice.is_playing() and not p.voice.is_paused():
            try:
                await p.play_next(ch=ctx.channel)
            except Exception as e:
                return await ctx.reply(f"재생 시작 실패: {type(e).__name__}: {e}")

    # ───────────────── 제어 ─────────────────
    @commands.command(name="스킵", aliases=["skip"])
    async def cmd_skip(self, ctx: commands.Context):
        p = self.player(ctx.guild)
        if not p.voice or not p.voice.is_connected() or not p.voice.is_playing():
            return await ctx.reply("재생 중인 곡이 없습니다.")
        p.voice.stop()
        await ctx.reply("⏭️ 다음 곡으로 넘어갑니다.")

    @commands.command(name="정지", aliases=["stop","일시정지","pause"])
    async def cmd_stop(self, ctx: commands.Context):
        p = self.player(ctx.guild)
        if not p.voice or not p.voice.is_connected():
            return await ctx.reply("재생 중이 아닙니다.")
        if p.voice.is_paused():
            p.voice.resume()
            return await ctx.reply("▶️ 재개했습니다.")
        if p.voice.is_playing():
            p.voice.pause()
            return await ctx.reply("⏸️ 일시정지했습니다.")
        return await ctx.reply("현재 재생/일시정지 상태가 아닙니다.")

    @commands.command(name="나가", aliases=["꺼져","leave","disconnect"])
    async def cmd_leave(self, ctx: commands.Context):
        p = self.player(ctx.guild)
        p.queue.clear()
        p.current = None
        if p.voice and p.voice.is_connected():
            with contextlib.suppress(Exception):
                await p.voice.disconnect(force=True)
            p.voice = None
            return await ctx.reply("👋 음성 채널에서 나갑니다.")
        return await ctx.reply("이미 음성 채널에 있지 않습니다.")

    @commands.command(name="반복", aliases=["loop","repeat"])
    async def cmd_loop(self, ctx: commands.Context, mode: str):
        p = self.player(ctx.guild)
        m = mode.lower()
        if m in ("off", "끄기"):
            p.repeat = "off"
        elif m in ("one", "한곡", "곡"):
            p.repeat = "one"
        elif m in ("all", "전체"):
            p.repeat = "all"
        else:
            return await ctx.reply("사용: `!반복 off|one|all`")
        await ctx.reply(f"🔁 반복 모드: **{p.repeat}**")

    @commands.command(name="볼륨", aliases=["volume","vol"])
    async def cmd_volume(self, ctx: commands.Context, vol: int):
        p = self.player(ctx.guild)
        v = max(0, min(150, int(vol))) / 100
        p.volume = v
        _save_volume(ctx.guild.id, v)
        # 현재 재생 중인 소스에 즉시 반영
        if p.voice and p.voice.source and isinstance(p.voice.source, discord.PCMVolumeTransformer):
            p.voice.source.volume = v
        await ctx.reply(f"🔊 볼륨: **{int(v*100)}%** (서버에 저장됨)")

    @commands.command(name="셔플", aliases=["shuffle"])
    async def cmd_shuffle(self, ctx: commands.Context):
        p = self.player(ctx.guild)
        if len(p.queue) <= 1:
            return await ctx.reply("셔플할 대기열이 없습니다.")
        first = p.queue[0]
        rest = p.queue[1:]
        random.shuffle(rest)
        p.queue = [first] + rest
        await ctx.reply("🔀 대기열을 셔플했습니다!")

    @commands.command(name="대기열", aliases=["queue","목록"])
    async def cmd_queue(self, ctx: commands.Context):
        p = self.player(ctx.guild)
        if not p.queue and not p.current:
            return await ctx.reply("현재 대기열이 비어 있습니다.")
        lines = []
        if p.current:
            lines.append(f"🎵 **현재**: {p.current.get('title','?')}")
        if p.queue:
            for i, it in enumerate(p.queue, start=1):
                lines.append(f"{i}. {it.get('title','(제목없음)')}")
        await ctx.reply("🎶 **대기열**\n" + "\n".join(lines[:15]))

async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))
