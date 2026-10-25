import json
import os
import re
import sqlite3
from datetime import datetime

import streamlit as st
from dotenv import load_dotenv
from google import genai
from google.genai import types
from sympy import Eq, Integer, Poly, Rational, latex, solve, symbols, sympify

load_dotenv()
st.set_page_config(page_title="MathMate AI 2.0", page_icon="📘", layout="centered")
x = symbols("x")
DB = "mathmate.db"
MODEL = "gemini-3.5-flash-lite"


def db_connect():
    return sqlite3.connect(DB)


def initialize():
    with db_connect() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            grade TEXT NOT NULL,
            topic TEXT NOT NULL,
            difficulty TEXT NOT NULL,
            a INTEGER NOT NULL,
            b INTEGER NOT NULL,
            c INTEGER NOT NULL,
            user_answer TEXT NOT NULL,
            correct_answer TEXT NOT NULL,
            correct INTEGER NOT NULL,
            explanation TEXT NOT NULL,
            analysis TEXT NOT NULL
        )""")


def api_key():
    try:
        key = st.secrets.get("GEMINI_API_KEY")
        if key:
            return key
    except Exception:
        pass
    return os.getenv("GEMINI_API_KEY")


def gemini(prompt):
    key = api_key()
    if not key:
        raise RuntimeError("GEMINI_API_KEY가 없습니다. .env 파일을 확인하세요.")
    client = genai.Client(api_key=key)
    return client.models.generate_content(model=MODEL, contents=prompt)


def create_problem(grade, topic, difficulty):
    quadratic = topic != "일차방정식"
    prompt = f"""당신은 한국 수학 문제 출제자입니다.
학년 {grade}, 단원 {topic}, 난이도 {difficulty}에 적절한 방정식 문제를 출제합니다.
아래 JSON 객체 하나만 반환하세요. 마크다운 금지.
{{"a":1,"b":-5,"c":6}}
방정식은 a*x^2+b*x+c=0 입니다.
조건: a,b,c는 -12부터 12 사이의 정수, b와 c는 0이어도 됩니다.
{'a는 반드시 0' if not quadratic else 'a는 0이 아니어야 하며 서로 다른 정수 근 두 개가 존재해야 함'}.
너무 쉽거나 자명한 0=0 문제는 금지합니다.
단원과 난이도에 어울리는 새로운 계수를 고르세요."""
    response = gemini(prompt)
    raw = (response.text or "").strip()
    match = re.search(r"\{[\s\S]*?\}", raw)
    if not match:
        raise ValueError("AI가 문제 데이터를 올바르게 반환하지 않았습니다. 다시 생성해 주세요.")
    obj = json.loads(match.group())
    if set(obj) != {"a", "b", "c"} or any(type(obj[k]) is not int or abs(obj[k]) > 12 for k in obj):
        raise ValueError("AI 문제의 계수 형식이 올바르지 않습니다. 다시 시도해 주세요.")
    a, b, c = (obj[k] for k in ("a", "b", "c"))
    if (quadratic and a == 0) or (not quadratic and (a != 0 or b == 0)):
        raise ValueError("AI가 선택한 단원과 맞지 않는 식을 생성했습니다. 다시 시도해 주세요.")
    expression = a*x*x + b*x + c
    roots = sorted(solve(Eq(expression, 0), x))
    if quadratic and (len(roots) != 2 or any(r.is_Integer is not True for r in roots)):
        raise ValueError("검증 가능한 정수 근이 아니므로 새 문제를 생성해 주세요.")
    if not quadratic and len(roots) != 1:
        raise ValueError("유효하지 않은 일차방정식입니다.")
    return {"a":a,"b":b,"c":c,"roots":roots,"grade":grade,"topic":topic,"difficulty":difficulty}


def parse_answer(text):
    # 입력은 정수 또는 분수 두 개 이하만 허용. 수식 코드 실행을 피한다.
    normalized = text.replace(" ", "").replace("x=", "").replace("X=", "")
    normalized = normalized.replace("또는", ",").replace("，", ",")
    parts = normalized.split(",")
    if not 1 <= len(parts) <= 2 or any(not re.fullmatch(r"[+-]?\d+(?:/[+-]?\d+)?", p) for p in parts):
        raise ValueError("정수 또는 분수를 입력해 주세요. 두 근은 쉼표로 구분합니다. 예: 2, 3")
    result = []
    for p in parts:
        val = Rational(p)
        if val.q == 0:
            raise ValueError("0으로 나눌 수 없습니다.")
        result.append(val)
    return sorted(set(result))


def answer_text(roots):
    return ", ".join(str(r) for r in roots)


def fallback_explanation(problem):
    a,b,c = (problem[k] for k in ("a","b","c"))
    expr = a*x*x+b*x+c
    if a == 0:
        return f"식 $${latex(Eq(expr, 0))}$$ 에서 상수항을 이항하고 x의 계수로 나눕니다. 정답은 **{answer_text(problem['roots'])}**입니다."
    from sympy import factor
    return f"식 $${latex(Eq(expr, 0))}$$ 을 인수분해하면 $${latex(Eq(factor(expr),0))}$$ 입니다. 각 인수를 0으로 놓아 풀면 **{answer_text(problem['roots'])}**입니다."


def get_explanation(problem, user_answer, correct):
    expr = problem["a"]*x*x+problem["b"]*x+problem["c"]
    prompt = f"""중학생 수학 교사로서 다음 문제의 풀이를 한국어로 3~5단계로 설명하세요.
