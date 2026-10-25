"""MathMate AI 6.6 — offline practice with wrong-answer review.

Run: python -m streamlit run app_v66.py
Uses the same dependencies as app.py; stores v2.1 attempts separately.
"""
import hashlib
import json
import math
import os
import random
import re
import sqlite3
import tempfile
import uuid
from pathlib import Path
import html
import base64
from datetime import datetime
from fractions import Fraction

import streamlit as st
from dotenv import load_dotenv
from sympy import Rational

load_dotenv()
st.set_page_config(page_title="MathMate AI 학생용 6.6", page_icon="📘", layout="centered")
# A형 공개 체험판: 학생 브라우저 세션마다 별도 임시 SQLite DB.
if "anonymous_db_id" not in st.session_state:
    st.session_state["anonymous_db_id"] = uuid.uuid4().hex
DB = str(Path(tempfile.gettempdir()) / ("mathmate_demo_" + st.session_state["anonymous_db_id"] + ".db"))
GRADES = ["중1", "중2", "중3", "고1", "고2", "고3"]
DIFFICULTIES = ["쉬움", "보통", "어려움"]
TOPICS = {
    "중1": ["정수와 유리수", "일차방정식", "비와 비율", "수학올림피아드"],
    "중2": ["연립방정식", "일차함수", "확률", "수학올림피아드"],
    "중3": ["인수분해", "이차방정식", "경우의 수", "수학올림피아드"],
    "고1": ["다항식", "방정식과 부등식", "경우의 수", "행렬", "도형의 방정식", "집합과 명제", "함수와 그래프", "수학올림피아드"],
    "고2": ["수열", "확률과 통계", "함수", "수학올림피아드"],
    "고3": ["수열", "확률과 통계", "미적분 응용", "미적분Ⅰ", "수학올림피아드"],
}


def connect():
    return sqlite3.connect(DB)


def init_db():
    with connect() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS questions (
            signature TEXT PRIMARY KEY, grade TEXT, topic TEXT, difficulty TEXT,
            question TEXT, created_at TEXT)""")
        cols = {row[1] for row in conn.execute("PRAGMA table_info(questions)")}
        if "family" not in cols:
            conn.execute("ALTER TABLE questions ADD COLUMN family TEXT")
        conn.execute("""CREATE TABLE IF NOT EXISTS attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT, grade TEXT,
            topic TEXT, difficulty TEXT, question TEXT, user_answer TEXT,
            correct_answer TEXT, correct INTEGER, explanation TEXT)""")
        attempt_cols = {row[1] for row in conn.execute("PRAGMA table_info(attempts)")}
        if "diagram_json" not in attempt_cols:
            conn.execute("ALTER TABLE attempts ADD COLUMN diagram_json TEXT")
        if "problem_json" not in attempt_cols:
            conn.execute("ALTER TABLE attempts ADD COLUMN problem_json TEXT")


def parse_answer(text):
    """Exact rational comparison, accepting integers, decimals, and fractions."""
    parts = re.sub(r"(?i)x\s*=", "", text).replace("또는", ",").replace("，", ",").split(",")
    if not 1 <= len(parts) <= 6:
        raise ValueError("정답은 쉼표로 구분해 최대 6개까지 입력하세요.")
    values = []
    for raw in parts:
        value = raw.strip().replace(" ", "")
        if not re.fullmatch(r"[+-]?(?:\d+(?:\.\d+)?|\.\d+)(?:/[+-]?(?:\d+(?:\.\d+)?|\.\d+))?", value):
            raise ValueError("정수, 소수 또는 분수로 입력하세요. 예: 3/4 또는 0.75")
        try:
            values.append(Rational(value))
        except (ValueError, TypeError, ZeroDivisionError) as exc:
            raise ValueError("분모가 0이 아닌 올바른 숫자를 입력하세요.") from exc
    return sorted(set(values))


def advanced_factor_problem(rng, avoid_families=()):
    """중3 인수분해: distinct reasoning strategies, independently calculated answers."""
    families = ["area_border", "factor_pair", "parameter_factor", "common_factor", "number_pattern", "difference_squares", "quadratic_relation", "tile_arrangement"]
    eligible = [f for f in families if f not in avoid_families]
    if not eligible:
        eligible = families
    family = rng.choice(eligible)
    if family == "area_border":
        w = rng.randint(7, 17)
        d = rng.randint(3, 9)
        border = rng.randint(1, 4)
        area = w * (w + d)
        outside = (w + 2*border)*(w+d+2*border)
        q = (f"직사각형 화단의 세로는 가로보다 {d}m 길다. 화단 바깥쪽에 폭이 {border}m인 통로를 네 변에 똑같이 만들었다. "
             f"통로까지 포함한 전체 넓이는 {outside}m²이고, 통로는 화단 내부와 겹치지 않는다. "
             "화단의 가로와 세로는 모두 자연수 길이이며 통로의 모서리는 직각이다. 원래 화단의 넓이는 몇 m²인가?")
        ans=area
        sol=(f"화단 가로를 x라 두면 (x+{2*border})(x+{d+2*border})={outside}. "
             f"전개하여 인수분해하면 (x-{w})(x+{w+d+4*border})=0. 양수 해 x={w}, 원래 넓이는 {area}.")
        params=(w,d,border)
    elif family == "factor_pair":
        a=rng.randint(4,13); b=rng.randint(a+2,a+11)
        total=a+b; product=a*b
        q=(f"서로 다른 두 자연수 A, B가 있으며 A는 B보다 작다. 두 수의 합은 {total}이고 곱은 {product}이다. "
           "두 수를 바로 추측하지 말고, 한 수를 x로 두어 이차식을 만든 뒤 인수분해하여 조건을 만족하는 두 수를 찾는다. "
           "그렇게 구한 두 수의 차 B-A를 구하시오.")
        ans=b-a
        sol=f"x({total}-x)={product}에서 x²-{total}x+{product}=(x-{a})(x-{b})=0. 차는 {b-a}."
        params=(a,b)
    elif family == "parameter_factor":
        a=rng.randint(3,11); b=rng.randint(a+2,a+10)
        summ=a+b; prod=a*b; target=b-a
        q=(f"이차식 x²-{summ}x+k가 정수 계수를 갖는 두 일차식의 곱으로 인수분해된다고 한다. "
           f"또한 이 식이 0이 되는 서로 다른 두 자연수의 합은 {summ}, 차는 {target}이다. "
           "이 조건을 만족하는 두 자연수는 모두 양수이며, k는 자연수이다. "
           "가능한 k의 값을 구하시오.")
        ans=prod
        sol=f"두 근은 ({summ}-{target})/2={a}, ({summ}+{target})/2={b}. 따라서 (x-{a})(x-{b})이므로 k={prod}."
        params=(a,b)
    elif family == "common_factor":
        a=rng.randint(2,7); b=rng.randint(2,9); c=rng.randint(2,8)
        x=rng.randint(3,10)
        target=(a*x+b)*(x+c)
        q=(f"어떤 직사각형의 가로는 (x+{c})cm, 세로는 ({a}x+{b})cm이다. "
           f"이 직사각형의 넓이는 {target}cm²이며 x는 양의 정수이다. "
           "넓이를 전개해 만든 이차방정식을 인수분해하여 x를 결정할 수 있다. "
           "직사각형의 둘레는 몇 cm인가?")
        ans=2*((a+1)*x+b+c)
        sol=f"(x+{c})({a}x+{b})={target}. 양수 범위에서 좌변은 증가하므로 x={x}가 유일하다. 둘레는 2[({x}+{c})+({a}×{x}+{b})]={ans}."
        params=(a,b,c,x)
    elif family == "number_pattern":
        n=rng.randint(8,25); k=rng.randint(2,6)
        product=n*(n+k)
        q=(f"서로 다른 두 자연수의 차는 {k}이고, 두 수의 곱은 {product}이다. "
           "작은 수를 x라 하면 큰 수는 x에 일정한 자연수를 더한 값으로 나타난다. "
           "곱에 관한 조건을 이차방정식으로 세워 인수분해한 뒤, 자연수 조건에 맞는 해만 선택한다. "
           "두 수의 합을 구하시오.")
        ans=2*n+k
        sol=f"x(x+{k})={product}에서 (x-{n})(x+{n+k})=0. 자연수 x={n}이므로 합은 {ans}."
        params=(n,k)
    elif family == "difference_squares":
        a=rng.randint(13,31); b=rng.randint(3, a-4)
        diff=a*a-b*b
        q=(f"한 정사각형의 한 변의 길이는 다른 정사각형보다 {a-b}cm 길다. "
           f"두 정사각형의 넓이의 차는 {diff}cm²이다. "
           "두 정사각형의 변의 길이는 자연수이고, 큰 정사각형에서 작은 정사각형을 제외한 부분의 넓이를 비교한다. "
           "합차공식을 활용하여 두 정사각형의 둘레의 합을 구하시오.")
        ans=4*(a+b)
        sol=f"변 길이를 A>B라 하면 (A-B)(A+B)={diff}, A-B={a-b}. A+B={a+b}이므로 둘레 합은 4(A+B)={ans}."
        params=(a,b)
    elif family == "quadratic_relation":
        a=rng.randint(3,10); b=rng.randint(a+2,a+12)
        summ=a+b; prod=a*b
        q=(f"어떤 두 자연수 p, q는 p<q를 만족한다. 두 수의 제곱의 합은 {a*a+b*b}이고, 두 수의 곱은 {prod}이다. "
           "두 수의 합을 직접 알 수는 없지만, 제곱의 합과 곱 사이의 관계를 이용하면 합의 제곱을 구할 수 있다. "
           "그다음 인수분해 또는 제곱의 차를 이용해 두 수를 결정한다. 큰 수 q를 구하시오.")
        ans=b
        sol=f"(p+q)²=p²+q²+2pq={summ*summ}이므로 p+q={summ}. t²-{summ}t+{prod}=(t-{a})(t-{b}), 따라서 q={b}."
        params=(a,b)
    else: # tile_arrangement
        n=rng.randint(5,14); k=rng.randint(2,7)
        area=n*(n+k)
        q=(f"정사각형 모양의 타일을 빈틈없이 놓아 직사각형을 만들었다. "
           f"타일은 모두 {area}장이고, 세로 방향의 타일 수는 가로 방향보다 {k}장 많다. "
           "타일을 자르거나 겹치게 놓을 수 없으며, 가로와 세로 방향의 타일 수는 자연수이다. "
           "타일 배열의 가로 방향 개수를 인수분해를 이용해 구한 뒤, 직사각형의 테두리에 놓인 타일은 모두 몇 장인지 구하시오.")
        ans=2*n+2*(n+k)-4
        sol=f"가로 x라 하면 x(x+{k})={area}에서 (x-{n})(x+{n+k})=0. 가로 {n}, 세로 {n+k}. 테두리 타일 수는 2×{n}+2×{n+k}-4={ans}."
        params=(n,k)
    signature=hashlib.sha256(json.dumps(["v23", "중3", "인수분해", "어려움", family,params],ensure_ascii=False).encode()).hexdigest()
    return {"question":q,"answer":[Rational(ans)],"explanation":sol,"signature":signature,
            "family":family,"grade":"중3","topic":"인수분해","difficulty":"어려움",
            "source_label":None,"source_url":None}



# 2.4: mathematically checked, original nonroutine question families.
# These are NOT authentic IMO/KMO/AIME/Kyoto past questions.
def reasoning_problem(grade, topic, difficulty, rng, avoid_families=()):
    R = Rational
    if topic == "수학올림피아드":
        pool = (["lattice_two_avoid", "lattice_avoid", "residue_logic", "circle_chord"]
                if grade.startswith("고") else
                ["square_difference", "residue_logic", "lattice_avoid", "symmetric_roots", "circle_chord"])
    elif topic in ("미적분Ⅰ", "미적분 응용") and difficulty == "어려움":
        pool = ["exp_extrema", "integral_symmetry", "tangent_integral"]
    elif topic == "일차함수" and difficulty == "어려움":
        pool = ["line_area"]
    elif topic == "함수" and difficulty == "어려움":
        pool = ["parabola_intersections"]
    elif topic in ("인수분해", "이차방정식", "다항식") and difficulty == "어려움":
        pool = ["symmetric_roots", "square_difference"]
    elif topic == "경우의 수" and difficulty == "어려움":
        pool = ["lattice_avoid"]
    else:
        return None
    fresh = [name for name in pool if name not in avoid_families]
    family = rng.choice(fresh or pool)
    diagram = None
    if family == "square_difference":
        # (n+k)^2 - n^2 = k(2n+k), unique n for fixed k and area.
        n = rng.randint(8, 26); k = rng.randint(2, 7)
        area = k*(2*n+k)
        q = (f"두 자연수 a, b(a>b)에 대하여 a-b={k}, a²-b²={area}이다. "
             "a²-b²를 직접 계산하지 않고 인수분해의 구조를 이용하여 ab의 값을 구하시오.")
        ans = n*(n+k)
        sol = f"(a-b)(a+b)={area}이므로 a+b={2*n+k}. 따라서 a={n+k}, b={n}, ab={ans}."
        params=(n,k)
    elif family == "residue_logic":
        # Small CRT with extra sum-of-digits style constraint: N is between 100 and 400,
        # 2 congruences, and N is divisible by a third modulus; unique chosen interval.
        m,n=rng.choice([(5,7),(7,11),(8,9)])
        base=rng.randint(10,30)
        target=base*m*n + rng.randint(1,m*n-1)
        r1,r2=target%m,target%n
        lower=(target//(m*n)-1)*m*n+1
        upper=lower+2*m*n-1
        # Exactly two CRT candidates in interval; impose parity of quotient to select.
        q=(f"자연수 N은 {lower} 이상 {upper} 이하이고, N을 {m}로 나눈 나머지는 {r1}, "
           f"{n}로 나눈 나머지는 {r2}이다. 또한 N을 {m*n}로 나눈 몫은 홀수이다. "
           "조건을 모두 만족하는 N을 구하시오.")
        candidates=[x for x in range(lower,upper+1) if x%m==r1 and x%n==r2 and (x//(m*n))%2==1]
        if len(candidates)!=1: raise ValueError("residue candidate uniqueness")
        ans=candidates[0]
        sol=f"두 나머지 조건으로 N≡{target%(m*n)} (mod {m*n}). 범위 내 두 후보 중 몫이 홀수인 것은 {ans}."
        params=(m,n,lower,r1,r2)
    elif family == "lattice_two_avoid":
        w=rng.randint(6,9);h=rng.randint(6,9)
        px=rng.randint(1,w-3);py=rng.randint(1,h-3)
        qx=rng.randint(px+1,w-1);qy=rng.randint(py+1,h-1)
        total=math.comb(w+h,w)
        via_p=math.comb(px+py,px)*math.comb(w+h-px-py,w-px)
        via_q=math.comb(qx+qy,qx)*math.comb(w+h-qx-qy,w-qx)
        both=math.comb(px+py,px)*math.comb(qx-px+qy-py,qx-px)*math.comb(w-qx+h-qy,w-qx)
        ans=total-via_p-via_q+both
        q=(f"격자점 (0,0)에서 ({w},{h})까지 오른쪽·위쪽으로만 한 칸씩 이동한다. "
           f"서로 다른 두 점 P({px},{py}), Q({qx},{qy})를 모두 피하는 최단 경로의 수를 구하시오. (그림 참고)")
        sol=f"포함배제: 전체 {total}, P 경유 {via_p}, Q 경유 {via_q}, 둘 다 경유 {both}. 답={total}-{via_p}-{via_q}+{both}={ans}."
        params=(w,h,px,py,qx,qy)
        diagram={"type":"grid","w":w,"h":h,"px":px,"py":py,"qx":qx,"qy":qy}
    elif family == "lattice_avoid":
        w=rng.randint(4,7); h=rng.randint(4,7)
        px=rng.randint(1,w-1); py=rng.randint(1,h-1)
        total=math.comb(w+h,w)
        via=math.comb(px+py,px)*math.comb(w+h-px-py,w-px)
        ans=total-via
        q=(f"좌표평면의 격자점 (0,0)에서 ({w},{h})까지 오른쪽 또는 위쪽으로만 한 칸씩 이동한다. "
           f"점 P({px},{py})를 지나지 않는 최단 경로의 수를 구하시오. (그림 참고)")
        sol=f"전체 {total}가지에서 P를 지나는 {math.comb(px+py,px)}×{math.comb(w+h-px-py,w-px)}={via}가지를 빼면 {ans}."
        params=(w,h,px,py); diagram={"type":"grid","w":w,"h":h,"px":px,"py":py}
    elif family == "symmetric_roots":
        # monic quadratic roots u,v. Given sum and difference of squares; unique uv.
        u=rng.randint(3,12); v=rng.randint(u+2,u+10)
        summ=u+v; diffsq=v*v-u*u
        q=(f"이차방정식 x²-{summ}x+k=0의 서로 다른 두 양의 정수 근을 α, β(α<β)라 하자. "
           f"β²-α²={diffsq}일 때 상수 k의 값을 구하시오.")
        ans=u*v
        sol=f"(β-α)(β+α)={diffsq}, β+α={summ}이므로 β-α={v-u}. 따라서 α={u}, β={v}, k=αβ={ans}."
        params=(u,v)
    elif family == "circle_chord":
        # perpendicular radius to chord bisects chord; right triangle exact.
        a,b=rng.choice([(3,4),(5,12),(8,15),(7,24)])
        scale=rng.randint(1,3)
        half=a*scale; dist=b*scale; radius=math.hypot(half,dist)
        radius=int(radius)
        q=(f"반지름이 {radius}인 원 O에서 현 AB의 길이는 {2*half}이다. "
           "중심 O에서 현 AB에 내린 수선의 발을 H라 할 때 OH의 길이를 구하시오. (그림 참고)")
        ans=dist
        sol=f"중심에서 현에 내린 수선은 현을 이등분하므로 AH={half}. 직각삼각형 OHA에서 OH²={radius}²-{half}², OH={dist}."
        params=(half,dist);diagram={"type":"chord","radius":radius,"half":half,"dist":dist}
    elif family == "exp_extrema":
        # f=e^x(x²-2cx+c²-1); f'=e^x[(x-c+1)^2-2]
        # extrema at c-1±sqrt2; hard irrational answers unsupported by exact rational UI.
        # Instead use f=e^x(x²-2cx+c²), f'=e^x(x-c)(x-c+2).
        # extrema at c-2 and c, f(c)=0, f(c-2)=4 e^(c-2) >0.
        # ask integer c from f(0)=c² and derivative f'(0)=c(c-2); given both via sum.
        c=rng.randint(3,8)
        f0=c*c; fp0=c*(c-2)
        q=("함수 f(x)=eˣ(x²+ax+b)가 다음 조건을 만족한다. "
           "(가) 서로 다른 두 극점의 x좌표 차는 2이다. "
           "(나) 두 극값 중 하나는 0이다. "
           f"(다) f(0)={f0}이고 f'(0)={fp0}이다. "
           "이때 a+b의 값을 구하시오.")
        # f'=e^x[x²+(a+2)x+(a+b)], zero-extremum -> polynomial has double root -> a²=4b.
        # a=±2c, b=c²; fp0=a+b, so a=fp0-b=-2c.
        ans=c*c-2*c
        sol=(f"f(0)=b={f0}, f'(0)=a+b={fp0}. 따라서 a={-2*c}, b={c*c}이고 a+b={ans}. "
             f"실제로 f(x)=eˣ(x-{c})², f'(x)=eˣ(x-{c})(x-{c}+2)로 두 극점의 차는 2, 극값 중 하나는 0이다.")
        params=(c,)
    elif family == "integral_symmetry":
        a=rng.randint(2,8); b=rng.randint(1,6)
        # odd part integrates to zero on symmetric interval, even x² term integrates.
        q=(f"다항함수 f(x)=x³+ax²+bx+c가 있다. "
           f"모든 실수 t에 대해 f(t)+f(-t)={2*a}t²+{2*b}라고 한다. "
           f"또한 ∫[-1,1] f(x)dx={R(2*a,3)+2*b}이다. "
           "f(1)+f(-1)의 값을 구하시오.")
        # Here a and b variable names are deliberately coefficients; c=b, answer 2a+2b.
        ans=2*a+2*b
        sol=f"짝함수 부분만 남기면 f(t)+f(-t)=2at²+2c. 조건에서 a={a}, c={b}. 따라서 f(1)+f(-1)={ans}."
        params=(a,b)
    elif family == "tangent_integral":
        # f'=3x²-6hx +k ; f'(h)=0 -> k=3h²; f=(x-h)^3+C.
        h=rng.randint(1,5); C=rng.randint(2,9)
        q=(f"삼차함수 f(x)는 f'(x)=3(x-{h})²를 만족한다. "
           f"곡선 y=f(x)의 x={h}에서의 접선은 y={C}이다. "
           f"∫[{h-1},{h+1}] f(x)dx의 값을 구하시오.")
        ans=2*C
        sol=f"f(x)=(x-{h})³+C이고 접선 조건에서 C={C}. 대칭 구간에서 홀함수 부분의 적분은 0이므로 적분값은 {ans}."
        params=(h,C)
    elif family == "line_area":
        x=rng.randint(2,7); y=rng.randint(3,9)
        q=(f"좌표평면에서 두 직선 y={y}x/{x}, y=-{y}x/{x}+{2*y}가 만나는 점을 P라 하자. "
           "두 직선과 x축이 이루는 삼각형의 넓이를 구하시오. (그림 참고)")
        ans=x*y
        sol=f"교점 P=({x},{y}), 두 x절편은 0과 {2*x}이다. 밑변 {2*x}, 높이 {y}이므로 넓이는 {ans}."
        params=(x,y); diagram={"type":"triangle_lines","x":x,"y":y}
    else: # parabola_intersections
        h=rng.randint(2,6); k=rng.randint(2,6)
        q=(f"이차함수 y=(x-{h})²-{k*k}의 그래프가 x축과 만나는 두 점을 A, B라 한다. "
           "꼭짓점을 V라 할 때 삼각형 ABV의 넓이를 구하시오. (그림 참고)")
        ans=k**3
        sol=f"x절편은 {h-k}, {h+k}이므로 AB={2*k}. 꼭짓점의 y좌표는 -{k*k}이므로 높이 {k*k}, 넓이는 {ans}."
        params=(h,k);diagram={"type":"parabola","h":h,"k":k}
    signature=hashlib.sha256(json.dumps(["v24",grade,topic,difficulty,family,params],ensure_ascii=False).encode()).hexdigest()
    return {"question":q,"answer":[R(ans)],"explanation":sol,"signature":signature,
            "family":family,"grade":grade,"topic":topic,"difficulty":difficulty,
            "diagram":diagram,"source_label":None,"source_url":None}


def diagram_svg(spec):
    """Vector diagrams derived directly from the same numeric parameters as answers."""
    if not spec: return None
    kind=spec["type"]
    parts=['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 660 350" width="660" height="350">',
           '<rect width="660" height="350" fill="white"/>',
           '<style>text{font:18px Arial,sans-serif;fill:#1b2b43}.axis{stroke:#9aaac0;stroke-width:2}.main{stroke:#2563eb;stroke-width:3;fill:none}.accent{stroke:#dc6a36;stroke-width:3;fill:none}</style>']
    def line(x1,y1,x2,y2,css="main"):
        parts.append(f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" class="{css}"/>')
    def text_at(x,y,t):
        parts.append(f'<text x="{x:.2f}" y="{y:.2f}">{html.escape(str(t))}</text>')
    def dot(x,y):
        parts.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="5" fill="#1b2b43"/>')
    if kind=="grid":
        w,h,px,py=[spec[k] for k in ("w","h","px","py")]
        unit=min(45,245/max(w,h)); ox=100; oy=290
        for i in range(w+1):line(ox+i*unit,oy,ox+i*unit,oy-h*unit,"axis")
        for j in range(h+1):line(ox,oy-j*unit,ox+w*unit,oy-j*unit,"axis")
        dot(ox,oy);text_at(ox-23,oy+24,"O")
        dot(ox+w*unit,oy-h*unit);text_at(ox+w*unit+8,oy-h*unit-8,"B")
        dot(ox+px*unit,oy-py*unit);text_at(ox+px*unit+8,oy-py*unit-8,"P")
        if "qx" in spec:
            qx,qy=spec["qx"],spec["qy"]
            dot(ox+qx*unit,oy-qy*unit);text_at(ox+qx*unit+8,oy-qy*unit-8,"Q")
            parts.append(f'<circle cx="{ox+qx*unit}" cy="{oy-qy*unit}" r="13" fill="none" stroke="#dc6a36" stroke-width="3"/>')
        parts.append(f'<circle cx="{ox+px*unit}" cy="{oy-py*unit}" r="13" fill="none" stroke="#dc6a36" stroke-width="3"/>')
    elif kind=="chord":
        r,half,dist=[spec[k] for k in ("radius","half","dist")]
        ox=310;oy=160;scale=115/r
        parts.append(f'<circle cx="{ox}" cy="{oy}" r="115" class="main"/>')
        cy=oy+dist*scale;ax=ox-half*scale;bx=ox+half*scale
        line(ax,cy,bx,cy,"accent");line(ox,oy,ax,cy);line(ox,oy,ox,cy)
        dot(ox,oy);text_at(ox+9,oy-9,"O")
        text_at(ax-24,cy+5,"A");text_at(bx+9,cy+5,"B");text_at(ox+8,cy+20,"H")
        parts.append(f'<path d="M {ox} {cy-13} h 13 v 13" stroke="#64748b" fill="none"/>')
    elif kind=="triangle_lines":
        x,y=spec["x"],spec["y"]; ox=100; oy=285; ux=440/(2*x);uy=190/y
        line(65,oy,590,oy,"axis");line(ox,oy,ox,40,"axis")
        line(ox,oy,ox+x*ux,oy-y*uy);line(ox+x*ux,oy-y*uy,ox+2*x*ux,oy,"accent")
        for xx,yy,lab in [(ox,oy,"A"),(ox+x*ux,oy-y*uy,"P"),(ox+2*x*ux,oy,"B")]:dot(xx,yy);text_at(xx+8,yy-10,lab)
        text_at(ox+x*ux+10,oy-y*uy+28,f"({x}, {y})")
    elif kind=="parabola":
        h,k=spec["h"],spec["k"]
        ox=330;oy=115;scale_x=35;scale_y=145/(k*k)
        line(65,oy,600,oy,"axis");line(ox,30,ox,320,"axis")
        pts=[]
        for i in range(161):
            t=-k-1+(2*k+2)*i/160
            xx=ox+t*scale_x; yy=oy-((t*t)-(k*k))*scale_y
            if -10<=xx<=670 and -10<=yy<=360:pts.append((xx,yy))
        if pts:parts.append('<polyline class="main" points="'+' '.join(f'{xx:.2f},{yy:.2f}' for xx,yy in pts)+'"/>')
        for t,lab in [(-k,"A"),(k,"B")]:dot(ox+t*scale_x,oy);text_at(ox+t*scale_x+8,oy-9,lab)
        dot(ox,oy+k*k*scale_y);text_at(ox+8,oy+k*k*scale_y+20,"V")
        text_at(ox-50,oy-15,f"x={h} 기준")
    parts.append('</svg>')
    return ''.join(parts).encode('utf-8')


def display_diagram(spec):
    svg=v66_svg(spec) or middle62_svg(spec) or v59_diagram(spec) or diagram_svg_hs(spec) or diagram_svg(spec)
    if svg:
        encoded=base64.b64encode(svg).decode('ascii')
        st.markdown(f'<img src="data:image/svg+xml;base64,{encoded}" style="width:100%;max-width:660px;height:auto" alt="수학 조건을 반영한 그림">',unsafe_allow_html=True)

def common_math_problem(grade, topic, difficulty, rng):
    """2022 개정 공통수학 1·2: 자체 제작 문항. 기출로 표시하지 않음."""
    R = Rational
    a, b, c = rng.sample(range(2, 18), 3)
    if topic == "집합과 명제":
        family = rng.choice(["union", "intersection", "difference", "implication"])
        if family == "union":
            common = rng.randint(2, 9)
            only_a, only_b = rng.randint(3, 12), rng.randint(3, 12)
            na, nb = common + only_a, common + only_b
            ans = common + only_a + only_b
            q = f"두 유한집합 A, B에 대해 n(A)={na}, n(B)={nb}, n(A∩B)={common}이다. n(A∪B)를 구하시오."
            sol = f"포함배제 원리: {na}+{nb}-{common}={ans}."
        elif family == "intersection":
            common = rng.randint(2, 9)
            na, nb = common + a, common + b
            union = na + nb - common
            ans = common
            q = f"두 집합 A, B에 대해 n(A)={na}, n(B)={nb}, n(A∪B)={union}이다. n(A∩B)를 구하시오."
            sol = f"n(A∩B)=n(A)+n(B)-n(A∪B)={na}+{nb}-{union}={ans}."
        elif family == "difference":
            common = rng.randint(2, 9)
            ans = a
            q = f"집합 A의 원소는 {a+common}개이고 A∩B의 원소는 {common}개이다. 차집합 A-B의 원소는 몇 개인가?"
            sol = f"n(A-B)=n(A)-n(A∩B)={a+common}-{common}={ans}."
        else:
            root = rng.randint(2, 12)
            ans = root
            q = f"실수 x에 대해 명제 'x>{root}이면 x>k이다'가 항상 참이 되도록 하는 정수 k의 최댓값을 구하시오."
            sol = f"x가 {root}보다 아주 조금 큰 경우도 고려하면 k≤{root}. 따라서 최댓값은 {root}."
    elif topic == "행렬":
        family = "matrix_multiplication"
        ans = a*c + b*a
        q = f"행렬 A=[[{a}, {b}], [1, 0]], B=[[{c}, 0], [{a}, 1]]일 때, 행렬 AB의 (1,1) 성분을 구하시오."
        sol = f"첫째 행과 첫째 열의 내적: {a}×{c}+{b}×{a}={ans}."
    elif topic == "도형의 방정식":
        family = rng.choice(["line_slope", "circle_radius", "midpoint"])
        if family == "line_slope":
            ans = a
            q = f"두 점 P(1, {b}), Q(4, {b+3*a})를 지나는 직선의 기울기를 구하시오."
            sol = f"기울기=({b+3*a}-{b})/(4-1)={ans}."
        elif family == "circle_radius":
            ans = a*a
            q = f"원의 방정식 (x-{b})²+(y+{c})²={a*a}에서 반지름의 제곱을 구하시오."
            sol = f"표준형 (x-p)²+(y-q)²=r²에서 r²={ans}."
        else:
            ans = a
            q = f"두 점 A({a-b}, 2), B({a+b}, 8)의 중점 M의 x좌표를 구하시오."
            sol = f"중점의 x좌표=({a-b}+{a+b})/2={ans}."
    elif topic == "함수와 그래프":
        family = rng.choice(["function_value", "inverse_linear", "rational_value"])
        if family == "function_value":
            ans = a*b+c
            q = f"함수 f(x)={a}x+{c}일 때 f({b})의 값을 구하시오."
            sol = f"f({b})={a}×{b}+{c}={ans}."
        elif family == "inverse_linear":
            ans = b
            q = f"함수 f(x)={a}x+{c}에서 f(x)={a*b+c}를 만족하는 x를 구하시오."
            sol = f"{a}x+{c}={a*b+c}에서 x={ans}."
        else:
            ans = a
            q = f"함수 f(x)={a*b}/(x-{c})에서 f({b+c})의 값을 구하시오. (x≠{c})"
            sol = f"f({b+c})={a*b}/{b}={ans}."
    else:
        raise ValueError("지원하지 않는 공통수학 단원입니다.")
    signature = hashlib.sha256(json.dumps(["common29", grade, topic, family, q], ensure_ascii=False).encode()).hexdigest()
    return {"question": q, "answer": [R(ans)], "explanation": sol, "signature": signature,
            "family": family, "grade": grade, "topic": topic, "difficulty": difficulty,
            "source_label": None, "source_url": None}


def choose_problem(grade, topic, difficulty, rng, avoid_families=()):
    if grade == "고1" and topic in ("행렬", "도형의 방정식", "집합과 명제", "함수와 그래프"):
        calibrated = calibrated_math_problem(grade, topic, difficulty, rng)
        return calibrated if calibrated is not None else common_math_problem(grade, topic, difficulty, rng)
    """Curriculum-matched, mathematically verified word-problem generators."""
    advanced = reasoning_problem(grade, topic, difficulty, rng, avoid_families)
    if advanced is not None:
        return advanced
    level = {"쉬움": 1, "보통": 2, "어려움": 3}[difficulty]
    menu = {
        "정수와 유리수": ["balance", "fraction_story"],
        "일차방정식": ["tickets", "ages", "balance"],
        "비와 비율": ["mixture", "ratio_story"],
        "연립방정식": ["tickets", "ages", "market"],
        "일차함수": ["taxi", "intersection"],
        "확률": ["probability", "conditional_bag"],
        "인수분해": ["rectangle", "factor_roots", "consecutive"],
        "이차방정식": ["rectangle", "consecutive", "factor_roots"],
        "경우의 수": ["paths", "committee", "inclusion"],
        "다항식": ["factor_roots", "remainder_poly", "rectangle"],
        "방정식과 부등식": ["tickets", "rectangle", "consecutive"],
        "수열": ["sequence_story", "sequence_sum", "sequence_reverse"],
        "확률과 통계": ["probability", "conditional_bag", "committee"],
        "함수": ["taxi", "intersection", "quadratic_vertex"],
        "미적분 응용": ["optimization", "rate_integral"],
        "수학올림피아드": ["square", "remainders", "paths", "committee", "inclusion", "consecutive", "divisors"],
    }
    families = menu.get(topic, [])
    if not families:
        raise ValueError("아직 지원하지 않는 단원입니다.")
    fresh = [f for f in families if f not in avoid_families]
    if not fresh:
        # Every family has appeared recently: rotate to the least recently used one.
        # The query lists newest first, so the largest index is the oldest.
        family = max(families, key=lambda f: list(avoid_families).index(f))
    else:
        family = rng.choice(fresh)
    R = Rational
    if family == "tickets":
        adult, child = rng.randint(7, 17), rng.randint(5, 14)
        pa, pc = rng.randint(9, 16)*1000, rng.randint(4, 8)*1000
        if pa == pc: pa += 2000
        total = adult + child; revenue = adult*pa + child*pc
        q = (f"한 체험관에서는 성인 입장권을 {pa:,}원, 청소년 입장권을 {pc:,}원에 판매한다. "
             f"어느 날 두 종류의 입장권을 합하여 {total}장 판매했고, 입장권 판매 금액은 모두 {revenue:,}원이었다. "
             "단체 할인이나 무료 입장은 없었으며, 모든 방문객은 입장권을 정확히 한 장씩 구매했다. "
             "이날 판매된 성인 입장권은 몇 장인지 구하시오.")
        ans = adult; sol = f"성인 x장, 청소년 {total}-x장. {pa}x+{pc}({total}-x)={revenue}이므로 x={adult}."
        params = (adult, child, pa, pc)
    elif family == "ages":
        younger = rng.randint(8, 17); older = younger + rng.randint(7, 15)
        after = rng.randint(3, 9); total = younger+older+2*after
        q = (f"현재 두 형제의 나이 차는 {older-younger}살이다. "
             f"{after}년 뒤 두 형제의 나이의 합은 {total}살이 된다고 한다. "
             "두 사람 모두 매년 같은 시점에 한 살씩 나이를 먹는다고 가정한다. "
             "현재 동생의 나이는 몇 살인지 구하시오.")
        ans=younger; sol=f"현재 동생 x살, 형 x+{older-younger}살. {after}년 뒤 합은 2x+{older-younger}+{2*after}={total}. x={younger}."
        params=(younger,older,after)
    elif family == "market":
        a,b=rng.randint(3,9),rng.randint(4,10)
        x,y=rng.randint(2,7)*1000,rng.randint(2,7)*1000+500
        c,d=a+1,b+2
        v1=a*x+b*y;v2=c*x+d*y
        q=(f"문구점에서 같은 종류의 공책과 펜을 판매한다. 첫 번째 손님은 공책 {a}권과 펜 {b}자루를 사고 {v1:,}원을 냈다. "
           f"두 번째 손님은 같은 가격으로 공책 {c}권과 펜 {d}자루를 사고 {v2:,}원을 냈다. "
           "할인이나 추가 비용은 없고 각 물건의 가격은 항상 일정하다. 공책 한 권의 가격을 구하시오.")
        ans=x;sol=f"공책 가격 x, 펜 가격 y로 놓고 {a}x+{b}y={v1}, {c}x+{d}y={v2}를 연립하면 x={x}."
        params=(a,b,x,y)
    elif family == "balance":
        x=rng.randint(9,32); multiplier=rng.randint(2,5); add=rng.randint(7,21)
        result=multiplier*x+add
        q=(f"어떤 수를 생각하여 그 수에 {multiplier}를 곱했다. "
           f"이 결과에 {add}를 더하니 {result}이 되었다. "
           "계산 순서는 곱셈을 먼저 하고 덧셈을 나중에 한 것이며, 중간에 반올림은 하지 않았다. "
           "처음 생각한 수를 구하시오.")
        ans=x;sol=f"{multiplier}x+{add}={result}이므로 x={x}.";params=(x,multiplier,add)
    elif family == "fraction_story":
        denominator=rng.choice([4,5,8,10]); total=denominator*rng.randint(5,18)
        num=rng.randint(1,denominator-1); left=total*(denominator-num)//denominator
        q=(f"한 학생이 가진 스티커는 모두 {total}장이다. "
           f"그중 전체의 {num}/{denominator}를 친구들에게 나누어 주었다. "
           "스티커는 모두 같은 크기이며 한 장을 나누어 주거나 쪼개지 않았다. "
           "학생에게 남은 스티커의 수를 구하시오.")
        ans=left;sol=f"남은 비율은 1-{num}/{denominator}. {total}×({denominator-num}/{denominator})={left}.";params=(denominator,total,num)
    elif family == "ratio_story":
        a,b=rng.randint(2,7),rng.randint(3,8); unit=rng.randint(4,15)
        q=(f"동아리의 A팀과 B팀 인원수의 비는 {a}:{b}이다. "
           f"두 팀의 총인원은 {unit*(a+b)}명이며, 모든 사람은 두 팀 중 정확히 한 팀에만 속한다. "
           "두 팀에서 같은 수의 인원이 이동하더라도 전체 인원수는 변하지 않는다고 한다. "
           "처음 A팀의 인원은 몇 명인지 구하시오.")
        ans=a*unit;sol=f"전체를 {a+b}등분하면 한 몫은 {unit}명. A팀은 {a}×{unit}={ans}명.";params=(a,b,unit)
    elif family == "mixture":
        a,b=rng.choice([(10,30),(20,40),(15,35)]); v1=rng.randint(2,8)*100;v2=rng.randint(2,8)*100
        percent=R(a*v1+b*v2,v1+v2)
        q=(f"농도가 {a}%인 소금물 {v1}g과 농도가 {b}%인 소금물 {v2}g을 섞는다. "
           "혼합 과정에서 소금이나 물은 증발하거나 손실되지 않는다. "
           "소금물의 전체 질량은 두 용액의 질량의 합과 같다. "
           "새로 만들어진 소금물의 농도는 몇 %인지 구하시오. 정수 또는 분수로 답해도 된다.")
        ans=percent;sol=f"소금 질량은 {a*v1}/100+{b*v2}/100g. 농도는 그 합을 {v1+v2}g으로 나누어 100을 곱한 {percent}%.";params=(a,b,v1,v2)
    elif family == "taxi":
        base=rng.randint(3,7)*1000;per=rng.randint(1,4)*1000;distance=rng.randint(5,14)
        fare=base+per*distance
        q=(f"한 택시의 요금은 기본요금 {base:,}원과 주행 거리 1km당 {per:,}원의 추가요금으로 계산된다. "
           f"어떤 승객은 총 {fare:,}원을 지불했다. "
           "대기요금과 통행료는 없고, 주행 거리는 정수 km라고 한다. "
           "이 승객이 이동한 거리를 구하시오.")
        ans=distance;sol=f"{base}+{per}x={fare}. 따라서 x={distance}km.";params=(base,per,distance)
    elif family == "intersection":
        x=rng.randint(3,13); m1,m2=rng.sample([2,3,4,5,6],2);b1=rng.randint(1,15);b2=b1+(m1-m2)*x
        q=(f"두 직선 y={m1}x+{b1}, y={m2}x+({b2})가 좌표평면에 그려져 있다. "
           "두 직선의 교점에서는 같은 x값에 대한 y값이 같다. "
           "직선들은 서로 평행하지 않으며 교점은 정확히 하나 존재한다. "
           "교점의 x좌표를 구하시오.")
        ans=x;sol=f"{m1}x+{b1}={m2}x+({b2})를 풀면 x={x}.";params=(x,m1,m2,b1)
    elif family == "rectangle":
        w=rng.randint(5,15);h=w+rng.randint(3,12);area=w*h;gap=h-w
        q=(f"직사각형 모양의 정원에서 세로 길이는 가로 길이보다 {gap}m 길다. "
           f"정원의 넓이는 {area}m²이다. "
           "가로와 세로의 길이는 모두 양수이고, 정원의 모양을 바꾸지 않는다고 한다. "
           "이 조건을 만족하는 정원의 가로 길이를 구하시오.")
        ans=w;sol=f"가로 x, 세로 x+{gap}. x(x+{gap})={area}을 인수분해하고 양수 해를 택하면 x={w}.";params=(w,h)
    elif family == "factor_roots":
        a,b=rng.sample(range(2,15),2);s=a+b;prod=a*b
        q=(f"어떤 이차식의 최고차항 계수는 1이고, 일차항의 계수는 -{s}, 상수항은 {prod}이다. "
           "이 식은 두 개의 서로 다른 자연수 일차식의 곱으로 인수분해할 수 있다. "
           "이 이차식을 0으로 놓아 얻는 방정식의 두 근은 모두 양의 정수이다. "
           "두 근 중 큰 값을 구하시오.")
        ans=max(a,b);sol=f"x²-{s}x+{prod}=(x-{a})(x-{b}). 두 근 중 큰 값은 {ans}.";params=(a,b)
    elif family == "consecutive":
        n=rng.randint(9,30);target=n*(n+1)
        q=(f"서로 연속하는 두 양의 정수가 있다. "
           f"두 수의 곱은 {target}이고, 두 수 모두 1보다 크다. "
           "작은 수를 x로 놓으면 큰 수는 x+1로 나타낼 수 있다. "
           "두 수 중 큰 수를 구하시오.")
        ans=n+1;sol=f"x(x+1)={target}. 인수분해하면 양의 정수 x={n}, 큰 수는 {n+1}.";params=(n,)
    elif family == "probability":
        red=rng.randint(5,14);blue=rng.randint(4,12)
        if level==1:
            ans=R(red,red+blue);condition="공을 한 개 무작위로 꺼낸다";sol=f"전체 {red+blue}개 중 빨간 공 {red}개. 확률 {ans}."
        else:
            ans=R(red*(red-1),(red+blue)*(red+blue-1));condition="공을 두 개 차례로 꺼내되 다시 넣지 않는다";sol=f"{red}/{red+blue}×{red-1}/{red+blue-1}={ans}."
        q=(f"상자에는 빨간 공 {red}개와 파란 공 {blue}개가 들어 있다. "
           f"각 공은 같은 확률로 선택되고, {condition}. "
           "모든 공은 크기와 무게가 같아 색 이외에는 구별되지 않는다. "
           f"{'빨간 공이 나올' if level==1 else '꺼낸 공 두 개가 모두 빨간색일'} 확률을 구하시오.")
        params=(red,blue,level)
    elif family == "conditional_bag":
        red=rng.randint(4,10);blue=rng.randint(4,10)
        ans=R(red*(red-1),(red+blue)*(red+blue-1))
        q=(f"주머니에 빨간 구슬 {red}개와 파란 구슬 {blue}개가 있다. "
           "서로 다른 구슬 두 개를 순서대로 뽑고, 뽑은 구슬은 다시 넣지 않는다. "
           "각 단계에서 남아 있는 구슬은 모두 같은 확률로 선택된다. "
           "첫 번째와 두 번째 구슬이 모두 빨간색일 확률을 구하시오.")
        sol=f"첫 번째 빨간색 확률 {red}/{red+blue}, 두 번째는 {red-1}/{red+blue-1}. 곱하면 {ans}.";params=(red,blue)
    elif family == "paths":
        w,h=rng.randint(4,8),rng.randint(4,8)
        px,py=rng.randint(1,w-1),rng.randint(1,h-1)
        ans=math.comb(px+py,px)*math.comb(w-px+h-py,w-px)
        q=(f"가로 {w}칸, 세로 {h}칸으로 이루어진 격자 모양의 길이 있다. "
           f"출발점은 (0,0), 도착점은 ({w},{h})이며, 매번 오른쪽 또는 위쪽으로만 한 칸씩 이동할 수 있다. "
           f"도중에 ({px},{py}) 지점을 반드시 지나야 하고, 같은 지점을 다시 방문할 수는 없다. "
           "출발점부터 도착점까지 가능한 최단 경로는 모두 몇 가지인가?")
        sol=f"중간점까지 {math.comb(px+py,px)}가지, 그 뒤 {math.comb(w-px+h-py,w-px)}가지. 곱하면 {ans}.";params=(w,h,px,py)
    elif family == "committee":
        girls=rng.randint(5,10);boys=rng.randint(5,10);size=3 if level<3 else 4
        ans=math.comb(girls+boys,size)-math.comb(boys,size)
        q=(f"한 동아리에는 여학생 {girls}명과 남학생 {boys}명이 있다. "
           f"이 중 서로 다른 {size}명을 뽑아 대표팀을 구성하려고 한다. "
           "대표팀에는 여학생이 적어도 한 명 포함되어야 하며, 뽑히는 순서는 고려하지 않는다. "
           "같은 학생을 두 번 뽑을 수 없을 때 대표팀 구성 방법은 모두 몇 가지인가?")
        sol=f"전체 {math.comb(girls+boys,size)}가지에서 남학생만 뽑는 {math.comb(boys,size)}가지를 빼면 {ans}.";params=(girls,boys,size)
    elif family == "inclusion":
        limit=rng.randint(140,350);a,b=rng.choice([(3,5),(4,7),(5,8),(7,9)])
        ans=limit-limit//a-limit//b+limit//math.lcm(a,b)
        q=(f"1부터 {limit}까지의 자연수가 각각 한 장씩 적힌 카드가 있다. "
           f"카드에 적힌 수가 {a}의 배수이면 제외하고, {b}의 배수여도 제외한다. "
           "두 조건에 모두 해당하는 카드는 중복하여 두 번 세지 않는다. "
           "남는 카드의 개수를 구하시오.")
        sol=f"{limit}-{limit//a}-{limit//b}+{limit//math.lcm(a,b)}={ans}.";params=(limit,a,b)
    elif family == "sequence_story":
        a=rng.randint(3,14);d=rng.randint(2,9);n=rng.randint(12,24)
        ans=a+(n-1)*d
        q=(f"한 공연장의 첫 번째 줄에는 의자가 {a}개 놓여 있다. "
           f"뒤쪽으로 한 줄 이동할 때마다 의자 수는 바로 앞줄보다 {d}개씩 많아진다. "
           f"이 규칙은 {n}번째 줄까지 변하지 않고, 모든 줄에 빈 공간 없이 의자가 놓인다. "
           f"{n}번째 줄의 의자 수를 구하시오.")
        sol=f"등차수열의 제{n}항은 {a}+({n}-1)×{d}={ans}.";params=(a,d,n)
    elif family == "sequence_sum":
        a=rng.randint(3,12);d=rng.randint(2,7);n=rng.randint(12,22)
        ans=n*(2*a+(n-1)*d)//2
        q=(f"한 계단식 공연장의 첫 줄에는 좌석이 {a}개 있다. "
           f"다음 줄부터는 바로 앞줄보다 좌석이 {d}개씩 늘어난다. "
           f"공연장은 모두 {n}줄이며 좌석 수의 증가 규칙은 마지막 줄까지 같다. "
           "모든 줄의 좌석 수를 합하면 몇 개인지 구하시오.")
        sol=f"등차수열 합 {n}×(2×{a}+({n}-1)×{d})/2={ans}.";params=(a,d,n)
    elif family == "sequence_reverse":
        a=rng.randint(3,12);d=rng.randint(2,7);n=rng.randint(12,23);last=a+(n-1)*d
        ans=a
        q=(f"한 수열은 각 항이 바로 앞 항보다 {d}씩 커지는 등차수열이다. "
           f"제{n}항의 값은 {last}이고, 모든 항은 정수이다. "
           "중간에 빠지거나 추가된 항은 없으며 증가 규칙은 처음부터 일정하다. "
           "이 수열의 첫째 항을 구하시오.")
        sol=f"첫째 항은 {last}-({n}-1)×{d}={a}.";params=(a,d,n)
    elif family == "remainder_poly":
        root=rng.randint(2,9);a=rng.randint(2,7);b=rng.randint(2,8);c=rng.randint(1,11)
        ans=a*root*root+b*root+c
        q=(f"다항식 P(x)={a}x²+{b}x+{c}가 있다. "
           f"이 다항식을 x-{root}로 나누었을 때 몫과 나머지를 생각한다. "
           "나머지는 x에 관계없는 상수이며, 다항식의 나눗셈 정리를 이용할 수 있다. "
           "이때 나머지를 구하시오.")
        sol=f"나머지정리에 따라 P({root})={a}×{root}²+{b}×{root}+{c}={ans}.";params=(root,a,b,c)
    elif family == "quadratic_vertex":
        h=rng.randint(2,8);k=rng.randint(3,19);a=rng.randint(1,4)
        ans=k
        q=(f"이차함수 y={a}(x-{h})²+{k}의 그래프를 생각하자. "
           "그래프는 위로 열린 포물선이고, 정의역은 모든 실수이다. "
           "꼭짓점은 그래프에서 가장 낮은 점이며, 함수값은 그 점에서 최소가 된다. "
           "이 함수의 최솟값을 구하시오.")
        sol=f"제곱항은 0 이상이고 x={h}에서 0이므로 최솟값은 {k}.";params=(h,k,a)
    elif family == "optimization":
        perimeter=rng.choice([24,32,40,48,60]);half=perimeter//2;ans=R(half*half,4)
        q=(f"길이가 모두 {perimeter}m인 울타리를 사용하여 직사각형 모양의 정원을 만들려고 한다. "
           "울타리는 직사각형의 네 변을 정확히 한 번씩 둘러싸며, 울타리의 길이는 남기지 않는다. "
           "가로 길이를 x라고 하면 세로 길이는 둘레 조건으로 정해진다. "
           "정원의 넓이가 최대가 될 때 그 넓이를 구하시오.")
        sol=f"가로 x, 세로 {half}-x이므로 넓이는 x({half}-x). 꼭짓점에서 최대 넓이는 {ans}m².";params=(perimeter,)
    elif family == "rate_integral":
        a=rng.randint(2,8);b=rng.randint(1,6);t=rng.randint(3,8)
        ans=R(a*t*t,2)+b*t
        q=(f"직선 위를 움직이는 물체의 속도가 시간 t초에서 v(t)={a}t+{b} (m/s)로 주어진다. "
           f"관찰은 t=0초부터 t={t}초까지 계속되며, 이 구간에서 속도는 항상 양수이다. "
           "속도의 시간에 대한 적분은 이동 거리를 나타낸다. "
           f"처음 {t}초 동안 물체가 이동한 거리를 구하시오.")
        sol=f"0부터 {t}까지 ({a}t+{b})를 적분하면 {a}×{t}²/2+{b}×{t}={ans}.";params=(a,b,t)
    elif family == "remainders":
        m,n=rng.choice([(5,7),(7,9),(8,11),(9,13)]);r1,r2=rng.randrange(m),rng.randrange(n)
        ans=next(i for i in range(1,m*n+1) if i%m==r1 and i%n==r2)
        q=(f"어떤 양의 정수 N을 {m}로 나누면 나머지가 {r1}이다. "
           f"같은 수 N을 {n}로 나누면 나머지가 {r2}이다. "
           "두 나눗셈에서 몫은 서로 달라도 되지만 N은 동일한 수여야 한다. "
           "이 조건을 동시에 만족하는 가장 작은 양의 정수 N을 구하시오.")
        sol=f"두 합동 조건을 차례로 대입하여 가장 작은 양의 정수 {ans}을 찾는다.";params=(m,n,r1,r2)
    elif family == "divisors":
        a,b=rng.randint(2,5),rng.randint(2,5);prime1,prime2=rng.sample([2,3,5,7],2)
        n=prime1**a*prime2**b;ans=(a+1)*(b+1)-2
        q=(f"자연수 N은 {prime1}^{a}×{prime2}^{b}로 소인수분해된다. "
           "N의 양의 약수는 서로 다른 양의 정수로 센다. "
           "그중 1과 N 자체는 제외하고 나머지 약수만 세려고 한다. "
           "조건을 만족하는 약수는 모두 몇 개인가?")
        sol=f"양의 약수 개수는 ({a}+1)({b}+1)개. 1과 N을 제외하면 {ans}개.";params=(prime1,prime2,a,b)
    else:  # square
        k=rng.randint(2,8);delta=rng.choice([45,63,105,135,165,195,231,315]);c=k*k+delta
        sols=[n for n in range(1,delta+1) if math.isqrt(n*n+2*k*n+c)**2==n*n+2*k*n+c]
        if not sols: raise ValueError("해가 없는 조건입니다.")
        ans=sum(sols)
        q=(f"양의 정수 n에 대하여 n²+{2*k}n+{c}가 완전제곱수가 된다고 한다. "
           "완전제곱수는 어떤 정수의 제곱으로 나타낼 수 있는 수를 뜻한다. "
           "n은 1 이상의 정수이며, 조건을 만족하는 서로 다른 n은 모두 포함한다. "
           "가능한 모든 n의 합을 구하시오.")
        sol=f"(n+{k})²+{delta}=m²에서 합차공식을 이용한다. 가능한 n은 {', '.join(map(str,sols))}, 합은 {ans}.";params=(k,delta)
    signature=hashlib.sha256(json.dumps([grade,topic,difficulty,family,params],ensure_ascii=False).encode()).hexdigest()
    return {"question":q,"answer":[R(ans)],"explanation":sol,"signature":signature,
            "family":family,"grade":grade,"topic":topic,"difficulty":difficulty,
            "source_label":None,"source_url":None}

# 원문 확인: 2024 AIME I, MAA 기출 (개인 학습용 한국어 재서술)
# https://live.poshenloh.com/past-contests/aime/2024I
AIME_KOREAN = [
    {"year":2024,"exam":"AIME I","number":1,"level":"보통","min_grade":2,
     "question":"아야는 매일 9 km를 걷고 카페에서 잠시 쉰다. 걷는 속도가 시속 s km이면 카페에 머문 t분을 포함해 총 4시간이 걸린다. 시속 (s+2) km로 걸으면 같은 t분을 포함해 2시간 24분이 걸린다. 시속 (s+1/2) km로 걸을 때 카페 시간을 포함한 전체 소요 시간은 몇 분인가?",
     "answer":204,"hint":"전체 시간에서 카페에 머문 시간을 빼서 두 식을 세워 보세요.",
     "explanation":"9/s+t/60=4, 9/(s+2)+t/60=12/5. 빼면 s=5/2, t=24. 새로운 속도는 시속 3 km이므로 9/3시간+24분=204분."},
    {"year":2024,"exam":"AIME I","number":2,"level":"어려움","min_grade":4,
     "question":"1보다 큰 실수 x, y가 log_x(y^x)=10, log_y(x^(4y))=10을 만족한다. xy의 값을 구하시오.",
     "answer":25,"hint":"로그의 지수를 앞으로 내리고, 밑을 서로 바꾼 두 로그의 곱을 생각하세요.",
     "explanation":"x·log_x(y)=10, 4y·log_y(x)=10. 두 식을 곱하면 4xy·log_x(y)·log_y(x)=100. 로그의 곱은 1이므로 xy=25."},
    {"year":2024,"exam":"AIME I","number":3,"level":"어려움","min_grade":2,
     "question":"앨리스와 밥이 돌 n개를 놓고 번갈아 가져간다. 앨리스가 먼저 시작하며, 한 차례에 돌을 1개 또는 4개 가져갈 수 있다. 마지막 돌을 가져가는 사람이 이긴다. 1≤n≤2024인 자연수 n 중 밥이 앨리스의 모든 선택에 대응하여 반드시 이길 수 있는 n의 개수를 구하시오. (두 사람 모두 최선의 수를 둔다.)",
     "answer":809,"hint":"작은 n부터 먼저 두는 사람이 불리한 경우를 적어 보고 주기를 찾으세요.",
     "explanation":"패배 위치는 n≡0 또는 2 (mod 5)이다. 1부터 2024까지 5개씩 묶으면 404묶음에서 808개, 남은 2021~2024 중 2022가 하나 더 있으므로 809개."},
    {"year":2024,"exam":"AIME I","number":4,"level":"보통","min_grade":3,
     "question":"1부터 10까지의 정수 중 서로 다른 4개를 고르는 복권이 있다. 내가 고른 4개 중 적어도 2개가 추첨된 4개와 일치하면 당첨이고, 4개 모두 일치하면 최고 당첨이다. 당첨되었다는 조건 아래 최고 당첨일 조건부확률을 기약분수 m/n으로 쓸 때 m+n을 구하시오.",
     "answer":116,"hint":"내가 고른 4개와 정확히 2개, 3개, 4개 일치하는 추첨 결과를 각각 세어 보세요.",
     "explanation":"당첨 결과의 수는 C(4,2)C(6,2)+C(4,3)C(6,1)+1=90+24+1=115. 최고 당첨은 1가지이므로 확률은 1/115, 답은 116."},
    {"year":2024,"exam":"AIME I","number":7,"level":"어려움","min_grade":5,
     "question":"복소수 z의 절댓값이 4일 때, (75+117i)z+(96+144i)/z 의 실수부가 가질 수 있는 최댓값을 구하시오. (i²=-1)",
     "answer":540,"hint":"z=4(cos θ+i sin θ)로 놓고 실수부를 삼각함수의 일차결합으로 나타내세요.",
     "explanation":"z=4(cos θ+i sin θ)이면 실수부는 324 cos θ−432 sin θ이다. 최댓값은 √(324²+432²)=540."},
    {"year":2024,"exam":"AIME I","number":6,"level":"어려움","min_grade":3,
     "question":"8×8 정사각 격자에서 왼쪽 아래 꼭짓점에서 오른쪽 위 꼭짓점까지, 격자선을 따라 오른쪽 또는 위쪽으로만 이동한다. 방향을 정확히 4번 바꾸는 최단 경로는 모두 몇 개인가?",
     "answer":294,"hint":"연속해서 같은 방향으로 가는 구간을 다섯 개로 나누어 생각하세요.",
     "explanation":"오른쪽부터 시작하면 오른쪽 구간 3개에 양의 정수 길이 8을 배분하는 방법 C(7,2)=21, 위쪽 구간 2개는 C(7,1)=7. 시작 방향이 2가지이므로 2×21×7=294."},
]


# 추가 기출: 원문과 정답을 대조한 AIME I (한국어 개인 학습용 재서술)
AIME_KOREAN.extend([
    {"year":2022,"exam":"AIME I","number":1,"level":"보통","min_grade":4,
     "question":"이차다항식 P(x), Q(x)의 최고차항 계수는 각각 2, -2이다. 두 그래프는 (16,54)와 (20,53)을 모두 지난다. P(0)+Q(0)을 구하시오.","answer":116,
     "hint":"P(x)+Q(x)는 일차식입니다.","explanation":"R=P+Q라 하면 R(16)=108, R(20)=106이고 기울기는 -1/2이다. R(0)=108+8=116."},
    {"year":2022,"exam":"AIME I","number":2,"level":"어려움","min_grade":2,
     "question":"십진법 세 자리 수 abc를 9진법으로 쓰면 bca가 된다. a,b,c는 0부터 8까지의 숫자이고 두 표현 모두 세 자리 수이다. 이 십진법 수를 구하시오.","answer":227,
     "hint":"100a+10b+c=81b+9c+a를 정리하세요.","explanation":"99a=71b+8c와 숫자 범위를 만족하는 해는 (a,b,c)=(2,2,7)이다. 227=272(9진법)."},
    {"year":2022,"exam":"AIME I","number":3,"level":"어려움","min_grade":4,
     "question":"등변사다리꼴 ABCD에서 AB∥CD, AB=500, CD=650, AD=BC=333이다. ∠A와 ∠D의 이등분선 교점을 P, ∠B와 ∠C의 이등분선 교점을 Q라 한다. PQ의 길이를 구하시오.","answer":242,
     "hint":"D=(0,0), C=(650,0)으로 놓고 이등분선이 만드는 이등변삼각형을 이용하세요.","explanation":"A=(75,h), B=(575,h). D에서 333 떨어진 윗변 점 A'=(333,0), C에서 333 떨어진 B'=(317,0). P=(204,h/2), Q=(446,h/2), 따라서 PQ=242."},
    {"year":2022,"exam":"AIME I","number":4,"level":"어려움","min_grade":6,
     "question":"복소수 w=(√3+i)/2, z=(-1+i√3)/2이다. 1≤r,s≤100인 양의 정수 순서쌍 (r,s) 중 i·w^r=z^s를 만족하는 개수를 구하시오. (i²=-1)","answer":834,
     "hint":"복소평면에서 편각을 비교하세요.","explanation":"편각 조건은 r+3≡4s (mod 12). s를 3으로 나눈 나머지별로 세면 34×9+33×8+33×8=834."},
    {"year":2023,"exam":"AIME I","number":1,"level":"보통","min_grade":3,
     "question":"남자 5명과 여자 9명이 원 위의 서로 같은 간격인 14개 자리에 무작위로 선다. 모든 남자의 정반대 자리에 여자가 있을 확률을 기약분수 m/n이라 할 때 m+n을 구하시오.","answer":191,
     "hint":"정반대 자리 7쌍 중 남자가 있는 5쌍을 고릅니다.","explanation":"유리한 남자 자리 선택은 C(7,5)·2⁵=672, 전체는 C(14,5)=2002. 확률 48/143이므로 191."},
    {"year":2023,"exam":"AIME I","number":2,"level":"어려움","min_grade":5,
     "question":"양의 실수 b≠1과 n이 √(log_b n)=log_b(√n), b·log_b n=log_b(bn)을 만족한다. n=j/k를 기약분수로 쓸 때 j+k를 구하시오.","answer":881,
     "hint":"x=log_b n으로 놓고 먼저 x를 구하세요.","explanation":"√x=x/2이므로 x=0 또는 4. 둘째 식에서 x=0은 불가능하며 4b=5. n=(5/4)^4=625/256, 합은 881."},
    {"year":2023,"exam":"AIME I","number":3,"level":"보통","min_grade":3,
     "question":"평면 위에 서로 평행한 두 직선이 없는 직선 40개가 있다. 정확히 3개 직선이 만나는 점 3개, 4개 직선이 만나는 점 4개, 5개 직선이 만나는 점 5개, 6개 직선이 만나는 점 6개가 있고, 7개 이상 만나는 점은 없다. 정확히 두 직선만 만나는 점의 수를 구하시오.","answer":607,
     "hint":"직선 두 개를 고르는 C(40,2)개 쌍을 중복 없이 세세요.","explanation":"C(40,2)-3C(3,2)-4C(4,2)-5C(5,2)-6C(6,2)=780-173=607."},
    {"year":2023,"exam":"AIME I","number":4,"level":"어려움","min_grade":4,
     "question":"13!/m이 완전제곱수가 되는 양의 정수 m을 모두 더한 수를 2^a·3^b·5^c·7^d·11^e·13^f라 쓸 때 a+b+c+d+e+f를 구하시오.","answer":12,
     "hint":"13!을 소인수분해하고, 각 지수의 짝홀성을 이용하세요.","explanation":"13!=2¹⁰·3⁵·5²·7·11·13. 가능한 m의 합은 (1+4+⋯+1024)(3+27+243)(1+25)·7·11·13=2¹·3²·5¹·7³·11¹·13⁴. 합은 12."},
    {"year":2023,"exam":"AIME I","number":5,"level":"어려움","min_grade":5,
     "question":"정사각형 ABCD의 외접원 위 점 P가 PA·PC=56, PB·PD=90을 만족한다. 정사각형 ABCD의 넓이를 구하시오.","answer":106,
     "hint":"외접원 반지름을 R, P의 중심각을 θ로 놓고 두 곱을 표현하세요.","explanation":"PA·PC=2R²|sinθ|, PB·PD=2R²|cosθ|. 따라서 (2R²)²=56²+90²=106²이고 정사각형 넓이는 2R²=106."},
])


# 추가 검증 기출: 2024 AIME I, 원문/정답/풀이 확인
AIME_KOREAN.extend([
    {"year":2024,"exam":"AIME I","number":9,"level":"어려움","min_grade":5,
     "question":"쌍곡선 x²/20−y²/24=1 위의 네 점 A,B,C,D가 마름모를 이루며, 두 대각선의 교점은 원점이다. 모든 이러한 마름모에 대해 BD²보다 항상 작은 실수 중 최댓값을 구하시오.",
     "answer":480,"hint":"대각선은 서로 수직이다. B=(x,mx)로 놓고 두 대각선 모두 쌍곡선과 만나는 기울기의 범위를 찾으세요.",
     "explanation":"BD²=480(1+m²)/(6−5m²). 수직인 다른 대각선도 쌍곡선과 만나려면 5/6<m²<6/5이다. 식은 m²에 대해 증가하며 하한은 480(달성되지 않음)이므로 답은 480."},
])

def calibrated_math_problem(grade, topic, difficulty, rng):
    """쉬움/어려움이 수치만 바뀐 동일 유형이 되지 않도록 별도 유형 사용."""
    R = Rational
    a = rng.randint(2, 8)
    b = rng.randint(2, 7)
    if difficulty == "쉬움":
        if topic == "집합과 명제":
            q=f"A={{1, 2, ..., {a+4}}}, B={{1, 2, ..., {a}}}일 때 집합 A∩B의 원소 개수를 구하시오."
            ans=a; sol=f"B가 A에 포함되므로 A∩B=B이고 원소 수는 {a}개."; family="easy_set_subset"
        elif topic == "행렬":
            q=f"행렬 A=[[{a}, 1], [2, {b}]]의 대각합(대각 성분의 합)을 구하시오."
            ans=a+b; sol=f"대각합은 {a}+{b}={ans}."; family="easy_matrix_trace"
        elif topic == "도형의 방정식":
            q=f"두 점 A(0,0), B({a},0) 사이의 거리를 구하시오."
            ans=a; sol=f"두 점은 x축 위에 있으므로 거리는 {a}."; family="easy_distance"
        elif topic == "함수와 그래프":
            q=f"함수 f(x)={a}x+{b}에서 f(0)의 값을 구하시오."
            ans=b; sol=f"x=0을 대입하면 f(0)={b}."; family="easy_function_eval"
        else:
            return None
    elif difficulty == "어려움":
        if topic == "집합과 명제":
            n=rng.randint(30,65); m=rng.randint(2,4); k=rng.randint(3,5)
            import math as _math
            count=n//m+n//k-n//_math.lcm(m,k)
            q=f"전체집합 U={{1,2,...,{n}}}에서 A는 {m}의 배수들의 집합, B는 {k}의 배수들의 집합이다. (A∪B)의 원소 개수를 구하시오."
            ans=count; sol=f"포함배제: ⌊{n}/{m}⌋+⌊{n}/{k}⌋−⌊{n}/{_math.lcm(m,k)}⌋={count}."; family="hard_set_inclusion_exclusion"
        elif topic == "행렬":
            q=f"A=[[{a}, 1], [1, {b}]], B=[[{b}, 1], [1, {a}]]일 때 AB−BA의 (1,2) 성분을 구하시오."
            ans=2*(a-b); sol=f"AB의 (1,2) 성분은 {a}+{a}=2×{a}, BA의 (1,2) 성분은 {b}+{b}=2×{b}; 차는 {ans}."; family="hard_matrix_commutator"
        elif topic == "도형의 방정식":
            r=rng.randint(3,10); d=rng.randint(1,r-1)
            q=f"원 x²+y²={r*r}와 직선 y={d}가 만나는 서로 다른 두 점을 P,Q라 한다. 선분 PQ의 길이의 제곱을 구하시오."
            ans=4*(r*r-d*d); sol=f"교점의 x좌표는 ±√({r*r}−{d*d}). 현 길이의 제곱은 4({r*r}−{d*d})={ans}."; family="hard_circle_chord"
        elif topic == "함수와 그래프":
            q=f"함수 f(x)=({a}x+1)/(x+{b})의 역함수 g(x)가 존재한다. g({a+1})의 값을 구하시오. (단, {a*b}≠1)"
            ans=(1-(a+1)*b); den=(a+1)-a
            sol=f"y=({a}x+1)/(x+{b})에서 x=(1−{b}y)/(y−{a}). y={a+1}을 대입하면 {ans}."; family="hard_rational_inverse"
        else:
            return None
    else:
        return None
    signature=hashlib.sha256(f"calibrated36|{grade}|{topic}|{difficulty}|{q}".encode()).hexdigest()
    return {"question":q,"answer":[R(ans)],"explanation":sol,"signature":signature,
            "family":family,"grade":grade,"topic":topic,"difficulty":difficulty,
            "source_label":None,"source_url":None}

def aime_real_problem(grade, difficulty, rng, recent_families=()):
    grade_num = GRADES.index(grade)+1
    candidates = [p for p in AIME_KOREAN if p["min_grade"] <= grade_num]
    if difficulty == "쉬움":
        candidates = [p for p in candidates if p["number"] == 1 and p["level"] == "보통"] or candidates
    elif difficulty == "보통":
        candidates = [p for p in candidates if p["level"] == "보통" and p["number"] != 1] or candidates
    else:
        candidates = [p for p in candidates if p["level"] == "어려움"] or candidates
    candidates = [p for p in candidates if f"aime_{p['year']}_{p['number']}" not in recent_families] or candidates
    item = rng.choice(candidates)
    family = f"aime_{item['year']}_{item['number']}"
    sig = hashlib.sha256(f"AIME-I-{item['year']}-{item['number']}".encode()).hexdigest()
    return {"question":item["question"],"answer":[Rational(item["answer"])],
            "explanation":item["explanation"],"signature":sig,"family":family,
            "grade":grade,"topic":"수학올림피아드","difficulty":difficulty,
            "source_label":f"실제 기출 · {item['year']} AIME I {item['number']}번 (한국어 재서술)",
            "source_url":f"https://live.poshenloh.com/past-contests/aime/{item['year']}I",
            "hint":item["hint"]}


# 고정 60문항: 검증 기출 16 + 출처를 분명히 표시한 자체 제작 44.
# 실제 기출이라고 허위 표시하지 않는다.
def build_sixty_pool():
    import random as _random
    r = _random.Random(37060)
    pool = {g: [] for g in GRADES}
    for item in AIME_KOREAN:
        allowed = GRADES[item["min_grade"]-1:]
        # 학년별 수를 균형 있게 배치하되 선행학습 권장 학년 준수
        g = min(allowed, key=lambda x: (len(pool[x]), -GRADES.index(x)))
        pool[g].append(dict(item, kind="real", grade=g))
    for g in GRADES:
        gi=GRADES.index(g)
        needed=10-len(pool[g])
        for j in range(needed):
            a=4+gi*2+j
            b=2+(j%5)
            kind=j%8
            if kind==0:
                q=f"1부터 {a*7}까지의 정수 중 {b}의 배수이면서 3의 배수가 아닌 수는 몇 개인가?"
                ans=a*7//b-a*7//math.lcm(b,3)
                sol=f"{b}의 배수 {a*7//b}개에서 {math.lcm(b,3)}의 배수 {a*7//math.lcm(b,3)}개를 빼면 {ans}개."
                hint="포함배제 원리를 적용해 보세요."
            elif kind==1:
                q=f"가로 {a+3}cm, 세로 {b+4}cm인 직사각형의 네 변을 따라 안쪽으로 폭 1cm의 테두리를 만든다. 테두리 넓이는 몇 cm²인가?"
                ans=(a+3)*(b+4)-(a+1)*(b+2)
                sol=f"전체 넓이에서 안쪽 직사각형 넓이를 빼면 {ans}."
                hint="안쪽 직사각형의 두 변은 각각 2cm씩 줄어듭니다."
            elif kind==2:
                q=f"서로 다른 {b+5}명 중 회장과 부회장을 각각 1명씩 뽑는다. 두 직책을 겸할 수 없을 때 방법의 수는?"
                ans=(b+5)*(b+4)
                sol=f"회장 {b+5}가지, 부회장 {b+4}가지로 {ans}가지."
                hint="직책을 구별하는 순서 있는 선택입니다."
            elif kind==3:
                q=f"첫째 항이 {a}, 공차가 {b}인 등차수열의 제{gi+8}항을 구하시오."
                ans=a+(gi+7)*b
                sol=f"a_n=a_1+(n−1)d={a}+{gi+7}×{b}={ans}."
                hint="등차수열의 일반항을 이용하세요."
            elif kind==4:
                q=f"서로 다른 두 주사위를 던져 나온 눈의 합이 {b+6}인 경우의 수를 구하시오."
                ans=sum(1 for x in range(1,7) for y in range(1,7) if x+y==b+6)
                sol=f"(첫째 주사위, 둘째 주사위)의 순서쌍을 세면 {ans}가지."
                hint="첫 번째 눈을 1부터 6까지 나누어 생각하세요."
            elif kind==5:
                q=f"양의 정수 x,y가 x+y={a+b}이고 x−y={a-b}일 때 xy를 구하시오."
                ans=a*b
                sol=f"두 식을 더하고 빼면 x={a}, y={b}. 따라서 xy={ans}."
                hint="두 연립방정식을 더하고 빼세요."
            elif kind==6:
                q=f"정사각형의 한 변을 {a}cm에서 {a+b}cm로 늘렸을 때 넓이가 몇 cm² 증가하는가?"
                ans=(a+b)**2-a*a
                sol=f"넓이의 차는 ({a+b})²−{a}²={ans}."
                hint="두 정사각형의 넓이를 각각 구하세요."
            else:
                q=f"{a}개의 서로 다른 물건을 {b}명에게 각각 최소 1개씩 주되, 물건을 받는 사람이 정확히 2명인 경우가 아니라 모든 사람이 적어도 1개 받는 조건은 사용하지 않는다. 대신 {a}개의 물건 중 서로 다른 2개를 골라 순서대로 놓는 방법의 수를 구하시오."
                ans=a*(a-1)
                sol=f"첫 물건 {a}가지, 둘째 물건 {a-1}가지로 {ans}가지."
                hint="첫 번째 선택 이후 남은 선택지를 세세요."
            pool[g].append({"kind":"original", "year":2026, "exam":"자체 제작", "number":j+1,
                            "question":q,"answer":ans,"hint":hint,"explanation":sol,
                            "level": ["쉬움","보통","어려움"][j%3]})
    assert sum(len(v) for v in pool.values()) == 60
    assert all(len(v)==10 for v in pool.values())
    return pool

SIXTY_POOL = build_sixty_pool()

def sixty_problem(grade, difficulty, rng, recent_families=()):
    items=SIXTY_POOL[grade]
    candidates=[x for x in items if x["level"]==difficulty] or items
    eligible=[x for x in candidates if f"pool_{grade}_{x['kind']}_{x['year']}_{x['number']}" not in recent_families] or candidates
    item=rng.choice(eligible)
    family=f"pool_{grade}_{item['kind']}_{item['year']}_{item['number']}"
    source=(f"실제 기출 · {item['year']} AIME I {item['number']}번 (한국어 재서술)"
            if item['kind']=="real" else "자체 제작 연습문제 · 실제 기출 아님")
    return {"question":item["question"],"answer":[Rational(item["answer"])],
            "explanation":item["explanation"],"signature":hashlib.sha256(family.encode()).hexdigest(),
            "family":family,"grade":grade,"topic":"수학올림피아드","difficulty":difficulty,
            "source_label":source,
            "source_url":(f"https://live.poshenloh.com/past-contests/aime/{item['year']}I" if item['kind']=="real" else None),
            "hint":item["hint"]}


def expanded_problem(grade, topic, difficulty, rng, avoid_families=()):
    """Additional independent structures for quadratic equations and polynomials."""
    import sympy as sp
    x=sp.Symbol('x'); a,b=rng.sample(range(2,9),2)
    if grade == '중3' and topic == '이차방정식':
        if difficulty == '쉬움':
            bank=[('root_positive',f'x² = {a*a}일 때 양수인 해를 구하시오.',a,f'양수인 해는 {a}이다.'),
                  ('root_factor',f'(x − {a})(x + {b}) = 0의 양수인 해를 구하시오.',a,f'두 인수 중 첫 번째가 0일 때 x={a}이다.')]
        elif difficulty == '보통':
            bank=[('root_sum',f'이차방정식 x² − {a+b}x + {a*b} = 0의 두 근의 합을 구하시오.',a+b,f'근과 계수의 관계로 합은 {a+b}이다.'),
                  ('root_shift',f'(x − {a})² = {b*b}의 두 근 중 큰 값을 구하시오.',a+b,f'x={a}±{b}이므로 큰 근은 {a+b}이다.')]
        else:
            bank=[('root_param',f'x² − {a+b}x + k = 0의 두 근이 자연수이고, 두 근의 차가 {abs(a-b)}일 때 k를 구하시오.',a*b,f'두 근의 합은 {a+b}, 차는 {abs(a-b)}이므로 두 근은 {min(a,b)}, {max(a,b)}이고 곱은 {a*b}이다.'),
                  ('root_recip',f'이차방정식 x² − {a+b}x + {a*b} = 0의 두 근을 α, β라 할 때, α² + β²의 값을 구하시오.',a*a+b*b,f'α+β={a+b}, αβ={a*b}이므로 α²+β²=(α+β)²−2αβ={a*a+b*b}이다.')]
    elif grade == '고1' and topic == '다항식':
        if difficulty == '쉬움':
            bank=[('poly_value',f'다항식 P(x)=x²+{a}x+{b}에서 P(0)의 값을 구하시오.',b,f'x=0을 대입하면 {b}이다.'),
                  ('poly_coeff',f'다항식 (x+{a})(x+{b})에서 x의 계수를 구하시오.',a+b,f'일차항은 ({a}+{b})x이다.')]
        elif difficulty == '보통':
            bank=[('poly_remainder',f'P(x)=x³+{a}x+{b}를 x−1로 나눈 나머지를 구하시오.',1+a+b,f'나머지정리에 따라 P(1)={1+a+b}이다.'),
                  ('poly_identity',f'(x+{a})³에서 x²의 계수를 구하시오.',3*a,f'이항 전개하면 x²의 계수는 3×{a}={3*a}이다.')]
        else:
            bank=[('poly_remainder_nested',f'다항식 P(x)를 (x−1)(x−2)로 나눈 나머지가 ax+b이다. P(1)={a+b}, P(2)={2*a+b}일 때 a+b의 값을 구하시오.',a+b,f'나머지정리로 연립하면 a={a}, b={b}이므로 합은 {a+b}이다.'),
                  ('poly_factor_remainder',f'삼차다항식 P(x)=x³+px²+qx+{a*b}가 x−1과 x−{a}로 나누어떨어진다. p+q의 값을 구하시오.',-1-a*b,f'P(1)=1+p+q+{a*b}=0이므로 p+q={-1-a*b}이다. 두 조건을 함께 만족하는 p,q가 존재한다.')]
    else:
        return None
    fresh=[item for item in bank if item[0] not in avoid_families]
    family,q,ans,sol=rng.choice(fresh or bank)
    sig=hashlib.sha256(f'expanded53|{grade}|{topic}|{difficulty}|{q}'.encode()).hexdigest()
    return {'question':q,'answer':[Rational(ans)],'explanation':sol,'signature':sig,'family':family,'grade':grade,'topic':topic,'difficulty':difficulty,'source_label':None,'source_url':None}

SUPERSCRIPT = str.maketrans('0123456789-+','⁰¹²³⁴⁵⁶⁷⁸⁹⁻⁺')
def math_display(text):
    """Convert plain-text powers and multiplication to readable Unicode for UI only."""
    text=str(text).replace('**','^')
    text=re.sub(r'\^([+-]?\d+)',lambda m:m.group(1).translate(SUPERSCRIPT),text)
    text=re.sub(r'\^\(([^()]+)\)',lambda m:'⁽'+m.group(1).translate(SUPERSCRIPT)+'⁾',text)
    text=text.replace('*','×').replace('$','')
    return text

def factor_mc_problem(grade, topic, difficulty, rng, avoid_families=()):
    """중3 인수분해: 기초/기존 심화/다단계 심화의 구조적으로 다른 문항."""
    import sympy as sp
    x=sp.Symbol("x")
    a,b=rng.sample(range(2,8),2)
    if difficulty == "쉬움":
        # 공식의 첫 적용 수준: 공통인수 묶기 / 두 일차식의 곱
        bank=[("easy_common", a*x+a*b, a*(x+b),
               [a*(x-b), (a+1)*(x+b), a*(x+b+1)],
               "공통인수를 먼저 찾아 묶는다."),
              ("easy_quadratic", (x+a)*(x+b), (x+a)*(x+b),
               [(x-a)*(x-b),(x+a)*(x-b),(x-a)*(x+b)],
               "합과 곱을 이용해 일차식 두 개로 인수분해한다.")]
    elif difficulty == "보통":
        t=x*x+a*x
        bank=[("medium_substitution", (t-b)*(t-a), (t-b)*(t-a),
               [(t+b)*(t+a),(t-b)*(t+a),(t+b)*(t-a)],
               "반복되는 식을 하나의 문자로 보고 인수분해한다."),
              ("medium_sophie", x**4+4*a**4,
               (x*x-2*a*x+2*a*a)*(x*x+2*a*x+2*a*a),
               [(x*x-2*a*x-2*a*a)*(x*x+2*a*x-2*a*a),
                (x*x-2*a*x+2*a*a)*(x*x+2*a*x-2*a*a),
                (x*x-4*a*x+2*a*a)*(x*x+4*a*x+2*a*a)],
               "완전제곱식을 만든 뒤 제곱의 차를 적용한다.")]
    else:
        # 여러 단계의 구조 인식: 합성 다항식의 Sophie Germain 항등식,
        # 혹은 4차 다항식의 대칭적 계수 비교.
        t=x*x+a*x+b
        u=x*x+a*x
        bank=[("hard_nested_sophie", t**4+4*b**4,
               (t*t-2*b*t+2*b*b)*(t*t+2*b*t+2*b*b),
               [(t*t-2*b*t-2*b*b)*(t*t+2*b*t-2*b*b),
                (t*t-2*b*t+2*b*b)*(t*t+2*b*t-2*b*b),
                (t*t-4*b*t+2*b*b)*(t*t+4*b*t+2*b*b)],
               "먼저 x에 대한 이차식을 하나의 문자로 치환하고, 숨은 완전제곱 구조를 만든다."),
              ("hard_double_substitution", (u*u-a*a)*(u*u-b*b),
               (u-a)*(u+a)*(u-b)*(u+b),
               [(u-a)*(u+a)*(u-b)*(u-b),
                (u-a)*(u-a)*(u-b)*(u+b),
                (u+a)*(u+a)*(u-b)*(u+b)],
               "공통 구조를 치환한 뒤 제곱의 차를 두 번 연속 적용한다.")]
    fresh=[v for v in bank if v[0] not in avoid_families]
    family,expression,correct,wrong,idea=rng.choice(fresh or bank)
    expression=sp.expand(expression)
    assert sp.expand(correct-expression)==0
    assert all(sp.expand(v-expression)!=0 for v in wrong)
    variants=[correct]+wrong
    rng.shuffle(variants)
    def pretty(v):
        return math_display(sp.sstr(v)).replace("×","·")
    choices=[pretty(v) for v in variants]
    # 식의 전개/인수분해가 동치인지 검산, 선택지 중 정답은 하나만.
    assert sum(sp.expand(v-expression)==0 for v in variants)==1
    answer=variants.index(correct)+1
    q="다음 식을 인수분해한 것으로 옳은 것은?\n\n"+pretty(expression)
    explanation=idea+" 정답 식은 "+pretty(correct)+" 이며, 전개하면 주어진 식과 일치한다."
    signature=hashlib.sha256(f"factor51|{difficulty}|{q}".encode()).hexdigest()
    return {"question":q,"answer":[Rational(answer)],"explanation":explanation,
            "signature":signature,"family":family,"grade":grade,"topic":topic,
            "difficulty":difficulty,"choices":choices,"answer_format":"multiple_choice",
            "source_label":None,"source_url":None}

def numeric_mc_options(p, rng):
    """수치형 정답에 대해서만 서로 다른 오답 3개를 생성한다."""
    if len(p.get("answer", [])) != 1:
        return p
    correct = Rational(p["answer"][0])
    distractors = []
    for delta in [1,-1,2,-2,3,-3,5,-5]:
        candidate = correct + delta
        if candidate != correct and candidate not in distractors:
            distractors.append(candidate)
        if len(distractors) == 3:
            break
    values = [correct] + distractors
    rng.shuffle(values)
    p["choices"] = [str(v) for v in values]
    p["answer"] = [Rational(values.index(correct)+1)]
    p["answer_format"] = "multiple_choice"
    p["explanation"] += f" (계산 결과: {correct})"
    return p


def foundation_problem(grade, topic, rng, avoid_families=()):
    """전 단원 기초 개념 확인: 복잡한 응용 없이 2개 이상 독립 유형 순환."""
    a=rng.randint(2,8); b=rng.randint(2,7)
    bank={
      "정수와 유리수": [("integer_add",f"{a} + {b}의 값을 구하시오.",a+b,"두 정수를 더한다."),("integer_sub",f"{a} − {b}의 값을 구하시오.",a-b,"앞의 수에서 뒤의 수를 뺀다.")],
      "일차방정식": [("linear_add",f"x + {a} = {a+b}일 때 x를 구하시오.",b,"양변에서 같은 수를 뺀다."),("linear_multiply",f"{a}x = {a*b}일 때 x를 구하시오.",b,"양변을 계수로 나눈다.")],
      "비와 비율": [("ratio_multiply",f"사과 {a}개의 가격이 {a*b*100}원이다. 1개의 가격은 몇 원인가?",b*100,"전체 가격을 개수로 나눈다."),("ratio_percent",f"{a*10}의 10%는 얼마인가?",a,"10%는 전체의 10분의 1이다.")],
      "연립방정식": [("system_sum",f"x+y={a+b}, x={a}일 때 y의 값을 구하시오.",b,"첫째 식에 x의 값을 대입한다."),("system_difference",f"x−y={a}, y={b}일 때 x의 값을 구하시오.",a+b,"둘째 식을 첫째 식에 대입한다.")],
      "일차함수": [("line_value",f"y={a}x+{b}에서 x=1일 때 y를 구하시오.",a+b,"x에 1을 대입한다."),("line_slope",f"일차함수 y={a}x+{b}의 기울기를 구하시오.",a,"x의 계수가 기울기이다.")],
      "확률": [("prob_coin", "공정한 동전을 한 번 던질 때 앞면이 나올 확률을 분수로 쓰시오.",Rational(1,2),"가능한 두 결과가 같은 확률이다."),("prob_die", "공정한 주사위를 한 번 던질 때 짝수가 나올 확률을 분수로 쓰시오.",Rational(1,2),"짝수는 2, 4, 6이다.")],
      "경우의 수": [("count_product",f"상의 {a}벌과 하의 {b}벌 중 각각 한 벌씩 고르는 방법은 몇 가지인가?",a*b,"곱의 법칙을 이용한다."),("count_sum",f"빨간 펜 {a}종과 파란 펜 {b}종 중 한 자루를 고르는 방법은 몇 가지인가?",a+b,"합의 법칙을 이용한다.")],
      "이차방정식": [("quad_positive",f"x²={a*a}의 양수인 해를 구하시오.",a,"양수인 제곱근을 찾는다."),("quad_factor",f"(x−{a})(x+{b})=0의 양수인 해를 구하시오.",a,"곱이 0이면 한 인수가 0이다.")],
      "다항식": [("poly_constant",f"P(x)=x²+{a}x+{b}일 때 P(0)을 구하시오.",b,"x에 0을 대입한다."),("poly_coefficient",f"다항식 {a}x²+{b}x+1에서 x의 계수를 구하시오.",b,"x가 한 번 곱해진 항의 계수이다.")],
      "방정식과 부등식": [("ineq_lower",f"x>{a}를 만족하는 가장 작은 자연수 x를 구하시오.",a+1,"a보다 큰 가장 작은 자연수를 찾는다."),("eq_square",f"x²={a*a}의 양수인 해를 구하시오.",a,"양수인 제곱근을 찾는다.")],
      "행렬": [("matrix_trace",f"행렬 A=[[{a},1],[2,{b}]]의 대각합을 구하시오.",a+b,"대각선의 두 성분을 더한다."),("matrix_entry",f"행렬 A=[[1,{a}],[{b},2]]의 (1,2) 성분을 구하시오.",a,"첫째 행 둘째 열을 확인한다.")],
      "도형의 방정식": [("point_distance",f"점 A(0,0)과 B({a},0) 사이의 거리를 구하시오.",a,"x축 위의 두 점 사이 거리이다."),("midpoint",f"점 A(0,0), B({2*a},0)의 중점의 x좌표를 구하시오.",a,"두 x좌표의 평균을 구한다.")],
      "집합과 명제": [("set_count",f"집합 A={{1,2,3,...,{a}}}의 원소 개수를 구하시오.",a,"1부터 a까지 센다."),("set_intersection",f"A={{1,2,...,{a}}}, B={{1,2,...,{a+b}}}일 때 A∩B의 원소 개수를 구하시오.",a,"A는 B의 부분집합이다.")],
      "함수와 그래프": [("function_zero",f"f(x)={a}x+{b}일 때 f(0)을 구하시오.",b,"x에 0을 대입한다."),("function_one",f"f(x)={a}x+{b}일 때 f(1)을 구하시오.",a+b,"x에 1을 대입한다.")],
      "수열": [("sequence_term",f"수열 {a}, {a+b}, {a+2*b}, ...의 셋째 항을 구하시오.",a+2*b,"같은 수를 계속 더한다."),("sequence_difference",f"등차수열 {a}, {a+b}, {a+2*b}, ...의 공차를 구하시오.",b,"이웃한 두 항의 차를 구한다.")],
      "확률과 통계": [("statistics_mean",f"두 수 {a}, {a+2*b}의 평균을 구하시오.",a+b,"두 수의 합을 2로 나눈다."),("statistics_range",f"자료 {a}, {a+b}, {a+2*b}의 범위를 구하시오.",2*b,"최댓값에서 최솟값을 뺀다.")],
      "함수": [("function_eval",f"f(x)=x²+{a}일 때 f(0)을 구하시오.",a,"x=0을 대입한다."),("function_eval_one",f"f(x)={a}x+{b}일 때 f(1)을 구하시오.",a+b,"x=1을 대입한다.")],
      "미적분 응용": [("derivative_power",f"f(x)=x²+{a}x일 때 f′(0)을 구하시오.",a,"먼저 미분한 뒤 0을 대입한다."),("integral_constant",f"0부터 {a}까지 상수함수 f(x)={b}의 정적분 값을 구하시오.",a*b,"가로와 세로를 곱한 직사각형 넓이이다.")],
      "미적분Ⅰ": [("derivative_linear",f"f(x)={a}x+{b}일 때 f′(1)을 구하시오.",a,"일차함수의 도함수는 상수이다."),("integral_linear",f"0부터 {a}까지 f(x)=2x의 정적분 값을 구하시오.",a*a,"삼각형의 넓이로 생각할 수 있다.")],
    }
    if topic not in bank: return None
    fresh=[v for v in bank[topic] if v[0] not in avoid_families]
    family,q,ans,sol=rng.choice(fresh or bank[topic])
    sig=hashlib.sha256(f"foundation54|{grade}|{topic}|{q}".encode()).hexdigest()
    return {"question":q,"answer":[Rational(ans)],"explanation":sol,"signature":sig,"family":family,
            "grade":grade,"topic":topic,"difficulty":"쉬움","source_label":None,"source_url":None}


def diversified_problem(grade, topic, difficulty, rng, avoid_families=()):
    """단원별 보통/어려움 독립 유형. 계산으로 검증 가능한 단답형 문항."""
    if difficulty not in ("보통", "어려움") or topic == "수학올림피아드":
        return None
    import sympy as sp
    from math import comb, factorial, lcm
    a,b,c = rng.sample(range(2,9),3)
    level = difficulty
    items=[]
    def add(family, q, answer, solution):
        items.append((family,q,sp.Rational(answer),solution))
    if topic == "정수와 유리수":
        if level == "보통":
            add("signed_brackets",f"({a} − {a+b}) × (−{c})의 값을 구하시오.",b*c,"괄호를 먼저 계산하고 부호를 확인한다.")
            add("fraction_ops",f"{a}/{b} + {c}/{b} − 1의 값을 기약분수로 구하시오.",sp.Rational(a+c-b,b),"통분한 뒤 분자를 정리한다.")
        else:
            add("signed_fraction_nested",f"({a}/{b} − {a+c}/{b}) ÷ (−{c}/{a})의 값을 구하시오.",sp.Rational(a,b),"괄호를 계산하고 나눗셈을 역수의 곱셈으로 바꾼다.")
            add("integer_sequence",f"연속한 세 정수의 합이 {3*a}이다. 세 정수의 제곱의 합을 구하시오.",3*a*a+2,"가운데 수를 중심으로 연속한 정수를 표현한다.")
    elif topic == "일차방정식":
        if level == "보통":
            add("linear_brackets",f"{a}(x−{b})={a*c}일 때 x를 구하시오.",b+c,"양변을 계수로 나누어 괄호를 정리한다.")
            add("linear_fraction",f"(x−{a})/{b}={c}일 때 x를 구하시오.",a+b*c,"분모를 없애고 이항한다.")
        else:
            add("linear_word",f"어떤 수의 {a}배에서 {b}를 빼면 그 수의 {a-1}배에 {c}를 더한 값과 같다. 어떤 수를 구하시오.",b+c,"어떤 수를 x로 놓고 두 표현을 같게 둔다.")
            add("linear_param",f"방정식 {a}(x−k)={a}x−{a*b}가 모든 실수 x에 대해 참일 때 k를 구하시오.",b,"항등식의 상수항을 비교한다.")
    elif topic == "비와 비율":
        if level == "보통":
            add("ratio_partition",f"전체 {a+b}개를 {a}:{b}로 나눌 때 더 많은 쪽은 몇 개인가?",max(a,b),"비의 전체 항 수로 나누어 배분한다.")
            add("discount",f"정가 {a*1000}원인 물건을 {b*10}% 할인하면 할인 금액은 몇 원인가?",a*b*100,"정가에 할인율을 곱한다.")
        else:
            add("ratio_change",f"두 수의 비가 {a}:{b}이고 합은 {a+b}이다. 두 수에 각각 {c}를 더했을 때 두 수의 곱을 구하시오.",(a+c)*(b+c),"처음 두 수를 비에 따라 구한 뒤 각각 더한다.")
            add("reverse_percent",f"어떤 가격을 20% 올린 결과가 {a*1200}원이다. 원래 가격은 몇 원인가?",a*1000,"인상 후 가격을 1.2로 나눈다.")
    elif topic == "연립방정식":
        if level == "보통":
            add("system_sumdiff",f"x+y={a+b}, x−y={a-b}일 때 x를 구하시오.",a,"두 식을 더해 x를 구한다.")
            add("system_substitution",f"2x+y={2*a+b}, x−y={a-b}일 때 y를 구하시오.",b,"두 식을 연립하여 x,y를 구한다.")
        else:
            add("system_word",f"연필 {a}자루와 공책 {b}권의 합계는 {a*300+b*700}원이다. 연필 한 자루가 300원일 때 공책 한 권은 몇 원인가?",700,"전체 금액에서 연필 값을 제외한다.")
            add("system_parameter",f"연립방정식 x+y={a+b}, {c}x+{c}y=k가 무수히 많은 해를 가질 때 k를 구하시오.",c*(a+b),"두 식이 서로 상수배여야 한다.")
    elif topic == "일차함수":
        if level == "보통":
            add("line_two_points",f"두 점 ({a},{b}), ({a+2},{b+2*c})를 지나는 직선의 기울기를 구하시오.",c,"y좌표 차를 x좌표 차로 나눈다.")
            add("line_intercept",f"기울기가 {a}이고 점 (1,{a+b})를 지나는 직선의 y절편을 구하시오.",b,"y=ax+k에 점을 대입한다.")
        else:
            add("line_intersection",f"두 직선 y={a}x+{b}, y=({a+1})x−{c}의 교점의 x좌표를 구하시오.",b+c,"두 직선의 y값이 같음을 이용한다.")
            add("line_parallel_area",f"직선 y={a}x+{b}와 평행하고 점 (0,{c})를 지나는 직선의 x절편을 구하시오.",-sp.Rational(c,a),"평행한 직선의 기울기는 같고 x절편에서는 y=0이다.")
    elif topic == "확률":
        if level == "보통":
            add("two_coins", "서로 독립인 공정한 동전 두 개를 던질 때 앞면이 정확히 한 번 나올 확률을 구하시오.",sp.Rational(1,2),"가능한 네 경우 중 조건을 만족하는 경우를 센다.")
            add("die_even_or_big",f"공정한 주사위 한 개를 던질 때 짝수 또는 {a%3+3} 이상이 나올 확률을 구하시오.",sp.Rational(len(set([2,4,6])|set(range(a%3+3,7))),6),"합집합에 해당하는 눈을 중복 없이 센다.")
        else:
            add("two_dice_sum",f"서로 독립인 공정한 주사위 두 개를 던질 때 눈의 합이 {a%5+6}일 확률을 구하시오.",sp.Rational(6-abs(7-(a%5+6)),36),"36개의 순서쌍 중 합이 맞는 경우를 센다.")
            add("without_replacement",f"빨간 공 {a}개와 파란 공 {b}개 중 두 개를 복원 없이 뽑을 때 모두 빨간 공일 확률을 구하시오.",sp.Rational(a*(a-1),(a+b)*(a+b-1)),"첫 번째와 두 번째 확률을 곱한다.")
    elif topic == "인수분해":
        return None # 기존 별도 인수분해 엔진 유지
    elif topic == "이차방정식":
        if level == "보통":
            add("quad_sum_roots",f"x²−{a+b}x+{a*b}=0의 두 근의 합을 구하시오.",a+b,"근과 계수의 관계를 사용한다.")
            add("quad_shift",f"(x−{a})²={b*b}의 두 근 중 큰 근을 구하시오.",a+b,"제곱근의 양·음 두 경우를 구한다.")
        else:
            add("quad_roots_squared",f"x²−{a+b}x+{a*b}=0의 두 근을 α,β라 할 때 α²+β²을 구하시오.",a*a+b*b,"근의 합과 곱으로 제곱합을 나타낸다.")
            add("quad_parameter_double",f"x²−2kx+{a*a}=0이 중근을 가지고 k가 양수일 때 k를 구하시오.",a,"판별식이 0이라는 조건을 쓴다.")
    elif topic == "경우의 수":
        if level == "보통":
            add("ordered_two",f"서로 다른 {a}명 중 회장과 부회장을 각각 한 명씩 뽑는 방법은 몇 가지인가?",a*(a-1),"역할이 달라 순서를 구분한다.")
            add("choose_two",f"서로 다른 {a}명 중 대표 2명을 뽑는 방법은 몇 가지인가?",comb(a,2),"순서를 구분하지 않는 조합이다.")
        else:
            add("adjacent_permutation",f"서로 다른 {a}명이 한 줄로 설 때 특정한 두 사람이 이웃하도록 서는 방법은 몇 가지인가?",2*factorial(a-1),"두 사람을 한 묶음으로 보고 내부 순서를 고려한다.")
            add("nonadjacent_permutation",f"서로 다른 {a}명이 한 줄로 설 때 특정한 두 사람이 이웃하지 않는 방법은 몇 가지인가?",factorial(a)-2*factorial(a-1),"전체 배열에서 이웃하는 배열을 뺀다.")
    elif topic == "다항식":
        if level == "보통":
            add("remainder_one",f"P(x)=x³+{a}x+{b}를 x−1로 나눈 나머지를 구하시오.",1+a+b,"나머지정리 P(1)을 사용한다.")
            add("coefficient_cube",f"(x+{a})³에서 x²의 계수를 구하시오.",3*a,"세제곱 전개에서 x² 항을 찾는다.")
        else:
            add("remainder_interpolation",f"P(x)를 (x−1)(x−2)로 나눈 나머지가 ax+b이다. P(1)={a+b}, P(2)={2*a+b}일 때 a−b를 구하시오.",a-b,"두 점에서 나머지식을 평가해 연립한다.")
            add("poly_identity",f"항등식 (x+{a})(x+{b})=x²+px+q에서 p²−4q의 값을 구하시오.",(a-b)**2,"p는 두 수의 합, q는 곱이다.")
    elif topic == "방정식과 부등식":
        if level == "보통":
            add("abs_eq",f"|x−{a}|={b}의 두 해의 합을 구하시오.",2*a,"절댓값을 양·음 두 경우로 나눈다.")
            add("quadratic_interval",f"(x−{a})(x−{b})<0을 만족하는 정수 x의 개수를 구하시오.",abs(a-b)-1,"두 근 사이의 정수를 센다.")
        else:
            add("abs_nested",f"|x−{a}|+|x−{a+b}|의 최솟값을 구하시오.",b,"두 점 사이 거리의 합의 최소를 생각한다.")
            add("quadratic_integer",f"(x−{a})(x−{b})≤0을 만족하는 정수 x의 개수를 구하시오.",abs(a-b)+1,"두 근을 포함한 구간의 정수를 센다.")
    elif topic == "행렬":
        if level == "보통":
            add("matrix_product_entry",f"A=[[{a},1],[0,{b}]], B=[[1,{c}],[1,0]]일 때 AB의 (1,2) 성분을 구하시오.",a*c,"첫째 행과 둘째 열의 내적이다.")
            add("matrix_square_entry",f"A=[[{a},1],[1,{b}]]일 때 A²의 (1,1) 성분을 구하시오.",a*a+1,"행렬을 자기 자신과 곱한다.")
        else:
            add("matrix_noncommute",f"A=[[{a},1],[1,{b}]], B=[[{b},1],[1,{a}]]일 때 AB−BA의 (1,2) 성분을 구하시오.",2*(a-b),"AB와 BA를 각각 계산해 비교한다.")
            add("matrix_power_triangular",f"A=[[1,{a}],[0,1]]일 때 A⁴의 (1,2) 성분을 구하시오.",4*a,"위삼각행렬의 거듭제곱 규칙을 찾는다.")
    elif topic == "도형의 방정식":
        if level == "보통":
            add("distance_square",f"두 점 (0,0), ({a},{b}) 사이 거리의 제곱을 구하시오.",a*a+b*b,"거리 공식의 제곱을 계산한다.")
            add("line_intercept",f"점 (0,{b})를 지나고 기울기가 {a}인 직선의 x절편을 구하시오.",-sp.Rational(b,a),"직선의 식에서 y=0을 대입한다.")
        else:
            add("circle_chord",f"원 x²+y²={a*a+b*b}와 직선 y={b}가 만나는 두 점 사이 거리의 제곱을 구하시오.",4*a*a,"원의 방정식에 y값을 대입해 두 교점을 찾는다.")
            add("circle_tangent",f"원 (x−{a})²+(y−{b})²={c*c}에 접하는 수평선 중 y좌표가 큰 직선의 y절편을 구하시오.",b+c,"중심의 y좌표에 반지름을 더한다.")
    elif topic == "집합과 명제":
        if level == "보통":
            add("set_inclusion",f"n(A)={a+b}, n(B)={b+c}, n(A∩B)={b}일 때 n(A∪B)를 구하시오.",a+b+c,"포함배제 공식을 적용한다.")
            add("set_complement",f"전체집합 U의 원소가 {a+b+c}개이고 n(A)={a+b}일 때 여집합 Aᶜ의 원소 개수를 구하시오.",c,"전체에서 A의 원소 수를 뺀다.")
        else:
            n=60+a
            add("set_multiples",f"1부터 {n}까지 자연수 중 2의 배수 또는 3의 배수인 수는 몇 개인가?",n//2+n//3-n//6,"2와 3의 배수를 세고 공통인 6의 배수를 뺀다.")
            add("set_three",f"n(A∪B)={a+b+c}, n(A−B)={a}, n(B−A)={c}일 때 n(A∩B)를 구하시오.",b,"합집합을 세 부분으로 나눈다.")
    elif topic == "함수와 그래프" or topic == "함수":
        if level == "보통":
            add("composition_linear",f"f(x)={a}x+{b}, g(x)=x+{c}일 때 f(g(1))을 구하시오.",a*(1+c)+b,"안쪽 함수부터 대입한다.")
            add("inverse_linear",f"f(x)={a}x+{b}일 때 f⁻¹({a*c+b})를 구하시오.",c,"원래 함수의 출력값에서 입력을 역으로 구한다.")
        else:
            add("composition_reverse",f"f(x)={a}x+{b}, g(x)={c}x−{b}일 때 f(g(x))=g(f(x))를 만족하는 x를 구하시오.",sp.Rational(b*(c+1-a),a*c-c*a) if False else sp.Rational(-b*(a+c-1),b*(a-c)) if a!=c else 0,"두 합성함수를 전개해 일차방정식을 푼다.") if False else None
            add("inverse_rational",f"f(x)=({a}x+1)/(x+{b})의 역함수 g에 대해 g({a+1})을 구하시오. (단, {a*b}≠1)",1-b*(a+1),"y=f(x)를 x에 대해 풀고 y를 대입한다.")
            add("quadratic_vertex",f"함수 f(x)=(x−{a})²+{b}에서 f(x)+f({a+c})의 최솟값을 구하시오.",b+c*c+b,"f(x)의 최솟값을 먼저 찾는다.")
    elif topic == "수열":
        if level == "보통":
            add("arithmetic_nth",f"첫째 항이 {a}, 공차가 {b}인 등차수열의 {c+4}번째 항을 구하시오.",a+(c+3)*b,"일반항 aₙ=a₁+(n−1)d를 사용한다.")
            add("geometric_nth",f"첫째 항이 {a}, 공비가 2인 등비수열의 제{b}항을 구하시오.",a*2**(b-1),"공비를 항 번호보다 한 번 적게 곱한다.")
        else:
            add("arithmetic_sum",f"첫째 항이 {a}, 공차가 {b}인 등차수열의 첫 {c+5}개 항의 합을 구하시오.",sp.Rational((c+5)*(2*a+(c+4)*b),2),"첫 항과 끝 항의 평균에 항 수를 곱한다.")
            add("arithmetic_inverse",f"등차수열에서 제3항이 {a+2*b}, 제7항이 {a+6*b}일 때 제10항을 구하시오.",a+9*b,"두 항의 차로 공차를 구한 뒤 일반항을 찾는다.")
    elif topic == "확률과 통계":
        if level == "보통":
            add("weighted_mean",f"평균이 {a}인 자료 {b}개와 평균이 {c}인 자료 {a}개를 합친 평균을 구하시오.",sp.Rational(a*b+c*a,a+b),"두 집단의 총합을 합친 뒤 전체 개수로 나눈다.")
            add("combination",f"서로 다른 {a}명 중 {min(3,a-1)}명을 선택하는 방법은 몇 가지인가?",comb(a,min(3,a-1)),"순서 없는 선택의 경우의 수이다.")
        else:
            add("conditional_prob",f"1부터 {a*b}까지의 자연수 중 균등하게 하나를 뽑았다. 짝수라는 조건에서 {a}의 배수일 확률을 구하시오.",sp.Rational((a*b)//lcm(2,a),(a*b)//2),"짝수인 경우만 표본공간으로 삼는다.")
            add("variance_shift",f"자료 {a}, {a+b}, {a+2*b}의 분산(편차 제곱의 평균)을 구하시오.",sp.Rational(2*b*b,3),"평균을 구한 뒤 편차 제곱을 평균낸다.")
    elif topic == "미적분 응용" or topic == "미적분Ⅰ":
        if level == "보통":
            add("derivative_at",f"f(x)=x³+{a}x²+{b}x일 때 f′(1)의 값을 구하시오.",3+2*a+b,"도함수를 구한 뒤 x=1을 대입한다.")
            add("definite_integral",f"0부터 {a}까지 함수 f(x)=2x+{b}의 정적분 값을 구하시오.",a*a+a*b,"부정적분을 구한 뒤 구간 끝값을 대입한다.")
        else:
            add("tangent_slope",f"곡선 y=x³−{a}x²+{b}x에서 x={a}인 점의 접선의 기울기를 구하시오.",a*a+b,"미분계수를 계산한다.")
            add("integral_area",f"곡선 y=x({a}−x)와 x축이 둘러싸는 영역의 넓이를 구하시오.",sp.Rational(a**3,6),"0부터 a까지 양수인 함수의 정적분을 계산한다.")
    if not items:
        return None
    available=[v for v in items if v[0] not in avoid_families]
    family,q,ans,sol=rng.choice(available or items)
    signature=hashlib.sha256(json.dumps(["v55",grade,topic,level,family,q],ensure_ascii=False).encode()).hexdigest()
    return {"question":q,"answer":[Rational(ans)],"explanation":sol,"signature":signature,
            "family":"v55_"+family,"grade":grade,"topic":topic,"difficulty":difficulty,
            "source_label":None,"source_url":None}

"""Hard reasoning templates. Constructed numerical answers, offline, no API."""
import hashlib, random
from fractions import Fraction

def generate_hard_v56(grade,topic,rng,avoid=()):
    a,b,c=rng.sample(range(3,10),3)
    items=[]
    def add(tag,q,ans,why):
        items.append((tag,q,Fraction(ans),why))
    # All questions are solvable with a unique rational/integer answer.
    if topic=='정수와 유리수':
        add('error_audit',f'어떤 학생이 −{a}−(−{b})를 −{a+b}라고 계산했다. 학생의 계산값에서 올바른 계산값을 뺀 수는?',-2*b,'괄호 앞의 뺄셈은 부호를 바꿔 더해야 한다.')
        add('elevator',f'지하 {a}층에서 {b}층 올라가고 다시 {c}층 내려갔다. 현재 층 번호는? (지하는 음수)',-a+b-c,'지하 층을 음수로 놓고 이동을 부호 있는 수로 계산한다.')
        add('hidden_integer',f'서로 연속한 홀수 세 개의 합이 {3*(2*a+1)}이다. 가장 큰 홀수는?',2*a+3,'가운데 홀수는 합의 1/3이다.')
        add('fraction_reverse',f'어떤 수에 {a}/{b}를 더한 뒤 {b}/{a}를 곱했더니 {c}가 되었다. 원래 수는?',Fraction(c*a,b)-Fraction(a,b),'마지막 연산부터 역순으로 되돌린다.')
    elif topic=='일차방정식':
        add('rectangle_perimeter',f'직사각형의 가로는 세로보다 {a}cm 길다. 둘레가 {4*b+2*a}cm일 때 세로는 몇 cm인가?',b,'세로를 x로 두면 2(x+x+a)=둘레이다.')
        add('wrong_sign',f'{a}x+{b}={a*c+b}를 풀면서 {b}를 이항할 때 부호를 바꾸지 않아 x={Fraction(a*c+2*b,a)}라고 답했다. 올바른 해는?',c,'상수항을 반대편으로 옮길 때 부호가 바뀐다.')
        add('age_reverse',f'현재 두 사람의 나이 차이는 {a}세다. {b}년 후 나이의 합이 {2*c+a+2*b}세라면 현재 어린 사람의 나이는?',c,'현재 어린 사람을 x로 두고 두 사람의 미래 나이 합을 표현한다.')
        add('price_model',f'입장료는 기본 {a*1000}원에 놀이기구 1회당 {b*100}원이 추가된다. 총 {a*1000+b*100*c}원을 냈다면 몇 회 탔는가?',c,'총액에서 기본요금을 먼저 제외한다.')
    elif topic=='비와 비율':
        add('mixing',f'농도 {a*5}% 소금물 {b*100}g에 물 {c*100}g을 더했다. 새 소금물의 소금 질량은 몇 g인가?',a*5*b,'물을 더해도 소금의 질량은 변하지 않는다.')
        add('ratio_inverse',f'두 수의 비는 {a}:{b}이고 큰 수와 작은 수의 차가 {abs(a-b)*c}이다. 두 수의 합은?',(a+b)*c,'비의 한 단위가 c임을 차이에서 구한다.')
        add('successive_discount',f'{a*10000}원인 상품을 20% 할인한 뒤 다시 10% 할인했다. 최종 가격은 몇 원인가?',a*7200,'연속 할인율은 더하지 않고 각각 곱한다.')
        add('rectangle_scale',f'직사각형의 가로를 {a}배, 세로를 {b}배 하면 넓이는 원래의 몇 배인가?',a*b,'넓이는 가로와 세로의 곱이다.')
    elif topic=='연립방정식':
        add('ticket_model',f'성인표 {a}장과 학생표 {b}장의 합계가 {a*12000+b*7000}원이다. 성인표 1장이 학생표보다 5000원 비싸고 성인표와 학생표의 가격 합이 19000원일 때 성인표 가격은?',12000,'두 표 가격의 합과 차를 연립한다.')
        add('rectangle_system',f'직사각형의 둘레가 {2*(a+b)}cm이고 가로가 세로보다 {abs(a-b)}cm 길다. 넓이는 몇 cm²인가?',a*b,'가로와 세로의 합과 차를 연립한다.')
        add('system_reverse',f'x+y={a+b}, 2x−y={2*a-b}를 만족한다. 3x+2y의 값은?',3*a+2*b,'두 식으로 x와 y를 먼저 결정한다.')
        add('parameter_trap',f'x+y={a+b}, 2x+2y=k가 해를 갖지 않도록 하는 k의 값으로 {2*(a+b)+1}을 택했다. 이때 두 식의 좌변을 비교하면 k와 {2*(a+b)}의 차는?',1,'둘째 좌변은 첫째 좌변의 2배이므로 우변이 다르면 모순이다.')
    elif topic=='일차함수':
        add('taxi_intersection',f'A 요금은 기본 {a*1000}원에 km당 {b*100}원, B 요금은 기본 {(a+2)*1000}원에 km당 {(b-2)*100}원이다. 요금이 같아지는 이동 거리는 몇 km인가?',10,'두 요금을 일차식으로 세워 교점을 구한다.')
        add('triangle_area',f'직선 y={a}x+{a*b}와 두 좌표축으로 둘러싸인 삼각형의 넓이는?',Fraction(a*b*b,2),'두 절편의 절댓값을 구해 삼각형 넓이를 계산한다.')
        add('parallel_condition',f'점 (0,{b})를 지나는 직선이 y={a}x+1과 평행하다. 이 직선이 x={c}일 때의 y좌표는?',a*c+b,'평행한 직선은 기울기가 같다.')
        add('reverse_slope',f'일차함수 f(x)의 값이 x={a}에서 {b}, x={a+2}에서 {b+2*c}이다. f(0)의 값은?',b-a*c,'두 점으로 기울기와 절편을 역으로 구한다.')
    elif topic=='확률':
        add('complement',f'서로 다른 두 주사위를 던질 때 적어도 한 개에서 6이 나올 확률은?',Fraction(11,36),'둘 다 6이 아닌 여사건을 이용한다.')
        add('geometry_probability',f'가로 {a}cm, 세로 {b}cm인 직사각형에서 꼭짓점 하나를 기준으로 가로 {a}cm, 세로 {b}cm인 직각삼각형을 색칠했다. 내부에서 임의의 점을 고를 때 색칠된 부분에 속할 확률은?',Fraction(1,2),'넓이의 비로 확률을 구한다.')
        add('without_replacement',f'빨간 공 {a}개, 파란 공 {b}개에서 복원 없이 2개를 뽑을 때 서로 다른 색일 확률은?',Fraction(2*a*b,(a+b)*(a+b-1)),'빨강-파랑과 파랑-빨강을 모두 센다.')
        add('conditional_die',f'주사위 눈이 짝수임을 알고 있다. 이 눈이 3의 배수일 조건부확률은?',Fraction(1,3),'표본공간은 2, 4, 6 세 개다.')
    elif topic=='이차방정식':
        add('rectangle_roots',f'가로가 세로보다 {a}cm 길고 넓이가 {b*(a+b)}cm²인 직사각형의 세로는?',b,'x(x+a)=넓이로 이차방정식을 세운다.')
        add('root_shift',f'방정식 x²−{a+b}x+{a*b}=0의 두 근에 각각 {c}를 더했다. 새 두 근의 곱은?',(a+c)*(b+c),'원래 두 근을 인수분해로 찾는다.')
        add('discriminant',f'x²−2kx+{a*a}=0이 서로 다른 두 실근을 갖도록 하는 양의 정수 k의 최솟값은?',a+1,'판별식이 양수여야 한다.')
        add('vertex_reverse',f'x²−{2*a}x+k=0이 중근을 가질 때 k는?',a*a,'완전제곱식이 되도록 상수항을 정한다.')
    elif topic=='경우의 수':
        from math import factorial,comb
        add('geometry_routes',f'격자에서 오른쪽으로 {a}칸, 위로 {b}칸만 이동하여 목적지에 도착하는 최단 경로는 몇 가지인가?',comb(a+b,a),'이동 순서에서 오른쪽 이동 위치를 선택한다.')
        add('adjacent',f'서로 다른 {a}명 중 특정 두 사람이 반드시 이웃하도록 한 줄로 서는 경우의 수는?',2*factorial(a-1),'두 사람을 한 묶음으로 본다.')
        add('nonadjacent',f'서로 다른 {a}명 중 특정 두 사람이 이웃하지 않게 한 줄로 서는 경우의 수는?',factorial(a)-2*factorial(a-1),'전체에서 이웃하는 경우를 뺀다.')
        add('password',f'숫자 0,1,2,3,4로 중복 없이 세 자리 자연수를 만들 때 짝수인 수는 몇 개인가?',30,'일의 자리가 0,2,4인 경우를 나누고 백의 자리 0을 제외한다.')
    elif topic=='다항식':
        add('remainder_inverse',f'다항식 P(x)를 x−1로 나눈 나머지는 {a}, x−2로 나눈 나머지는 {b}이다. P(x)를 (x−1)(x−2)로 나눈 나머지 R(x)에 대하여 R(3)은?',2*b-a,'일차식 R(x)가 (1,a), (2,b)를 지난다.')
        add('area_polynomial',f'직사각형의 가로가 x+{a}, 세로가 x+{b}이다. 넓이 다항식에서 x의 계수는?',a+b,'넓이를 두 일차식의 곱으로 표현한다.')
        add('identity_parameter',f'(x+{a})(x+{b})=x²+px+q가 항등식일 때 p²−4q는?',(a-b)**2,'계수 비교로 p와 q를 결정한다.')
        add('factor_value',f'P(x)=x³−{a*a}x이고 x={b}일 때 P(x)의 값은?',b*(b-a)*(b+a),'공통인수와 제곱의 차를 활용한다.')
    elif topic=='방정식과 부등식':
        add('integer_boundary',f'(x−{a})(x−{a+b})<0을 만족하는 정수 x의 개수는?',b-1,'두 근 사이에 있는 정수만 센다. 끝점은 포함되지 않는다.')
        add('abs_geometry',f'수직선에서 두 점 {a}, {a+b}까지 거리의 합이 최소가 되는 모든 실수 x의 범위의 길이는?',b,'두 점 사이에서는 거리 합이 일정하다.')
        add('parameter_no_solution',f'|x−{a}|=k가 서로 다른 두 실근을 가지도록 하는 정수 k의 최솟값은?',1,'절댓값이 양수일 때 좌우 두 해가 있다.')
        add('reverse_interval',f'부등식 x²−{a+b}x+{a*b}≤0의 정수해는 모두 몇 개인가?',abs(a-b)+1,'두 근 사이의 양 끝을 포함한다.')
    elif topic=='행렬':
        add('noncommute',f'A=[[1,{a}],[0,1]], B=[[1,0],[{b},1]]일 때 AB−BA의 (1,1) 성분은?',a*b,'행렬 곱셈 순서에 따라 결과가 달라진다.')
        add('matrix_power',f'A=[[1,{a}],[0,1]]일 때 A의 {b}제곱의 (1,2) 성분은?',a*b,'위삼각행렬 거듭제곱에서 오른쪽 위 항이 누적된다.')
        add('matrix_inverse_equation',f'A=[[{a},0],[0,{b}]], AX=[[{a*c},0],[0,{b*c}]]일 때 X의 (1,1) 성분은?',c,'대각행렬의 각 행에 대응하는 계수를 비교한다.')
        add('matrix_word',f'두 상태를 나타내는 열벡터 v=({a},{b})에 변환 A=[[1,1],[0,1]]을 적용한다. 변환된 벡터의 첫째 성분은?',a+b,'첫 행과 열벡터를 곱한다.')
    elif topic=='도형의 방정식':
        add('chord_geometry',f'원 x²+y²={a*a+b*b}와 직선 y={b}가 만나는 두 점 사이 거리는?',2*a,'직선을 원에 대입해 x좌표 두 개를 찾는다.')
        add('tangent_count',f'원 (x−{a})²+(y−{b})²={c*c}에 접하는 수평선 중 y절편이 더 큰 직선의 y절편은?',b+c,'중심에서 반지름만큼 위로 이동한 수평선이다.')
        add('midpoint_reverse',f'선분 AB의 중점은 ({a},{b})이고 A=(1,2)이다. B의 x좌표는?',2*a-1,'중점 공식으로 미지의 끝점을 역으로 구한다.')
        add('distance_locus',f'점 P=(x,0)이 A=(0,{a}), B=({b},0)에서 같은 거리에 있을 때 x는?',Fraction(b*b-a*a,2*b),'두 거리의 제곱을 같게 놓아 x²을 소거한다.')
    elif topic=='집합과 명제':
        add('inclusion_exclusion',f'1부터 {a*b*6}까지의 자연수 중 2의 배수 또는 3의 배수는 몇 개인가?',a*b*4,'2와 3의 배수를 더하고 6의 배수를 한 번 뺀다.')
        add('set_reverse',f'전체 학생 {a+b+c}명 중 A 활동만 {a}명, B 활동만 {b}명, 두 활동 모두 {c}명이다. A 활동에 참여한 학생은?',a+c,'A만 참여한 학생과 두 활동 모두 참여한 학생을 더한다.')
        add('logic_counterexample',f'명제 “모든 자연수 n에 대해 n²+n은 홀수이다”의 반례로 n={a}를 택했다. n²+n을 2로 나눈 나머지는?',0,'연속한 두 정수의 곱은 짝수다.')
        add('set_three_groups',f'A에만 속한 원소가 {a}개, B에만 속한 원소가 {b}개, A∩B가 {c}개이다. n(A∪B)는?',a+b+c,'서로 겹치지 않는 세 영역을 더한다.')
    elif topic in ('함수와 그래프','함수'):
        add('inverse_domain',f'f(x)=({a}x+1)/(x+{b})이고 {a*b}≠1이다. f(x)={a+1}을 만족하는 x는?',1-b*(a+1),'양변에 분모를 곱하고 x에 대해 정리한다.')
        add('composition_reverse',f'f(x)={a}x+{b}이고 f(f(x))={a*a*c+a*b+b}이다. x는?',c,'합성함수를 전개한 뒤 역산한다.')
        add('quadratic_min',f'f(x)=(x−{a})²+{b}이고 x≥{a+c}일 때 f(x)의 최솟값은?',c*c+b,'꼭짓점이 정의역 밖에 있으므로 경계에서 최소이다.')
        add('graph_intersection',f'y=x²와 y={a}x가 만나는 두 점 사이 거리의 제곱은?',a*a*(a*a+1),'두 교점을 구한 뒤 거리 공식에 대입한다.')
    elif topic=='수열':
        add('inverse_arithmetic',f'등차수열에서 제3항이 {a+2*b}, 제7항이 {a+6*b}이다. 제10항은?',a+9*b,'두 항의 차로 공차를 먼저 구한다.')
        add('sum_reverse',f'첫째 항이 {a}, 공차가 {b}인 등차수열의 첫 {c}개 항의 합은?',Fraction(c*(2*a+(c-1)*b),2),'첫 항과 끝 항의 평균에 항 수를 곱한다.')
        add('geometric_model',f'첫날 {a}개를 만들고 매일 전날의 2배씩 만든다. 첫 {b}일 동안 만든 총 개수는?',a*(2**b-1),'등비수열의 합을 이용한다.')
        add('alternating',f'수열의 홀수 번째 항은 {a}, 짝수 번째 항은 −{b}이다. 첫 {2*c+1}개 항의 합은?',(c+1)*a-c*b,'홀수 번째와 짝수 번째 항의 개수를 나누어 센다.')
    elif topic=='확률과 통계':
        add('conditional_selection',f'1부터 {6*a}까지의 자연수 중 하나를 뽑았다. 짝수라는 사실을 알 때 3의 배수일 확률은?',Fraction(1,3),'짝수 집합 안에서 6의 배수 비율을 센다.')
        add('variance_trap',f'자료 {a}, {a+b}, {a+2*b}에 각각 {c}를 더했다. 새로운 자료의 분산은?',Fraction(2*b*b,3),'같은 수를 더해도 분산은 변하지 않는다.')
        add('group_mean_reverse',f'평균 {a}인 {b}명과 평균 {c}인 {a}명이 있다. 전체 평균은?',Fraction(a*b+c*a,a+b),'각 집단의 총합을 합친 뒤 전체 인원으로 나눈다.')
        add('prob_complement',f'동전을 {a}번 던질 때 앞면이 적어도 한 번 나올 확률은?',Fraction(2**a-1,2**a),'앞면이 한 번도 안 나오는 여사건을 뺀다.')
    elif topic in ('미적분 응용','미적분Ⅰ'):
        add('velocity_reverse',f'물체의 위치가 s(t)=t³−{a}t²+{b}t이다. t={a}일 때 순간속도는?',a*a+b,'위치함수를 미분해 해당 시각에 대입한다.')
        add('area_geometry',f'y=x({a}−x)와 x축이 둘러싸는 영역의 넓이는?',Fraction(a**3,6),'교점을 찾고 양수인 구간에서 적분한다.')
        add('derivative_tangent',f'f(x)=x³−{a}x²+{b}x의 x={a}에서 접선 기울기는?',a*a+b,'도함수를 구한 뒤 접점의 x좌표를 대입한다.')
        add('integral_reverse',f'f′(x)=2x+{a}, f(0)={b}이다. f({c})는?',c*c+a*c+b,'도함수를 적분한 뒤 초기조건으로 적분상수를 정한다.')
    elif topic=='인수분해':
        add('sophie_identity',f'x⁴+4×{a}⁴를 인수분해할 때 두 이차인수의 상수항의 곱은?',4*a**4,'완전제곱을 더하고 빼서 제곱의 차로 바꾼다.')
        add('area_factor',f'직사각형의 넓이가 x²+{a+b}x+{a*b}이고 한 변이 x+{a}일 때 다른 변의 상수항은?',b,'넓이 다항식을 인수분해해 다른 변을 구한다.')
        add('factor_reverse',f'x²−{a*a}를 (x+p)(x+q)로 인수분해했을 때 p>q라면 p−q는?',2*a,'제곱의 차를 이용한다.')
        add('hidden_square',f'x⁴+4×{a}⁴를 (x²+u)²−(vx)² 꼴로 나타냈다. u의 값은?',2*a*a,'중간항을 보충하여 완전제곱을 만든다.')
    if not items:return None
    recent={x.removeprefix('v56_') for x in avoid}
    fresh=[i for i in items if i[0] not in recent]
    tag,q,ans,why=rng.choice(fresh or items)
    sig=hashlib.sha256(f'v56|{grade}|{topic}|{q}'.encode()).hexdigest()
    return dict(question=q,answer=[ans],explanation=why,signature=sig,
                family='v56_'+tag,grade=grade,topic=topic,difficulty='어려움',
                source_label=None,source_url=None)




def visual_hs_problem(grade, topic, rng, avoid=()):
    """고1 어려움: 도형과 조건을 한 데이터에서 만들어 답/그림 불일치를 방지."""
    if grade != "고1":
        return None
    from math import comb
    a = rng.randint(2, 6)
    b = rng.randint(2, 5)
    if topic == "집합과 명제":
        # n(A), n(B), n(A∪B) from regions; diagram only gives n(A\B), n(B\A), outside and unknown intersection
        only_a, only_b, both, outside = a+3, b+2, a+b+2, a+1
        union = only_a + only_b + both
        total = union + outside
        q = (f"전체집합 U의 원소는 {total}개이고, 그림에서 A∩B의 원소 수는 미지수 x이다. "
             f"n(A∪B)={union}이고, A에 속하는 원소를 하나 무작위로 고를 때 "
             f"그 원소가 B에도 속할 확률의 분자를 구하시오. "
             f"(확률을 기약분수로 나타냈을 때 분자)")
        from fractions import Fraction
        ans = Fraction(both, only_a+both).numerator
        why = f"합집합의 원소 수에서 A에만 속한 {only_a}개와 B에만 속한 {only_b}개를 빼면 교집합은 {both}개다. A는 {only_a+both}개이므로 조건부확률은 {Fraction(both,only_a+both)}이다."
        diagram = dict(type="venn2", a=only_a, b=only_b, outside=outside)
        family="hs_visual_venn_conditional"
    elif topic == "도형의 방정식":
        t=rng.randint(1,4)
        h,k=rng.randint(-4,4),rng.randint(-3,3)
        q=(f"중심이 C({h}, {k})이고 반지름이 {5*t}인 원을 직선 y={k+3*t}이 A, B에서 만난다. "
           "삼각형 CAB의 넓이를 구하시오. 그림은 좌표 관계를 나타낸다.")
        ans=12*t*t
        why=f"중심에서 현까지 거리는 {3*t}, 반현 길이는 √(({5*t})²−({3*t})²)={4*t}이다. 따라서 밑변 AB={8*t}, 높이={3*t}이므로 넓이는 {ans}이다."
        diagram=dict(type="circle_chord_hs", h=h,k=k,t=t)
        family="hs_visual_circle_chord"
    elif topic == "함수와 그래프":
        u=rng.randint(2,5)
        v=rng.randint(1,4)
        # parabola y=(x-u)^2-v², roots u±v, vertex (u,-v²), area with x-axis and vertex
        q=(f"그림의 포물선은 y=(x−{u})²−{v*v}이고 x축과 A, B에서 만난다. "
           "꼭짓점 V와 두 교점 A, B가 이루는 삼각형의 넓이를 구하시오.")
        ans=v**3
        why=f"x절편은 {u-v}, {u+v}이므로 AB={2*v}이고 꼭짓점에서 x축까지 거리는 {v*v}이다. 넓이는 {ans}이다."
        diagram=dict(type="parabola_hs", u=u,v=v)
        family="hs_visual_parabola_area"
    elif topic == "경우의 수":
        w,h=rng.randint(4,7),rng.randint(4,6)
        px,py=rng.randint(1,w-1),rng.randint(1,h-1)
        total=comb(w+h,w)
        via=comb(px+py,px)*comb(w+h-px-py,w-px)
        ans=total-via
        q=(f"격자에서 O(0,0)에서 B({w},{h})까지 오른쪽 또는 위쪽으로 한 칸씩 이동한다. "
           f"그림에 표시된 P({px},{py})를 지나지 않는 최단 경로의 수를 구하시오.")
        why=f"전체 경로는 {total}가지, P를 지나는 경로는 {comb(px+py,px)}×{comb(w+h-px-py,w-px)}={via}가지이므로 {ans}가지다."
        diagram=dict(type="grid",w=w,h=h,px=px,py=py)
        family="hs_visual_grid_avoid"
    elif topic == "다항식":
        # rectangle with side x+a and x+b, perimeter given for x=c; infer area and evaluate
        c=rng.randint(2,6)
        perimeter=2*(2*c+a+b)
        ans=(c+a)*(c+b)
        q=(f"그림의 직사각형 가로는 x+{a}, 세로는 x+{b}이다. 둘레가 {perimeter}일 때 넓이를 구하시오.")
        why=f"2((x+{a})+(x+{b}))={perimeter}에서 x={c}, 넓이는 ({c+a})×({c+b})={ans}이다."
        diagram=dict(type="rect_hs",a=a,b=b)
        family="hs_visual_rect_area"
    elif topic == "방정식과 부등식":
        # interval roots a and a+b; exclude endpoints and require even integers
        low=a; high=a+2*b+1
        evens=[x for x in range(low+1,high) if x%2==0]
        ans=len(evens)
        q=(f"그림의 수직선에서 두 열린 점의 좌표는 {low}, {high}이다. "
           f"(x−{low})(x−{high})<0을 만족하는 짝수 정수 x의 개수를 구하시오.")
        why=f"해는 {low}<x<{high}이다. 이 사이의 짝수 정수는 {evens}이므로 {ans}개다."
        diagram=dict(type="interval_hs",low=low,high=high)
        family="hs_visual_interval_even"
    elif topic == "행렬":
        # matrix multiplication visual schematic; AB (1,2) for matrices triangular
        c=rng.randint(2,7)
        ans=a*c+b
        q=(f"그림에서 A와 B는 각각 2×2 행렬이다. 행렬곱 AB의 (1,2) 성분을 구하시오.")
        why=f"AB의 (1,2) 성분은 A의 첫 행과 B의 둘째 열을 곱해 더하므로 {a}×{c}+{b}×1={ans}이다."
        diagram=dict(type="matrix_hs",a=a,b=b,c=c)
        family="hs_visual_matrix_product"
    else:
        return None
    sig=hashlib.sha256(f"v57|{grade}|{topic}|{q}".encode()).hexdigest()
    return dict(question=q,answer=[Rational(ans)],explanation=why,signature=sig,
                family=family,grade=grade,topic=topic,difficulty="어려움",
                diagram=diagram,source_label=None,source_url=None)


def diagram_svg_hs(spec):
    """그림을 수치 데이터에서 직접 그린 SVG로 출력."""
    if not spec or spec.get("type") not in {"venn2","circle_chord_hs","parabola_hs","rect_hs","interval_hs","matrix_hs"}:
        return None
    kind=spec["type"]
    parts=['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 660 350" width="660" height="350">',
           '<rect width="660" height="350" fill="white"/>',
           '<style>text{font:19px Arial,sans-serif;fill:#152238}.line{stroke:#2563eb;stroke-width:3;fill:none}.aux{stroke:#d97706;stroke-width:2.5;fill:none}.axis{stroke:#94a3b8;stroke-width:1.5}</style>']
    def ln(x1,y1,x2,y2,cls="line"):
        parts.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" class="{cls}"/>')
    def tx(x,y,t):
        parts.append(f'<text x="{x}" y="{y}">{html.escape(str(t))}</text>')
    if kind=="venn2":
        parts.append('<rect x="60" y="35" width="540" height="270" rx="10" fill="none" stroke="#475569" stroke-width="2"/>')
        parts.append('<circle cx="265" cy="168" r="105" fill="#3b82f6" fill-opacity=".10" stroke="#2563eb" stroke-width="3"/>')
        parts.append('<circle cx="395" cy="168" r="105" fill="#f59e0b" fill-opacity=".10" stroke="#d97706" stroke-width="3"/>')
        for x,y,t in [(75,60,"U"),(195,85,"A"),(460,85,"B"),(228,175,spec["a"]),(325,175,"x"),(450,175,spec["b"]),(555,278,spec["outside"])]:tx(x,y,t)
    elif kind=="circle_chord_hs":
        t=spec["t"]
        parts.append('<circle cx="330" cy="166" r="125" class="line"/>')
        ln(230,91,430,91,"aux");ln(330,166,230,91);ln(330,166,430,91);ln(330,166,330,91,"axis")
        for x,y,t0 in [(315,184,"C"),(214,83,"A"),(438,83,"B"),(340,128,"3t"),(345,205,"r=5t")]:tx(x,y,t0)
        tx(70,310,f't = {t}');tx(365,68,"AB")
    elif kind=="parabola_hs":
        u,v=spec["u"],spec["v"]
        # parabola plotted using x'=x-u, vertex y=-v², x intercept ±v
        ln(70,125,600,125,"axis");ln(330,30,330,315,"axis")
        pts=[]
        for i in range(181):
            z=-v-1+(2*v+2)*i/180
            xx=330+z*35; yy=125-(z*z-v*v)*min(130/(v*v),12)
            if 0<=yy<=350:pts.append(f'{xx:.1f},{yy:.1f}')
        parts.append('<polyline class="line" points="'+' '.join(pts)+'"/>')
        for x,y,t0 in [(330-35*v,118,"A"),(330+35*v,118,"B"),(335,125+min(130,12*v*v)+23,"V")]:tx(x,y,t0)
        tx(65,322,f'꼭짓점 ({u}, −{v*v})')
    elif kind=="rect_hs":
        parts.append('<rect x="170" y="70" width="300" height="195" fill="#eff6ff" stroke="#2563eb" stroke-width="3"/>')
        tx(295,295,f'x + {spec["a"]}');tx(478,174,f'x + {spec["b"]}')
    elif kind=="interval_hs":
        low,high=spec["low"],spec["high"]
        ln(95,165,565,165,"axis");ln(160,165,495,165,"line")
        for x,t0 in [(160,low),(495,high)]:
            parts.append(f'<circle cx="{x}" cy="165" r="7" fill="white" stroke="#2563eb" stroke-width="3"/>')
            tx(x-8,202,t0)
        tx(265,135,"해의 범위")
    elif kind=="matrix_hs":
        a,b,c=spec["a"],spec["b"],spec["c"]
        tx(120,110,"A =");tx(360,110,"B =")
        for x in [190,430]:
            ln(x,120,x,240);ln(x,120,x+15,120);ln(x,240,x+15,240)
            ln(x+135,120,x+135,240);ln(x+120,120,x+135,120);ln(x+120,240,x+135,240)
        for x,y,t0 in [(230,163,a),(285,163,b),(230,220,0),(285,220,1),(470,163,1),(525,163,c),(470,220,0),(525,220,1)]:tx(x,y,t0)
    parts.append('</svg>')
    return ''.join(parts).encode('utf-8')




def hs58_challenge(grade, topic, rng, avoid=()):
    """Independent, exact-answer multistep high-school challenges (original)."""
    if grade != "고1": return None
    from math import comb, gcd
    from fractions import Fraction
    candidates=[]
    def add(family, q, answer, explanation, diagram=None):
        candidates.append(("v58_"+family,q,answer,explanation,diagram))
    if topic == "집합과 명제":
        # Quantified implication over a finite universe, with a parameter.
        n=rng.randint(13,22); d=rng.choice([2,3,4]); r=rng.randint(1,d-1)
        good=[k for k in range(1,n+1) if k%d==r]
        q=(f"전체집합 U={{1,2,…,{n}}}에서 A={{x∈U | x를 {d}로 나눈 나머지가 {r}}}이다. "
           f"B_t={{x∈U | x≤t}}라 할 때, 명제 ‘모든 x∈A에 대하여 x∈B_t’가 참이고 "
           f"‘모든 x∈B_t에 대하여 x∈A’는 거짓이 되게 하는 정수 t의 최솟값을 구하시오. (1≤t≤{n})")
        add("logic_quantifier",q,max(good),f"첫 명제는 A⊆B_t, 즉 t≥max(A)={max(good)}이다. r≠1이므로 1∈B_t이지만 1∉A이다. 따라서 둘째 명제는 거짓이고 최솟값은 {max(good)}.") if r!=1 else None
        # Set cardinalities, three-way overlap, reverse inference.
        x=rng.randint(3,7); ab=rng.randint(2,5); ac=rng.randint(2,5); bc=rng.randint(2,5)
        only_a=rng.randint(3,8); only_b=rng.randint(3,8); only_c=rng.randint(3,8)
        nA=only_a+ab+ac+x; nB=only_b+ab+bc+x; nC=only_c+ac+bc+x
        pair_ab=ab+x; pair_ac=ac+x; pair_bc=bc+x
        union=only_a+only_b+only_c+ab+ac+bc+x
        q=(f"세 집합 A,B,C에 대해 n(A)={nA}, n(B)={nB}, n(C)={nC}, "
           f"n(A∩B)={pair_ab}, n(B∩C)={pair_bc}, n(C∩A)={pair_ac}, "
           f"n(A∪B∪C)={union}이다. 정확히 두 집합에만 속하는 원소의 개수를 구하시오.")
        add("venn_three_reverse",q,ab+ac+bc,
            f"포함배제에 의해 세 집합의 공통 원소는 {union}−({nA}+{nB}+{nC})+({pair_ab}+{pair_bc}+{pair_ac})={x}. 정확히 두 집합에만 속하는 수는 세 쌍 교집합의 합에서 공통 원소를 세 번 빼서 {ab+ac+bc}이다.")
        a=rng.randint(2,7); b=rng.randint(a+3,a+9)
        q=(f"실수 전체에서 명제 p: x²−{a+b}x+{a*b}≤0, q: x≥k이다. "
           f"p가 q이기 위한 충분조건이지만 필요조건은 아니도록 하는 정수 k의 최댓값을 구하시오.")
        add("sufficient_interval",q,a,
            f"p의 진리집합은 [{a},{b}]이다. p⇒q이려면 k≤{a}이고, q⇒p는 실수 전체에서 거짓이므로 필요조건이 아니다. 최댓값은 {a}.")
    elif topic == "도형의 방정식":
        h=rng.randint(-3,3); k=rng.randint(-3,3); radius=rng.choice([5,10,13]); dist=rng.choice({5:[3,4],10:[6,8],13:[5,12]}[radius]);
        q=(f"원 (x−({h}))²+(y−({k}))²={radius**2}에 대해 직선 y={k+dist}이 두 점 P,Q에서 만난다. "
           f"원 위에서 현 PQ와 같은 길이를 갖는 현들의 중점이 이루는 도형의 넓이를 구하시오. (원주율은 π로 표시하지 말고, 넓이를 π로 나눈 값을 답하시오.)")
        add("chord_locus",q,dist*dist,
            f"길이가 같은 현은 중심에서 거리가 모두 {dist}이다. 따라서 중점의 자취는 중심이 ({h},{k}), 반지름이 {dist}인 원이며 넓이/π={dist*dist}.",None)
        a=rng.randint(2,5); b=rng.randint(1,4)
        q=(f"점 A(0,0), B({2*a},0), C(0,{2*b})에 대해 점 P가 선분 AB 위를 움직인다. "
           f"삼각형 APC의 넓이가 삼각형 PBC 넓이의 {a}배일 때, AP의 길이를 구하시오.")
        add("moving_area_ratio",q,Fraction(2*a*a,a+1),
            f"두 삼각형의 높이는 C에서 AB까지 같으므로 넓이의 비는 AP:PB={a}:1이다. AB={2*a}이므로 AP={2*a*a}/{a+1}.")
    elif topic == "함수와 그래프":
        a=rng.randint(2,5); b=rng.randint(2,6)
        q=(f"f(x)=|x−{a}|+|x+{b}|라 하자. 방정식 f(x)=k가 서로 다른 실근을 "
           f"무한히 많이 갖도록 하는 실수 k의 값을 구하시오.")
        add("absolute_flat",q,a+b,
            f"−{b}≤x≤{a}에서는 두 절댓값의 합이 {a+b}로 일정하다. 그 외 구간에서는 값이 증가하므로 k={a+b}일 때 해가 무한히 많다.")
    elif topic == "경우의 수":
        n=rng.randint(6,10); k=rng.randint(2,4)
        q=(f"서로 다른 {n}명을 한 줄로 세울 때, 지정된 두 사람 A,B 사이에 정확히 {k}명이 있도록 세우는 방법의 수를 구하시오.")
        ans=2*(n-k-1)*math.factorial(n-2)
        add("spacing_people",q,ans,
            f"A와 B의 자리쌍은 {n-k-1}개이고 순서 2가지, 나머지 {n-2}명은 ({n-2})!가지이므로 {ans}.")
        n=rng.randint(6,10); r=rng.randint(2,n-2)
        q=(f"1부터 {n}까지 서로 다른 자연수 중 {r}개를 고른다. 연속한 두 수가 포함되지 않게 고르는 경우의 수를 구하시오.")
        ans=comb(n-r+1,r)
        add("nonadjacent_subset",q,ans,
            f"고른 수를 a₁<…<a_{r}라 하면 bᵢ=aᵢ−(i−1)는 1부터 {n-r+1}까지 서로 다른 {r}개를 고르는 것과 일대일 대응한다. 따라서 {ans}.")
    elif topic == "다항식":
        a=rng.randint(2,7); b=rng.randint(2,8)
        q=(f"다항식 P(x)를 (x−{a})²로 나눈 나머지는 {b}x+{a}이고, "
           f"(x−{a+1})로 나눈 나머지는 {a*b+b}이다. "
           f"P(x)를 (x−{a})²(x−{a+1})로 나눈 나머지 R(x)에 대해 R(0)의 값을 구하시오.")
        # R=(b*x+a)+k*(x-a)^2, R(a+1)=b(a+1)+a+k = ab+b => k=-a
        k=-a
        ans=a+k*a*a
        add("hermite_remainder",q,ans,
            f"R(x)={b}x+{a}+k(x−{a})². x={a+1}을 대입하면 {b*(a+1)+a}+k={a*b+b}이므로 k=−{a}. R(0)={ans}.")
    elif topic == "방정식과 부등식":
        a=rng.randint(2,7); b=rng.randint(2,7)
        q=(f"이차방정식 x²−2kx+({a}k+{b})=0이 서로 다른 두 양의 실근을 갖도록 하는 "
           f"정수 k 중 {a+1}≤k≤{a+20}을 만족하는 k의 개수를 구하시오.")
        good=[k for k in range(a+1,a+21) if k>0 and a*k+b>0 and k*k>a*k+b]
        add("positive_roots_parameter",q,len(good),
            f"두 양의 실근 조건은 근의 합 2k>0, 곱 {a}k+{b}>0, 판별식 4(k²−{a}k−{b})>0이다. 주어진 정수 범위에서 조건을 만족하는 k는 {good}, 총 {len(good)}개.")
    elif topic == "행렬":
        a=rng.randint(2,8); b=rng.randint(2,8); n=rng.randint(4,9)
        q=(f"행렬 A=[[1,{a}],[0,1]], B=[[1,0],[{b},1]]에 대하여 "
           f"AⁿB의 (1,1) 성분을 구하시오. (n={n})")
        add("matrix_power_product",q,1+n*a*b,
            f"A=I+N이고 N²=0이므로 Aⁿ=I+nN=[[1,{n*a}],[0,1]]. B와 곱하면 (1,1) 성분은 1+{n*a}×{b}={1+n*a*b}.")
    if not candidates:return None
    eligible=[c for c in candidates if c[0] not in avoid] or candidates
    family,q,ans,why,diagram=rng.choice(eligible)
    return dict(question=q,answer=[Rational(ans)],explanation=why,
        signature=hashlib.sha256((family+q).encode()).hexdigest(),family=family,
        grade=grade,topic=topic,difficulty="어려움",diagram=diagram,
        source_label="자체 제작 고난도 · 기출 아님",source_url=None)


def olympiad58(grade, difficulty, rng, avoid=()):
    """Original olympiad-style puzzles inspired by contest topic taxonomy, not copied questions."""
    if difficulty != "어려움": return None
    from math import comb
    gi=GRADES.index(grade)
    items=[]
    def add(tag,q,ans,why):items.append(("ol58_"+tag,q,ans,why))
    n=rng.randint(30,65)+gi*7; m=rng.choice([4,5,6,7])
    q=f"1부터 {n}까지의 정수 중 {m}의 배수도 아니고 {m+1}의 배수도 아닌 수는 몇 개인가?"
    ans=n-n//m-n//(m+1)+n//math.lcm(m,m+1)
    add("sieve",q,ans,f"포함배제: {n}−{n//m}−{n//(m+1)}+{n//math.lcm(m,m+1)}={ans}.")
    n=rng.randint(8,14)+gi
    q=f"원 위에 서로 다른 {n}개의 점을 잡고 모든 두 점을 선분으로 연결한다. 세 선분이 내부의 한 점에서 만나지 않도록 배치했을 때, 원 내부의 교점은 최대 몇 개인가?"
    add("circle_intersections",q,comb(n,4),f"내부의 각 교점은 서로 다른 4개의 끝점을 선택한 두 대각선에 일대일 대응한다. 따라서 C({n},4)={comb(n,4)}.")
    n=rng.randint(5,9)+gi
    q=f"{n}×{n} 격자에서 왼쪽 아래에서 오른쪽 위까지 오른쪽·위쪽으로만 이동한다. 대각선 y=x보다 위쪽으로는 절대 올라가지 않는 최단 경로의 수는?"
    ans=comb(2*n,n)//(n+1)
    add("catalan",q,ans,f"전체 C({2*n},{n})에서 반사원리로 금지 경로를 빼면 카탈란 수 C({2*n},{n})/({n+1})={ans}.")
    a=rng.randint(4,10)+gi; b=rng.randint(3,8)
    q=f"양의 정수 x,y,z가 x+y+z={a+b+3}이고 x≥{a}, y≥{b}, z≥1일 때 순서쌍 (x,y,z)의 개수는?"
    add("stars_bars",q,comb(5,2),f"x' = x−{a}, y'=y−{b}, z'=z−1로 치환하면 합이 2인 음이 아닌 정수 세 쌍이므로 C(4,2)=6.")
    eligible=[i for i in items if i[0] not in avoid] or items
    fam,q,ans,why=rng.choice(eligible)
    return dict(question=q,answer=[Rational(ans)],explanation=why,
      signature=hashlib.sha256((fam+q).encode()).hexdigest(),family=fam,
      grade=grade,topic="수학올림피아드",difficulty=difficulty,
      source_label="AMC/AIME 주제 분류 참고 · 자체 제작 문제 (실제 기출 아님)",source_url=None,
      hint="경우 나누기, 포함배제, 일대일 대응 또는 반사원리를 생각해 보세요.")




# ===== 5.9: family-balanced reasoning bank (single-file, offline) =====
def v59_bank(grade, topic, difficulty, rng, avoid=()):
    """Genuinely different mathematical structures; numerical answers checked by construction."""
    if difficulty != '어려움' or not (grade=='고1' or (grade=='중3' and topic=='인수분해')): return None
    from math import comb, factorial, gcd
    from fractions import Fraction
    import sympy as sp
    bank=[]
    def add(tag,q,ans,why,diagram=None):
        bank.append(('v59_'+tag,q,Rational(ans),why,diagram))
    a,b,c=[rng.randint(2,7) for _ in range(3)]
    if topic=='다항식' and grade=='고1':
        # (1) interpolation/remainder
        u,v=rng.sample(range(1,9),2); r=rng.randint(2,8)
        add('poly_remainder_interpolate',f'다항식 P(x)를 (x−{u})(x−{v})로 나눈 나머지가 R(x)이다. P({u})={a*u+b}, P({v})={a*v+b}일 때 R(−{r})을 구하시오.',b-a*r,f'R은 일차 이하이며 두 점에서의 값이 일차식 {a}x+{b}와 같으므로 R(x)={a}x+{b}.')
        # (2) cubic coefficient from special values
        h=rng.randint(2,5); t=h
        add('poly_cubic_divisibility',f'P(x)=x³+px²+qx+{t}이고 P(1)=0, P(−1)=0, P({h})=0이다. p+q를 구하시오.',-h-1,f'P(x)=(x−1)(x+1)(x−{h})=x³−{h}x²−x+{h}여야 한다. 단, 상수항이 {t}와 일치해야 하므로 이 조건은 t={h}일 때만 가능하다.' )
        # (3) polynomial roots with shifted substitution
        k=rng.randint(2,6); z=rng.randint(1,5)
        add('poly_shifted_roots',f'방정식 (x²−{k}x)²−{z*z}=0의 서로 다른 실근의 개수를 구하시오.',4 if k*k>4*z else (3 if k*k==4*z else 2),f'x²−{k}x=±{z}로 나눈다. +{z}쪽은 서로 다른 실근 2개, −{z}쪽은 판별식 {k*k}−{4*z}의 부호로 판단한다.')
        # (4) symmetric power sums
        s=rng.randint(3,9); prod=rng.randint(1,5)
        add('poly_symmetric_identity',f'실수 x,y가 x+y={s}, xy={prod}를 만족한다. x³+y³−3xy(x+y)의 값을 구하시오.',s**3-6*prod*s,f'x³+y³=(x+y)³−3xy(x+y)이므로 식은 {s}³−6×{prod}×{s}.')
        # (5) polynomial area inverse
        t=rng.randint(2,6); d=rng.randint(1,5)
        add('poly_geometry_perimeter',f'직사각형의 가로와 세로가 각각 x+{a}, 2x+{b}이다. 둘레가 {2*(3*t+a+b)}이고 넓이가 S일 때 S−x²의 값을 구하시오.',(t+a)*(2*t+b)-t*t,f'둘레에서 x={t}, S=({t+a})({2*t+b})를 얻는다.',{'type':'v59_rectangle','a':t+a,'b':2*t+b})
        # (6) coefficient compare polynomial identity
        k=rng.randint(2,6); m=rng.randint(1,5)
        add('poly_identity_coeff',f'모든 실수 x에 대하여 (x²+ax+{k})(x+b)=x³+{k+m}x²+cx+{k*m}이다. a+b+c의 값을 구하시오.',(k+m-m)+(m)+(k+(k+m-m)*m),f'상수항에서 b={m}, x² 계수에서 a={k}, x 계수 c={k}+{k}×{m}이다.')
    elif topic=='인수분해' and grade=='중3':
        # Numeric challenges on factor structure, not repeated multiple-choice identities
        x=rng.randint(3,9); y=rng.randint(1,x-1)
        add('factor_diff_squares_inverse',f'양의 정수 p>q에 대해 p²−q²={x*x-y*y}, p+q={x+y}일 때 p−q의 값을 구하시오.',x-y,'제곱의 차 (p+q)(p−q)를 이용한다.')
        k=rng.randint(3,8)
        add('factor_quartic_zero',f'방정식 x⁴−({k*k+1})x²+{k*k}=0의 서로 다른 실근의 개수를 구하시오.',4,f'(x²−1)(x²−{k*k})=0으로 인수분해한다.')
        n=rng.randint(5,12)
        add('factor_consecutive_product',f'두 자연수의 차는 2이고 곱은 {n*(n+2)}이다. 두 수의 합을 구하시오.',2*n+2,'작은 수를 x라 두고 x(x+2)를 완전제곱식으로 변형한다.')
        k=rng.randint(2,6); r=rng.randint(1,5)
        add('factor_substitution_roots',f'(x²−{k}x)²−{r*r}=0의 서로 다른 실근은 모두 몇 개인가?',4 if k*k>4*r else (3 if k*k==4*r else 2),'x²−kx를 한 문자로 치환한 뒤 제곱의 차로 분해하고 두 이차방정식의 판별식을 조사한다.')
        t=rng.randint(3,5)
        add('factor_area_difference',f'정사각형 A의 한 변은 x+{t}, 정사각형 B의 한 변은 x−{t}이다. 두 넓이의 차가 {4*t*6}일 때 x를 구하시오.',6,'넓이의 차를 합차 공식으로 인수분해하면 4tx이다.',{'type':'v59_squares','outer':t+6,'inner':6-t if t<6 else t-6})
        k=rng.randint(2,7); j=rng.randint(2,7)
        add('factor_parameter_double_root',f'x²−2ax+{k*k}=0이 중근을 가지며 a는 양수이다. 이때 (a+{j})²−(a−{j})²의 값을 구하시오.',4*k*j,f'판별식 4a²−4×{k*k}=0, a={k}. 합차 공식을 적용한다.')
        p=rng.randint(2,7); q=rng.randint(2,7)
        add('factor_hidden_factor',f'x²+({p+q})x+{p*q}=0의 두 근 α,β에 대하여 α²+β²를 구하시오.',p*p+q*q,'(x+p)(x+q)=0으로 분해하거나 근과 계수 관계를 사용한다.')
    elif grade=='고1' and topic=='집합과 명제':
        # true quantified inclusion: parameter interval
        l=rng.randint(2,6); u=l+rng.randint(4,9)
        add('logic_parameter_interval',f'실수 x에 대하여 명제 “{l}≤x≤{u}이면 x≥k”가 항상 참이 되게 하는 정수 k의 최댓값을 구하시오.',l,'전칭명제가 참이려면 구간 전체가 x≥k에 포함되어야 하므로 k≤왼쪽 끝점이다.',{'type':'v59_interval','l':l,'u':u})
        # three-set reverse inference
        x=rng.randint(2,7); aa,bb,cc=[rng.randint(2,6) for _ in range(3)]; o=[rng.randint(2,5) for _ in range(3)]
        A=o[0]+aa+cc+x;B=o[1]+aa+bb+x;C=o[2]+bb+cc+x;AB=aa+x;BC=bb+x;CA=cc+x;U=sum(o)+aa+bb+cc+x
        add('logic_venn3_inverse',f'n(A)={A}, n(B)={B}, n(C)={C}, n(A∩B)={AB}, n(B∩C)={BC}, n(C∩A)={CA}, n(A∪B∪C)={U}일 때, 정확히 한 집합에만 속하는 원소의 개수를 구하시오.',sum(o),'포함배제로 삼중 교집합을 복원한 뒤 각 집합에만 속하는 부분을 합한다.',{'type':'v59_venn3','o':o,'pairs':[aa,bb,cc],'center':x})
        # implication and divisibility
        n=rng.randint(20,45); d=rng.choice([3,5,7])
        add('logic_counterexample_count',f'전체집합 U={{1,2,…,{n}}}에서 명제 “x가 {d}의 배수이면 x는 짝수이다”의 반례가 되는 원소의 개수를 구하시오.',sum(i%d==0 and i%2 for i in range(1,n+1)),'반례는 전제가 참이고 결론이 거짓인 수이다. 홀수인 배수만 센다.')
        # sufficient condition interval
        k=rng.randint(2,7); h=rng.randint(3,8)
        add('logic_sufficient_vs_necessary',f'실수 x에 대하여 p: (x−{k})(x−{k+h})≤0, q: x≥a이다. p가 q이기 위한 충분조건이지만 필요조건은 아니도록 하는 정수 a의 최댓값은?',k,'p의 진리집합은 닫힌 구간이므로 p⇒q는 a≤왼쪽 끝점일 때 참이다.')
        # count set from polynomial inequality
        a=rng.randint(2,7); b=a+rng.randint(5,11)
        add('logic_set_comprehension',f'U={{1,2,…,{b+4}}}, A={{x∈U | (x−{a})(x−{b})<0}}, B={{x∈U | x는 홀수}}일 때 n(A∖B)를 구하시오.',sum(i%2==0 for i in range(a+1,b)),'이차부등식의 해는 열린 구간이고, A∖B는 그 안의 짝수들이다.',{'type':'v59_interval','l':a,'u':b})
    elif grade=='고1' and topic=='도형의 방정식':
        # line-circle chord with hidden Pythagorean triple
        t=rng.randint(1,4);h=rng.randint(-3,3);k=rng.randint(-3,3)
        add('geo_chord_length',f'원 (x−({h}))²+(y−({k}))²={25*t*t}과 직선 y={k+3*t}의 두 교점을 A,B라 한다. AB의 길이를 구하시오.',8*t,'중심에서 직선까지 거리 3t, 반지름 5t이므로 반현은 4t이다.',{'type':'circle_chord_hs','h':h,'k':k,'t':t})
        a=rng.randint(3,9);b=rng.randint(2,7)
        add('geo_locus_circle',f'점 P(x,y)가 A(0,0), B({2*a},0)에 대하여 PA²+PB²={2*(a*a+b*b)}를 만족한다. 점 P의 자취가 이루는 도형의 넓이를 π로 나눈 값을 구하시오.',b*b,'완전제곱으로 정리하면 (x−a)²+y²=b²이다.',{'type':'v59_locus','a':a,'b':b})
        a=rng.randint(2,8);b=rng.randint(2,8)
        add('geo_line_area_ratio',f'A(0,0), B({2*a},0), C(0,{2*b})이다. P는 선분 AB 위의 점이고 △APC:△PBC={a}:1이다. AP의 길이를 구하시오.',Fraction(2*a*a,a+1),'높이가 같은 두 삼각형의 넓이 비는 밑변 AP:PB와 같다.',{'type':'v59_triangle','a':2*a,'b':2*b,'p':Fraction(2*a*a,a+1)})
        m=rng.randint(2,7);n=rng.randint(2,6)
        add('geo_perpendicular_bisector',f'A({-m},0), B({m},0), C(0,{n})에서 세 점으로부터 같은 거리에 있는 점 P의 y좌표를 구하시오.',Fraction(n*n-m*m,2*n),'PA=PB이므로 P는 y축 위에 있다. PA²=PC²로 y를 구한다.',{'type':'v59_triangle','a':2*m,'b':n,'p':m})
        r=rng.randint(3,9);d=rng.randint(1,r-1)
        add('geo_tangent_length',f'원 x²+y²={r*r} 밖의 점 P({r+d},0)에서 원에 그은 접선의 접점을 T라 할 때 PT²을 구하시오.',(r+d)**2-r*r,'반지름 OT와 접선 PT는 수직이므로 직각삼각형에서 PT²=OP²−OT².',{'type':'v59_tangent','r':r,'d':d})
    elif grade=='고1' and topic=='함수와 그래프':
        a=rng.randint(2,7);b=rng.randint(2,6)
        add('func_absolute_plateau',f'f(x)=|x−{a}|+|x+{b}|이다. 방정식 f(x)=k가 서로 다른 실근을 무한히 많이 가지도록 하는 k를 구하시오.',a+b,'두 꺾임점 사이에서 함수값이 일정해지는 구간을 찾는다.',{'type':'v59_abs','a':a,'b':b})
        a=rng.randint(2,6);b=rng.randint(2,7)
        add('func_inverse_domain',f'f(x)=(x−{a})²+{b} (x≥{a})이다. f⁻¹({b+9})의 값을 구하시오.',a+3,'정의역이 꼭짓점 오른쪽이므로 양의 제곱근을 택한다.',{'type':'v59_parabola','a':a,'b':b})
        a=rng.randint(2,6);b=rng.randint(2,6)
        add('func_graph_intersections',f'포물선 y=x²−{a*a}와 직선 y={b}가 만나는 두 점 사이의 거리를 제곱한 값을 구하시오.',4*(a*a+b),'교점의 x좌표는 ±√(a²+b)이고 두 점의 y좌표는 같다.',{'type':'v59_parabola','a':0,'b':-a*a,'line':b})
        a=rng.randint(2,6);b=rng.randint(2,6)
        add('func_composition_fixed',f'f(x)=2x+{a}, g(x)=x²−{b}이다. f(g(x))=g(f(x))을 만족하는 실수 x들의 합을 구하시오.',Fraction(-4*a,2), '양변을 전개해 이차방정식으로 정리하고 근과 계수 관계를 이용한다.')
        a=rng.randint(2,6);b=rng.randint(2,6)
        add('func_piecewise_continuity',f'f(x)는 x<{a}일 때 2x+{b}, x≥{a}일 때 kx−{b}이다. f가 x={a}에서 연속이 되도록 하는 k를 구하시오.',Fraction(2*a+2*b,a),'좌극한과 함수값을 같게 둔다.',{'type':'v59_piecewise','a':a,'b':b})
    elif grade=='고1' and topic=='경우의 수':
        n=rng.randint(7,11);k=rng.randint(1,3)
        add('comb_spacing',f'서로 다른 {n}명을 일렬로 세울 때 A와 B 사이에 정확히 {k}명이 있도록 세우는 방법은?',2*(n-k-1)*factorial(n-2),'두 사람의 위치쌍을 정한 뒤 나머지를 배열한다.')
        n=rng.randint(9,15);r=rng.randint(3,5)
        add('comb_nonadjacent',f'1부터 {n}까지의 정수에서 서로 연속하지 않도록 {r}개를 고르는 방법의 수는?',comb(n-r+1,r),'선택한 수에 간격을 제거하는 치환을 적용한다.')
        w=rng.randint(5,8);h=rng.randint(4,7);px=rng.randint(1,w-1);py=rng.randint(1,h-1)
        ans=comb(w+h,w)-comb(px+py,px)*comb(w+h-px-py,w-px)
        add('comb_grid_avoid',f'격자 O(0,0)에서 B({w},{h})까지 오른쪽·위쪽으로만 이동한다. P({px},{py})를 지나지 않는 최단 경로의 수를 구하시오.',ans,'전체 최단 경로에서 P를 지나는 경로를 뺀다.',{'type':'grid','w':w,'h':h,'px':px,'py':py})
        n=rng.randint(7,11);k=rng.randint(2,4)
        add('comb_at_least_one',f'서로 다른 {n}명 중 {k}명을 뽑는다. 지정된 A,B 중 적어도 한 명이 포함되게 뽑는 방법의 수는?',comb(n,k)-comb(n-2,k),'여사건을 사용한다.')
        n=rng.randint(5,8)
        add('comb_circular_no_adjacent',f'서로 다른 {n}명을 원탁에 앉힌다. 지정된 A,B가 이웃하지 않게 앉는 경우의 수는?',factorial(n-1)-2*factorial(n-2),'원순열 전체에서 A,B를 한 덩어리로 보는 경우를 뺀다.')
    elif grade=='고1' and topic=='방정식과 부등식':
        a=rng.randint(3,7);b=rng.randint(2,6)
        lo=a+1; hi=a+20
        good=[k for k in range(lo,hi+1) if k*k>a*k+b]
        add('ineq_positive_roots',f'x²−2kx+({a}k+{b})=0이 서로 다른 두 양의 실근을 갖게 하는 정수 k({lo}≤k≤{hi})의 개수는?',len(good),'판별식 양수, 두 근의 합과 곱이 양수인 조건을 함께 사용한다.')
        a=rng.randint(2,7);b=a+rng.randint(5,12)
        add('ineq_integer_interval',f'(x−{a})(x−{b})<0과 x²−{(a+1)**2}≥0을 동시에 만족하는 정수 x의 개수를 구하시오.',max(0,b-(a+1)),'첫 조건은 a<x<b, 둘째는 |x|≥a+1. 두 조건의 공통 정수를 센다.',{'type':'v59_interval','l':a,'u':b})
        a=rng.randint(2,7);b=rng.randint(2,6)
        add('ineq_abs_parameter',f'부등식 |x−{a}|≤k를 만족하는 정수 x가 정확히 {2*b+1}개가 되도록 하는 양의 정수 k를 구하시오.',b,'중심이 정수인 닫힌 구간의 정수 개수는 2k+1이다.',{'type':'v59_interval','l':a-b,'u':a+b})
        a=rng.randint(2,7);b=rng.randint(3,9)
        add('ineq_discriminant_range',f'모든 실수 x에 대해 x²−2ax+k>0가 참이 되도록 하는 정수 k 중 {a*a-3}≤k≤{a*a+b}인 것의 개수를 구하시오.',b,'최솟값 k−a²가 0보다 커야 한다.')
        a=rng.randint(2,6);b=rng.randint(2,6)
        add('ineq_real_world_ticket',f'공연장 입장권은 성인 {a+5}천 원, 청소년 {b+2}천 원이다. 성인 {a}명과 청소년 x명이 입장할 때 총액이 {a*(a+5)+(b+2)*8}천 원 이하라면 가능한 청소년 수의 최댓값은?',8,'실생활 조건을 일차부등식으로 모델링한다.')
    elif grade=='고1' and topic=='행렬':
        a=rng.randint(2,7);b=rng.randint(2,7);n=rng.randint(4,9)
        add('matrix_nilpotent',f'A=[[1,{a}],[0,1]], B=[[1,0],[{b},1]]일 때 A^{n}B의 (1,1) 성분은?',1+n*a*b,'A=I+N, N²=0이므로 Aⁿ=I+nN이다.')
        a=rng.randint(2,7);b=rng.randint(2,7)
        add('matrix_noncommute',f'A=[[1,{a}],[0,1]], B=[[1,0],[{b},1]]일 때 AB−BA의 (1,1) 성분을 구하시오.',a*b,'행렬곱의 순서가 바뀌면 성분이 달라진다.')
        a=rng.randint(2,7);b=rng.randint(2,7)
        add('matrix_trace_square',f'A=[[{a},1],[0,{b}]]일 때 A²의 대각합을 구하시오.',a*a+b*b,'상삼각행렬 제곱의 대각성분을 계산한다.')
        a=rng.randint(2,7);b=rng.randint(2,7)
        add('matrix_linear_equation',f'A=[[1,{a}],[0,1]]이다. AX=[[1,{b}],[0,1]]을 만족하는 X의 (1,2) 성분을 구하시오.',b-a,'A의 역행렬을 곱하거나 성분을 비교한다.')
        a=rng.randint(2,7);b=rng.randint(2,7)
        add('matrix_pattern',f'A=[[0,−1],[1,0]]이다. A^{4*a+b}의 (1,1) 성분을 구하시오.',[1,0,-1,0][b%4],'A⁴=I이므로 지수를 4로 나눈 나머지만 확인한다.')
    if not bank:return None
    fresh=[v for v in bank if v[0] not in avoid]
    if not fresh: fresh=bank
    fam,q,ans,why,diagram=rng.choice(fresh)
    return dict(question=q,answer=[ans],explanation=why,signature=hashlib.sha256((fam+'|'+q).encode()).hexdigest(),family=fam,grade=grade,topic=topic,difficulty=difficulty,diagram=diagram,source_label='자체 제작 심화 응용 · 기출 아님',source_url=None)


def v59_olympiad(grade, difficulty, rng, avoid=()):
    if grade!='고1' or difficulty!='어려움':return None
    from math import comb, factorial
    bank=[]
    def add(tag,q,ans,why,diagram=None):bank.append(('v59_ol_'+tag,q,Rational(ans),why,diagram))
    n=rng.randint(7,11)
    add('circle_chords',f'원 위에 {n}개의 점이 있다. 어느 세 현도 원 내부의 한 점에서 만나지 않게 모든 현을 그었다. 내부 교점의 수를 구하시오.',comb(n,4),'서로 다른 네 꼭짓점이 내부 교점 하나를 결정한다.')
    n=rng.randint(6,10)
    add('catalan',f'{n}×{n} 격자에서 (0,0)에서 ({n},{n})까지 오른쪽 또는 위쪽으로만 이동한다. 항상 y≤x를 만족하는 최단 경로의 수는?',comb(2*n,n)//(n+1),'반사원리를 적용하면 카탈란 수가 된다.',{'type':'v59_dyck','n':n})
    n=rng.randint(8,14);r=rng.randint(3,5)
    add('no_consecutive',f'1부터 {n}까지의 수에서 서로 이웃하는 수가 없도록 {r}개를 고르는 방법의 수는?',comb(n-r+1,r),'선택한 수의 순서에 따라 간격을 한 칸씩 줄이는 대응을 사용한다.')
    a=rng.randint(4,8);b=rng.randint(3,7)
    add('stars_bars',f'양의 정수 x,y,z가 x+y+z={a+b+4}, x≥{a}, y≥{b}, z≥1을 만족하는 순서쌍 (x,y,z)의 개수는?',10,'x−a,y−b,z−1은 합이 3인 음이 아닌 정수이므로 C(5,2)=10이다.')
    n=rng.randint(40,80);a=rng.choice([4,5,6]);b=a+1
    add('inclusion_exclusion',f'1부터 {n}까지 중 {a}의 배수도 {b}의 배수도 아닌 수는 몇 개인가?',n-n//a-n//b+n//(a*b),'포함배제 원리를 이용한다.')
    n=rng.randint(8,13)
    add('handshake',f'{n}명의 사람이 모두 서로 한 번씩 악수한다. 단, 지정된 세 사람끼리는 서로 악수하지 않는다. 총 악수 횟수는?',comb(n,2)-3,'전체 두 사람 선택에서 지정된 세 쌍을 제외한다.')
    a=rng.randint(3,8);b=rng.randint(2,6)
    add('number_theory_mod',f'자연수 N을 {a}로 나누면 나머지가 {a-1}, {a+1}로 나누면 나머지가 {a}이다. N이 {a*(a+1)*b} 이하일 때 가능한 N의 개수를 구하시오.',b,'N+1은 연속한 두 수 a,a+1의 공배수이므로 N=a(a+1)t−1이다.')
    n=rng.randint(7,11)
    add('polygon_diagonals',f'볼록 {n}각형의 모든 대각선을 그었을 때 대각선의 개수와 변의 개수의 차는?',n*(n-3)//2-n,'각 꼭짓점에서 대각선은 n−3개, 두 번씩 세므로 n(n−3)/2이다.')
    fresh=[x for x in bank if x[0] not in avoid] or bank
    fam,q,ans,why,diagram=rng.choice(fresh)
    return dict(question=q,answer=[ans],explanation=why,signature=hashlib.sha256((fam+q).encode()).hexdigest(),family=fam,grade=grade,topic='수학올림피아드',difficulty=difficulty,diagram=diagram,source_label='자체 제작 올림피아드 응용 · 기출 아님',source_url=None)


def v59_diagram(spec):
    if not spec or not str(spec.get('type','')).startswith('v59_'):return None
    import html as _html
    typ=spec['type']; out=['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 620 310"><rect width="620" height="310" fill="white"/><style>text{font:17px sans-serif;fill:#172b4d}.shape{fill:#dbeafe;fill-opacity:.55;stroke:#2563eb;stroke-width:2.5}.axis{stroke:#94a3b8;stroke-width:2}</style>']
    def text(x,y,t):out.append(f'<text x="{x}" y="{y}">{_html.escape(str(t))}</text>')
    def line(x,y,X,Y,style='axis'):out.append(f'<line x1="{x}" y1="{y}" x2="{X}" y2="{Y}" class="{style}"/>')
    if typ=='v59_rectangle':
        out.append('<rect x="145" y="50" width="310" height="190" class="shape"/>');text(260,275,f'{spec["a"]}');text(465,150,f'{spec["b"]}')
    elif typ=='v59_squares':
        out.append('<rect x="100" y="35" width="240" height="240" class="shape"/><rect x="385" y="105" width="105" height="105" class="shape"/>');text(110,27,'A');text(395,97,'B')
    elif typ=='v59_interval':
        line(75,145,545,145);line(150,145,470,145,'shape');text(140,185,spec['l']);text(465,185,spec['u']);out.append('<circle cx="150" cy="145" r="6" fill="white" stroke="#2563eb" stroke-width="2"/><circle cx="470" cy="145" r="6" fill="white" stroke="#2563eb" stroke-width="2"/>')
    elif typ=='v59_venn3':
        out.append('<rect x="55" y="20" width="520" height="265" fill="none" stroke="#94a3b8"/><circle cx="250" cy="135" r="90" class="shape"/><circle cx="365" cy="135" r="90" class="shape"/><circle cx="310" cy="202" r="90" class="shape"/>');text(180,70,'A');text(425,70,'B');text(310,277,'C');text(299,155,'?')
    elif typ=='v59_locus':
        out.append('<circle cx="310" cy="155" r="105" class="shape"/>');line(90,155,530,155);line(310,40,310,275);text(320,147,f'({spec["a"]},0)');text(410,140,f'r={spec["b"]}')
    elif typ=='v59_triangle':
        out.append('<polygon points="130,250 495,250 130,55" class="shape"/>');line(130,55,345,250,'shape');text(110,275,'A');text(500,275,'B');text(110,48,'C');text(345,275,'P')
    elif typ=='v59_tangent':
        out.append('<circle cx="240" cy="155" r="95" class="shape"/>');line(240,155,520,155);line(520,155,290,75,'shape');text(230,175,'O');text(525,175,'P');text(290,65,'T')
    elif typ in ('v59_abs','v59_parabola','v59_piecewise'):
        line(80,170,540,170);line(310,25,310,290)
        if typ=='v59_abs':
            out.append('<polyline points="100,70 210,215 405,215 520,70" fill="none" stroke="#2563eb" stroke-width="3"/>');text(270,243,'평평한 구간')
        elif typ=='v59_parabola':
            pts=[]
            for i in range(101):
                x=(i-50)/13; y=x*x;pts.append(f'{310+x*45:.1f},{230-y*12:.1f}')
            out.append('<polyline points="'+' '.join(pts)+'" fill="none" stroke="#2563eb" stroke-width="3"/>')
            if 'line' in spec:line(85,115,535,115,'shape')
        else:
            line(100,245,310,135,'shape');line(310,135,520,65,'shape')
    elif typ=='v59_dyck':
        for i in range(9):
            line(120+40*i,40,120+40*i,280);line(120,40+30*i,440,40+30*i)
        line(120,280,440,40,'shape');text(450,45,'y=x')
    out.append('</svg>');return ''.join(out).encode('utf-8')



# ===== 6.0: senior high school reasoning bank / filtered olympiad =====
def v60_hard(grade, topic, difficulty, rng, avoid=()):
    if difficulty != '어려움' or grade not in ('고2','고3'): return None
    from math import comb, factorial
    from fractions import Fraction
    bank=[]
    def add(tag,q,ans,why,diagram=None):
        bank.append(('v60_'+grade+'_'+topic+'_'+tag,q,Rational(ans),why,diagram))
    a=rng.randint(2,6); b=rng.randint(2,7); c=rng.randint(2,5)
    if topic=='수열':
        n=rng.randint(8,17); d=rng.randint(2,8); first=rng.randint(2,10)
        add('arithmetic_inverse',f'등차수열의 첫째항이 {first}, 공차가 양의 정수이고 제{n}항까지의 합이 {n*first+d*n*(n-1)//2}이다. 제{n+3}항과 제{n-2}항의 차를 구하시오.',5*d,'등차수열의 합으로 공차를 먼저 복원한다. 두 항의 차는 공차의 5배이다.')
        n=rng.randint(7,12); r=rng.randint(2,4); u=rng.randint(1,5)
        add('geometric_telescoping',f'a₁={u}, aₙ₊₁={r}aₙ인 수열에서 Σ(k=1부터 {n}까지) (aₖ₊₁−aₖ)/aₖ₊₁의 값을 구하시오.',Fraction(n*(r-1),r),'각 항이 1−1/r로 같다는 사실을 이용한다.')
        n=rng.randint(9,16); k=rng.randint(3,n-2)
        add('sum_difference',f'수열의 부분합 Sₙ=n³−{a}n²+{b}n이다. aₙ이 {k}번째 항일 때 aₖ−aₖ₋₁을 구하시오.',6*k-6-2*a,'aₙ=Sₙ−Sₙ₋₁을 만든 뒤 인접 항의 차를 계산한다.')
        n=rng.randint(8,15); d=rng.randint(2,6)
        add('arithmetic_pair_constraints',f'등차수열에서 a₃+a₇={2*a+8*d}, a₅+a₉={2*a+12*d}이다. a₂₀−a₁₀을 구하시오.',10*d,'두 식을 빼 공차를 찾고, 필요한 항의 차만 계산한다.')
        n=rng.randint(6,11); t=rng.randint(2,5)
        add('recursive_invariant',f'a₁={t}, aₙ₊₁=2aₙ+2ⁿ이다. aₙ을 구하시오. (정수로 답하시오)',(t+n-1)*2**(n-1),'bₙ=aₙ/2ⁿ⁻¹로 놓으면 bₙ₊₁=bₙ+1이 된다.')
        n=rng.randint(8,14); d=rng.randint(2,6)
        add('alternating_arithmetic',f'aₙ={a}+(n−1)×{d}인 등차수열에 대해 a₁−a₂+a₃−a₄+⋯−a{2*(n//2)}의 값을 구하시오.',-(n//2)*d,'인접한 두 항을 짝지으면 각각 −d가 된다.')
        n=rng.randint(6,12)
        add('sigma_floor',f'Σ(k=1부터 {n}까지) (⌊k/2⌋+⌈k/2⌉)의 값을 구하시오.',n*(n+1)//2,'바닥함수와 천장함수의 합이 k라는 항등식을 활용한다.')
    elif topic=='확률과 통계':
        n=rng.randint(8,13); k=rng.randint(3,5)
        add('hypergeometric',f'서로 다른 빨간 공 {n}개와 파란 공 {k}개에서 동시에 3개를 뽑는다. 정확히 파란 공 2개가 나올 확률에 {comb(n+k,3)}을 곱한 값을 구하시오.',comb(k,2)*n,'전체 조합에 확률을 곱하면 유리한 경우의 수가 남는다.')
        n=rng.randint(8,14); r=rng.randint(3,5)
        add('nonadjacent_selection',f'1부터 {n}까지의 정수 중 서로 이웃하는 수가 없도록 {r}개를 고르는 방법의 수를 구하시오.',comb(n-r+1,r),'선택한 순서에서 강제 간격을 제거하여 조합으로 바꾼다.')
        n=rng.randint(7,12); k=rng.randint(2,4)
        add('conditional_urn',f'상자에 빨간 공 {n}개, 파란 공 {k}개가 있다. 비복원으로 두 개를 뽑았을 때 적어도 하나가 파란 공일 확률에 {comb(n+k,2)}을 곱한 값을 구하시오.',comb(n+k,2)-comb(n,2),'여사건인 빨간 공 두 개를 빼는 방식으로 계산한다.')
        n=rng.randint(6,11)
        add('variance_shift',f'자료 x₁,…,x_{n}의 평균은 {a}, 분산은 {b}이다. 새 자료 yᵢ={c}xᵢ−{a}의 분산을 구하시오.',c*c*b,'평행이동은 분산을 바꾸지 않고 배율 c는 분산을 c²배 한다.')
        n=rng.randint(8,14); r=rng.randint(3,5)
        add('exactly_two',f'동전을 {n}번 던질 때 앞면이 정확히 {r}번 나올 확률에 2^{n}을 곱한 값을 구하시오.',comb(n,r),'독립 시행의 이항분포에서 확률은 C(n,r)/2ⁿ이다.')
        n=rng.randint(7,12)
        add('derangement_two',f'서로 다른 {n}명을 일렬로 세운다. 지정된 두 사람 A,B가 모두 자신의 원래 자리에 서지 않는 배열의 수는?',factorial(n)-2*factorial(n-1)+factorial(n-2),'포함배제로 A 고정, B 고정, 둘 다 고정을 제외한다.')
        n=rng.randint(8,14)
        add('three_set_inclusion',f'학생 {n+20}명 중 수학을 선택한 학생 {n+4}명, 과학을 선택한 학생 {n+3}명이고 둘 다 선택한 학생이 {a}명이다. 두 과목 중 어느 것도 선택하지 않은 학생 수를 구하시오.',n+20-(n+4)-(n+3)+a,'포함배제로 합집합을 구한 후 전체에서 뺀다.')
    elif topic=='함수':
        h=rng.randint(2,6); k=rng.randint(1,6)
        add('inverse_restricted',f'f(x)=(x−{h})²+{k} (x≥{h})일 때 f⁻¹({k+25})−f⁻¹({k+4})의 값을 구하시오.',3,'역함수에서 정의역 제한 때문에 양의 제곱근을 취한다.',{'type':'v59_parabola'})
        p=rng.randint(2,5); q=rng.randint(1,5)
        add('composition_sum',f'f(x)={p}x+{q}, g(x)=x²−{a}이다. f(g(x))=g(f(x))의 서로 다른 실근의 합을 구하시오.',Fraction(-2*p*q,p*p-p),'전개 후 이차항과 일차항의 계수로 근의 합을 구한다.')
        h=rng.randint(2,6); k=rng.randint(2,5)
        add('absolute_minimum',f'f(x)=|x−{h}|+|x+{k}|이다. f(x)의 최솟값을 구하시오.',h+k,'두 꺾임점 사이에서 삼각부등식의 등호가 성립한다.',{'type':'v59_abs'})
        x=rng.randint(2,6); t=rng.randint(2,5)
        add('rational_inverse',f'f(x)=({x}x+1)/(x+{t})이다. f(x)=2의 해가 유일하다고 할 때 그 해를 구하시오.',Fraction(2*t-1,x-2) if x!=2 else 0,'양변에 분모를 곱하되 분모가 0인 해는 제외한다.') if x!=2 else None
        h=rng.randint(2,5)
        add('graph_intersections',f'y=x²−{h*h}와 y={a}의 교점 두 개 사이의 거리의 제곱을 구하시오.',4*(h*h+a),'x좌표의 차를 이용한다.',{'type':'v59_parabola','line':a})
        p=rng.randint(2,5); q=rng.randint(2,6)
        add('piecewise_continuity',f'f(x)는 x<{p}에서 3x+{q}, x≥{p}에서 kx−{q}이다. x={p}에서 연속이 되도록 하는 k를 구하시오.',Fraction(3*p+2*q,p),'양쪽 함수값을 일치시킨다.',{'type':'v59_piecewise'})
    elif topic in ('미적분Ⅰ','미적분 응용'):
        p=rng.randint(2,6); q=rng.randint(2,5)
        add('tangent_extremum',f'f(x)=x³−3×{p*p}x+{q}이다. 극댓값과 극솟값의 차를 구하시오.',4*p**3,'도함수의 영점 ±p에서의 함숫값 차를 계산한다.',{'type':'v59_parabola'})
        a=rng.randint(2,5); b=rng.randint(2,6)
        add('integral_area',f'두 곡선 y={a}x와 y=x²가 둘러싸는 영역의 넓이에 6을 곱한 값을 구하시오.',a**3,'교점 0,a 사이에서 위 함수와 아래 함수를 적분한다.',{'type':'v59_parabola','line':0})
        p=rng.randint(2,6)
        add('velocity_displacement',f'물체의 속도가 v(t)=3t²−{3*p*p} (0≤t≤{2*p})이다. 이 시간 동안 이동한 총거리를 구하시오.',4*p**3,'속도 부호가 t=p에서 바뀌므로 절댓값 적분을 구간별로 계산한다.')
        a=rng.randint(2,5); b=rng.randint(2,6)
        add('derivative_product',f'f(x)=x²+{a}x+{b}, g(x)=x³−{b}x이다. (fg)′(1)의 값을 구하시오.',(2+a)*(1-b)+(1+a+b)*(3-b),'곱의 미분법을 적용한다.')
        a=rng.randint(2,6)
        add('integral_parameter',f'f(x)=x²−{a*a}이고 ∫(0부터 k까지) f(x)dx=0이다. 양수 k를 구하시오. (정답은 k²의 값)',3*a*a,'k³/3−a²k=0을 인수분해해 양의 해를 찾는다.')
        p=rng.randint(2,6)
        add('slope_secant',f'f(x)=x³−{p}x²이다. x=0과 x={p+2}를 잇는 할선의 기울기를 구하시오.',(p+2)**2-p*(p+2),'두 점의 함수값 차를 x좌표 차로 나눈다.')
        a=rng.randint(2,6); b=rng.randint(2,5)
        add('max_area_rectangle',f'가로가 x, 세로가 {a}−x인 직사각형의 넓이를 A(x)라 한다. A(x)의 최댓값에 4를 곱한 값을 구하시오.',a*a,'A(x)는 아래로 볼록한 이차식이므로 꼭짓점에서 최대이다.',{'type':'v59_rectangle','a':a,'b':a})
    if not bank: return None
    unused=[x for x in bank if x[0] not in avoid]
    fam,q,ans,why,diagram=rng.choice(unused or bank)
    return dict(question=q,answer=[ans],explanation=why,signature=hashlib.sha256((fam+q).encode()).hexdigest(),family=fam,grade=grade,topic=topic,difficulty=difficulty,diagram=diagram,source_label='MathMate 자체 제작 · 고난도 추론형',source_url=None)


def v60_olympiad(grade,difficulty,rng,avoid=()):
    if difficulty!='어려움' or grade not in ('고1','고2','고3'):return None
    from math import comb, factorial
    bank=[]
    def add(tag,q,ans,why,diagram=None):bank.append(('v60_ol_'+grade+'_'+tag,q,Rational(ans),why,diagram))
    n=rng.randint(8,13)
    add('dyck_paths',f'{n}×{n} 격자에서 (0,0)에서 ({n},{n})까지 오른쪽·위쪽으로만 움직인다. 경로가 y=x 위쪽으로 넘어가지 않는 최단 경로 수를 구하시오.',comb(2*n,n)//(n+1),'반사원리로 카탈란 수를 얻는다.',{'type':'v59_dyck','n':n})
    n=rng.randint(9,15);r=rng.randint(4,6)
    add('nonconsecutive_circular',f'원형으로 배열된 {n}개의 자리에서 서로 이웃한 두 자리를 동시에 고르지 않으면서 {r}자리를 선택하는 방법의 수를 구하시오.',n*comb(n-r-1,r-1)//r,'원형에서 인접 금지 조건을 간격 분배로 바꾸면 n/r×C(n−r−1,r−1)이다.')
    n=rng.randint(8,13)
    n=rng.randint(9,16);r=rng.randint(3,5)
    add('stars_bars_upper',f'음이 아닌 정수 x,y,z가 x+y+z={n}, x≤{r}를 만족하는 순서쌍 (x,y,z)의 개수를 구하시오.',comb(n+2,2)-comb(n-r+1,2),'전체 별과 막대에서 x≥r+1인 경우를 뺀다.')
    n=rng.randint(8,15)
    add('permutations_fixed',f'서로 다른 {n}명 중 지정된 세 사람 A,B,C가 모두 원래 위치에 있지 않도록 일렬로 배열하는 방법의 수는?',factorial(n)-3*factorial(n-1)+3*factorial(n-2)-factorial(n-3),'포함배제 원리로 세 사람의 고정 여부를 계산한다.')
    n=rng.randint(10,18);r=rng.randint(3,6)
    add('lattice_obstacle',f'격자 (0,0)에서 ({n},{n})까지 오른쪽·위쪽으로만 가는 최단 경로 중 P({r},{r})를 지나지 않는 경로 수를 구하시오.',comb(2*n,n)-comb(2*r,r)*comb(2*(n-r),n-r),'전체 경로에서 P를 지나는 경로를 제외한다.',{'type':'grid','w':n,'h':n,'px':r,'py':r})
    n=rng.randint(12,20);r=rng.randint(4,7)
    n=rng.randint(7,12)
    n=rng.randint(9,15)
    add('surjection',f'{n}명의 서로 다른 학생을 이름이 붙은 세 팀에 배정하되 세 팀이 모두 비어 있지 않게 하는 방법의 수를 구하시오.',3**n-3*2**n+3,'전체 함수에서 비어 있는 팀이 있는 배정을 포함배제로 제외한다.')
    n=rng.randint(8,13)
    add('rectangle_subgrid',f'{n}×{n-2} 격자에서 격자선을 변으로 하는 직사각형 중 정사각형이 아닌 것의 개수를 구하시오.',comb(n+1,2)*comb(n-1,2)-sum((n-k+1)*(n-2-k+1) for k in range(1,n-1)),'세로·가로 격자선 두 개씩 선택한 전체 직사각형에서 각 변 길이별 정사각형을 뺀다.')
    unused=[x for x in bank if x[0] not in avoid]
    fam,q,ans,why,diagram=rng.choice(unused or bank)
    return dict(question=q,answer=[ans],explanation=why,signature=hashlib.sha256((fam+q).encode()).hexdigest(),family=fam,grade=grade,topic='수학올림피아드',difficulty=difficulty,diagram=diagram,source_label='MathMate 자체 제작 올림피아드형 · 실제 기출 아님',source_url=None)

def v61_middle_kmo(grade, difficulty, rng, avoid=()):
    """Original KMO-inspired, multi-step numeric challenges; no historical exam text."""
    if grade not in ('중1','중2','중3'):
        return None
    from math import comb, factorial, gcd
    bank=[]
    def add(tag, q, answer, explanation, diagram=None):
        bank.append(('v61_mkmo_'+tag,q,Rational(answer),explanation,diagram))
    # Number theory: CRT + interval + coprimality
    a=rng.choice([5,7,11]); b=rng.choice([8,9,13]); L=a*b
    low=rng.randint(3,6)*L; high=low+rng.randint(15,24)*L
    vals=[v for v in range(low,high+1) if v%a==a-1 and v%b==b-1 and gcd(v,6)==1]
    add('crt_coprime',f'{low} 이상 {high} 이하의 정수 N 중 N을 {a}로 나누면 나머지가 {a-1}, {b}로 나누면 나머지가 {b-1}이며, N과 6이 서로소인 N의 개수를 구하시오.',len(vals),f'N+1은 {L}의 배수이다. N={L}t−1로 놓고 구간을 제한한 뒤 2와 3의 배수인 경우를 제외하면 {len(vals)}개이다.')
    # Divisor-count inversion with a divisibility constraint
    p,q=rng.sample([2,3,5,7],2); exponent=rng.randint(3,5); n=(p**exponent)*(q**2)
    add('divisor_constraints',f'N={p}⁽{exponent}⁾×{q}²의 양의 약수 d 중 d가 {p*p}의 배수이면서 N/d가 {q}의 배수인 것의 개수를 구하시오.',(exponent-1)*2,f'd={p}^i{q}^j로 쓰면 2≤i≤{exponent}, 0≤j≤1이다. 따라서 ({exponent}−1)×2={(exponent-1)*2}개이다.')
    # Counting onto functions with forbidden individual assignments
    n=rng.randint(7,10)
    ans=2*(3**(n-1)-2*2**(n-1)+1)
    add('onto_forbidden',f'서로 다른 {n}명을 A,B,C 세 팀에 배정한다. 세 팀은 모두 비어 있지 않아야 하고, 지정된 학생 한 명은 A팀에 들어갈 수 없다. 배정 방법의 수를 구하시오.',ans,f'지정된 학생은 B 또는 C 중 하나를 선택한다. 나머지 학생들이 A와 아직 등장하지 않은 팀에 각각 적어도 한 명씩 들어가야 하므로 2×(3^{n-1}−2×2^{n-1}+1)={ans}이다.')
    # Lattice paths via two ordered checkpoints and avoiding one point
    w=rng.randint(9,13); h=rng.randint(8,12)
    A=(2,2); B=(w-2,h-2); forbidden=(w//2,h//2)
    total=comb(4,2)*comb((B[0]-A[0])+(B[1]-A[1]),B[0]-A[0])*comb(4,2)
    via=comb(4,2)*comb((forbidden[0]-A[0])+(forbidden[1]-A[1]),forbidden[0]-A[0])*comb((B[0]-forbidden[0])+(B[1]-forbidden[1]),B[0]-forbidden[0])*comb(4,2)
    add('two_checkpoints_avoid',f'격자에서 (0,0)에서 ({w},{h})까지 오른쪽 또는 위쪽으로만 최단 이동한다. A(2,2)와 B({B[0]},{B[1]})를 모두 지나되 P({forbidden[0]},{forbidden[1]})는 지나지 않는 경로의 수를 구하시오.',total-via,f'A와 B를 지나는 경로는 구간별 조합을 곱해 {total}개이다. 그중 P도 지나는 {via}개를 빼면 {total-via}개이다.',{'type':'grid','w':w,'h':h,'px':forbidden[0],'py':forbidden[1]})
    # Permutations with exact adjacency of designated pair but forbidden adjacency with third
    n=rng.randint(8,11)
    ans=2*factorial(n-1)-4*factorial(n-2)
    add('adjacent_pair_exclusion',f'서로 다른 {n}명을 일렬로 세울 때 A와 B는 반드시 이웃하고, C는 A와도 B와도 이웃하지 않도록 세우는 방법의 수를 구하시오.',ans,f'AB를 한 덩어리로 보면 2×({n-1})!가지이다. C가 그 덩어리에 붙는 경우 4×({n-2})!가지를 빼서 {ans}이다.')
    # Distinct digits divisible by 5 with position restriction
    # count by combinatorics, no large enumeration
    # digits 0..7, 5-digit numbers, ending 0 or 5, first digit even
    import itertools
    nums=[t for t in itertools.permutations(range(8),5) if t[0] in (2,4,6) and t[-1] in (0,5) and sum(t)%3==0]
    add('digit_mod3',f'0부터 7까지의 숫자 중 서로 다른 5개를 골라 다섯 자리 자연수를 만든다. 첫 자리는 짝수이고, 수는 15의 배수여야 한다. 가능한 수의 개수를 구하시오.',len(nums),f'끝자리는 0 또는 5이고 각 자릿수의 합이 3의 배수여야 한다. 첫 자리는 2,4,6 중 하나로 제한하여 경우를 나누면 {len(nums)}개이다.')
    # geometry via Pick theorem on lattice triangle with interior lattice points
    a=rng.choice([6,8,10]); b=rng.choice([6,9,12]); c=rng.choice([2,3,4]);
    # vertices (0,0),(a,0),(c,b): boundary a+gcd(a-c,b)+gcd(c,b)
    boundary=a+gcd(a-c,b)+gcd(c,b); interior=(a*b-boundary+2)//2
    add('pick_lattice_triangle',f'좌표평면에서 꼭짓점이 (0,0), ({a},0), ({c},{b})인 삼각형의 내부에 있는 정수 격자점의 개수를 구하시오. (변 위의 점은 제외)',interior,f'넓이는 {a*b}/2, 경계 격자점 수는 {a}+gcd({a-c},{b})+gcd({c},{b})={boundary}이다. 픽의 정리 S=I+B/2−1에서 I={interior}이다.')
    # sum of floor of rational multiples, using coprime residues
    m=rng.choice([7,9,11,13]); a=rng.choice([2,3,4,5]);
    while gcd(m,a)!=1:a+=1
    ans=sum((a*k)//m for k in range(1,m))
    add('floor_sum',f'⌊x⌋는 x 이하의 최대 정수이다. S=⌊{a}/{m}⌋+⌊{2*a}/{m}⌋+⋯+⌊{a*(m-1)}/{m}⌋의 값을 구하시오.',ans,f'{a}와 {m}은 서로소이므로 나머지가 1부터 {m-1}까지 한 번씩 나타난다. S=({a}−1)({m}−1)/2={ans}이다.')
    # combinations with exact three pair intersections via PIE
    n=rng.randint(10,15); k=rng.randint(4,6)
    # subsets with no three consecutive selected via DP exact
    from functools import lru_cache
    @lru_cache(None)
    def dp(i,remaining,run):
        if i==n:return int(remaining==0)
        res=dp(i+1,remaining,0)
        if remaining and run<2:res+=dp(i+1,remaining-1,run+1)
        return res
    ans=dp(0,k,0)
    add('no_three_consecutive',f'1부터 {n}까지의 정수 중 {k}개를 고를 때, 연속된 세 정수를 동시에 고르는 일이 없도록 고르는 방법의 수를 구하시오.',ans,f'왼쪽부터 선택 여부를 결정하면서 직전 연속 선택 수가 0,1,2인 상태를 기록하는 점화식으로 계산하면 {ans}개이다.')
    # Number theory: exponent of prime in factorial ratio
    n=rng.randint(30,55); r=rng.randint(10,20); p=rng.choice([2,3,5]);
    def valuation(x):
        z=0
        while x:x//=p;z+=x
        return z
    ans=valuation(n)-valuation(r)-valuation(n-r)
    add('binomial_valuation',f'이항계수 C({n},{r})를 소인수분해할 때 소수 {p}의 지수를 구하시오.',ans,f'르장드르 공식으로 v_{p}(n!)−v_{p}(r!)−v_{p}((n−r)!)을 계산하면 {ans}이다.')
    # Combinatorial geometry: non-crossing selection of chords? intersections of diagonals with no triple concurrence
    n=rng.randint(9,14)
    add('diagonal_intersections',f'원 위에 {n}개의 점을 놓고 모든 두 점을 현으로 연결한다. 원 내부에서 서로 다른 세 현이 한 점에서 만나지 않도록 점들을 놓았을 때, 현들의 내부 교점은 몇 개인가?',comb(n,4),f'서로 다른 네 점을 택할 때마다 대각선 형태의 두 현이 내부에서 정확히 한 번 교차한다. 따라서 C({n},4)={comb(n,4)}이다.')
    # integer solutions with pairwise inequality using shift
    n=rng.randint(22,35); low=rng.randint(3,6)
    # x>y>z>=low, x+y+z=n, enumerate independently
    triples=[(x,y,n-x-y) for x in range(low+2,n+1) for y in range(low+1,x) if low<=n-x-y<y]
    add('strict_partition_three',f'정수 x,y,z가 x>y>z≥{low}, x+y+z={n}을 만족하는 순서쌍 (x,y,z)의 개수를 구하시오.',len(triples),f'z를 {low}부터 시작해 y는 z+1 이상, x는 y+1 이상인 범위에서 합 조건을 적용하면 {len(triples)}개이다.')
    unused=[v for v in bank if v[0] not in avoid]
    fam,q,ans,why,diagram=rng.choice(unused or bank)
    return dict(question=q,answer=[ans],explanation=why,signature=hashlib.sha256((fam+q).encode()).hexdigest(),family=fam,grade=grade,topic='수학올림피아드',difficulty=difficulty,diagram=diagram,source_label='KMO 출제 영역 참고 · MathMate 자체 제작 (실제 기출 아님)',source_url='https://ipsi1.uwayapply.com/ksi/kmo/etc_file/etc_fileN34.pdf')


# ===== 6.2 Middle-school advanced: independent reasoning families =====
def middle62_hard(grade, topic, rng, avoid=()):
    if grade not in ('중1','중2','중3') or topic == '수학올림피아드':
        return None
    from math import comb, factorial, gcd
    import sympy as sp
    bank=[]
    def add(tag,q,ans,why,diagram=None):
        bank.append(('m62_'+grade+'_'+topic+'_'+tag,q,sp.Rational(ans),why,diagram))
    a=rng.randint(3,8); b=rng.randint(2,6); c=rng.randint(2,5)
    if topic=='정수와 유리수':
        n=rng.randint(7,13); k=rng.randint(3,6)
        add('floor_residues',f'⌊t⌋는 t 이하의 최대 정수이다. S=⌊{n}/7⌋+⌊{2*n}/7⌋+⋯+⌊{6*n}/7⌋의 값을 구하시오. 단, {n}은 7의 배수가 아니다.',3*(n-1),f'7과 {n}은 서로소이므로 소수부분의 합은 1+2+⋯+6을 7로 나눈 값 3이다. S=3({n}−1)이다.') if n%7 else None
        add('rational_reconstruct',f'기약분수 x/y에서 분자에 {b}, 분모에 {c}를 더하면 1이 되고, 원래 분자와 분모의 합은 {2*a+b-c}이다. x를 구하시오.',a,f'x+{b}=y+{c}, x+y={2*a+b-c}를 연립하면 x={a}이다.') if a+b-c>0 and gcd(a,a+b-c)==1 else None
        d=rng.randint(5,11); p=rng.randint(2,5)
        add('numberline_distance',f'수직선에서 점 A의 좌표는 −{d}, B의 좌표는 {p}이다. 점 P가 두 점 사이에 있고 PA:PB={b}:{c}일 때 P의 좌표를 구하시오.',sp.Rational(-d*c+p*b,b+c),f'내분점 공식에 의해 P=(−{d}×{c}+{p}×{b})/({b}+{c})이다.',dict(type='m62_numberline',points=[[-d,'A'],[p,'B'],[float(sp.Rational(-d*c+p*b,b+c)),'P']]))
        x=rng.randint(2,7); y=rng.randint(3,8)
        add('absolute_minimax',f'정수 t에 대하여 |t+{x}|+|t−{y}|의 최솟값을 구하시오.',x+y,f'두 점 −{x}와 {y} 사이에 있는 모든 t에서 거리의 합이 {x+y}로 일정하다.',dict(type='m62_numberline',points=[[-x,'A'],[y,'B']]))
        add('modular_fraction',f'양의 정수 n에 대하여 ({a}n+{b})/n이 정수이고 n이 {b}보다 작을 때, 가능한 n의 개수를 구하시오.',sum(1 for t in range(1,b) if b%t==0),f'식은 {a}+{b}/n이므로 n은 {b}의 양의 약수 중 {b} 미만이어야 한다.')
    elif topic=='일차방정식':
        x=rng.randint(4,10); price=rng.randint(800,1600)//100*100; fixed=rng.randint(2000,4500)//100*100
        add('taxi_intersection',f'두 택시 요금제가 있다. A는 기본요금 {fixed}원에 1km당 {price}원, B는 기본요금 {fixed+price*x}원에 1km당 요금이 없다. 두 요금이 같아지는 거리는 몇 km인가?',x,f'{fixed}+{price}t={fixed+price*x}를 풀면 t={x}이다.',dict(type='m62_lines',lines=[[price,fixed,'A'],[0,fixed+price*x,'B']],xmax=x+3))
        total=rng.randint(22,45); k=rng.randint(3,8); t=rng.randint(3,7)
        add('age_reverse',f'현재 아버지 나이는 아들 나이의 {k}배이다. {t}년 후 아버지 나이는 아들 나이의 {k-1}배가 된다. 현재 아들 나이를 구하시오.',(k-2)*t,f'현재 아들 나이를 x라 하면 {k}x+{t}=({k-1})(x+{t}), x=({k-2})×{t}이다.')
        x=rng.randint(3,8); y=rng.randint(4,10)
        add('fraction_linear',f'(x−{x})/{b}=(x+{y})/{c}일 때 x의 값을 구하시오. 단, {b}와 {c}는 서로 다르다.',sp.Rational(c*x+b*y,c-b),f'{c}(x−{x})={b}(x+{y})이므로 x=({c*x}+{b*y})/({c-b})이다.') if b!=c else None
        n=rng.randint(4,9); t=rng.randint(2,5)
        add('balance_weight',f'양팔저울 왼쪽에 같은 무게의 구슬 {n}개와 {a}g 추, 오른쪽에 구슬 {n+t}개와 {b}g 추가 있다. 저울이 평형일 때 구슬 한 개의 무게(g)를 구하시오.',sp.Rational(a-b,t),f'{n}x+{a}=({n+t})x+{b}이므로 x=({a-b})/{t}이다.') if a>b else None
        add('parameter_identity',f'방정식 {a}(x−k)+{b}x=({a+b})x−{a*c}가 모든 실수 x에서 참이다. k²의 값을 구하시오.',c*c,f'항등식의 상수항 비교로 {a}k={a*c}, k={c}이다.')
    elif topic=='비와 비율':
        x=rng.randint(4,9); y=rng.randint(3,7)
        add('mixture_inverse',f'농도 {a*2}% 소금물 {x*100}g과 농도 {b*2}% 소금물 {y*100}g을 섞었다. 혼합 소금물의 농도(%)를 구하시오.',sp.Rational(2*a*x+2*b*y,x+y),f'소금의 질량 합을 전체 질량으로 나누면 ({2*a}×{x}+{2*b}×{y})/({x+y})%이다.',dict(type='m62_bars',parts=[x,y],labels=[f'{2*a}%',f'{2*b}%']))
        t=rng.randint(3,7)
        add('ratio_after_transfer',f'두 상자 A, B의 구슬 수의 비는 {a}:{b}이고 총 {a+b}×{t}개이다. A에서 B로 {t}개 옮긴 뒤 B에 있는 구슬은 몇 개인가?',b*t+t,f'처음 B에 {b*t}개 있으므로 옮긴 후 {b*t+t}개이다.',dict(type='m62_bars',parts=[a,b],labels=['A','B']))
        up=rng.choice([10,20,25]); down=rng.choice([10,20,25]); v=rng.randint(4,9)*1000
        add('successive_percent',f'{v}원인 상품을 {up}% 인상한 뒤 {down}% 할인했다. 최종 가격은 몇 원인가?',sp.Rational(v*(100+up)*(100-down),10000),f'{v}×(1+{up}/100)×(1−{down}/100)으로 계산한다.')
        u=rng.randint(2,5); v=rng.randint(3,6)
        add('similar_triangle_ratio',f'그림에서 DE∥BC, AD:DB={u}:{v}이고 삼각형 ADE의 넓이가 {u*u*7}cm²이다. 사다리꼴 DBCE의 넓이를 구하시오.',7*((u+v)**2-u*u),f'닮음비가 {u}:({u+v})이므로 넓이비는 {u*u}:{(u+v)**2}이다.',dict(type='m62_similar',u=u,v=v))
        add('reverse_ratio',f'A:B={a}:{b}, B:C={c}:{a}일 때 A:C를 기약한 비로 나타내면 p:q이다. p+q를 구하시오.',(a*c+b*a)//gcd(a*c,b*a),f'A:C={a*c}:{b*a}이고 최대공약수로 나누어 두 항을 더한다.')
    elif topic=='연립방정식':
        x=rng.randint(3,10); y=rng.randint(4,12); p=rng.randint(2,6); q=rng.randint(2,6)
        add('ticket_model',f'전시회 성인표는 {p*1000}원, 청소년표는 {q*1000}원이다. 총 {x+y}명이 입장해 {p*x*1000+q*y*1000}원을 받았다. 성인 관람객은 몇 명인가?',x,f'성인 x, 청소년 y로 놓고 인원 합과 총수입을 연립하면 성인은 {x}명이다.') if p!=q else None
        add('intersection_area',f'두 직선 y={p}x+{y-p*x}, y=−{q}x+{y+q*x}가 만나는 점 P에서 x축에 내린 수선의 발을 H라 한다. 삼각형 OPH의 넓이를 구하시오. O는 원점이다.',sp.Rational(x*y,2),f'두 직선의 교점은 ({x},{y})이고 삼각형 OPH의 넓이는 {x}×{y}/2이다.',dict(type='m62_lines',lines=[[p,y-p*x,'l'],[-q,y+q*x,'m']],xmax=x+3))
        s=rng.randint(2,6); t=rng.randint(2,6)
        add('digit_reverse',f'두 자리 자연수의 십의 자리 숫자는 일의 자리 숫자보다 {s} 크고, 자릿수를 바꾼 수와 원래 수의 합은 {11*(2*t+s)}이다. 원래 자연수를 구하시오.',10*(t+s)+t,f'십의 자리를 x, 일의 자리를 y로 두면 x−y={s}, x+y={2*t+s}이다.') if t+s<=9 else None
        add('parallel_infinite',f'연립방정식 {a}x+{b}y={a*c+b*2}, {2*a}x+{2*b}y=k가 무수히 많은 해를 갖도록 하는 k를 구하시오.',2*(a*c+2*b),'두 식이 정확히 같은 직선을 나타내야 하므로 오른쪽도 2배가 된다.')
        add('integer_optimization',f'정수 x,y가 2x+3y={2*a+3*b}, x≥0, y≥0을 만족할 때 x의 최댓값을 구하시오.',max([i for i in range((2*a+3*b)//2+1) if (2*a+3*b-2*i)%3==0]),'y=(합−2x)/3이 음이 아닌 정수가 되도록 x를 최대화한다.')
    elif topic=='일차함수':
        x=rng.randint(3,8); m=rng.randint(2,5); n=rng.randint(1,4)
        add('triangle_area_lines',f'두 직선 y={m}x+{n}, y=−{m}x+{2*m*x+n}와 y축으로 둘러싸인 삼각형의 넓이를 구하시오.',m*x*x,f'두 직선의 교점은 ({x},{m*x+n})이고 y축에서의 두 절편 차는 {2*m*x}이므로 넓이는 {m*x*x}이다.',dict(type='m62_lines',lines=[[m,n,'l'],[-m,2*m*x+n,'m']],xmax=x+2))
        p=rng.randint(2,5); q=rng.randint(3,8)
        add('taxi_compare',f'A요금은 기본 {p*1000}원에 1km당 {q*100}원, B요금은 기본 {p*1000+q*100*6}원에 1km당 요금이 없다. A요금이 B요금보다 저렴한 자연수 거리(km)는 몇 개인가? 단, 1km부터 10km까지 고려한다.',5,'A가 B보다 저렴하려면 거리가 6km 미만이므로 1~5km의 5개다.',dict(type='m62_lines',lines=[[q*100,p*1000,'A'],[0,p*1000+q*100*6,'B']],xmax=10))
        y=rng.randint(4,9)
        add('point_reflection',f'점 P({x},{y})를 직선 y=x에 대하여 대칭이동한 점 Q를 지나고 기울기가 −{m}인 직선의 y절편을 구하시오.',x+m*y,f'Q=({y},{x})이므로 y=−{m}x+b에 대입해 b={x+m*y}이다.',dict(type='m62_points',points=[[x,y,'P'],[y,x,'Q']],diagonal=True))
        add('intersection_parameter',f'직선 y={m}x+k와 y=−{n}x+{(m+n)*x+4}의 교점의 x좌표가 {x}일 때 k를 구하시오.',4,f'{m}×{x}+k=−{n}×{x}+{(m+n)*x+4}이므로 k=4이다.')
        add('line_area_intercept',f'직선 y=−{m}x+{m*x}와 두 좌표축으로 둘러싸인 삼각형의 넓이를 구하시오.',sp.Rational(m*x*x,2),f'x절편은 {x}, y절편은 {m*x}이므로 넓이는 {m*x*x}/2이다.',dict(type='m62_lines',lines=[[-m,m*x,'l']],xmax=x+2))
    elif topic=='확률':
        n=rng.randint(5,9); r=rng.randint(2,n-2)
        add('without_replacement_conditional',f'빨간 공 {n}개, 파란 공 {r}개에서 2개를 차례로 복원 없이 뽑는다. 첫 번째 공이 빨간 공이었다는 조건 아래 두 번째 공도 빨간 공일 확률을 구하시오.',sp.Rational(n-1,n+r-1),'첫 번째 빨간 공을 제외한 전체 공 수와 남은 빨간 공 수를 비교한다.',dict(type='m62_bars',parts=[n,r],labels=['빨강','파랑']))
        add('dice_sum_conditional',f'서로 다른 주사위 두 개를 던진다. 두 눈의 합이 {n+5} 이상일 때, 두 눈이 모두 짝수일 조건부확률을 구하시오.',sp.Rational(sum(1 for i in (2,4,6) for j in (2,4,6) if i+j>=n+5),sum(1 for i in range(1,7) for j in range(1,7) if i+j>=n+5)) if n+5<=12 else 0,'합 조건을 만족하는 36개 순서쌍 중 짝수·짝수 순서쌍을 센다.') if n+5<=12 else None
        add('geometric_probability',f'한 변의 길이가 {n}인 정사각형 안에서 한 점을 균일하게 고른다. 정사각형의 왼쪽 아래 꼭짓점을 중심으로 하는 반지름 {r}인 사분원 안에 들어갈 확률을 구하시오. 단, π=3.14로 계산하여 소수로 답하시오.',sp.Rational(314*r*r,400*n*n),f'사분원 넓이/정사각형 넓이 = 3.14×{r}²/(4×{n}²)이다.',dict(type='m62_quarter',n=n,r=r))
        k=rng.randint(3,6)
        add('hypergeometric',f'빨간 공 {n}개와 파란 공 {r}개 중 3개를 동시에 뽑는다. 빨간 공이 정확히 2개일 확률을 구하시오.',sp.Rational(comb(n,2)*r,comb(n+r,3)),f'전체 경우 C({n+r},3), 유리한 경우 C({n},2)×{r}이다.',dict(type='m62_bars',parts=[n,r],labels=['빨강','파랑']))
        add('at_least_one',f'빨간 공 {n}개와 파란 공 {r}개 중 3개를 동시에 뽑을 때 빨간 공이 적어도 한 개 포함될 확률을 구하시오.',1-sp.Rational(comb(r,3),comb(n+r,3)),f'여사건은 세 공 모두 파란색인 경우이므로 1−C({r},3)/C({n+r},3)이다.')
    elif topic=='인수분해':
        x=rng.randint(2,6); y=rng.randint(2,6)
        add('hidden_substitution',f'다항식 (x²+{a}x)²−{(2*y)**2}를 인수분해했을 때, x²의 계수가 1인 두 이차식의 상수항의 곱을 구하시오.',-4*y*y,f'T=x²+{a}x로 치환하면 (T−{2*y})(T+{2*y})이므로 상수항 곱은 −{4*y*y}이다.')
        add('difference_of_squares_area',f'그림에서 큰 정사각형의 한 변은 x+{a}, 작은 정사각형의 한 변은 x−{b}이다. 두 넓이의 차를 px+q로 나타낼 때 p+q를 구하시오.',2*(a+b)+a*a-b*b,f'(x+{a})²−(x−{b})²=({a+b})(2x+{a-b})이다.',dict(type='m62_nested_squares',a=a,b=b))
        add('root_condition_factor',f'다항식 x²+px+{a*b}가 x−{a}를 인수로 가질 때, p²−4×{a*b}의 값을 구하시오.',(a-b)**2,f'나머지정리로 {a*a}+{a}p+{a*b}=0이므로 p=−({a+b}), 판별식은 ({a-b})²이다.')
        add('integer_factor_count',f'정수 a,b가 a>b≥1, ab={a*b}를 만족한다. 이때 x²−(a+b)x+ab의 서로 다른 인수분해 형태 (x−a)(x−b)는 몇 가지인가?',sum(1 for u in range(1,math.isqrt(a*b)+1) if (a*b)%u==0 and u!=(a*b)//u),f'{a*b}의 양의 약수쌍 중 서로 다른 두 수로 이루어진 쌍을 센다.')
        add('symmetric_factor',f'x+y={a+b}, xy={a*b}일 때 x³+y³의 값을 구하시오.',a**3+b**3,f'x³+y³=(x+y)((x+y)²−3xy)={(a+b)}×(({a+b})²−3×{a*b})이다.')
    elif topic=='이차방정식':
        x=rng.randint(3,8); y=rng.randint(2,6)
        add('rectangle_roots',f'그림의 직사각형의 두 변은 x와 x+{y}이다. 넓이가 {x*(x+y)}일 때 대각선 길이의 제곱을 구하시오.',x*x+(x+y)**2,f'변의 길이 t는 t(t+{y})={x*(x+y)}의 양의 근 {x}이다. 피타고라스 정리를 쓴다.',dict(type='m62_rectangle',w=x,h=x+y))
        add('root_shift',f'x²−{2*a}x+{a*a-b*b}=0의 두 근을 α,β라 한다. (α−β)²의 값을 구하시오.',4*b*b,f'근은 {a-b},{a+b}이므로 차의 제곱은 (2×{b})²이다.')
        add('parameter_two_roots',f'이차방정식 x²−2kx+{a*a}=0이 서로 다른 두 양의 실근을 갖는 정수 k의 최솟값을 구하시오.',a+1,f'두 양의 실근 조건은 k>0이고 판별식 4(k²−{a*a})>0이므로 k>{a}이다.')
        add('parabola_axis',f'포물선 y=x²−{2*a}x+{a*a-b*b}와 x축의 두 교점을 A,B라 한다. 선분 AB의 길이의 제곱을 구하시오.',4*b*b,f'x절편은 {a-b}, {a+b}이므로 AB=2×{b}이다.',dict(type='m62_parabola',h=a,r=b))
        add('root_reciprocal',f'x²−{a+b}x+{a*b}=0의 두 근을 α,β라 할 때 1/α+1/β의 값을 구하시오.',sp.Rational(a+b,a*b),'근과 계수 관계로 (α+β)/(αβ)를 계산한다.')
    elif topic=='경우의 수':
        w=rng.randint(5,8); h=rng.randint(4,7); px=rng.randint(1,w-1); py=rng.randint(1,h-1)
        via=comb(px+py,px)*comb(w+h-px-py,w-px)
        add('grid_avoid',f'격자에서 O(0,0)에서 B({w},{h})까지 오른쪽 또는 위쪽으로만 이동한다. P({px},{py})를 지나지 않는 최단 경로의 수를 구하시오.',comb(w+h,w)-via,f'전체 C({w+h},{w})에서 P를 지나는 C({px+py},{px})×C({w+h-px-py},{w-px})를 뺀다.',dict(type='grid',w=w,h=h,px=px,py=py))
        n=rng.randint(6,9)
        add('nonadjacent',f'서로 다른 {n}명이 한 줄로 설 때 특정한 A,B가 이웃하지 않고 양 끝에도 서지 않도록 하는 방법의 수를 구하시오.',((n-2)*(n-3)-2*(n-3))*factorial(n-2),f'A,B의 자리를 양 끝을 제외한 {n-2}개 중 서로 다르게 정한 후 나머지를 배치하고, 이웃하는 경우를 제외한다.')
        k=rng.randint(3,5)
        add('no_adjacent_subset',f'1부터 {n+3}까지의 정수 중 서로 이웃한 수 없이 {k}개를 고르는 방법의 수를 구하시오.',comb(n+4-k,k),f'고른 수를 a₁<⋯<a_{k}라 하고 bᵢ=aᵢ−(i−1)로 치환하면 C({n+4-k},{k})이다.')
        add('rectangle_count',f'가로 {w}칸, 세로 {h}칸으로 이루어진 격자에서 서로 다른 크기의 직사각형을 포함해 만들 수 있는 직사각형은 모두 몇 개인가?',comb(w+1,2)*comb(h+1,2),f'세로선 {w+1}개 중 2개, 가로선 {h+1}개 중 2개를 고른다.',dict(type='m62_grid_rect',w=w,h=h))
        add('roundtable_noadj',f'서로 다른 {n}명이 원탁에 앉을 때 A와 B가 서로 이웃하지 않는 원형 배열의 수를 구하시오.',factorial(n-1)-2*factorial(n-2),f'전체 ({n-1})!에서 A,B를 묶은 2×({n-2})!을 뺀다.')
    fresh=[p for p in bank if p[0] not in avoid]
    if not bank:return None
    fam,q,ans,why,diagram=rng.choice(fresh or bank)
    return dict(question=q,answer=[ans],explanation=why,signature=hashlib.sha256((fam+'|'+q).encode()).hexdigest(),family=fam,grade=grade,topic=topic,difficulty='어려움',diagram=diagram,source_label='MathMate 자체 제작 중등 심화 · 기출 아님',source_url=None)


def middle62_svg(spec):
    if not spec or not str(spec.get('type','')).startswith('m62_'):return None
    import html as _html
    typ=spec['type']
    out=['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 660 360"><rect width="660" height="360" fill="white"/><style>text{font:16px sans-serif;fill:#20304a}.line{stroke:#2563eb;stroke-width:3;fill:none}.thin{stroke:#a5b4c8;stroke-width:1.5;fill:none}.fill{stroke:#2563eb;stroke-width:2;fill:#dbeafe}</style>']
    def ln(x,y,X,Y,cls='line'):out.append(f'<line x1="{x:.2f}" y1="{y:.2f}" x2="{X:.2f}" y2="{Y:.2f}" class="{cls}"/>')
    def txt(x,y,t):out.append(f'<text x="{x:.2f}" y="{y:.2f}">{_html.escape(str(t))}</text>')
    def dot(x,y):out.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="5" fill="#e86d32"/>')
    if typ=='m62_numberline':
        ps=spec['points'];lo=min(p[0] for p in ps)-2;hi=max(p[0] for p in ps)+2
        f=lambda v:90+480*(v-lo)/(hi-lo)
        ln(70,175,590,175,'thin')
        for v in range(math.floor(lo),math.ceil(hi)+1):
            if (hi-lo)<=30:ln(f(v),169,f(v),181,'thin')
        for v,label in ps:dot(f(v),175);txt(f(v)-10,153,label);txt(f(v)-18,211,f'{v:g}')
    elif typ=='m62_lines':
        lines=spec['lines'];mx=spec.get('xmax',10); values=[m*t+z for m,z,_ in lines for t in (0,mx)]; low=min(values); high=max(values);pad=max((high-low)*.15,1);low-=pad;high+=pad
        X=lambda x:100+470*x/mx;Y=lambda y:290-230*(y-low)/(high-low)
        ln(90,Y(0),585,Y(0),'thin');ln(X(0),45,X(0),310,'thin');txt(590,Y(0),'x');txt(88,40,'y')
        for m,z,label in lines:ln(X(0),Y(z),X(mx),Y(m*mx+z));txt(X(mx)-10,Y(m*mx+z)-8,label)
    elif typ=='m62_points':
        ps=spec['points'];mx=max(max(abs(p[0]),abs(p[1])) for p in ps)+2;u=115/mx
        ln(90,180,570,180,'thin');ln(330,325,330,35,'thin')
        if spec.get('diagonal'):ln(200,310,460,50,'thin')
        for x,y,l in ps:dot(330+x*u,180-y*u);txt(338+x*u,173-y*u,f'{l}({x},{y})')
    elif typ=='m62_similar':
        A=(320,45);B=(100,300);C=(565,300);r=spec['u']/(spec['u']+spec['v']);D=(A[0]+(B[0]-A[0])*r,A[1]+(B[1]-A[1])*r);E=(A[0]+(C[0]-A[0])*r,A[1]+(C[1]-A[1])*r)
        out.append(f'<polygon points="{A[0]},{A[1]} {B[0]},{B[1]} {C[0]},{C[1]}" class="fill"/>');ln(*D,*E)
        for x,y,t in [(A[0],A[1]-12,'A'),(B[0]-18,B[1]+20,'B'),(C[0]+10,C[1]+20,'C'),(D[0]-25,D[1],'D'),(E[0]+10,E[1],'E')]:txt(x,y,t)
        txt(130,120,f'AD:DB={spec["u"]}:{spec["v"]}')
    elif typ=='m62_bars':
        parts=spec['parts'];labels=spec['labels'];total=sum(parts);start=100
        for val,lab in zip(parts,labels):
            width=460*val/total;out.append(f'<rect x="{start:.2f}" y="130" width="{width:.2f}" height="80" class="fill"/>');txt(start+width/2-20,165,lab);txt(start+width/2-12,195,val);start+=width
    elif typ=='m62_nested_squares':
        out.append('<rect x="160" y="50" width="260" height="260" class="fill"/><rect x="220" y="110" width="140" height="140" fill="white" stroke="#e86d32" stroke-width="3"/>');txt(190,40,f'x+{spec["a"]}');txt(245,105,f'x−{spec["b"]}')
    elif typ=='m62_rectangle':
        w=spec['w'];h=spec['h'];out.append('<rect x="160" y="70" width="330" height="230" class="fill"/>');ln(160,70,490,300);txt(290,325,w);txt(505,180,h)
    elif typ=='m62_parabola':
        h=spec['h'];r=spec['r'];X=lambda x:330+(x-h)*65/r;Y=lambda y:140-y*20/r
        ln(60,140,610,140,'thin');ln(X(0),20,X(0),330,'thin');pts=[]
        for i in range(101):
            x=h-1.8*r+3.6*r*i/100;y=(x-h)**2-r*r
            pts.append(f'{X(x):.2f},{Y(y):.2f}')
        out.append('<polyline points="'+' '.join(pts)+'" class="line"/>')
        for x,lab in [(h-r,'A'),(h+r,'B')]:dot(X(x),140);txt(X(x)+7,130,lab)
        dot(X(h),Y(-r*r));txt(X(h)+10,Y(-r*r)+10,'V')
    elif typ=='m62_quarter':
        n=spec['n'];r=spec['r'];unit=235/n;ox=155;oy=300
        out.append(f'<rect x="{ox}" y="{oy-235}" width="235" height="235" class="fill"/>')
        out.append(f'<path d="M {ox} {oy} L {ox+r*unit} {oy} A {r*unit} {r*unit} 0 0 0 {ox} {oy-r*unit} Z" fill="#f9b65d" fill-opacity=".7" stroke="#d97706" stroke-width="2"/>');txt(400,185,f'한 변 {n}');txt(160,322,f'반지름 {r}')
    elif typ=='m62_grid_rect':
        w=spec['w'];h=spec['h'];u=min(35,250/max(w,h));ox=140;oy=300
        for i in range(w+1):ln(ox+i*u,oy,ox+i*u,oy-h*u,'thin')
        for j in range(h+1):ln(ox,oy-j*u,ox+w*u,oy-j*u,'thin')
        txt(ox+w*u+10,oy,f'{w}칸');txt(ox-60,oy-h*u,f'{h}칸')
    out.append('</svg>');return ''.join(out).encode('utf-8')



# ===== 6.3 Olympiad hard bank: independent KMO/IMO-inspired constructions =====
def olympiad63_hard(grade, difficulty, rng, avoid=()):
    """Original, automatically gradable hard olympiad tasks; NOT copied past papers."""
    if grade not in ('중1','중2','중3','고1','고2','고3') or difficulty != '어려움':
        return None
    from math import comb, gcd, factorial
    from functools import lru_cache
    from itertools import permutations, combinations
    bank = []
    def add(tag, q, answer, why, diagram=None):
        bank.append(('v63_ol_' + tag, q, Rational(answer), why, diagram))

    # 1. Simultaneous quadratic congruences, solved by periodicity/CRT.
    a, b = rng.sample([5, 7, 11, 13], 2)
    ra, rb = rng.choice([1, 4]), rng.choice([1, 4])
    lo = rng.randint(300, 600)
    hi = lo + rng.randint(1700, 2700)
    valid = [x for x in range(lo, hi + 1) if x*x % a == ra % a and x*x % b == rb % b]
    add('quadratic_crt', f'{lo}≤n≤{hi}인 자연수 n 중 n²을 {a}로 나눈 나머지가 {ra%a}, {b}로 나눈 나머지가 {rb%b}인 n의 개수를 구하시오.', len(valid),
        f'각 소수에 대한 제곱 합동식의 해를 먼저 찾는다. 중국인의 나머지 정리로 주기 {a*b}의 잔여류를 결합하고 [{lo},{hi}]에 속하는 수를 세면 {len(valid)}개이다.')

    # 2. Permutations of a multiset with NO equal adjacent letters (DP).
    counts = rng.choice([(3,3,2,2), (3,3,3,2), (4,3,2,2)])
    @lru_cache(None)
    def count_words(state, last):
        if not any(state): return 1
        return sum(count_words(tuple(state[j]-1 if i==j else state[i] for i in range(4)), j)
                   for j in range(4) if state[j] and j != last)
    answer = count_words(counts, -1)
    add('multiset_no_equal_neighbors', f'A가 {counts[0]}개, B가 {counts[1]}개, C가 {counts[2]}개, D가 {counts[3]}개 있다. 이 문자들을 한 줄로 배열할 때 같은 문자가 서로 이웃하지 않는 배열의 수를 구하시오.', answer,
        f'남은 문자 개수 (a,b,c,d)와 마지막 문자를 상태로 두고, 직전 문자와 다른 것만 선택하는 점화식을 적용하면 {answer}가지이다.')

    # 3. Two obstacles on a monotone lattice path, counted by DP.
    w, h = rng.randint(9, 12), rng.randint(8, 11)
    p = (rng.randint(2,4), rng.randint(2,4))
    q = (rng.randint(w-4,w-2), rng.randint(h-4,h-2))
    blocked = {p,q}
    dp = [[0]*(h+1) for _ in range(w+1)]
    dp[0][0] = 1
    for x in range(w+1):
        for y in range(h+1):
            if (x,y) in blocked: dp[x][y] = 0; continue
            if x==0 and y==0: continue
            dp[x][y] = (dp[x-1][y] if x else 0) + (dp[x][y-1] if y else 0)
    answer = dp[w][h]
    add('lattice_two_obstacles', f'격자 O(0,0)에서 T({w},{h})까지 오른쪽·위쪽으로만 최단 이동한다. P{p}, Q{q}를 모두 지나지 않는 경로의 수를 구하시오.', answer,
        f'전체 경로에서 P 또는 Q를 지나는 경로를 포함배제로 제외한다. 또는 F(x,y)=F(x−1,y)+F(x,y−1), F(P)=F(Q)=0으로 계산하면 {answer}이다.',
        {'type':'grid','w':w,'h':h,'px':p[0],'py':p[1],'qx':q[0],'qy':q[1]})

    # 4. Restricted digit permutations, requiring both a modular condition and local rule.
    digits = tuple(range(8))
    length = rng.choice([5,6])
    modulus = rng.choice([7,9,11])
    answer = 0
    for seq in permutations(digits, length):
        if seq[0] == 0 or any(abs(seq[i]-seq[i-1]) == 1 for i in range(1,length)): continue
        residue = 0
        for d in seq: residue = (residue*10+d)%modulus
        if residue == 0: answer += 1
    add('digit_divisibility_adjacent', f'0부터 7까지의 숫자 중 서로 다른 {length}개를 골라 {length}자리 자연수를 만든다. 이웃한 두 자리 숫자의 차가 1이 되는 곳이 없고, 수가 {modulus}의 배수인 경우의 수를 구하시오.', answer,
        f'사용한 숫자의 집합, 마지막 숫자, {modulus}로 나눈 나머지를 상태로 하는 자릿수 DP를 만든다. 0으로 시작하거나 차가 1인 인접 자리를 제외하면 {answer}개이다.')

    # 5. Exactly k selected positions on a cycle, nonadjacent AND sum congruence.
    n = rng.randint(12,15); k = rng.randint(4,5); mod = rng.choice([3,4,5])
    answer = sum(1 for c in combinations(range(1,n+1),k)
                 if all(c[i+1]-c[i]>1 for i in range(k-1)) and not(c[0]==1 and c[-1]==n)
                 and sum(c)%mod==0)
    add('cycle_nonadjacent_mod', f'원형으로 놓인 1부터 {n}까지의 자리에서 {k}자리를 선택한다. 이웃한 자리는 동시에 고르지 않으며, 선택한 자리 번호의 합은 {mod}의 배수여야 한다. 방법의 수를 구하시오.', answer,
        f'원형의 양 끝 1과 {n}도 이웃한다는 점에 주의한다. 선택 여부와 마지막 선택 위치, 합의 나머지를 추적하여 세면 {answer}가지이다.')

    # 6. Number of pairwise coprime strictly ordered positive triples with a fixed sum.
    n = rng.randint(45,66)
    answer = sum(1 for x in range(1,n+1) for y in range(x+1,(n-x)//2+1)
                 if (z:=n-x-y)>y and gcd(x,y)==gcd(y,z)==gcd(x,z)==1)
    add('pairwise_coprime_triples', f'양의 정수 x<y<z가 x+y+z={n}이고 x,y,z가 서로 쌍마다 서로소일 때, 순서쌍 (x,y,z)의 개수를 구하시오.', answer,
        f'x<y<z와 합 조건으로 x,y의 범위를 제한한 뒤, gcd(x,y)=gcd(y,z)=gcd(x,z)=1을 판정한다. 가능한 쌍은 {answer}개이다.')

    # 7. Proper colorings of a cycle using exactly three named colors.
    n = rng.randint(9,16)
    answer = (2**n + 2*(-1)**n) - 3*(1 + (-1)**n)
    add('cycle_exact_three_colors', f'정{n}각형의 꼭짓점에 빨강·파랑·초록 세 색을 칠한다. 이웃한 꼭짓점은 서로 다른 색이어야 하고 세 색을 모두 사용해야 한다. 회전·대칭으로 일치하더라도 꼭짓점의 위치가 다르면 다른 색칠로 센다. 방법의 수를 구하시오.', answer,
        f'고리 그래프의 k색 올바른 색칠 수는 (k−1)^{n}+(−1)^{n}(k−1)이다. 세 색으로 칠한 전체에서 한 색을 사용하지 않은 경우를 포함배제로 빼면 {answer}가지이다.')

    # 8. Binary necklaces under rotations with exact number of ones, Burnside via explicit orbit enumeration.
    n = rng.choice([11,12,13,14]); k = rng.randint(4,6)
    masks = [sum(1<<i for i in inds) for inds in combinations(range(n),k)]
    seen=set()
    for mask in masks:
        orbit=tuple(sorted((((mask<<s)|(mask>>(n-s))) & ((1<<n)-1)) for s in range(n)))
        seen.add(orbit)
    answer=len(seen)
    add('binary_necklace_fixed_weight', f'원형으로 배열된 {n}개의 구슬 중 정확히 {k}개를 검게 칠한다. 회전해서 일치하는 배열은 같은 것으로 보되, 뒤집어서만 일치하는 것은 다르게 센다. 서로 다른 배열의 수를 구하시오.', answer,
        f'회전군 {n}개의 작용에 번사이드 보조정리를 적용한다. 회전으로 고정되는 이진 배열의 개수를 합하여 {n}으로 나누면 {answer}가지이다.')

    # 9. Count integer solutions with squares via divisors and parity.
    target = rng.choice([180, 240, 315, 420, 504, 630, 720])
    answer = sum(1 for a in range(1,int(target**0.5)+1) if target%a==0
                 and (b:=target//a)>a and (a+b)%2==0)
    add('difference_of_squares_factor', f'양의 정수 x>y≥1에 대하여 x²−y²={target}을 만족하는 순서쌍 (x,y)의 개수를 구하시오.', answer,
        f'(x−y)(x+y)={target}에서 양의 약수 쌍 a<b를 고른다. a,b가 같은 홀짝이고 y=(b−a)/2≥1이어야 하므로 {answer}개이다.')

    # 10. Domino tilings of 3 x even-width board, nontrivial profile DP.
    width = rng.choice([8,10,12])
    @lru_cache(None)
    def tile(col,mask):
        if col==width: return int(mask==0)
        def fill(row, occupied, nextmask):
            if row==3: return tile(col+1,nextmask)
            if occupied & (1<<row): return fill(row+1,occupied,nextmask)
            result=0
            if row+1<3 and not occupied&(1<<(row+1)):
                result+=fill(row+1,occupied|(1<<row)|(1<<(row+1)),nextmask)
            result+=fill(row+1,occupied|(1<<row),nextmask|(1<<row))
            return result
        return fill(0,mask,0)
    answer=tile(0,0)
    add('domino_three_by_n', f'가로 {width}칸, 세로 3칸인 직사각형 격자를 1×2 또는 2×1 도미노로 빈틈이나 겹침 없이 채우는 방법의 수를 구하시오. 도미노는 서로 구별하지 않는다.', answer,
        f'한 열을 채울 때 다음 열에 걸쳐 놓인 칸을 3비트 상태로 기록하는 프로필 DP를 사용한다. 전체 {width}열을 채우면 {answer}가지이다.')

    # 11. Catalan paths that avoid one specific diagonal point.
    n=rng.randint(9,13); r=rng.randint(3,n-3)
    @lru_cache(None)
    def dyck(x,y):
        if y>x or (x,y)==(r,r):return 0
        if (x,y)==(n,n):return 1
        return (dyck(x+1,y) if x<n else 0)+(dyck(x,y+1) if y<n else 0)
    answer=dyck(0,0)
    add('catalan_forbidden_diagonal', f'{n}×{n} 격자에서 (0,0)에서 ({n},{n})까지 오른쪽·위쪽으로만 움직인다. 항상 y≤x를 유지하고 P({r},{r})는 지나지 않는 최단 경로 수를 구하시오.', answer,
        f'반사원리로 전체 카탈란 수 C_{n}을 구한다. P를 지나는 경로는 C_{r}×C_{n-r}이므로 차는 {answer}이다.',
        {'type':'v59_dyck','n':n})

    # 12. Integer lattice points inside a non-axis-aligned triangle (Pick theorem).
    a=rng.choice([9,11,13,15]); b=rng.choice([8,10,12]); c=rng.randint(3,7)
    boundary=a+gcd(c,b)+gcd(a-c,b)
    answer=(a*b-boundary+2)//2
    add('pick_triangle_interior', f'좌표평면에서 A(0,0), B({a},0), C({c},{b})를 꼭짓점으로 하는 삼각형 내부(세 변 제외)에 있는 정수 격자점의 수를 구하시오.', answer,
        f'넓이는 {a*b}/2이고 경계 격자점 수는 {a}+gcd({c},{b})+gcd({a-c},{b})={boundary}이다. 픽의 정리 S=I+B/2−1을 적용하면 I={answer}이다.')

    # 13. Restricted onto assignments with individual forbidden choices, PIE / enumeration.
    n=rng.randint(8,11)
    # Student 0 cannot join A, student 1 cannot join B, every team used.
    answer=0
    for t0 in (1,2):
        for t1 in (0,2):
            used={t0,t1}
            # inclusion-exclusion over the remaining absent teams
            for mask in range(8):
                missing={j for j in range(3) if mask&(1<<j)}
                if used & missing:continue
                answer+=(-1)**len(missing)*(3-len(missing))**(n-2)
    add('onto_two_forbidden', f'서로 다른 {n}명을 A·B·C 세 팀에 배정한다. 모든 팀에 최소 한 명이 있어야 한다. 지정된 학생 P는 A팀에, 다른 학생 Q는 B팀에 들어갈 수 없을 때 배정 방법의 수를 구하시오.', answer,
        f'P는 B·C, Q는 A·C 중 하나를 고른다. 각 선택에서 비어 있는 팀이 없도록 포함배제를 적용하면 {answer}가지이다.')

    # Fair cycle through distinct structural families, not numeric clones.
    unused=[v for v in bank if v[0] not in avoid]
    if unused:
        chosen=rng.choice(unused)
    else:
        # If all families appear in history, choose the least recently used.
        ages={v[0]: (list(avoid).index(v[0]) if v[0] in avoid else len(avoid)) for v in bank}
        oldest=max(ages.values())
        chosen=rng.choice([v for v in bank if ages[v[0]]==oldest])
    fam,q,ans,why,diagram=chosen
    return dict(question=q, answer=[ans], explanation=why,
                signature=hashlib.sha256((fam+q).encode()).hexdigest(),
                family=fam,grade=grade,topic='수학올림피아드',difficulty=difficulty,
                diagram=diagram,source_label='MathMate 자체 제작 고난도 올림피아드 · 실제 KMO/IMO 기출 아님',source_url=None)



# ===== 6.4: 고1 보통/어려움 — 풀이 구조 순환형 문제은행 =====
def v64_hs1(grade, topic, difficulty, rng, avoid=()):
    if grade != '고1' or difficulty not in ('보통','어려움'):
        return None
    from math import comb, factorial
    from fractions import Fraction
    bank=[]
    def add(tag, question, answer, explanation, diagram=None):
        family='v64_'+difficulty+'_'+topic+'_'+tag
        bank.append((family,question,Rational(answer),explanation,diagram))
    a,b,c=rng.randint(2,7),rng.randint(2,7),rng.randint(2,6)
    hard=difficulty=='어려움'
    if topic=='다항식':
        if hard:
            u,v,w=sorted(rng.sample(range(1,11),3)); m=rng.randint(2,8); n=rng.randint(2,8)
            add('three_point_remainder',f'다항식 P(x)를 (x−{u})(x−{v})(x−{w})로 나눈 나머지는 이차 이하이다. P({u})={u*u+m*u+n}, P({v})={v*v+m*v+n}, P({w})={w*w+m*w+n}일 때 나머지의 상수항을 구하시오.',n,'세 점에서 같은 값을 갖는 이차 이하 다항식은 유일하므로 나머지는 x²+mx+n이다.')
            t=rng.randint(2,6)
            add('double_root_coefficient',f'다항식 P(x)=x³+px²+qx+{t*t*t}가 (x−{t})²을 인수로 갖고 P(−{t})=0이다. p+q의 값을 구하시오.',-t + (-t*t),'P(x)=(x−t)²(x+t)이며 전개하면 p=−t, q=−t²이다.')
            r=rng.randint(2,6); d=rng.randint(2,7)
            add('symmetric_reconstruction',f'두 실수 x,y가 x+y={r}, xy=−{d}일 때 x⁴+y⁴의 값을 구하시오.',(r*r+2*d)**2-2*d*d,'x²+y²=(x+y)²−2xy, x⁴+y⁴=(x²+y²)²−2x²y².')
            z=rng.randint(2,7); h=rng.randint(2,6)
            add('polynomial_identity',f'모든 실수 x에 대하여 (x+{z})P(x)−(x−{z})P(−x)={2*h*z}x²+{2*z*z*z}이다. P(x)=ax²+bx+c일 때 b의 값을 구하시오.',h,'양변을 전개하면 x² 계수는 2z(a+b)이며 상수항은 2zc이다. 단, x³항은 소거되므로 a+b만 정해져 b는 결정되지 않는다.') if False else None
            q=rng.randint(2,8); t=rng.randint(2,7)
            add('remainder_at_negative',f'P(x)를 (x−{q})로 나눈 나머지는 {q*q+t}, (x+{q})로 나눈 나머지는 {q*q-t}이다. P(x)를 x²−{q*q}로 나눈 나머지 R(x)에 대하여 R(0)을 구하시오.',q*q,'나머지는 일차식이며 R(q)+R(−q)=2R(0)이다.')
            m=rng.randint(2,8); n=rng.randint(2,7)
            add('factor_constraint',f'P(x)=x⁴−({m*m+n*n})x²+{m*m*n*n}이다. P(x)=0인 서로 다른 실근의 제곱의 합을 구하시오.',2*(m*m+n*n) if m!=n else 2*m*m,'P(x)=(x²−m²)(x²−n²)로 분해해 서로 다른 근을 센다.')
        else:
            u,v=rng.sample(range(1,9),2); m=rng.randint(2,8)
            add('linear_remainder',f'P({u})={2*u+m}, P({v})={2*v+m}일 때 P(x)를 (x−{u})(x−{v})로 나눈 나머지 R(x)의 R(0)을 구하시오.',m,'나머지 R은 일차 이하이며 두 점을 지나는 일차식 2x+m이다.')
            add('symmetric_square',f'x+y={a}, xy={b}일 때 x²+y²을 구하시오.',a*a-2*b,'(x+y)²−2xy를 이용한다.')
            add('polynomial_difference',f'P(x)=(x+{a})(x−{b})이다. P({b+1})−P({b})의 값을 구하시오.',a+b+1,'P(b)=0, P(b+1)=(a+b+1)이다.')
            add('area_polynomial',f'직사각형의 두 변이 x+{a}, x+{b}이다. 넓이 다항식의 일차항 계수를 구하시오.',a+b,'두 일차식을 전개한다.',{'type':'v59_rectangle','a':'x+'+str(a),'b':'x+'+str(b)})
            add('reverse_factor',f'x²+px+{a*b}=(x+{a})(x+{b})일 때 p를 구하시오.',a+b,'두 일차인수의 합을 이용한다.')
    elif topic=='집합과 명제':
        if hard:
            N=rng.randint(45,100); x=rng.randint(6,12); y=rng.randint(6,12); z=rng.randint(5,10); t=rng.randint(2,5)
            A=x+t+z; B=y+t+z; C=x+y+z+t
            add('venn_inverse',f'전체집합 U에서 n(A)={A}, n(B)={B}, n(A∩B)={t+z}, n(A∪B)={C}이다. n(A∖B)를 구하시오.',x,'A에만 속하는 원소는 n(A)−n(A∩B)이다.',{'type':'v59_venn3'})
            k=rng.randint(2,6); m=rng.randint(3,7)
            add('necessary_sufficient_parameter',f'실수 x에 대한 조건 p: x²−{2*k}x+{k*k}≤{m*m}, q: {k-m}≤x≤{k+m}가 있다. p가 q이기 위한 조건은 필요조건인가, 충분조건인가? 필요충분조건이면 2, 필요조건만이면 1, 충분조건만이면 3을 입력하시오.',2,'완전제곱하면 |x−k|≤m으로 두 조건의 진리집합이 일치한다.')
            L=rng.randint(2,7); R=L+rng.randint(3,8)
            add('universal_implication',f'모든 실수 x에 대하여 “{L}≤x≤{R}이면 x²−2kx+{L*R}≤0”이 참이 되게 하는 실수 k의 최솟값을 구하시오.',Fraction(L+R,2),'x>0이므로 k≥(x²+LR)/(2x)이다. 이 함수는 구간 양 끝에서 최댓값이 (L+R)/2이다.')
            n=rng.randint(40,100); d=rng.randint(3,7); e=d+1
            add('set_count_complement',f'U={{1,2,…,{n}}}에서 A는 {d}의 배수의 집합, B는 {e}의 배수의 집합이다. A∪B의 여집합의 원소 개수를 구하시오.',n-n//d-n//e+n//(d*e),'포함배제 원리를 적용하고 전체에서 뺀다.')
            p=rng.randint(2,8); q=rng.randint(2,8)
            add('logic_counterexample_range',f'실수 x에 대한 명제 “x²≤{p*p}이면 x≤k”가 항상 참이 되게 하는 정수 k의 최솟값을 구하시오.',p,'전건의 해집합은 [−p,p]이고, 결론이 항상 참이려면 k≥p이다.')
        else:
            n=rng.randint(30,80); d=rng.randint(3,8)
            add('multiples_complement',f'U={{1,2,…,{n}}}이고 A는 {d}의 배수의 집합이다. n(Aᶜ)를 구하시오.',n-n//d,'전체에서 배수 개수를 뺀다.')
            x,y,z=rng.randint(8,17),rng.randint(8,17),rng.randint(3,7)
            add('venn_intersection',f'n(A)={x+z}, n(B)={y+z}, n(A∪B)={x+y+z}일 때 n(A∩B)를 구하시오.',z,'포함배제 원리 n(A)+n(B)−n(A∪B).',{'type':'v59_venn3'})
            add('set_difference',f'n(A∩B)={z}, n(A)={x+z}일 때 n(A∖B)를 구하시오.',x,'A에만 속하는 원소를 센다.')
            add('implication_interval',f'모든 실수 x에 대하여 “{a}≤x≤{a+b}이면 x≥k”가 참인 정수 k의 최댓값을 구하시오.',a,'k는 구간의 왼쪽 끝점 이하이다.',{'type':'v59_interval','l':a,'u':a+b})
            add('logic_negation',f'명제 “모든 자연수 n에 대하여 n²+n은 짝수이다”의 부정은 참인가? 참이면 1, 거짓이면 0을 입력하시오.',0,'연속한 두 정수의 곱은 항상 짝수이므로 원명제는 참이고 부정은 거짓이다.')
    elif topic=='도형의 방정식':
        if hard:
            r=rng.randint(4,10); h=rng.randint(1,r-1)
            add('chord_area',f'원 x²+y²={r*r}과 직선 y={h}의 두 교점을 A,B라 한다. 원점 O에 대하여 삼각형 OAB의 넓이의 제곱을 구하시오.',h*h*(r*r-h*h),'AB=2√(r²−h²), 높이는 h이므로 넓이는 h√(r²−h²).',None)
            m=rng.randint(2,8); n=rng.randint(2,8)
            add('locus_distance_sum',f'A(0,0), B({2*m},0)이고 점 P(x,y)가 PA²+PB²={2*(m*m+n*n)}를 만족한다. P의 자취가 둘러싸는 넓이를 π로 나눈 값을 구하시오.',n*n,'완전제곱으로 정리하면 (x−m)²+y²=n²이다.',{'type':'v59_locus','a':m,'b':n})
            k=rng.randint(2,7); t=rng.randint(2,8)
            add('perpendicular_bisector',f'A(−{k},0), B({k},0), C(0,{t})에서 세 점까지 거리가 같은 점 P의 y좌표를 구하시오.',Fraction(t*t-k*k,2*t),'PA=PB에서 x=0, PA=PC에서 y를 구한다.')
            r=rng.randint(3,9); d=rng.randint(2,8)
            add('tangent_power',f'원 x²+y²={r*r}의 외부 점 P({r+d},0)에서 그은 접선의 길이를 L이라 할 때 L²을 구하시오.',(r+d)**2-r*r,'접점의 반지름은 접선에 수직이므로 L²=OP²−r².',{'type':'v59_tangent','r':r,'d':d})
            u=rng.randint(2,7); v=rng.randint(2,7)
            add('triangle_coordinate_area',f'A(0,0), B({2*u},0), C(0,{2*v})이다. AB 위의 P에 대하여 △APC의 넓이가 △PBC의 넓이의 {u}배일 때 AP를 구하시오.',Fraction(2*u*u,u+1),'두 삼각형은 높이가 같으므로 밑변 비 AP:PB=u:1이다.',{'type':'v59_triangle','a':2*u,'b':2*v,'p':Fraction(2*u*u,u+1)})
        else:
            r=rng.randint(4,9); h=rng.randint(1,r-1)
            add('chord_half_square',f'원 x²+y²={r*r}과 y={h}의 교점을 A,B라 할 때 AB²을 구하시오.',4*(r*r-h*h),'교점의 x좌표는 ±√(r²−h²).')
            add('midpoint_reverse',f'A({a},{b}), B(x,{c})의 중점의 x좌표가 {a+4}일 때 x를 구하시오.',a+8,'중점 공식 (a+x)/2=a+4.')
            add('distance_squared',f'A(0,0), B({a},{b})일 때 AB²을 구하시오.',a*a+b*b,'두 점 사이 거리의 제곱은 가로차 제곱과 세로차 제곱의 합이다.')
            add('circle_radius',f'(x−{a})²+(y+{b})²={c*c}인 원의 반지름을 구하시오.',c,'원의 표준형에서 우변의 제곱근이 반지름이다.')
            add('line_intercept',f'직선 {a}x+{b}y={a*b*c}가 x축과 만나는 점의 x좌표를 구하시오.',b*c,'y=0을 대입한다.')
    elif topic=='함수와 그래프':
        if hard:
            u=rng.randint(2,8); v=rng.randint(2,7)
            add('absolute_flat',f'f(x)=|x−{u}|+|x+{v}|이다. f(x)=k의 서로 다른 실근이 무한히 많아지도록 하는 k를 구하시오.',u+v,'두 꺾임점 사이에서는 절댓값의 합이 일정하다.',{'type':'v59_abs','a':u,'b':v})
            m=rng.randint(2,6); k=rng.randint(2,8)
            add('inverse_composition',f'f(x)={m}x+{k}, g(x)=x² (x≥0)이다. (g⁻¹∘f)({m})의 제곱을 구하시오.',m*m+k,'g⁻¹(y)=√y이므로 제곱하면 f(m)이다.')
            t=rng.randint(2,7); h=rng.randint(2,6)
            add('intersection_distance',f'포물선 y=x²−{t*t}와 직선 y={h}의 두 교점 사이 거리의 제곱을 구하시오.',4*(t*t+h),'x좌표가 ±√(t²+h)이므로 두 점 사이 거리는 2√(t²+h).',{'type':'v59_parabola','a':0,'b':-t*t,'line':h})
            p=rng.randint(2,7); q=rng.randint(2,8)
            add('restricted_inverse',f'f(x)=(x−{p})²+{q} (x≥{p})이다. f⁻¹({q+49})−f⁻¹({q+9})를 구하시오.',4,'정의역 제한으로 역함수는 p+√(y−q)이다.')
            a1=rng.randint(2,8); b1=rng.randint(2,7)
            add('piecewise_continuity',f'f(x)는 x<{a1}에서 2x+{b1}, x≥{a1}에서 kx−{b1}이다. x={a1}에서 연속이 되도록 하는 k를 구하시오.',Fraction(2*a1+2*b1,a1),'좌우 식의 경계값을 일치시킨다.',{'type':'v59_piecewise','a':a1,'b':b1})
        else:
            a1=rng.randint(2,8); b1=rng.randint(2,7)
            add('quadratic_vertex',f'f(x)=(x−{a1})²+{b1}의 최솟값을 구하시오.',b1,'제곱항은 0 이상이다.',{'type':'v59_parabola','a':a1,'b':b1})
            add('composition',f'f(x)={a1}x+{b1}, g(x)=x²일 때 (f∘g)(2)를 구하시오.',4*a1+b1,'g(2)=4를 f에 대입한다.')
            add('inverse_linear',f'f(x)={a1}x+{b1}일 때 f⁻¹({3*a1+b1})을 구하시오.',3,'역함수의 입력에 해당하는 원래 x를 찾는다.')
            add('intersection_count',f'y=x²와 y={a1}x의 서로 다른 교점의 개수를 구하시오.',2,'x(x−a)=0이므로 서로 다른 두 근이다.')
            add('absolute_min',f'f(x)=|x−{a1}|+|x+{b1}|의 최솟값을 구하시오.',a1+b1,'두 점 사이에서 거리의 합이 일정하다.',{'type':'v59_abs','a':a1,'b':b1})
    elif topic=='경우의 수':
        if hard:
            n=rng.randint(7,11); k=rng.randint(2,4)
            add('separation',f'서로 다른 {n}명을 한 줄로 세울 때 특정 두 사람 사이에 정확히 {k}명이 있도록 하는 배열의 수를 구하시오.',2*(n-k-1)*factorial(n-2),'두 사람의 자리쌍 (n−k−1)개, 순서 2가지, 나머지 (n−2)!가지.')
            n=rng.randint(9,13); r=rng.randint(3,5)
            add('nonadjacent',f'1부터 {n}까지 서로 다른 자연수 중 {r}개를 선택하되 연속한 두 수가 없도록 하는 방법의 수를 구하시오.',comb(n-r+1,r),'선택한 수 aᵢ에서 (i−1)을 빼면 조합 C(n−r+1,r)과 대응한다.')
            n=rng.randint(5,8); m=rng.randint(4,7); i=rng.randint(1,n-1); j=rng.randint(1,m-1)
            total=comb(n+m,n); through=comb(i+j,i)*comb(n+m-i-j,n-i)
            add('grid_avoid',f'격자에서 (0,0)에서 ({n},{m})까지 오른쪽 또는 위쪽으로만 가는 최단 경로 중 ({i},{j})를 지나지 않는 경로 수를 구하시오.',total-through,'전체 최단 경로에서 지정 점을 지나는 경로를 뺀다.',None)
            n=rng.randint(6,9)
            add('round_table_nonadjacent',f'서로 다른 {n}명이 원탁에 앉을 때 지정된 두 사람 A,B가 이웃하지 않는 원순열의 수를 구하시오.',factorial(n-1)-2*factorial(n-2),'전체 (n−1)!에서 두 사람을 한 묶음으로 보는 2(n−2)!를 뺀다.')
            n=rng.randint(5,8); k=rng.randint(2,n-2)
            add('distribution_positive',f'서로 다른 {n}개의 공을 A,B,C 세 상자에 넣되 모든 상자가 비지 않고 A상자에 정확히 {k}개 들어가게 하는 방법의 수를 구하시오.',comb(n,k)*(2**(n-k)-2),'A에 들어갈 공을 고른 뒤 남은 공을 B,C에 모두 비지 않게 배분한다.')
        else:
            n=rng.randint(6,10); k=rng.randint(2,4)
            add('seating_gap',f'서로 다른 {n}명 중 지정된 두 사람이 반드시 이웃하도록 한 줄로 세우는 방법의 수를 구하시오.',2*factorial(n-1),'두 사람을 하나의 묶음으로 보고 내부 순서 2가지.')
            add('choose_nonadjacent',f'1부터 {n}까지의 정수 중 서로 연속하지 않는 두 수를 고르는 방법의 수를 구하시오.',comb(n,2)-(n-1),'전체 두 수 선택에서 연속한 쌍을 뺀다.')
            add('shortest_paths',f'격자에서 (0,0)에서 ({a},{b})까지 오른쪽·위쪽으로만 가는 최단 경로의 수를 구하시오.',comb(a+b,a),'전체 이동 a+b번 중 오른쪽 이동 a번의 위치를 정한다.',None)
            add('restricted_digits',f'서로 다른 숫자 1,2,3,4,5로 세 자리 자연수를 만들 때 백의 자리와 일의 자리의 합이 짝수인 수의 개수를 구하시오.',(3*2+2*1)*3,'양 끝은 둘 다 홀수이거나 둘 다 짝수여야 하고, 가운데는 남은 3개 중 선택한다.')
            add('committee',f'남학생 {a}명, 여학생 {b}명 중 3명을 선발하되 여학생이 정확히 한 명인 경우의 수를 구하시오.',comb(a,2)*b,'남학생 두 명과 여학생 한 명을 각각 선택한다.')
    elif topic=='방정식과 부등식':
        if hard:
            m=rng.randint(2,8); n=rng.randint(2,8)
            good=[k for k in range(m+1,m+21) if k*k>m*k+n]
            add('positive_roots',f'x²−2kx+({m}k+{n})=0이 서로 다른 두 양의 실근을 갖는 정수 k 중 {m+1}≤k≤{m+20}인 것의 개수를 구하시오.',len(good),'두 근의 합·곱이 양수이고 판별식이 양수여야 한다.')
            l=rng.randint(2,8); u=l+rng.randint(5,12)
            add('integer_intersection',f'(x−{l})(x−{u})<0과 x≥{l+2}를 동시에 만족하는 정수 x의 개수를 구하시오.',max(0,u-l-2),'첫 부등식은 l<x<u이고, 두 번째와 교집합을 취한다.',{'type':'v59_interval','l':l,'u':u})
            h=rng.randint(2,7); w=rng.randint(2,7)
            add('absolute_interval_count',f'|x−{h}|≤k를 만족하는 정수 x가 정확히 {2*w+1}개일 때 양의 정수 k를 구하시오.',w,'중심이 정수이므로 정수해의 수는 2k+1이다.')
            p=rng.randint(2,8); q=rng.randint(2,8)
            add('quadratic_parameter',f'이차방정식 x²−2({p})x+k=0이 서로 다른 두 실근을 가지면서 두 근의 곱이 양수일 때 가능한 양의 정수 k의 개수를 구하시오.',p*p-1,'두 근의 합은 양수, 곱 k>0, 판별식 p²−k>0이다.')
            x=rng.randint(2,8); y=x+rng.randint(4,10)
            add('absolute_reverse',f'|t−{x}|+|t−{y}|의 최솟값을 구하시오.',y-x,'수직선의 두 점 사이에서 거리 합이 최소가 된다.',{'type':'v59_interval','l':x,'u':y})
        else:
            l=rng.randint(2,7); u=l+rng.randint(4,10)
            add('integer_roots',f'(x−{l})(x−{u})<0을 만족하는 정수 x의 개수를 구하시오.',u-l-1,'양 끝점 사이의 정수만 센다.',{'type':'v59_interval','l':l,'u':u})
            add('quadratic_discriminant',f'x²−2kx+{a*a}=0이 중근을 갖도록 하는 양의 정수 k를 구하시오.',a,'판별식 4(k²−a²)=0.')
            add('absolute_two_roots',f'|x−{a}|={b}의 서로 다른 두 해의 합을 구하시오.',2*a,'두 해는 a−b, a+b이다.')
            add('mixture',f'{a}% 소금물 100g에 물 {100*b}g을 더하면 농도는 몇 %인가? 답은 기약분수로 입력해도 됩니다.',Fraction(a,b+1),'소금 양은 그대로이고 전체 질량은 100(b+1)g이다.')
            add('inequality_intersection',f'x≥{a}와 x<{a+b}를 만족하는 정수 x의 개수를 구하시오.',b,'a부터 a+b−1까지 센다.')
    elif topic=='행렬':
        if hard:
            n=rng.randint(5,12); u=rng.randint(2,7); v=rng.randint(2,7)
            add('nilpotent_power',f'A=[[1,{u}],[0,1]], B=[[1,0],[{v},1]]일 때 A의 {n}제곱과 B의 곱 AⁿB의 (1,1) 성분을 구하시오.',1+n*u*v,'A=I+N, N²=0이므로 Aⁿ=I+nN이다.')
            add('noncommutativity',f'A=[[1,{u}],[0,1]], B=[[1,0],[{v},1]]일 때 AB−BA의 (1,1) 성분을 구하시오.',u*v,'행렬 곱을 직접 계산하면 AB의 (1,1)은 1+uv, BA는 1이다.')
            add('trace_square',f'A=[[{u},1],[0,{v}]]일 때 A²의 대각성분의 합을 구하시오.',u*u+v*v,'위삼각행렬의 제곱에서도 대각성분은 각각 u²,v²이다.')
            add('matrix_inverse_parameter',f'A=[[{u},0],[0,{v}]], B=[[{u*n},0],[0,{v*n}]]이고 AX=B일 때 X의 (1,1) 성분을 구하시오.',n,'A가 가역이므로 X=A⁻¹B이다.')
            add('matrix_recurrence',f'A=[[1,{u}],[0,1]]일 때 A의 {n}제곱의 (1,2) 성분을 구하시오.',n*u,'곱셈할 때마다 오른쪽 위 성분에 u가 더해진다.')
        else:
            add('product_entry',f'A=[[1,{a}],[0,1]], B=[[1,0],[{b},1]]일 때 AB의 (1,1) 성분을 구하시오.',1+a*b,'행렬 곱의 행과 열을 내적한다.')
            add('matrix_sum',f'A=[[{a},1],[0,{b}]], B=[[{c},0],[1,2]]일 때 (A+B)의 (1,1) 성분을 구하시오.',a+c,'같은 위치의 성분을 더한다.')
            add('matrix_square',f'A=[[{a},0],[0,{b}]]일 때 A²의 (2,2) 성분을 구하시오.',b*b,'대각행렬의 제곱은 각 대각성분을 제곱한다.')
            add('matrix_order',f'A=[[1,{a}],[0,1]], B=[[1,0],[{b},1]]일 때 BA의 (1,1) 성분을 구하시오.',1,'BA의 첫째 행은 B의 첫째 행과 A를 곱한 결과다.')
            add('matrix_scalar',f'A=[[{a},1],[0,{b}]]일 때 {c}A의 (2,2) 성분을 구하시오.',b*c,'행렬의 모든 성분에 스칼라를 곱한다.')
    # 6.5: 실제 어려움에 적합하지 않은 단일공식·직접계산 유형은 제외.
    # 각 단원에서 보존할 유형은 명시적으로 심사한 것만 허용한다.
    if hard:
        approved = {
            '다항식': {'three_point_remainder','double_root_coefficient','symmetric_reconstruction','remainder_at_negative'},
            '방정식과 부등식': {'positive_roots','integer_intersection','quadratic_parameter'},
            '경우의 수': {'separation','nonadjacent','grid_avoid','round_table_nonadjacent','distribution_positive'},
            '행렬': {'nilpotent_power','noncommutativity','matrix_inverse_parameter'},
            '도형의 방정식': {'locus_distance_sum','perpendicular_bisector','tangent_power','triangle_coordinate_area'},
            '집합과 명제': {'universal_implication','set_count_complement'},
            '함수와 그래프': {'absolute_flat','restricted_inverse','piecewise_continuity'},
        }
        allowed = approved.get(topic, set())
        bank = [
            entry for entry in bank if any(entry[0].endswith('_'+tag) for tag in allowed)
        ]
    if not bank: return None
    fresh=[entry for entry in bank if entry[0] not in avoid]
    if not fresh: fresh=bank
    fam,q,ans,why,diagram=rng.choice(fresh)
    return dict(question=q,answer=[ans],explanation=why,
        signature=hashlib.sha256((fam+'|'+q).encode()).hexdigest(),
        family=fam,grade=grade,topic=topic,difficulty=difficulty,
        diagram=diagram,source_label='MathMate 자체 제작 · 고1 사고력/응용형 (기출 아님)',source_url=None)


# ===== 6.6: balanced reasoning banks; independent diagram data =====
def v66_bank(grade, topic, difficulty, rng, avoid=()):
    if difficulty != '어려움' or topic == '수학올림피아드': return None
    from math import comb, factorial
    bank=[]
    def add(tag,q,ans,why,diagram=None):
        bank.append(('v66_'+grade+'_'+topic+'_'+tag,q,Rational(ans),why,diagram))
    a,b,c=rng.randint(2,6),rng.randint(2,7),rng.randint(2,5)
    if grade=='고1' and topic=='집합과 명제':
        n=rng.randint(65,100); ab=rng.randint(5,9); ac=rng.randint(4,8); bc=rng.randint(5,9); t=rng.randint(2,4); aa=rng.randint(8,15);bb=rng.randint(8,15);cc=rng.randint(8,15)
        A=aa+ab+ac+t;B=bb+ab+bc+t;C=cc+ac+bc+t
        add('three_sets_inverse',f'전체집합 U에서 세 집합 A,B,C의 원소 수가 각각 {A},{B},{C}, n(A∩B)={ab+t}, n(A∩C)={ac+t}, n(B∩C)={bc+t}, n(A∪B∪C)={aa+bb+cc+ab+ac+bc+t}이다. 정확히 두 집합에만 속하는 원소의 수를 구하시오.',ab+ac+bc,'포함배제로 삼중교집합의 원소 수를 역산한 뒤, 쌍별 교집합에서 삼중교집합을 각각 제외한다.',{'type':'v66_venn','labels':[aa,bb,cc,ab,ac,bc,t]})
        lo=rng.randint(2,6);hi=lo+rng.randint(3,7)
        add('implication_integer_k',f'모든 실수 x에 대해 “{lo}≤x≤{hi}이면 x²−2kx+{lo*hi}≤0”이 참이 되게 하는 정수 k의 최솟값을 구하시오.',(lo+hi+1)//2,'x가 양수이므로 k≥(x²+lo·hi)/(2x). 이 함수는 구간의 양 끝에서 최대가 (lo+hi)/2이다.',{'type':'v66_interval','lo':lo,'hi':hi})
        r=rng.randint(2,7);d=rng.randint(1,4)
        add('set_symmetric_difference',f'U={{1,2,…,{r*12}}}, A는 {r}의 배수, B는 {r+d}의 배수이다. A 또는 B 중 정확히 한 집합에만 속하는 원소의 수를 구하시오.',r*12//r+r*12//(r+d)-2*(r*12//math.lcm(r,r+d)),'대칭차의 원소 수는 n(A)+n(B)−2n(A∩B)이다.')
        p=rng.randint(3,8);q=rng.randint(2,6)
        add('necessary_counterexample',f'조건 p: |x−{p}|<{q}, q: x<{p+q}에 대해 p가 q이기 위한 조건은? 필요조건만이면 1, 충분조건만이면 2, 필요충분조건이면 3, 어느 것도 아니면 4를 입력하시오.',2,'|x−p|<q이면 x<p+q이다. 역은 x가 매우 작을 때 성립하지 않는다.',{'type':'v66_interval','lo':p-q,'hi':p+q})
        u=rng.randint(2,6);v=rng.randint(2,6)
        # Simple parity truth-value question removed from difficult bank.
        d=rng.randint(3,7);e=d+1;N=rng.randint(80,140)
        add('exactly_one_multiple',f'1부터 {N}까지 자연수 중 {d}의 배수이거나 {e}의 배수이지만 둘 다의 배수는 아닌 수의 개수를 구하시오.',N//d+N//e-2*(N//(d*e)),'두 집합의 대칭차를 포함배제로 계산한다.',{'type':'v66_venn','labels':['A','B','', '', '', '', '']})
        h=rng.randint(2,8);k=rng.randint(2,6)
        add('contrapositive_interval',f'모든 실수 x에 대하여 “x²<{h*h}이면 x<{h+k}”는 참이다. 그 대우 “x≥{h+k}이면 x²≥{h*h}”의 참·거짓을 판정하시오. 참이면 1, 거짓이면 0.',1,'원명제가 참이므로 대우도 참이다. 부등식으로도 확인할 수 있다.')
        t=rng.randint(2,7);m=rng.randint(2,6)
        add('parameter_subset',f'A={{x∈R | (x−{t})²≤{m*m}}}, B={{x∈R | k≤x≤{t+m+2}}}이다. A⊆B가 성립하도록 하는 정수 k의 최댓값을 구하시오.',t-m,'A의 최소 원소 t−m 이상을 B가 포함해야 하므로 k≤t−m이다.',{'type':'v66_interval','lo':t-m,'hi':t+m})
    elif grade=='고1' and topic=='행렬':
        n=rng.randint(5,12);u=rng.randint(2,6);v=rng.randint(2,6)
        add('unipotent_commutator',f'A=[[1,{u}],[0,1]], B=[[1,0],[{v},1]]이다. AⁿB−BAⁿ에서 n={n}일 때 대각성분의 합이 아닌 (1,1) 성분을 구하시오.',n*u*v,'Aⁿ=[[1,nu],[0,1]]. 두 곱의 (1,1) 성분은 각각 1+nuv와 1이다.',{'type':'v66_matrix','a':u,'b':v,'n':n})
        p=rng.randint(2,7);q=rng.randint(2,7)
        add('square_trace_reverse',f'A=[[x,{p}],[{q},−x]]이고 A²={p*q+16}I이다. x가 양수일 때 x를 구하시오.',4,'A²=(x²+pq)I이므로 x²=16이고 x>0이다.',{'type':'v66_matrix','a':p,'b':q,'n':2})
        u=rng.randint(2,8);v=rng.randint(2,7);n=rng.randint(3,10)
        add('matrix_power_sum',f'A=[[1,{u}],[0,1]]이다. S=I+A+A²+⋯+A^{n}일 때 S의 (1,2) 성분을 구하시오.',u*n*(n+1)//2,'Aᵏ=I+kN이므로 해당 성분은 u(0+1+⋯+n)이다.',{'type':'v66_matrix','a':u,'b':v,'n':n})
        x=rng.randint(2,6);y=rng.randint(2,6)
        add('matrix_product_order',f'A=[[1,{x}],[0,1]], B=[[1,0],[{y},1]]일 때 (AB)²−A²B²의 (1,1) 성분을 구하시오.',-x*y,'AB의 제곱의 (1,1)은 (1+xy)²+xy, A²B²의 (1,1)은 1+4xy. 차이는 x²y²−xy? 직접 전개 확인 필요.') if False else None
        m=rng.randint(2,7);n=rng.randint(2,6)
        add('matrix_linear_recurrence',f'A=[[1,{m}],[0,1]]이고 X₁=I, Xₖ₊₁=AXₖ+A이다. X_{n}의 (1,2) 성분을 구하시오.',m*(n-1)*n//2+m*(n-1),'Xₙ=Aⁿ⁻¹+Σ(j=1부터 n−1)Aʲ이다. (1,2) 성분은 m[(n−1)+n(n−1)/2].') if False else None
        k=rng.randint(3,8);u=rng.randint(2,7)
        add('matrix_equation_inverse',f'A=[[1,{u}],[0,1]], X=[[x,y],[0,1]]이고 AX=[[{k},{u*(k+1)}],[0,1]]이다. x+y를 구하시오.',k+u*k,'행렬 곱의 첫 행은 [x,y+u]이다. 따라서 x=k, y=uk이다.') if False else None
        a=rng.randint(2,7);b=rng.randint(2,7);n=rng.randint(4,10)
        add('conjugate_nilpotent',f'A=[[1,{a}],[0,1]], B=[[1,0],[{b},1]]이다. AⁿB−BAⁿ의 (2,2) 성분을 n={n}일 때 구하시오.',-n*a*b,'AⁿB의 (2,2)=1이고 BAⁿ의 (2,2)=1+nab이다.',{'type':'v66_matrix','a':a,'b':b,'n':n})
        t=rng.randint(2,6);k=rng.randint(3,9)
        add('matrix_polynomial',f'A=[[{t},1],[0,{t}]]이다. (A−{t}I)²=0을 이용하여 A^{k}의 (1,2) 성분을 구하시오.',k*t**(k-1),'A=tI+N, N²=0이므로 이항정리에서 일차항만 남는다.',{'type':'v66_matrix','a':t,'b':1,'n':k})
        a=rng.randint(2,6);b=rng.randint(2,6)
        # Trace identity is a direct fact, not suitable for difficult bank.
        u=rng.randint(2,6);n=rng.randint(4,10)
        add('matrix_inverse_power',f'A=[[1,{u}],[0,1]]이다. A⁻ⁿ의 (1,2) 성분을 n={n}일 때 구하시오.',-n*u,'A⁻¹=I−N이고 N²=0이므로 (I−N)ⁿ=I−nN이다.',{'type':'v66_matrix','a':u,'b':1,'n':n})
        a=rng.randint(2,7);b=rng.randint(2,7)
        add('matrix_two_step',f'A=[[1,{a}],[0,1]], B=[[1,0],[{b},1]]이다. (AB−BA)²의 (1,1) 성분을 구하시오.',a*a*b*b,'AB−BA는 대각행렬 diag(ab,−ab)이므로 제곱의 (1,1) 성분은 a²b²이다.',{'type':'v66_matrix','a':a,'b':b,'n':2})
    elif grade=='고1' and topic=='함수와 그래프':
        h=rng.randint(2,7);k=rng.randint(2,6)
        add('absolute_level_sets',f'f(x)=|x−{h}|+|x+{k}|이다. f(x)=m의 서로 다른 실근이 무한히 많아지는 유일한 m을 구하시오.',h+k,'두 꺾임점 사이에서 절댓값의 합이 일정하다.',{'type':'v66_abs','a':h,'b':k})
        a=rng.randint(2,6);b=rng.randint(2,7)
        add('quadratic_interval_maxmin',f'f(x)=−(x−{a})²+{b*b}이고 정의역은 0≤x≤{2*a+1}이다. 최댓값과 최솟값의 차를 구하시오.',(a+1)**2,'꼭짓점에서 최대, 두 끝점 중 꼭짓점에서 더 먼 x=2a+1에서 최소가 된다.',{'type':'v66_quad','h':a,'k':b*b,'end':2*a+1})
        p=rng.randint(2,7);q=rng.randint(2,7)
        add('inverse_domain_range',f'f(x)=(x−{p})²+{q} (x≥{p})이고 g=f⁻¹이다. g({q+64})−g({q+9})를 구하시오.',5,'g(y)=p+√(y−q)이므로 8−3=5.',{'type':'v66_quad','h':p,'k':q,'end':p+5})
        u=rng.randint(2,7);v=rng.randint(2,6)
        add('composite_fixed_points',f'f(x)={u}−x, g(x)=x²−{v}이다. f(g(x))=x의 서로 다른 실근의 합을 구하시오.',-1,'u−x²+v=x를 정리하면 x²+x−(u+v)=0. 근의 합은 −1이다.')
        a=rng.randint(2,7);b=rng.randint(2,7)
        add('piecewise_matching',f'f(x)=2x+{a} (x<{b}), f(x)=kx−{a} (x≥{b})이다. 함수가 x={b}에서 연속이 되도록 하는 k를 구하시오.',Rational(2*b+2*a,b),'좌극한과 함수값을 같게 놓는다.',{'type':'v66_piece','a':a,'b':b})
        p=rng.randint(2,7);q=rng.randint(2,6)
        add('absolute_inequality_count',f'정수 x가 |x−{p}|+|x+{q}|≤{p+q+4}를 만족할 때 가능한 x의 개수를 구하시오.',p+q+5,'허용 구간은 [−q−2,p+2]이며 양 끝을 포함한다.',{'type':'v66_abs','a':p,'b':q})
        a=rng.randint(2,6);b=rng.randint(2,7)
        add('quadratic_root_parameter',f'함수 f(x)=x²−{2*a}x+k가 x축과 서로 다른 두 점에서 만나고 그 두 교점의 거리가 {2*b}일 때 k를 구하시오.',a*a-b*b,'두 근은 a±b이므로 곱은 k=a²−b²이다.',{'type':'v66_quad','h':a,'k':-b*b,'end':a+2*b})
        a=rng.randint(2,7);b=rng.randint(2,7)
        add('reflection_composition',f'f(x)={a}x+{b}, g(x)=−x이다. f∘g와 g∘f의 그래프가 만나는 점의 x좌표를 구하시오.',Rational(-b,a),'−ax+b=−ax−b이므로 b>0일 때 만나지 않는다.') if False else None
    elif grade=='고1' and topic=='다항식':
        a=rng.randint(2,7);b=rng.randint(2,7)
        add('double_root_remainder',f'다항식 P(x)=x³+px²+qx+{a*a*b}가 (x−{a})²로 나누어떨어지고 P(−{b})=0이다. p+q를 구하시오.',b-2*a+a*a-2*a*b,'P=(x−a)²(x+b)로 놓으면 p=b−2a, q=a²−2ab이다.')
        u,v,w=sorted(rng.sample(range(1,12),3));t=rng.randint(2,6)
        add('interpolation_remainder',f'P(x)를 (x−{u})(x−{v})(x−{w})로 나눈 나머지는 이차 이하이다. P({u})={u*u+t*u+3}, P({v})={v*v+t*v+3}, P({w})={w*w+t*w+3}일 때 나머지의 일차항 계수를 구하시오.',t,'세 점에서 일치하는 이차 이하 다항식은 유일하다.')
        x=rng.randint(2,7);y=rng.randint(2,7)
        add('symmetric_cubic',f'두 실수 α,β가 α+β={x}, αβ=−{y}일 때 α³+β³을 구하시오.',x**3+3*x*y,'α³+β³=(α+β)³−3αβ(α+β)이다.')
    elif grade=='고1' and topic=='도형의 방정식':
        r=rng.randint(5,10);d=rng.randint(1,r-1)
        add('chord_inverse',f'원 x²+y²={r*r}의 현 AB가 중심에서 거리 {d}에 있고, M은 현의 중점이다. △OAB의 넓이의 제곱을 구하시오.',d*d*(r*r-d*d),'현의 반길이는 √(r²−d²)이고 높이는 d이다.',{'type':'chord','radius':r,'half':math.sqrt(r*r-d*d),'dist':d})
        a=rng.randint(2,7);b=rng.randint(2,7)
        add('circle_locus',f'A(0,0), B({2*a},0)이고 PA²+PB²={2*(a*a+b*b)}인 점 P의 자취가 둘러싸는 넓이를 π로 나눈 값을 구하시오.',b*b,'(x−a)²+y²=b²로 정리한다.',{'type':'v66_circle','a':a,'b':b})
        a=rng.randint(2,6);b=rng.randint(2,7)
        add('coordinate_area_ratio',f'A(0,0), B({2*a},0), C(0,{2*b})이고 P가 AB 위에 있다. △APC:△PBC={a}:1일 때 AP를 구하시오.',Rational(2*a*a,a+1),'높이가 같아 넓이의 비는 밑변의 비다.',{'type':'triangle_lines','x':a,'y':b})
    elif grade=='고1' and topic=='방정식과 부등식':
        a=rng.randint(2,7);b=rng.randint(2,6)
        add('positive_root_interval',f'이차방정식 x²−2kx+{a*a}=0이 서로 다른 두 양의 실근을 갖도록 하는 정수 k 중 {a}≤k≤{a+b}인 것의 개수를 구하시오.',b,'서로 다른 두 양의 근은 k>a일 때 존재하므로 a+1,…,a+b이다.',{'type':'v66_interval','lo':a,'hi':a+b})
        a=rng.randint(2,6);b=rng.randint(3,8)
        add('integer_between_roots',f'부등식 (x−{a})(x−{a+b})<0의 정수해 중 짝수인 것의 개수를 구하시오.',sum((i%2==0) for i in range(a+1,a+b)),'근 사이의 정수 중 짝수만 센다.',{'type':'v66_interval','lo':a,'hi':a+b})
    elif grade=='고1' and topic=='경우의 수':
        n=rng.randint(7,11);k=rng.randint(2,4)
        add('two_people_gap',f'서로 다른 {n}명을 일렬로 세울 때 특정 두 사람 사이에 정확히 {k}명이 있는 배열 수를 구하시오.',2*(n-k-1)*factorial(n-2),'두 사람의 자리쌍, 순서, 나머지 사람들의 배열을 곱한다.')
        n=rng.randint(8,13);r=rng.randint(3,5)
        add('nonadjacent_numbers',f'1부터 {n}까지 서로 다른 정수 중 이웃한 수가 없도록 {r}개를 선택하는 방법의 수를 구하시오.',comb(n-r+1,r),'간격을 한 칸씩 제거해 일반 조합으로 변환한다.')
    elif grade in ('중1','중2','중3'):
        if topic=='정수와 유리수':
            n=rng.randint(10,22);d=rng.randint(3,7)
            add('signed_walk',f'수직선의 0에서 출발해 오른쪽으로 {n}칸, 왼쪽으로 {n+d}칸, 다시 오른쪽으로 {2*d}칸 이동했다. 최종 위치와 출발점의 거리의 제곱을 구하시오.',d*d,'최종 위치는 d이며 거리는 |d|이다.',{'type':'m62_numberline','points':[(0,'O'),(d,'P')]})
            a=rng.randint(2,7);b=rng.randint(2,6)
            add('rational_balance',f'어떤 수 x에 {a}/{b}를 더한 값의 {b}배가 {a*b+2*a}이다. x를 구하시오.',Rational(a*b+a,b),'b(x+a/b)=ab+2a이므로 bx=ab+a이다.')
        elif topic=='일차방정식':
            a=rng.randint(2,7);b=rng.randint(2,7)
            add('tickets_revenue',f'성인 입장권은 {a*1000}원, 학생권은 {b*1000}원이다. 성인 {b+3}명과 학생 x명이 입장해 총 {a*(b+3)*1000+b*(a+4)*1000}원을 냈다. x를 구하시오.',a+4,'전체 금액에서 성인 요금을 뺀 뒤 학생권 가격으로 나눈다.')
            x=rng.randint(3,10);a=rng.randint(2,7)
            add('equation_reverse',f'어떤 수의 {a}배에서 {a*x-2*x}을 뺐더니 그 수의 2배가 되었다. 이 수를 구하시오.',x,'ax−(a−2)x=2x는 항등식이므로 해가 무수히 많다.') if False else None
        elif topic=='비와 비율':
            a=rng.randint(2,7);b=rng.randint(2,7);t=rng.randint(2,6)
            add('mixture_inverse',f'{a*5}% 소금물 {b*100}g에 물 {t*100}g을 더했다. 최종 소금물의 농도(%)를 기약분수로 구하시오.',Rational(a*5*b,b+t),'소금의 질량은 변하지 않고 전체 질량만 증가한다.')
            a=rng.randint(2,6);b=rng.randint(2,7)
            add('similar_area_ratio',f'닮은 두 삼각형의 대응변의 길이의 비가 {a}:{a+b}일 때 넓이의 비(작은 삼각형/큰 삼각형)를 구하시오.',Rational(a*a,(a+b)**2),'닮음비의 제곱이 넓이비다.',{'type':'m62_similar','u':a,'v':b})
        elif topic=='연립방정식':
            a=rng.randint(2,7);b=rng.randint(2,7);x=rng.randint(2,7);y=rng.randint(2,7)
            add('pricing_inverse',f'두 상품 A,B의 가격을 각각 x,y원이라 한다. {a}x+{b}y={a*x+b*y}, {b}x+{a+1}y={b*x+(a+1)*y}일 때 x+y를 구하시오.',x+y,'두 식을 소거법으로 풀어 각 가격을 복원한다.')
            a=rng.randint(2,6);b=rng.randint(2,6)
            add('graph_intersection',f'직선 y={a}x+{b}와 y=−x+{(a+1)*b}의 교점의 x좌표를 구하시오.',Rational(a*b,a+1),'두 직선의 y값을 같게 놓고 푼다.',{'type':'m62_lines','lines':[(a,b,'A'),(-1,(a+1)*b,'B')],'xmax':b+4})
        elif topic=='일차함수':
            a=rng.randint(2,6);b=rng.randint(2,6);c=rng.randint(2,6)
            add('taxi_break_even',f'A 요금은 기본 {a*1000}원에 km당 {b*1000}원, B 요금은 기본 {(a+c)*1000}원에 km당 {(b-1)*1000}원이다. 두 요금이 같아지는 이동 거리를 구하시오.',c,'기본료 차이와 단위 거리 요금 차이를 비교한다.',{'type':'m62_lines','lines':[(b,a,'A'),(b-1,a+c,'B')],'xmax':c+5})
            a=rng.randint(2,7);b=rng.randint(2,6)
            add('triangle_from_lines',f'직선 y={a}x+{b}와 y=−{a}x+{b}가 x축과 만나는 두 점, 두 직선의 교점으로 이루어진 삼각형 넓이를 구하시오.',Rational(b*b,a),'두 x절편은 ±b/a이고 교점은 (0,b)이다.',{'type':'m62_lines','lines':[(a,b,'L1'),(-a,b,'L2')],'xmax':b+3})
        elif topic=='확률':
            r=rng.randint(3,7);b=rng.randint(3,7)
            add('conditional_two_balls',f'빨간 공 {r}개, 파란 공 {b}개에서 동시에 2개를 뽑는다. 서로 다른 색일 확률을 기약분수로 구하시오.',Rational(r*b,comb(r+b,2)),'유리한 경우는 r·b, 전체는 C(r+b,2)이다.')
            n=rng.randint(5,9)
            add('grid_diagonal_probability',f'가로 {n}칸, 세로 {n}칸인 정사각 격자에서 단위 정사각형 하나를 임의로 고른다. 주대각선과 만나는 칸일 확률을 구하시오.',Rational(1,n),'전체 n²칸 중 대각선이 통과하는 칸은 n칸이다.',{'type':'m62_grid_rect','w':n,'h':n})
        elif topic=='인수분해':
            a=rng.randint(2,7);b=rng.randint(2,7)
            add('area_difference',f'두 정사각형의 변의 길이는 x+{a}, x−{b}이다. 두 넓이의 차가 {a*a-b*b+2*(a+b)*5}일 때 x를 구하시오.',5,'제곱의 차로 인수분해하면 (a+b)(2x+a−b)이다.',{'type':'m62_nested_squares','a':a,'b':b})
            p=rng.randint(2,7);q=rng.randint(2,7)
            add('factor_reverse',f'x²−({p+q})x+{p*q}=0의 두 근을 α,β라 할 때 α²+β²를 구하시오.',p*p+q*q,'근과 계수의 관계로 합과 곱을 복원한다.')
        elif topic=='이차방정식':
            a=rng.randint(2,7);b=rng.randint(2,7)
            add('parabola_root_gap',f'포물선 y=(x−{a})²−{b*b}가 x축과 만나는 두 점 사이의 거리의 제곱을 구하시오.',4*b*b,'두 근은 a±b이다.',{'type':'m62_parabola','h':a,'r':b})
            a=rng.randint(2,7);b=rng.randint(2,7)
            add('integer_roots_parameter',f'이차방정식 x²−kx+{a*b}=0의 두 근이 양의 정수 {a},{b}일 때 k를 구하시오.',a+b,'두 근의 합은 k이다.')
        elif topic=='경우의 수':
            w=rng.randint(5,8);h=rng.randint(5,8);px=rng.randint(1,w-1);py=rng.randint(1,h-1)
            add('grid_forbidden',f'(0,0)에서 ({w},{h})까지 오른쪽과 위쪽으로만 이동하는 최단 경로 중 ({px},{py})를 지나지 않는 경로의 수를 구하시오.',comb(w+h,w)-comb(px+py,px)*comb(w+h-px-py,w-px),'전체 경로에서 지정 점을 지나는 경로를 제외한다.',{'type':'grid','w':w,'h':h,'px':px,'py':py})
            n=rng.randint(8,12);r=rng.randint(3,5)
            add('nonadjacent_choose',f'1부터 {n}까지 자연수 중 서로 이웃한 두 수가 없도록 {r}개를 선택하는 방법의 수를 구하시오.',comb(n-r+1,r),'간격을 제거해 조합 C(n−r+1,r)로 대응한다.')
    elif grade in ('고2','고3'):
        if topic=='수열':
            n=rng.randint(6,12);a=rng.randint(2,7)
            add('telescoping_rational',f'수열 aₙ=1/[n(n+1)]일 때 첫째항부터 제{n}항까지의 합을 구하시오.',Rational(n,n+1),'1/[k(k+1)]=1/k−1/(k+1)로 부분분수 분해한다.')
            n=rng.randint(7,13);a=rng.randint(2,7)
            add('recursive_difference',f'a₁={a}, aₙ₊₁=2aₙ+2ⁿ이다. a_{n}을 구하시오.',(a+n-1)*2**(n-1),'2ⁿ⁻¹로 나누어 등차수열로 변환한다.')
            n=rng.randint(6,12);a=rng.randint(2,7)
            add('alternating_sum',f'aₙ={a}+{a}n인 등차수열에서 a₁−a₂+a₃−⋯−a_{2*n}의 값을 구하시오.',-n*a,'인접한 두 항의 차는 −a이고 n쌍이 있다.')
        elif topic=='확률과 통계':
            r=rng.randint(4,9);b=rng.randint(4,9)
            add('without_replacement',f'빨간 공 {r}개, 파란 공 {b}개에서 동시에 3개를 뽑는다. 정확히 빨간 공 2개가 나올 확률을 구하시오.',Rational(comb(r,2)*b,comb(r+b,3)),'유리한 조합 수를 전체 조합 수로 나눈다.')
            n=rng.randint(7,11)
            add('derangement_two',f'서로 다른 {n}명이 지정된 자리 {n}개에 무작위로 선다. 지정된 두 사람이 모두 자신의 자리에 서지 않을 확률을 구하시오.',Rational(math.factorial(n)-2*math.factorial(n-1)+math.factorial(n-2),math.factorial(n)),'포함배제로 두 사람이 각자 자리에 서는 사건을 제외한다.')
            n=rng.randint(8,14);r=rng.randint(3,5)
            add('no_adjacent',f'1부터 {n}까지 정수에서 서로 이웃하지 않는 {r}개를 선택할 확률을 구하시오.',Rational(comb(n-r+1,r),comb(n,r)),'전체 조합과 이웃하지 않는 조합을 비교한다.')
        elif topic=='함수':
            a=rng.randint(2,6);b=rng.randint(2,7)
            add('absolute_flat',f'f(x)=|x−{a}|+|x+{b}|일 때 f(x)=k가 무한히 많은 실근을 갖도록 하는 k를 구하시오.',a+b,'두 꺾임점 사이에서 함수값이 일정하다.',{'type':'v66_abs','a':a,'b':b})
            a=rng.randint(2,6);b=rng.randint(2,7)
            add('inverse_difference',f'f(x)=(x−{a})²+{b} (x≥{a})의 역함수 g에 대하여 g({b+81})−g({b+16})을 구하시오.',5,'역함수는 a+√(y−b)이다.',{'type':'v66_quad','h':a,'k':b,'end':a+6})
        elif topic in ('미적분Ⅰ','미적분 응용'):
            a=rng.randint(2,6)
            add('absolute_velocity',f'속도 v(t)=3t²−{3*a*a} (0≤t≤{2*a})인 물체의 총 이동 거리를 구하시오.',8*a**3,'t=a에서 부호가 바뀌므로 절댓값 적분을 나누어 계산한다.')
            a=rng.randint(2,6)
            add('integral_root',f'양수 k가 ∫₀ᵏ(x²−{a*a})dx=0을 만족한다. k²의 값을 구하시오.',3*a*a,'k³/3−a²k=0에서 양의 해를 구한다.')
            a=rng.randint(2,6)
            add('parabola_line_area',f'y={a}x와 y=x²가 둘러싸는 영역의 넓이에 6을 곱한 값을 구하시오.',a**3,'교점 x=0,a 사이에서 (ax−x²)를 적분한다.',{'type':'v66_quad','h':0,'k':0,'end':a})
    if not bank:return None
    fresh=[entry for entry in bank if entry[0] not in avoid]
    fam,q,ans,why,diagram=rng.choice(fresh or bank)
    return dict(question=q,answer=[ans],explanation=why,
        signature=hashlib.sha256((fam+'|'+q).encode()).hexdigest(),
        family=fam,grade=grade,topic=topic,difficulty=difficulty,diagram=diagram,
        source_label='MathMate 자체 제작 · 6.6 응용/추론형 (기출 아님)',source_url=None)

def v66_svg(spec):
    if not spec or not str(spec.get('type','')).startswith('v66_'):return None
    import html as _h
    typ=spec['type']
    out=['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 660 350"><rect width="660" height="350" fill="white"/><style>text{font:17px Arial,sans-serif;fill:#20304a}.axis{stroke:#94a3b8;stroke-width:1.5}.line{stroke:#2563eb;stroke-width:3;fill:none}</style>']
    def txt(x,y,t):out.append(f'<text x="{x:.1f}" y="{y:.1f}">{_h.escape(str(t))}</text>')
    def ln(x,y,X,Y,cls='line'):out.append(f'<line x1="{x:.1f}" y1="{y:.1f}" x2="{X:.1f}" y2="{Y:.1f}" class="{cls}"/>')
    if typ=='v66_venn':
        for x,y,col in [(285,130,'#93c5fd'),(375,130,'#fbbf24'),(330,205,'#86efac')]:out.append(f'<circle cx="{x}" cy="{y}" r="96" fill="{col}" fill-opacity=".28" stroke="#334155" stroke-width="2"/>')
        txt(212,52,'A');txt(455,52,'B');txt(326,317,'C');txt(40,30,'U')
        vals=spec.get('labels',[])
        if len(vals)==7 and all(isinstance(x,int) for x in vals):
            for x,y,v in [(225,125,vals[0]),(425,125,vals[1]),(328,263,vals[2]),(330,95,vals[3]),(278,184,vals[4]),(385,184,vals[5]),(330,150,vals[6])]:txt(x,y,v)
    elif typ=='v66_interval':
        lo,hi=spec['lo'],spec['hi'];ln(90,175,575,175,'axis');txt(590,182,'x');ln(210,160,210,190);ln(460,160,460,190);ln(210,175,460,175)
        out.append('<line x1="210" y1="175" x2="460" y2="175" stroke="#2563eb" stroke-width="8"/>')
        txt(194,213,lo);txt(446,213,hi);txt(250,110,'조건의 진리집합')
    elif typ=='v66_matrix':
        a,b,n=spec['a'],spec['b'],spec['n'];txt(100,80,f'A = [ 1   {a} ]');txt(153,120,'[ 0   1 ]');txt(340,80,f'B = [ 1   0 ]');txt(393,120,f'[ {b}   1 ]');txt(220,225,f'n = {n}');txt(145,290,'행렬 곱셈의 순서와 성분에 주의')
    elif typ in ('v66_abs','v66_quad','v66_piece'):
        ln(70,175,595,175,'axis');ln(330,35,330,315,'axis');txt(599,170,'x');txt(341,33,'y')
        pts=[]
        if typ=='v66_abs':
            a,b=spec['a'],spec['b'];fn=lambda x:abs(x-a)+abs(x+b);left=-b;right=a;xx0=330;scale=30;yy0=290;sy=12
            for i in range(161):
                x=-9+i*18/160;pts.append(f'{xx0+x*scale:.1f},{yy0-fn(x)*sy:.1f}')
            txt(330+left*scale,315,f'−{b}');txt(330+right*scale,315,a)
        elif typ=='v66_quad':
            h,k,end=spec['h'],spec['k'],spec['end'];xx0=130;sc=430/max(end,1);yy0=270;sy=180/max(k+(end-h)**2,1)
            for i in range(161):
                x=end*i/160;pts.append(f'{xx0+x*sc:.1f},{yy0-(-(x-h)**2+k)*sy:.1f}')
            txt(xx0+h*sc,320,f'x={h}')
        else:
            a,b=spec['a'],spec['b'];xx0=330;scale=30;yy0=255;sy=13
            for i in range(161):
                x=-7+i*16/160;y=2*x+a if x<b else (2+2*a/b)*x-a
                pts.append(f'{xx0+x*scale:.1f},{yy0-y*sy:.1f}')
            txt(xx0+b*scale,315,f'x={b}')
        out.append('<polyline points="'+' '.join(pts)+'" class="line"/>')
    elif typ=='v66_circle':
        a,b=spec['a'],spec['b'];r=105;out.append(f'<circle cx="330" cy="170" r="{r}" class="line"/>');ln(100,275,560,275,'axis');txt(335,170,f'({a},0)');txt(400,85,f'r={b}')
    out.append('</svg>');return ''.join(out).encode('utf-8')


def generate_unique(grade, topic, difficulty):
    rng = random.SystemRandom()
    with connect() as conn:
        for _ in range(60):
            recent = [r[0] for r in conn.execute(
                "SELECT family FROM questions WHERE grade=? AND topic=? AND difficulty=? AND family IS NOT NULL ORDER BY created_at DESC, rowid DESC LIMIT 50",
                (grade, topic, difficulty)).fetchall()]
            try:
                if topic == "수학올림피아드":
                    p = (olympiad63_hard(grade,difficulty,rng,recent) or v61_middle_kmo(grade,difficulty,rng,recent) or v60_olympiad(grade,difficulty,rng,recent) or sixty_problem(grade,difficulty,rng,recent))
                elif difficulty == "어려움" and topic != "수학올림피아드":
                    # Alternate new and established banks so small new banks do not dominate.
                    legacy = (v64_hs1(grade,topic,difficulty,rng,recent[:35]) if grade == "고1" else
                              middle62_hard(grade,topic,rng,recent) if grade.startswith("중") else
                              v60_hard(grade,topic,difficulty,rng,recent))
                    recent_new = sum(str(f).startswith('v66_') for f in recent[:8])
                    if recent_new >= 3 and legacy is not None:
                        p = legacy
                    else:
                        p = v66_bank(grade,topic,difficulty,rng,recent[:35]) or legacy
                    p = p or diversified_problem(grade,topic,difficulty,rng,recent)
                elif grade == "고1" and difficulty == "보통":
                    p = v64_hs1(grade,topic,difficulty,rng,recent[:20])
                elif difficulty == "어려움" and grade in ("중1", "중2", "중3"):
                    p = middle62_hard(grade,topic,rng,recent) or diversified_problem(grade,topic,difficulty,rng,recent)
                elif difficulty == "쉬움" and topic != "인수분해":
                    p = foundation_problem(grade,topic,rng,recent)
                elif difficulty == "어려움" and (grade == "고1" or (grade == "중3" and topic == "인수분해")):
                    p = (v59_bank(grade,topic,difficulty,rng,recent) or
                         hs58_challenge(grade,topic,rng,recent) or
                         generate_hard_v56(grade,topic,rng,recent) or
                         diversified_problem(grade,topic,difficulty,rng,recent) or
                         choose_problem(grade,topic,difficulty,rng,recent))
                elif grade in ("고2", "고3") and difficulty == "어려움":
                    p = v60_hard(grade,topic,difficulty,rng,recent) or diversified_problem(grade,topic,difficulty,rng,recent)
                elif grade == "중3" and topic == "인수분해":
                    p = factor_mc_problem(grade,topic,difficulty,rng,recent)
                else:
                    p = (diversified_problem(grade,topic,difficulty,rng,recent) or
                         expanded_problem(grade,topic,difficulty,rng,recent) or
                         choose_problem(grade,topic,difficulty,rng,recent))
                if topic != "수학올림피아드" and "choices" not in p and len(p.get("answer", [])) == 1 and rng.random() < 0.45:
                    p = numeric_mc_options(p, rng)
            except ValueError:
                continue
            # 이미 정답을 맞힌 문제는 새 문제로 다시 출제하지 않는다.
            already_correct = conn.execute(
                "SELECT 1 FROM attempts WHERE question=? AND grade=? AND topic=? AND correct=1 LIMIT 1",
                (p["question"], grade, topic)).fetchone()
            if already_correct:
                continue
            if topic == "수학올림피아드":
                return p  # 제한된 문항은 정답 이력이 없는 것만 출제
            try:
                conn.execute("""INSERT INTO questions
                    (signature, grade, topic, difficulty, question, created_at, family)
                    VALUES (?,?,?,?,?,?,?)""", (
                    p["signature"], grade, topic, difficulty, p["question"],
                    datetime.now().isoformat(timespec="microseconds"), p["family"]))
                return p
            except sqlite3.IntegrityError:
                continue
    raise ValueError("아직 풀지 않은 새 문제를 찾지 못했어요. 다른 단원/난이도를 선택하거나 오답 복습을 이용하세요.")


def problem_image(question, grade, topic, difficulty):
    # Create a crisp, scalable exam-card SVG.

    import textwrap

    # Break lines by display width (Korean characters count as two columns).
    chunks = []
    for paragraph in math_display(question).splitlines():
        if not paragraph.strip():
            chunks.append("")
            continue
        chunks.extend(textwrap.wrap(paragraph, width=24, break_long_words=False,
                                    break_on_hyphens=False) or [""])
    width = 880
    line_height = 51
    height = max(300, 205 + len(chunks) * line_height)
    title = html.escape(f"{grade}  ·  {topic}  ·  {difficulty}")
    lines = "".join(
        f'<text x="62" y="{180 + i * line_height}" class="question">{html.escape(line)}</text>'
        for i, line in enumerate(chunks)
    )
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
    <style>
    .head {{font: 600 19px 'Malgun Gothic','Apple SD Gothic Neo','Noto Sans CJK KR',sans-serif; fill:#50637f}}
    .question {{font: 500 27px 'Malgun Gothic','Apple SD Gothic Neo','Noto Sans CJK KR',sans-serif; fill:#172033}}
    </style>
    <rect x="1" y="1" width="878" height="{height-2}" rx="22" fill="#ffffff" stroke="#dce5f0" stroke-width="2"/>
    <rect x="1" y="1" width="878" height="11" rx="5" fill="#3563da"/>
    <text x="62" y="65" class="head">MATHMATE AI  ·  문제</text>
    <text x="62" y="103" class="head">{title}</text>
    <line x1="62" y1="127" x2="818" y2="127" stroke="#e4eaf3" stroke-width="2"/>
    {lines}
    </svg>'''
    return svg.encode("utf-8")


def display_problem_image(question, grade, topic, difficulty):
    svg_bytes = problem_image(question, grade, topic, difficulty)
    encoded = base64.b64encode(svg_bytes).decode("ascii")
    st.markdown(
        f'<img src="data:image/svg+xml;base64,{encoded}" '
        'style="display:block;width:100%;height:auto" alt="수학 문제">',
        unsafe_allow_html=True,
    )


def show_source(problem):
    # Never label an AI-generated problem as a past competition question.
    source = problem.get("source_label")
    url = problem.get("source_url")
    if source and url and re.fullmatch(r"https?://[^\s]+", url):
        st.caption(f"📚 출처: {source}")
        st.link_button("원문 출처 확인", url)
    else:
        st.caption("출처: 자체 생성 문제 · 실제 올림피아드 기출로 확인된 문제는 아닙니다.")


def format_answer(answers):
    return ", ".join(str(a) for a in answers)


def save_attempt(p, user, correct):
    with connect() as conn:
        payload = dict(p)
        payload["answer"] = [str(x) for x in p["answer"]]
        conn.execute("""INSERT INTO attempts
            (created_at,grade,topic,difficulty,question,user_answer,correct_answer,correct,explanation,problem_json)
            VALUES (?,?,?,?,?,?,?,?,?,?)""", (
                datetime.now().strftime("%Y-%m-%d %H:%M"), p["grade"], p["topic"],
                p["difficulty"], p["question"], user, format_answer(p["answer"]),
                int(correct), p["explanation"], json.dumps(payload, ensure_ascii=False, default=str)))


# Exam-source directory: references only, not a claim that every paper is licensed
# for redistribution or that each individual year is hosted at the same URL.
EXAM_SOURCES = {
    "IMO": {"country":"국제", "kind":"증명형", "url":"https://www.imo-official.org/problems.aspx", "note":"공식 연도별 문제·언어별 PDF 목록", "range":(2006,2025)},
    "KMO": {"country":"한국", "kind":"정답형·증명형", "url":"https://www.kmo.or.kr/", "note":"대한수학회 한국수학올림피아드 공식 사이트 · 자료 공개 여부 확인", "range":(2006,2025)},
    "AIME": {"country":"미국", "kind":"정수 정답형", "url":"https://maa.org/student-programs/amc/", "note":"MAA AMC 공식 안내 · 연도별 기출 공개·이용 권한 확인", "range":(2006,2025)},
    "AMC 10/12": {"country":"미국", "kind":"객관식", "url":"https://maa.org/student-programs/amc/", "note":"MAA AMC 공식 안내 · 고난도 문항 선별", "range":(2006,2025)},
    "교토대": {"country":"일본", "kind":"서술형", "url":"https://www.kyoto-u.ac.jp/", "note":"교토대학교 공식 사이트 · 입시 원문 위치와 공개 범위 확인 필요", "range":(2006,2025)},
    "도쿄대": {"country":"일본", "kind":"서술형", "url":"https://www.u-tokyo.ac.jp/", "note":"도쿄대학교 공식 사이트 · 입시 원문 위치와 공개 범위 확인 필요", "range":(2006,2025)},
    "STEP": {"country":"영국", "kind":"서술형", "url":"https://www.ocr.org.uk/students/step-mathematics/", "note":"OCR STEP 공식 안내 및 준비 자료", "range":(2006,2025)},
    "BMO": {"country":"영국", "kind":"증명형", "url":"https://ukmt.org.uk/", "note":"UKMT 공식 사이트 · 과거 문제 공개 범위 확인", "range":(2006,2025)},
}
FAMOUS_REFERENCES = [
    {"exam":"IMO", "year":1988, "number":"6", "tag":"정수론 · 유명 고전", "reason":"널리 알려진 IMO 1988 제6문 · 고전 명문제"},
    {"exam":"IMO", "year":2011, "number":"2", "tag":"조합·기하 · 유명 고전", "reason":"풍차(Windmill) 문제로 알려진 IMO 2011 제2문"},
]

# 공식 기출의 수학적 조건을 한국어로 독자적으로 요약한 선별 문항.
# 원문 전체 복제가 아니며, 반드시 원문 링크와 대조해 학습합니다.
VERIFIED_KOREAN_PROBLEMS = {
    ("IMO", 1988, "6"): {
        "field": "정수론", "format": "증명형", "difficulty": "최상위", "figure": False,
        "title": "비에타 점프의 고전",
        "statement": "양의 정수 a, b에 대해 (a²+b²)/(ab+1)이 정수라고 하자. 이 정수가 반드시 완전제곱수임을 증명하시오.",
        "hint": "한 변수를 근으로 갖는 이차방정식을 만들고, 다른 근이 더 작은 양의 정수가 되는지 살펴보세요.",
        "source": "https://www.imo-official.org/problems/1988/",
    },
    ("IMO", 2011, "2"): {
        "field": "조합·기하", "format": "증명형", "difficulty": "최상위", "figure": False,
        "title": "풍차(Windmill)",
        "statement": "평면 위에 세 점이 일직선상에 놓이지 않는 유한한 점 집합 S가 있고, 점은 적어도 두 개라고 하자. S의 한 점을 지나는 직선을 시계 방향으로 돌리다가 다른 점을 처음 만나면 회전 중심을 그 점으로 바꾸고, 이 과정을 끝없이 반복한다. 적절한 시작점과 시작 직선을 택하면 S의 모든 점이 회전 중심으로 무한히 여러 번 선택됨을 증명하시오.",
        "hint": "방향을 정한 직선의 양쪽에 놓인 점들의 개수가 회전 중심이 바뀔 때 어떻게 되는지 생각해 보세요.",
        "source": "https://www.imo-official.org/problems/2011/",
    },
    ("IMO", 2006, "1"): {
        "field": "기하", "format": "증명형", "difficulty": "심화", "figure": False,
        "title": "삼각형의 내심과 거리",
        "statement": "삼각형 ABC의 내심을 I라 하자. 내부의 점 P가 ∠PBA+∠PCA=∠PBC+∠PCB를 만족한다. AP≥AI임을 보이고, 등호는 P=I일 때에만 성립함을 증명하시오.",
        "hint": "주어진 각의 합 조건을 한 점에서 바라보는 각의 관계로 바꾸어 보세요.",
        "source": "https://www.imo-official.org/problems/2006/",
    },
    ("IMO", 2006, "2"): {
        "field": "조합·기하", "format": "증명형", "difficulty": "최상위", "figure": False,
        "title": "정2006각형의 삼각분할",
        "statement": "정2006각형에서 양 끝점이 경계를 홀수 개의 변으로 이루어진 두 부분으로 나누는 대각선을 '좋은 대각선'이라 하고, 모든 변도 '좋은 변'이라 하자. 내부에서 서로 만나지 않는 2003개의 대각선으로 이 다각형을 삼각형으로 나눈다. 좋은 변 두 개를 갖는 이등변삼각형의 개수가 최대가 되도록 할 때 그 최댓값을 구하시오.",
        "hint": "좋은 변의 끝점이 갖는 꼭짓점 번호의 홀짝성을 분류해 보세요.",
        "source": "https://www.imo-official.org/problems/2006/",
    },
}


def render_korean_exam_problem(exam, year, number):
    item = VERIFIED_KOREAN_PROBLEMS.get((exam, year, str(number)))
    if not item:
        st.warning("이 문항은 한국어 내용 검증이 아직 끝나지 않았습니다. 공식 원문에서 확인해 주세요. 다른 문항의 내용을 임의로 대체하지 않습니다.")
        return
    st.markdown(f"### {item['title']}")
    st.caption(f"{item['field']} · {item['format']} · {item['difficulty']} · 한국어 독자 요약")
    st.markdown(item["statement"])
    with st.expander("💡 풀이 힌트"):
        st.write(item["hint"])
    st.caption("수학적 조건을 한국어로 요약했습니다. 원문 문구 및 도형은 공식 PDF를 기준으로 확인하세요. 증명형은 자동 정오 판정을 하지 않습니다.")
    st.link_button("📖 이 문제의 공식 원문 확인", item["source"])


def init_exam_db():
    with connect() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS exam_notes (
          exam TEXT NOT NULL, year INTEGER NOT NULL, problem TEXT NOT NULL,
          note TEXT NOT NULL DEFAULT '', completed INTEGER NOT NULL DEFAULT 0,
          updated_at TEXT NOT NULL, PRIMARY KEY(exam, year, problem))""")

def olympiad_exam_view(grade, difficulty):
    init_exam_db()
    st.subheader("🏅 올림피아드 문제")
    st.caption("한국어 기출 선별 수록 · 최근 20년(2006~2025) + 유명 고전 · 풀이 기록")
    st.info("실제 기출만 사용합니다. 한국어 검증 완료 문항은 앱 안에 표시하고, 미검증 문항은 공식 원문으로 안내합니다.")
    mode = st.radio("탐색 방식", ["시험별 찾기", "유명 고전"], horizontal=True)
    if mode == "유명 고전":
        choices = [f"{r['exam']} {r['year']} · {r['number']}번 — {r['tag']}" for r in FAMOUS_REFERENCES]
        selected = FAMOUS_REFERENCES[st.selectbox("유명 문제", range(len(choices)), format_func=lambda i: choices[i])]
        exam, year, number = selected["exam"], selected["year"], selected["number"]
        st.write(selected["reason"])
    else:
        exam = st.selectbox("시험", list(EXAM_SOURCES), index=0)
        year = st.selectbox("연도", list(range(2025, 2005, -1)))
        if exam == "IMO":
            number = str(st.selectbox("문항 번호", range(1, 7)))
        elif exam == "AIME":
            number = str(st.selectbox("문항 번호", range(1, 16)))
        elif exam == "AMC 10/12":
            number = str(st.selectbox("문항 번호", range(1, 26), index=19))
        else:
            number = st.text_input("문항 번호 (공식 원문 확인 후 입력)", value="1", max_chars=20).strip() or "1"
    meta = EXAM_SOURCES[exam]
    st.markdown(f"**{exam} · {year}년 · {number}번**")
    st.caption(f"{meta['country']} · {meta['kind']} | {meta['note']}")
    if exam == "IMO" and (exam, year, number) not in VERIFIED_KOREAN_PROBLEMS:
        st.caption("한국어 수록 문항: IMO 2006년 1·2번, 2011년 2번, 1988년 6번(유명 고전)")
    st.link_button("📚 공식 출처에서 원문 찾기", meta["url"], use_container_width=True)
    if exam == "IMO":
        st.caption("IMO 공식 아카이브에서 연도를 선택하면 해당 연도 1~6번 원문과 그림을 확인할 수 있습니다.")
    else:
        st.warning("현재 링크는 공식 사이트의 진입점입니다. 해당 연도·문항의 직접 원문 링크를 검증했다는 뜻이 아닙니다.")
    render_korean_exam_problem(exam, year, number)
    st.warning("시험별 문항 난이도는 검증 전이므로 학년·쉬움/보통/어려움 선택과 연동하지 않습니다. 자동 정답 판정도 제공하지 않습니다.")
    with connect() as conn:
        prior = conn.execute("SELECT note,completed FROM exam_notes WHERE exam=? AND year=? AND problem=?", (exam,year,number)).fetchone()
    note_key = f"exam_note_{exam}_{year}_{number}"
    done_key = f"exam_done_{exam}_{year}_{number}"
    if st.session_state.get("exam_current") != (exam,year,number):
        st.session_state["exam_current"] = (exam,year,number)
        st.session_state[note_key] = prior[0] if prior else ""
        st.session_state[done_key] = bool(prior[1]) if prior else False
    st.text_area("내 풀이 / 핵심 아이디어", height=230, key=note_key)
    st.checkbox("풀이 완료", key=done_key)
    if st.button("💾 풀이 기록 저장", use_container_width=True):
        with connect() as conn:
            conn.execute("""INSERT INTO exam_notes (exam,year,problem,note,completed,updated_at)
              VALUES (?,?,?,?,?,?) ON CONFLICT(exam,year,problem) DO UPDATE SET
              note=excluded.note, completed=excluded.completed, updated_at=excluded.updated_at""",
              (exam,year,number,st.session_state[note_key],int(st.session_state[done_key]),datetime.now().isoformat(timespec="seconds")))
        st.success("이 문제의 풀이 기록을 저장했습니다.")
    st.download_button("📄 내 풀이 내려받기", data=f"{exam} {year} Problem {number}\n공식 출처: {meta['url']}\n\n" + st.session_state[note_key],
                       file_name=f"mathmate_{exam.replace(' ','_')}_{year}_{number}.txt", mime="text/plain")
    with connect() as conn:
        rows = conn.execute("SELECT exam,year,problem,completed,updated_at FROM exam_notes ORDER BY updated_at DESC LIMIT 20").fetchall()
        counts = conn.execute("SELECT COUNT(*), COALESCE(SUM(completed),0) FROM exam_notes").fetchone()
    st.caption(f"기출 풀이 기록: {counts[0]}문제 · 완료 {counts[1]}문제")
    if rows:
        with st.expander("최근 풀이 기록"):
            st.dataframe([{"시험":e,"연도":y,"문항":n,"완료":"✓" if d else "진행 중","수정":t} for e,y,n,d,t in rows],
                         hide_index=True, use_container_width=True)

def licensed_olympiad_view(grade, difficulty):
    """로컬 개인학습 화면: 이미 앱에 포함된 한국어 기출 요약과 풀이 기록."""
    init_exam_db()
    st.subheader("🏅 올림피아드 문제")
    st.caption("개인 학습용 · 앱에서 한국어 문제 읽기 · 증명 풀이 기록")
    st.info("IMO 기출의 수학적 조건을 한국어로 정리한 학습용 요약 4문항입니다. 원문 전체의 공식 번역이나 60문항 완성본은 아닙니다.")
    grade_candidates = {
        "중1": [("IMO", 1988, "6")],
        "중2": [("IMO", 1988, "6"), ("IMO", 2011, "2")],
        "중3": [("IMO", 1988, "6"), ("IMO", 2011, "2")],
        "고1": [("IMO", 1988, "6"), ("IMO", 2011, "2"), ("IMO", 2006, "1")],
        "고2": list(VERIFIED_KOREAN_PROBLEMS),
        "고3": list(VERIFIED_KOREAN_PROBLEMS),
    }
    available = list(VERIFIED_KOREAN_PROBLEMS)
    recommended = grade_candidates[grade]
    only_recommended = st.checkbox(f"{grade} 추천 문제만 보기", value=False)
    options = recommended if only_recommended else available
    selected = st.selectbox("문제 선택", options, format_func=lambda x: f"{x[0]} {x[1]}년 {x[2]}번 · {VERIFIED_KOREAN_PROBLEMS[x]['title']}")
    exam, year, number = selected
    item = VERIFIED_KOREAN_PROBLEMS[selected]
    st.markdown(f"### {exam} {year}년 {number}번")
    st.caption(f"{item['field']} · {item['format']} · {item['difficulty']} · {'추천 학년' if selected in recommended else '도전 문제'}")
    st.markdown(item['statement'])
    with st.expander("💡 힌트 보기"):
        st.write(item['hint'])
    st.caption("출처: International Mathematical Olympiad, " + str(year) + "년 " + number + "번 · 개인 학습용 한국어 요약")
    st.caption("증명 문제이므로 자동 정답 판정은 하지 않습니다. 원문과 번역이 완전히 동일하다는 보증은 아닙니다.")
    with connect() as conn:
        prior = conn.execute("SELECT note,completed FROM exam_notes WHERE exam=? AND year=? AND problem=?", (exam,year,number)).fetchone()
    key = f"v30_{exam}_{year}_{number}"
    if st.session_state.get("v30_selected") != selected:
        st.session_state["v30_selected"] = selected
        st.session_state[key + '_note'] = prior[0] if prior else ''
        st.session_state[key + '_done'] = bool(prior[1]) if prior else False
    st.text_area("나의 증명 / 풀이", key=key+'_note', height=220)
    st.checkbox("내가 풀이를 완료했어요", key=key+'_done')
    if st.button("💾 풀이 저장", use_container_width=True):
        with connect() as conn:
            conn.execute("""INSERT INTO exam_notes (exam,year,problem,note,completed,updated_at)
            VALUES (?,?,?,?,?,?) ON CONFLICT(exam,year,problem) DO UPDATE SET
            note=excluded.note, completed=excluded.completed, updated_at=excluded.updated_at""",
            (exam,year,number,st.session_state[key+'_note'],int(st.session_state[key+'_done']),datetime.now().isoformat(timespec='seconds')))
        st.success("풀이를 내 컴퓨터의 학습 기록에 저장했어요.")
    with connect() as conn:
        total, done = conn.execute("SELECT COUNT(*),COALESCE(SUM(completed),0) FROM exam_notes").fetchone()
    st.caption(f"기출 풀이 기록: {total}문항 · 완료 {done}문항")


def main():
    init_db()
    st.markdown("""<style>
      .block-container {max-width:850px;padding-top:2rem}
      h1 {letter-spacing:-.04em}
      div[data-testid='stMetric'] {background:#f2f6fc;border-radius:12px;padding:12px}
      </style>""", unsafe_allow_html=True)
    st.title("📘 MathMate AI 6.6")
    st.caption("2022 개정 교육과정 · 공통수학1·2 · 올림피아드 문제")
    st.caption("오프라인 출제 · 맞힌 문제 반복 최소화 · 틀린 문제 다시 풀기")
    st.info("Gemini API 없이 출제합니다. 중등 어려움에도 조건과 연결된 그림·그래프 및 응용 추론 문제를 추가했습니다. 쉬움·보통은 기존 기준을 유지합니다. 학교 기출과의 난이도 비교는 아직 필요합니다.")
    tab1, tab2, tab3 = st.tabs(["📝 문제 풀기", "📒 오답노트", "📊 학습 통계"])
    with tab1:
        grade = st.selectbox("학년", GRADES, index=2)
        topic = st.selectbox("단원", TOPICS[grade], key=f"topic_{grade}")
        difficulty = st.selectbox("난이도", DIFFICULTIES, index=1)
        if st.button("✨ 새 문제 생성", type="primary", use_container_width=True):
            try:
                st.session_state.v21_problem = generate_unique(grade, topic, difficulty)
                st.session_state.v21_graded = False
                st.session_state.v21_user = ""
                st.rerun()
            except Exception as exc:
                st.error(f"문제 생성 실패: {exc}")
        if True:
            p = st.session_state.get("v21_problem")
            if p and (p.get("grade") != grade or p.get("topic") != topic or p.get("difficulty") != difficulty):
                p = None
            if p:
                st.subheader("문제")
                display_problem_image(p["question"], p["grade"], p["topic"], p["difficulty"])
                display_diagram(p.get("diagram"))
                show_source(p)
                if p.get("hint"):
                    with st.expander("💡 힌트"):
                        st.write(p["hint"])
                with st.form("v21_answer_form"):
                    if p.get("choices"):
                        selection = st.radio("정답을 고르세요", range(1, len(p["choices"])+1),
                            format_func=lambda n: f"{n}. {math_display(p['choices'][n-1])}", index=None,
                            disabled=st.session_state.get("v21_graded", False))
                        user = str(selection) if selection is not None else ""
                    else:
                        user = st.text_input("정답 (정수·소수·분수)", placeholder="예: 3/4 또는 0.75",
                                             disabled=st.session_state.get("v21_graded", False))
                    submitted = st.form_submit_button("정답 제출", disabled=st.session_state.get("v21_graded", False))
                if submitted:
                    try:
                        correct = parse_answer(user) == sorted(set(p["answer"]))
                        save_attempt(p, user, correct)
                        st.session_state.v21_graded = True
                        st.session_state.v21_correct = correct
                        st.rerun()
                    except ValueError as exc:
                        st.warning(str(exc))
                if st.session_state.get("v21_graded", False):
                    if st.session_state.get("v21_correct"):
                        st.success("정답입니다! 🎉")
                    else:
                        st.error("오답입니다. 오답노트에 저장했어요.")
                    if p.get("choices"):
                        st.write("**정답:**", f"{int(p['answer'][0])}번 — {p['choices'][int(p['answer'][0])-1]}")
                    else:
                        st.write("**정답:**", format_answer(p["answer"]))
                    st.write("풀이:", math_display(p["explanation"]))
    with tab2:
        with connect() as conn:
            rows = conn.execute("""SELECT id,created_at,topic,question,user_answer,
                correct_answer,explanation,diagram_json,problem_json,grade,difficulty
                FROM attempts WHERE correct=0 AND NOT EXISTS (
                    SELECT 1 FROM attempts solved WHERE solved.correct=1
                    AND solved.question=attempts.question AND solved.grade=attempts.grade
                    AND solved.topic=attempts.topic
                ) ORDER BY id DESC""").fetchall()
        st.subheader(f"오답노트 ({len(rows)}개)")
        if not rows:
            st.info("아직 오답이 없습니다.")
        for rid, date, unit, question, user, answer, explanation, diagram_json, problem_json, original_grade, original_difficulty in rows:
            with st.expander(f"{date} | {unit} | #{rid}"):
                display_problem_image(question, "오답 복습", unit, "")
                st.write("**내 답:**", user)
                if problem_json:
                    if st.button("🔁 이 문제 다시 풀기", key=f"review_{rid}"):
                        try:
                            reviewed = json.loads(problem_json)
                            reviewed["answer"] = [Rational(x) for x in reviewed["answer"]]
                            st.session_state.v50_review = reviewed
                            st.session_state.v50_review_id = rid
                            st.session_state.v50_review_graded = False
                            st.rerun()
                        except (ValueError, KeyError, TypeError) as exc:
                            st.warning(f"복습 데이터를 읽지 못했습니다: {exc}")
                else:
                    st.caption("이전 버전 기록에는 재출제 데이터가 없어 정답·풀이 확인만 가능합니다.")
                st.write("**정답:**", answer)
                st.write("풀이:", math_display(explanation))
                if st.button("이 오답 기록 삭제", key=f"delete_{rid}"):
                    with connect() as conn:
                        conn.execute("DELETE FROM attempts WHERE id=?", (rid,))
                    st.rerun()
        review = st.session_state.get("v50_review")
        if review:
            st.divider()
            st.subheader("🔁 선택한 오답 다시 풀기")
            st.write(f"{review['grade']} · {review['topic']} · {review['difficulty']}")
            st.write(math_display(review["question"]))
            with st.form("v50_review_form"):
                if review.get("choices"):
                    retry_selection = st.radio("복습 정답", range(1,len(review["choices"])+1),
                        format_func=lambda n: f"{n}. {math_display(review['choices'][n-1])}", index=None,
                        disabled=st.session_state.get("v50_review_graded", False))
                    retry_answer = str(retry_selection) if retry_selection is not None else ""
                else:
                    retry_answer = st.text_input("다시 푼 정답", disabled=st.session_state.get("v50_review_graded", False))
                retry_submit = st.form_submit_button("복습 정답 제출", disabled=st.session_state.get("v50_review_graded", False))
            if retry_submit:
                try:
                    retry_correct = parse_answer(retry_answer) == sorted(set(review["answer"]))
                    save_attempt(review, retry_answer, retry_correct)
                    st.session_state.v50_review_graded = True
                    st.session_state.v50_review_correct = retry_correct
                    st.rerun()
                except ValueError as exc:
                    st.warning(str(exc))
            if st.session_state.get("v50_review_graded", False):
                if st.session_state.get("v50_review_correct", False):
                    st.success("복습 정답! 이 문제는 오답 목록에서 제외됩니다.")
                else:
                    st.error("아직 오답입니다. 다시 복습할 수 있어요.")
                if review.get("choices"):
                    st.write("**정답:**", f"{int(review['answer'][0])}번 — {review['choices'][int(review['answer'][0])-1]}")
                else:
                    st.write("**정답:**", format_answer(review["answer"]))
                st.write("풀이:", math_display(review["explanation"]))
            if st.button("복습 닫기"):
                st.session_state.pop("v50_review", None)
                st.rerun()
    with tab3:
        with connect() as conn:
            total, wins = conn.execute("SELECT COUNT(*),COALESCE(SUM(correct),0) FROM attempts").fetchone()
            units = conn.execute("SELECT topic,COUNT(*),SUM(correct) FROM attempts GROUP BY topic").fetchall()
        c1, c2, c3 = st.columns(3)
        c1.metric("풀이 수", total)
        c2.metric("정답 수", wins)
        c3.metric("정답률", f"{wins/total:.0%}" if total else "-")
        if units:
            st.dataframe([{"단원":u,"풀이 수":n,"정답 수":ok,
                           "정답률":f"{ok/n:.0%}"} for u,n,ok in units],
                         hide_index=True, use_container_width=True)
        else:
            st.info("문제를 풀면 통계가 나타납니다.")
    st.caption("⚠️ 학습 기록은 이 실행 환경의 SQLite에 저장됩니다. 클라우드 재시작 시 영구 보존되지 않을 수 있습니다.")


if __name__ == "__main__":
    main()
