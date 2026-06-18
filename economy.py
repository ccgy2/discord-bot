# cogs/economy.py
import os
import json
import asyncio
import random
import re
import contextlib
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional, Tuple, Set

import discord
from discord.ext import commands

# ── 데이터 경로
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
os.makedirs(DATA_DIR, exist_ok=True)
BAL_PATH = os.path.join(DATA_DIR, "balances.json")
QUIZ_PATH = os.path.join(DATA_DIR, "quiz.json")
ECON_PATH = os.path.join(DATA_DIR, "economy_settings.json")
_file_lock = asyncio.Lock()
_quiz_lock = asyncio.Lock()
_set_lock = asyncio.Lock()

# ── 기본 설정
DEFAULT_SETTINGS = {
    "DAILY_REWARD": 1000,
    "QUIZ_REWARD": 300,
    "QUIZ_TIMEOUT_SEC": 30,
}

# ── 기본 문제(샘플)
DEFAULT_QUESTIONS = [
    {"id": 1, "q": "지구에서 가장 큰 바다는?", "choices": ["인도양", "태평양", "대서양", "북극해"], "answer": 2},
    {"id": 2, "q": "대한민국의 수도는?",     "choices": ["부산", "대전", "서울", "인천"],         "answer": 3},
    {"id": 3, "q": "물의 화학식은?",         "choices": ["H2O", "CO2", "NaCl", "O2"],          "answer": 1},
]

NUM_EMOJIS = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]

# ── 권한 판정
def _is_admin(bot: commands.Bot, ctx: commands.Context) -> bool:
    owner_id = bot.config.get("owner_id")
    if owner_id and int(owner_id) == ctx.author.id:
        return True
    perms = ctx.author.guild_permissions
    return perms.administrator or perms.manage_guild or perms.manage_messages

# ── 안전한 JSON 로드/저장
async def _load_json_safe(path: str, default):
    lock = _set_lock if path == ECON_PATH else (_quiz_lock if path == QUIZ_PATH else _file_lock)
    async with lock:
        if not os.path.exists(path):
            with open(path, "w", encoding="utf-8") as f:
                json.dump(default, f, ensure_ascii=False, indent=2)
            return json.loads(json.dumps(default))
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return json.loads(json.dumps(default))

async def _save_json_safe(path: str, data):
    lock = _set_lock if path == ECON_PATH else (_quiz_lock if path == QUIZ_PATH else _file_lock)
    async with lock:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

# ── balances 관리
async def _load_balances() -> Dict[str, Any]:
    return await _load_json_safe(BAL_PATH, {})

async def _save_balances(balances: Dict[str, Any]):
    await _save_json_safe(BAL_PATH, balances)

def _ensure_user(balances: Dict[str, Any], uid: str, default_amt: int = 1000):
    if uid not in balances:
        balances[uid] = {"money": default_amt}

# ── settings / quiz bank
async def _load_settings() -> Dict[str, Any]:
    return await _load_json_safe(ECON_PATH, DEFAULT_SETTINGS)

async def _save_settings(settings: Dict[str, Any]):
    await _save_json_safe(ECON_PATH, settings)

async def _load_quiz_bank() -> List[Dict[str, Any]]:
    return await _load_json_safe(QUIZ_PATH, DEFAULT_QUESTIONS)

async def _save_quiz_bank(bank: List[Dict[str, Any]]):
    await _save_json_safe(QUIZ_PATH, bank)

def _next_quiz_id(bank: List[Dict[str, Any]]) -> int:
    return (max((int(q.get("id", 0)) for q in bank), default=0) + 1)

def _parse_choices_and_answer(text: str) -> Tuple[List[str], int]:
    """
    입력 형식:
      보기1 ; 보기2 ; 보기3 ; 보기4 | 정답번호
    반환: (choices, answer_index_1based)
    """
    if "|" not in text:
        raise ValueError("보기/정답 구분기호 '|' 가 없습니다.")
    left, right = text.split("|", 1)
    choices = [c.strip() for c in re.split(r"[;,]", left) if c.strip()]
    ans = int(right.strip())
    if not (2 <= len(choices) <= 5):
        raise ValueError("보기는 2~5개여야 합니다.")
    if not (1 <= ans <= len(choices)):
        raise ValueError("정답번호가 보기 범위를 벗어났습니다.")
    return choices, ans