문제: {str(expr)} = 0
검증된 정답: {answer_text(problem['roots'])}
학생 답: {user_answer}
채점 결과: {'정답' if correct else '오답'}
검증된 정답을 절대 바꾸지 마세요. 오답이라면 가능한 실수 원인을 단정하지 말고 설명하세요.
마크다운으로 간결하게 작성하세요."""
    try:
        text = gemini(prompt).text
        return text or fallback_explanation(problem)
    except Exception:
        return fallback_explanation(problem)


def save_attempt(p, user, correct, explanation):
    with db_connect() as conn:
        conn.execute("""INSERT INTO attempts
        (created_at,grade,topic,difficulty,a,b,c,user_answer,correct_answer,correct,explanation,analysis)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""", (
            datetime.now().strftime("%Y-%m-%d %H:%M"),p["grade"],p["topic"],p["difficulty"],
            p["a"],p["b"],p["c"],user,answer_text(p["roots"]),int(correct),
            explanation, "정답" if correct else "AI 풀이를 확인하고 같은 유형을 다시 연습하세요."
        ))

initialize()
if "problem" not in st.session_state:
    st.session_state.problem = None
if "graded" not in st.session_state:
    st.session_state.graded = False
if "feedback" not in st.session_state:
    st.session_state.feedback = ""

st.title("📘 MathMate AI 2.0")
st.caption("Gemini AI 문제 생성 · SymPy 검증 · 오답노트")
tab1, tab2, tab3 = st.tabs(["📝 문제 풀기", "📒 오답노트", "📊 학습 통계"])

with tab1:
    grade = st.selectbox("학년", ["중1","중2","중3","고1"], index=2)
    topic = st.selectbox("단원", ["일차방정식","이차방정식","인수분해"])
    difficulty = st.selectbox("난이도", ["쉬움","보통","어려움"])
    if st.button("✨ AI 새 문제 생성", type="primary"):
        with st.spinner("AI 문제를 만들고 수학적으로 검증하는 중..."):
            try:
                st.session_state.problem = create_problem(grade, topic, difficulty)
                st.session_state.graded = False
                st.session_state.feedback = ""
                st.rerun()
            except Exception as e:
                st.error(f"문제 생성 실패: {e}")
    p = st.session_state.problem
    if p:
        expr = p["a"]*x*x + p["b"]*x + p["c"]
        st.subheader("다음 방정식을 푸시오")
        st.latex(latex(Eq(expr, 0)))
        with st.form("answer_form", clear_on_submit=False):
            user = st.text_input("답 입력 (두 근이면 예: 2, 3)", disabled=st.session_state.graded)
            submitted = st.form_submit_button("정답 제출", disabled=st.session_state.graded)
        if submitted:
            try:
                parsed = parse_answer(user)
                correct = parsed == sorted(set(p["roots"]))
                with st.spinner("채점 및 풀이 준비 중..."):
                    explanation = get_explanation(p, user, correct)
                save_attempt(p, user, correct, explanation)
                st.session_state.feedback = explanation
                st.session_state.graded = True
                st.session_state.correct = correct
                st.rerun()
            except ValueError as e:
                st.warning(str(e))
        if st.session_state.graded:
            if st.session_state.correct:
                st.success("정답입니다! 🎉")
            else:
                st.error("오답입니다. 오답노트에 자동 저장했어요.")
            st.write("**정답:**", answer_text(p["roots"]))
            st.markdown("**풀이 및 오답 분석**")
            st.markdown(st.session_state.feedback)
            st.info("다음 문제를 풀려면 'AI 새 문제 생성'을 눌러 주세요.")

with tab2:
    with db_connect() as conn:
        mistakes = conn.execute("""SELECT id,created_at,topic,a,b,c,user_answer,correct_answer,explanation
          FROM attempts WHERE correct=0 ORDER BY id DESC""").fetchall()
    st.subheader(f"오답노트 ({len(mistakes)}개)")
    if not mistakes:
        st.info("아직 오답이 없습니다.")
    for row in mistakes:
        id_,date,unit,a,b,c,user,correct,explanation = row
        with st.expander(f"{date} | {unit} | 문제 #{id_}"):
            st.latex(latex(Eq(a*x*x+b*x+c,0)))
            st.write("내 답:",user)
            st.write("정답:",correct)
            st.markdown(explanation)
            if st.button("이 오답 기록 삭제",key=f"delete_{id_}"):
                with db_connect() as conn:
                    conn.execute("DELETE FROM attempts WHERE id=?",(id_,))
                st.rerun()

with tab3:
    with db_connect() as conn:
        total, wins = conn.execute("SELECT COUNT(*),COALESCE(SUM(correct),0) FROM attempts").fetchone()
        units = conn.execute("SELECT topic,COUNT(*),SUM(correct) FROM attempts GROUP BY topic").fetchall()
    c1,c2,c3 = st.columns(3)
    c1.metric("풀이 수",total)
    c2.metric("정답 수",wins)
    c3.metric("정답률",f"{wins/total:.0%}" if total else "-")
    if units:
        st.subheader("단원별 학습 기록")
        st.dataframe([{"단원":u,"풀이 수":n,"정답 수":ok,"정답률":f"{ok/n:.0%}"} for u,n,ok in units],hide_index=True,use_container_width=True)
    else:
        st.info("문제를 풀면 통계가 나타납니다.")

st.caption("⚠️ 현재 SQLite 기록은 이 컴퓨터에 저장됩니다. 공개 배포 전에는 사용자 로그인 및 온라인 DB를 연결해야 합니다.")