# ── 진행중 세션 구조
personal_sessions: Dict[int, Dict[int, Dict[str, Any]]] = {}  # 개인: guild_id -> user_id -> session
group_sessions: Dict[int, Dict[str, Any]] = {}                # 단체: channel_id -> session
active_by_msg: Dict[int, Dict[str, Any]] = {}                 # msg_id -> session 참조

class Economy(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ================= 출석 =================
    @commands.command(name="daily", aliases=["출석", "출첵", "출석체크"])
    async def daily(self, ctx: commands.Context):
        settings = await _load_settings()
        daily_reward = int(settings.get("DAILY_REWARD", DEFAULT_SETTINGS["DAILY_REWARD"]))

        balances = await _load_balances()
        uid = str(ctx.author.id)
        _ensure_user(balances, uid, 1000)

        today = datetime.now(timezone.utc).date().isoformat()
        last = balances[uid].get("last_daily", "")

        if not _is_admin(self.bot, ctx):
            if last == today:
                return await ctx.reply("오늘은 이미 출석했습니다 ✅ 내일 다시 시도해 주세요!")

        balances[uid]["money"] = int(balances[uid]["money"]) + daily_reward
        balances[uid]["last_daily"] = today
        await _save_balances(balances)
        await ctx.reply(f"📅 출석 체크 완료! **+{daily_reward}원** 지급 ✅ 현재 잔액: {balances[uid]['money']}원")

    @commands.command(name="dailyset", aliases=["출석설정"])
    async def daily_set(self, ctx: commands.Context, amount: Optional[int] = None):
        if not _is_admin(self.bot, ctx):
            return await ctx.reply("권한이 없습니다. (관리자/봇 오너만 가능)")
        if amount is None or amount < 0:
            return await ctx.reply("사용법: `!출석설정 <금액>` (0 이상 정수)")
        settings = await _load_settings()
        settings["DAILY_REWARD"] = int(amount)
        await _save_settings(settings)
        await ctx.reply(f"✅ 출석 보상을 **{amount}원**으로 설정했습니다.")

    # ================= 퀴즈 메인 그룹 =================
    @commands.group(name="퀴즈", aliases=["quiz"], invoke_without_command=True)
    async def quiz_group(self, ctx: commands.Context):
        p = self.bot.config.get("prefix", "!")
        await ctx.reply(
            f"🧠 퀴즈 사용법\n"
            f"`{p}퀴즈 개인 [초]` — 개인전 (작성자만 응답)\n"
            f"`{p}퀴즈 단체 [인원] [초]` — 단체전(선착순 N명)\n"
            f"`{p}퀴즈 시작 <ID> 개인|단체 [인원] [초]` — 특정 ID 문제 즉시 출제(관리자)\n"
            f"`{p}퀴즈 마감 <ID>` — 해당 문제(ID) 진행중이면 강제 마감(관리자)\n"
            f"`{p}퀴즈관리 추가/수정/목록` — 문제은행 관리(관리자)\n"
            f"`{p}퀴즈보상 <금액>`, `{p}퀴즈시간 <초>` — 기본 보상/시간 설정(관리자)"
        )

    # ---------- 랜덤 개인 퀴즈 ----------
    @quiz_group.command(name="개인", aliases=["solo", "personal"])
    async def quiz_personal(self, ctx: commands.Context, seconds: Optional[int] = None):
        await self._start_random_quiz(ctx, mode="personal", seconds=seconds)

    # ---------- 랜덤 단체 퀴즈 ----------
    @quiz_group.command(name="단체", aliases=["group", "전체"])
    async def quiz_groupmode(self, ctx: commands.Context, winners: Optional[int] = 1, seconds: Optional[int] = None):
        await self._start_random_quiz(ctx, mode="group", winners=winners, seconds=seconds)

    # ---------- 특정 ID로 즉시 출제 (관리자) ----------
    @quiz_group.command(name="시작", aliases=["start"])
    async def quiz_start(self, ctx: commands.Context, qid: int, mode: str = "개인", winners: Optional[int] = 1, seconds: Optional[int] = None):
        if not _is_admin(self.bot, ctx):
            return await ctx.reply("권한이 없습니다.")
        bank = await _load_quiz_bank()
        q = next((qq for qq in bank if int(qq.get("id", 0)) == int(qid)), None)
        if not q:
            return await ctx.reply("해당 ID의 문제가 없습니다.")
        mode = mode.lower()
        if mode.startswith("개") or mode.startswith("p"):
            await self._start_quiz_from_item(ctx, q, mode="personal", seconds=seconds)
        else:
            await self._start_quiz_from_item(ctx, q, mode="group", winners=winners, seconds=seconds)

    # ---------- 강제 마감 (관리자) ----------
    @quiz_group.command(name="마감", aliases=["close"])
    async def quiz_close(self, ctx: commands.Context, qid: int):
        if not _is_admin(self.bot, ctx):
            return await ctx.reply("권한이 없습니다.")
        closed_any = False
        for ch_id, sess in list(group_sessions.items()):
            if sess.get("quiz_id") == qid:
                closed_any = True
                await self._finalize_group_by_force(ctx.guild, ch_id, sess, forced_by=ctx.author)
        for gid, users in list(personal_sessions.items()):
            for uid, sess in list(users.items()):
                if sess.get("quiz_id") == qid:
                    closed_any = True
                    await self._finalize_personal_by_force(gid, uid, sess, forced_by=ctx.author)
        if not closed_any:
            return await ctx.reply("진행중인 해당 ID의 퀴즈를 찾을 수 없습니다.")
        await ctx.reply(f"✅ 문제 ID {qid} 을(를) 강제 마감했습니다.")

    # ================= 보상/시간 설정 (관리자) =================
    # — 여기서 '퀴즈시간'을 기본 이름으로, 다양한 별칭 추가
    @commands.command(name="퀴즈시간", aliases=["quiztime", "퀴즈시간설정", "퀴즈-시간"])
    async def quiz_time_set_kor(self, ctx: commands.Context, seconds: Optional[int] = None):
        await self._set_quiz_time(ctx, seconds)

    @commands.command(name="퀴즈보상", aliases=["quizreward", "퀴즈보상설정"])
    async def quiz_reward_set_kor(self, ctx: commands.Context, amount: Optional[int] = None):
        await self._set_quiz_reward(ctx, amount)

    async def _set_quiz_time(self, ctx: commands.Context, seconds: Optional[int]):
        if not _is_admin(self.bot, ctx):
            return await ctx.reply("권한이 없습니다.")
        if seconds is None:
            p = self.bot.config.get("prefix", "!")
            return await ctx.reply(f"사용법: `{p}퀴즈시간 <초>`  (예: `{p}퀴즈시간 45`)")
        try:
            sec = int(seconds)
        except Exception:
            return await ctx.reply("초는 정수로 입력하세요. 예: `30`")
        if sec <= 3:
            return await ctx.reply("최소 4초 이상으로 설정해주세요.")
        settings = await _load_settings()
        settings["QUIZ_TIMEOUT_SEC"] = sec
        await _save_settings(settings)
        await ctx.reply(f"✅ 퀴즈 기본 제한 시간을 **{sec}초**로 설정했습니다.")

    async def _set_quiz_reward(self, ctx: commands.Context, amount: Optional[int]):
        if not _is_admin(self.bot, ctx):
            return await ctx.reply("권한이 없습니다.")
        if amount is None:
            p = self.bot.config.get("prefix", "!")
            return await ctx.reply(f"사용법: `{p}퀴즈보상 <금액>` (예: `{p}퀴즈보상 500`)")
        try:
            amt = int(amount)
        except Exception:
            return await ctx.reply("금액은 정수로 입력하세요.")
        if amt < 0:
            return await ctx.reply("0 이상으로 입력하세요.")
        settings = await _load_settings()
        settings["QUIZ_REWARD"] = amt
        await _save_settings(settings)
        await ctx.reply(f"✅ 퀴즈 보상을 **{amt}원**으로 설정했습니다.")

    # ================= 내부 시작 함수들 =================
    async def _start_random_quiz(self, ctx: commands.Context, mode: str = "personal", winners: Optional[int] = 1, seconds: Optional[int] = None):
        bank = await _load_quiz_bank()
        if not bank:
            return await ctx.reply("문제 은행이 비어 있어요. 관리자가 `!퀴즈관리 추가`로 문제를 넣어주세요.")
        q = random.choice(bank)
        await self._start_quiz_from_item(ctx, q, mode=mode, winners=winners, seconds=seconds)

    async def _start_quiz_from_item(self, ctx: commands.Context, q: Dict[str, Any], mode: str = "personal", winners: Optional[int] = 1, seconds: Optional[int] = None):
        settings = await _load_settings()
        timeout = int(seconds if seconds and seconds > 3 else settings.get("QUIZ_TIMEOUT_SEC", DEFAULT_SETTINGS["QUIZ_TIMEOUT_SEC"]))
        reward  = int(settings.get("QUIZ_REWARD", DEFAULT_SETTINGS["QUIZ_REWARD"]))

        qid = int(q.get("id", 0))
        choices: List[str] = q.get("choices", [])
        answer = int(q.get("answer", 1))
        if not choices or not (1 <= answer <= len(choices)):
            return await ctx.reply("이 문제는 형식이 잘못되어 건너뜁니다. 다른 문제로 다시 시도하세요.")

        desc = "\n".join([f"{i+1}. {c}" for i, c in enumerate(choices)])
        if mode == "personal":
            embed = discord.Embed(
                title=f"🧠 개인 퀴즈 (ID: {qid})",
                description=f"> {q.get('q')}\n\n{desc}\n\n"
                            f"⏳ 제한 {timeout}초 · 정답 보상 **{reward}원**\n"
                            f"👉 보기 번호 이모지로 반응하세요 (작성자만 가능)",
                color=0x2ecc71
            )
            msg = await ctx.reply(embed=embed)
            for i in range(len(choices)):
                await msg.add_reaction(NUM_EMOJIS[i])

            sess = {
                "msg_id": msg.id,
                "quiz_id": qid,
                "answer": answer,
                "expires": datetime.now(timezone.utc) + timedelta(seconds=timeout),
                "reward": reward,
                "mode": "personal",
                "owner_id": ctx.author.id
            }
            personal_sessions.setdefault(ctx.guild.id, {})[ctx.author.id] = sess
            active_by_msg[msg.id] = sess

            def check(payload: discord.RawReactionActionEvent):
                if payload.user_id != ctx.author.id: return False
                if payload.message_id != msg.id: return False
                try:
                    idx = NUM_EMOJIS.index(str(payload.emoji)) + 1
                except ValueError:
                    return False
                payload.choice_index = idx  # type: ignore
                return True

            try:
                payload: discord.RawReactionActionEvent = await self.bot.wait_for("raw_reaction_add", timeout=timeout, check=check)
            except asyncio.TimeoutError:
                personal_sessions[ctx.guild.id].pop(ctx.author.id, None)
                active_by_msg.pop(msg.id, None)
                try:
                    closed = embed.copy()
                    closed.color = 0xe74c3c
                    closed.set_footer(text=f"시간 초과 · 정답: {answer}")
                    with contextlib.suppress(Exception):
                        await msg.edit(embed=closed)
                except Exception:
                    pass
                return await ctx.reply("⏰ 시간 초과! 개인 퀴즈가 종료되었습니다.")

            choice_idx = getattr(payload, "choice_index", 0)
            personal_sessions[ctx.guild.id].pop(ctx.author.id, None)
            active_by_msg.pop(msg.id, None)

            if choice_idx == answer:
                balances = await _load_balances()
                uid = str(ctx.author.id)
                _ensure_user(balances, uid, 1000)
                balances[uid]["money"] = int(balances[uid]["money"]) + int(reward)
                await _save_balances(balances)
                try:
                    ok = embed.copy(); ok.color = 0x3498db
                    ok.set_footer(text=f"정답! 보상 {reward}원 지급")
                    with contextlib.suppress(Exception): await msg.edit(embed=ok)
                except Exception:
                    pass
                await ctx.reply(f"✅ 정답! **+{reward}원** 지급 🎉 현재 잔액: {balances[uid]['money']}원")
            else:
                try:
                    wrong = embed.copy(); wrong.color = 0xe67e22
                    wrong.set_footer(text=f"오답! 정답: {answer}")
                    with contextlib.suppress(Exception): await msg.edit(embed=wrong)
                except Exception:
                    pass
                await ctx.reply("❌ 오답! 다음에 다시 도전해요.")

        else:  # group
            target = max(1, min(50, int(winners or 1)))
            embed = discord.Embed(
                title=f"🏟️ 단체 퀴즈 (ID: {qid})",
                description=f"> {q.get('q')}\n\n{desc}\n\n"
                            f"⏳ 제한 {timeout}초 · 정답 보상 **{reward}원** · 선착순 {target}명\n"
                            f"👉 보기 번호 이모지를 누르세요!",
                color=0x9b59b6
            )
            msg = await ctx.reply(embed=embed)
            for i in range(len(choices)):
                await msg.add_reaction(NUM_EMOJIS[i])

            sess = {
                "msg_id": msg.id,
                "quiz_id": qid,
                "answer": answer,
                "expires": datetime.now(timezone.utc) + timedelta(seconds=timeout),
                "reward": reward,
                "mode": "group",
                "target": target,
                "winners": set(),
                "channel_id": ctx.channel.id,
                "guild_id": ctx.guild.id
            }
            group_sessions[ctx.channel.id] = sess
            active_by_msg[msg.id] = sess

            def check(payload: discord.RawReactionActionEvent):
                if payload.user_id == self.bot.user.id: return False
                if payload.message_id != msg.id: return False
                try:
                    idx = NUM_EMOJIS.index(str(payload.emoji)) + 1
                except ValueError:
                    return False
                payload.choice_index = idx  # type: ignore
                return True

            try:
                while True:
                    payload: discord.RawReactionActionEvent = await self.bot.wait_for("raw_reaction_add", timeout=timeout, check=check)
                    sess_now = group_sessions.get(ctx.channel.id)
                    if not sess_now:
                        break
                    if datetime.now(timezone.utc) > sess_now["expires"]:
                        raise asyncio.TimeoutError()

                    choice_idx = getattr(payload, "choice_index", 0)
                    user_id = payload.user_id
                    if choice_idx == sess_now["answer"] and user_id not in sess_now["winners"]:
                        balances = await _load_balances()
                        sid = str(user_id)
                        _ensure_user(balances, sid, 1000)
                        balances[sid]["money"] = int(balances[sid]["money"]) + int(sess_now["reward"])
                        await _save_balances(balances)
                        sess_now["winners"].add(user_id)
                        await ctx.channel.send(f"🎉 정답! <@{user_id}> +{sess_now['reward']}원 (#{len(sess_now['winners'])}/{sess_now['target']})")
                        if len(sess_now["winners"]) >= sess_now["target"]:
                            raise asyncio.TimeoutError()
            except asyncio.TimeoutError:
                final = embed.copy()
                final.color = 0x2ecc71 if sess.get("winners") else 0xe74c3c
                final.set_footer(text=f"정답:{answer} · 우승자:{len(sess.get('winners') or [])}명")
                with contextlib.suppress(Exception):
                    await msg.edit(embed=final)
                group_sessions.pop(ctx.channel.id, None)
                active_by_msg.pop(msg.id, None)
                winners_line = ", ".join(f"<@{uid}>" for uid in (sess.get("winners") or [])) or "없음"
                await ctx.channel.send(f"🏁 단체 퀴즈 종료! 우승자: {winners_line}")
                return

    # ================= 문제은행 관리 =================
    @commands.group(name="퀴즈관리", invoke_without_command=True)
    async def quiz_admin(self, ctx: commands.Context):
        await ctx.reply("관리자용 퀴즈 관리: `!퀴즈관리 추가/수정/목록`")

    @quiz_admin.command(name="추가", aliases=["add"])
    async def quiz_add(self, ctx: commands.Context, *, text: str = ""):
        if not _is_admin(self.bot, ctx): return await ctx.reply("권한이 없습니다.")
        if "|" not in text:
            return await ctx.reply("형식: `!퀴즈관리 추가 질문 | 보기1 ; 보기2 ; ... | 정답번호`")
        q_part, rest = text.split("|", 1)
        question = q_part.strip()
        try:
            choices, ans = _parse_choices_and_answer(rest)
        except Exception as e:
            return await ctx.reply(f"입력 오류: {e}")
        bank = await _load_quiz_bank()
        new_id = _next_quiz_id(bank)
        bank.append({"id": new_id, "q": question, "choices": choices, "answer": ans})
        await _save_quiz_bank(bank)
        await ctx.reply(f"✅ 문제 추가(ID: {new_id})")

    @quiz_admin.command(name="수정", aliases=["edit"])
    async def quiz_edit(self, ctx: commands.Context, *, text: str = ""):
        if not _is_admin(self.bot, ctx): return await ctx.reply("권한이 없습니다.")
        m = re.match(r"\s*(\d+)\s*\|\s*(.+)", text)
        if not m: return await ctx.reply("형식: `!퀴즈관리 수정 <ID> | 질문 | 보기1 ; ... | 정답번호`")
        qid = int(m.group(1)); rest = m.group(2)
        parts = [p.strip() for p in rest.split("|")]
        if len(parts) < 2: return await ctx.reply("형식 오류")
        question = parts[0]
        try:
            choices, ans = _parse_choices_and_answer("|".join(parts[1:]))
        except Exception as e:
            return await ctx.reply(f"입력 오류: {e}")
        bank = await _load_quiz_bank()
        for q in bank:
            if int(q.get("id", 0)) == qid:
                q["q"] = question; q["choices"] = choices; q["answer"] = ans
                await _save_quiz_bank(bank)
                return await ctx.reply(f"✏️ 문제(ID: {qid}) 수정 완료")
        await ctx.reply("해당 ID 문제가 없습니다.")

    @quiz_admin.command(name="목록", aliases=["list"])
    async def quiz_list(self, ctx: commands.Context, page: Optional[int] = 1):
        bank = await _load_quiz_bank()
        if not bank: return await ctx.reply("문제 은행이 비어 있습니다.")
        per = 10
        total = (len(bank) + per - 1) // per
        page = max(1, min(total, int(page)))
        start = (page - 1) * per
        items = bank[start:start+per]
        lines = []
        for q in items:
            ch = q.get("choices", [])
            preview = "; ".join(ch) if len(ch) <= 4 else "; ".join(ch[:4]) + " …"
            lines.append(f"**[{q.get('id')}]** {q.get('q')}  —  ({preview})  / 정답:{q.get('answer')}")
        embed = discord.Embed(title=f"🗂️ 퀴즈 목록 (페이지 {page}/{total}, 총 {len(bank)}문제)",
                              description="\n".join(lines), color=0x95a5a6)
        await ctx.reply(embed=embed)

    # ================= 수동 마감 보조 함수들 =================
    async def _finalize_group_by_force(self, guild: discord.Guild, ch_id: int, sess: Dict[str, Any], forced_by: discord.Member):
        msg_id = sess.get("msg_id")
        answer_idx = sess.get("answer")
        target = sess.get("target", 1)
        channel = guild.get_channel(ch_id)
        if not channel:
            group_sessions.pop(ch_id, None)
            active_by_msg.pop(msg_id, None)
            return
        try:
            message = await channel.fetch_message(msg_id)
        except Exception:
            group_sessions.pop(ch_id, None)
            active_by_msg.pop(msg_id, None)
            return

        correct_emoji = NUM_EMOJIS[answer_idx - 1]
        reaction = next((r for r in message.reactions if str(r.emoji) == correct_emoji), None)
        chosen: List[int] = []
        if reaction:
            users = []
            async for u in reaction.users():
                users.append(u)
            for u in users:
                if u.bot: continue
                if u.id in sess.get("winners", set()):  # 이미 지급자 제외
                    continue
                if u.id in chosen: continue
                chosen.append(u.id)
                if len(chosen) >= target:
                    break

        if chosen:
            balances = await _load_balances()
            for uid in chosen:
                sid = str(uid)
                _ensure_user(balances, sid, 1000)
                balances[sid]["money"] = int(balances[sid]["money"]) + int(sess.get("reward", 0))
            await _save_balances(balances)

        final = discord.Embed(title="🏁 단체 퀴즈 (강제 마감)",
                              description=f"정답: {answer_idx}\n관리자 {forced_by} 님이 마감함",
                              color=0x95a5a6)
        winners_all = set(sess.get("winners", set())) | set(chosen)
        final.set_footer(text=f"우승자: {len(winners_all)}명")
        with contextlib.suppress(Exception):
            await message.edit(embed=final)

        winners_line = ", ".join(f"<@{uid}>" for uid in winners_all) or "없음"
        await channel.send(f"🔒 관리자 강제 마감: 우승자: {winners_line}")
        group_sessions.pop(ch_id, None)
        active_by_msg.pop(msg_id, None)

    async def _finalize_personal_by_force(self, guild_id: int, user_id: int, sess: Dict[str, Any], forced_by: discord.Member):
        msg_id = sess.get("msg_id")
        owner_id = sess.get("owner_id")
        guild = self.bot.get_guild(guild_id)
        if not guild:
            personal_sessions.get(guild_id, {}).pop(user_id, None)
            active_by_msg.pop(msg_id, None)
            return
        message = None
        for ch in guild.text_channels:
            with contextlib.suppress(Exception):
                message = await ch.fetch_message(msg_id)
                if message:
                    break
        if not message:
            personal_sessions.get(guild_id, {}).pop(user_id, None)
            active_by_msg.pop(msg_id, None)
            return
        answer_idx = sess.get("answer")
        correct_emoji = NUM_EMOJIS[answer_idx - 1]
        reacted = False
        reaction = next((r for r in message.reactions if str(r.emoji) == correct_emoji), None)
        if reaction:
            async for u in reaction.users():
                if u.id == owner_id:
                    reacted = True
                    break
        if reacted:
            balances = await _load_balances()
            sid = str(owner_id)
            _ensure_user(balances, sid, 1000)
            balances[sid]["money"] = int(balances[sid]["money"]) + int(sess.get("reward", 0))
            await _save_balances(balances)
            await message.channel.send(f"✅ (강제 마감) <@{owner_id}> 정답으로 보상지급 +{sess.get('reward',0)}원")
        final = discord.Embed(title="🛑 개인 퀴즈 (강제 마감)",
                              description=f"정답: {answer_idx}\n관리자 {forced_by} 님이 마감함",
                              color=0xe67e22)
        with contextlib.suppress(Exception):
            await message.edit(embed=final)
        personal_sessions.get(guild_id, {}).pop(user_id, None)
        active_by_msg.pop(msg_id, None)

async def setup(bot: commands.Bot):
    await bot.add_cog(Economy(bot))
