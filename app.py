"""
보령국민체육센터 공공데이터 시각화 대시보드
- 데이터 출처: 공공데이터포털 '공공체육시설이용자현황' (2020~2024)
- 3개 테이블: entries(입장기록), lessons(강습이력), applications(강좌신청정보)
"""
import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pathlib import Path

st.set_page_config(
    page_title="보령국민체육센터 4년의 발자취",
    page_icon="🏊",
    layout="wide",
)

DB_PATH = Path(__file__).parent / "bcsports.db"

@st.cache_resource
def get_conn():
    return sqlite3.connect(str(DB_PATH), check_same_thread=False)

@st.cache_data
def run_query(sql: str) -> pd.DataFrame:
    return pd.read_sql(sql, get_conn())

# ============================================================
# 헤더
# ============================================================
st.title("🏊 보령국민체육센터, 4년의 발자취")
st.markdown(
    "**공공데이터로 들여다본 지방 공공체육시설의 운영 변화**  \n"
    "데이터 기간: 2020-09 ~ 2024-08 · 분석 대상: 입장기록 457K건, 강습이력 26K건, 강좌신청 11K건"
)

# KPI
kpis = run_query("""
SELECT
  (SELECT COUNT(*) FROM entries) AS total_visits,
  (SELECT COUNT(DISTINCT member_id) FROM entries WHERE member_id > 0) AS members,
  (SELECT COUNT(*) FROM lessons) AS lessons,
  (SELECT SUM(paid) FROM applications) AS revenue
""")
c1, c2, c3, c4 = st.columns(4)
c1.metric("총 입장 건수", f"{int(kpis['total_visits'][0]):,}")
c2.metric("순 회원 수", f"{int(kpis['members'][0]):,}")
c3.metric("강습 등록 건수", f"{int(kpis['lessons'][0]):,}")
c4.metric("누적 결제금액", f"{int(kpis['revenue'][0]):,} 원")

st.divider()

# ============================================================
# 차트 1: 월별 입장객 & 순 방문자 추이
# ============================================================
st.header("① 월별 입장객 추이 — 개관·코로나·회복의 4년")

sql1 = """
SELECT ym,
       COUNT(*)               AS visits,
       COUNT(DISTINCT member_id) AS unique_members
FROM entries
GROUP BY ym
ORDER BY ym
"""
df1 = run_query(sql1)

fig1 = make_subplots(specs=[[{"secondary_y": True}]])
fig1.add_trace(
    go.Bar(x=df1["ym"], y=df1["visits"], name="총 입장 건수",
           marker_color="#4C8BF5", opacity=0.55),
    secondary_y=False,
)
fig1.add_trace(
    go.Scatter(x=df1["ym"], y=df1["unique_members"], name="월별 순 방문자",
               mode="lines+markers", line=dict(color="#E15554", width=3)),
    secondary_y=True,
)
fig1.update_layout(
    height=430, hovermode="x unified",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    margin=dict(l=10, r=10, t=30, b=10),
)
fig1.update_yaxes(title_text="총 입장 건수", secondary_y=False)
fig1.update_yaxes(title_text="순 방문자 수", secondary_y=True)
fig1.update_xaxes(title_text="연월")
st.plotly_chart(fig1, use_container_width=True)

with st.expander("📋 SQL 보기"):
    st.code(sql1, language="sql")

st.info(
    "**인사이트:**  \n"
    "• 2020년 9월 개관했지만 **코로나19로 인해 2021년 3월부터 실질 운영** 시작  \n"
    "• 2022년 봄 1만 명 돌파, **2024년 7월 19,664명으로 역대 최고치** → 안정적 성장세  \n"
    "• 매년 **7~8월(여름 수영장 성수기)** 와 **1~2월(겨울 비수기)** 의 계절성이 뚜렷  \n"
    "• 순 방문자수는 1,300명 수준에서 포화 → 지역 인구 대비 침투 한계 시사"
)

st.divider()

# ============================================================
# 차트 2: 요일 × 시간대 히트맵
# ============================================================
st.header("② 요일 × 시간대 입장 히트맵 — 인력 배치의 최적해")

sql2 = """
SELECT dow, entry_hour, COUNT(*) AS visits
FROM entries
WHERE entry_hour BETWEEN 5 AND 22
GROUP BY dow, entry_hour
ORDER BY dow, entry_hour
"""
df2 = run_query(sql2)
dow_kr = ["월", "화", "수", "목", "금", "토", "일"]
df2["요일"] = df2["dow"].map(dict(enumerate(dow_kr)))
pivot = df2.pivot(index="요일", columns="entry_hour", values="visits").reindex(dow_kr)

fig2 = px.imshow(
    pivot, aspect="auto", color_continuous_scale="YlOrRd",
    labels=dict(x="시간대", y="요일", color="입장 건수"),
    text_auto=True,
)
fig2.update_layout(height=400, margin=dict(l=10, r=10, t=30, b=10))
fig2.update_xaxes(dtick=1)
st.plotly_chart(fig2, use_container_width=True)

with st.expander("📋 SQL 보기"):
    st.code(sql2, language="sql")

st.info(
    "**인사이트:**  \n"
    "• 평일 **오전 6시가 압도적 피크** → 출근 전 운동족이 핵심 이용층  \n"
    "• **월요일 6시(8,722건)**, **수요일 6시(8,933건)** 가 주간 최정점  \n"
    "• **저녁 19~20시 두 번째 피크** (직장인 퇴근 후 이용)  \n"
    "• **주말은 평일 대비 절반 이하** → 공공체육시설은 '직장인의 일상' 인프라  \n"
    "• 운영 시사점: 평일 새벽 인력 강화, 주말은 가족 단위 프로그램 강화 필요"
)

st.divider()

# ============================================================
# 차트 3: 온라인 vs 오프라인 강습 비율 변화
# ============================================================
st.header("③ 강습 방식 변화 — 비대면 시도와 회귀")

sql3 = """
SELECT year, method, COUNT(*) AS cnt
FROM lessons
WHERE year BETWEEN 2020 AND 2024
GROUP BY year, method
ORDER BY year, method
"""
df3 = run_query(sql3)
df3_pivot = df3.pivot(index="year", columns="method", values="cnt").fillna(0)
df3_pivot["total"] = df3_pivot.sum(axis=1)
df3_pivot["online_pct"] = df3_pivot.get("ONLINE", 0) / df3_pivot["total"] * 100

col1, col2 = st.columns([2, 1])
with col1:
    fig3a = go.Figure()
    fig3a.add_trace(go.Bar(
        x=df3_pivot.index, y=df3_pivot.get("OFFLINE", 0),
        name="OFFLINE", marker_color="#264653",
    ))
    fig3a.add_trace(go.Bar(
        x=df3_pivot.index, y=df3_pivot.get("ONLINE", 0),
        name="ONLINE", marker_color="#E76F51",
    ))
    fig3a.update_layout(
        barmode="stack", height=400,
        xaxis_title="연도", yaxis_title="강습 등록 건수",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=10, r=10, t=30, b=10),
    )
    st.plotly_chart(fig3a, use_container_width=True)

with col2:
    fig3b = go.Figure()
    fig3b.add_trace(go.Scatter(
        x=df3_pivot.index, y=df3_pivot["online_pct"],
        mode="lines+markers+text",
        text=[f"{v:.1f}%" for v in df3_pivot["online_pct"]],
        textposition="top center",
        line=dict(color="#E76F51", width=3),
        marker=dict(size=10),
        name="온라인 비중",
    ))
    fig3b.update_layout(
        height=400, yaxis_title="온라인 비중 (%)",
        xaxis_title="연도", showlegend=False,
        margin=dict(l=10, r=10, t=30, b=10),
    )
    st.plotly_chart(fig3b, use_container_width=True)

with st.expander("📋 SQL 보기"):
    st.code(sql3, language="sql")

st.info(
    "**인사이트:**  \n"
    "• 코로나 직격탄이었던 **2020~2021년은 오히려 온라인 비중이 1%대** → 시설 자체가 비대면 강습 인프라 부족 추정  \n"
    "• **2022년부터 온라인 11.8%, 2023년 17.9%로 급증** → 시스템 정비 후 비대면 시도  \n"
    "• **2024년 다시 18.0% → 17.9%로 정체** → 사회적 거리두기 해제 후 대면 강습으로 회귀하는 추세  \n"
    "• 오프라인 강습은 2023년 8,742건 → 2024년 5,405건으로 감소 (단, 2024년은 8월까지의 부분 데이터)"
)

st.divider()

# ============================================================
# 차트 4: 연도별 매출 / 할인 / 결제 추이
# ============================================================
st.header("④ 강습 매출 구조 — 유료에서 무료로의 전환")

sql4 = """
SELECT year,
       SUM(price)    AS total_price,
       SUM(discount) AS total_discount,
       SUM(paid)     AS total_paid,
       SUM(is_paid)  AS paid_count,
       COUNT(*)      AS total_apps,
       ROUND(100.0 * SUM(is_paid) / COUNT(*), 1) AS paid_ratio
FROM applications
WHERE year BETWEEN 2020 AND 2024
GROUP BY year
ORDER BY year
"""
df4 = run_query(sql4)

fig4 = make_subplots(specs=[[{"secondary_y": True}]])
fig4.add_trace(
    go.Bar(x=df4["year"], y=df4["total_paid"], name="결제금액 합계",
           marker_color="#2A9D8F"),
    secondary_y=False,
)
fig4.add_trace(
    go.Bar(x=df4["year"], y=df4["total_discount"], name="할인금액 합계",
           marker_color="#F4A261"),
    secondary_y=False,
)
fig4.add_trace(
    go.Scatter(x=df4["year"], y=df4["paid_ratio"], name="유료 강좌 비율(%)",
               mode="lines+markers+text",
               text=[f"{v}%" for v in df4["paid_ratio"]],
               textposition="top center",
               line=dict(color="#E63946", width=3),
               marker=dict(size=10)),
    secondary_y=True,
)
fig4.update_layout(
    height=450, barmode="group", hovermode="x unified",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    margin=dict(l=10, r=10, t=30, b=10),
)
fig4.update_yaxes(title_text="금액 (원)", secondary_y=False)
fig4.update_yaxes(title_text="유료 강좌 비율 (%)", secondary_y=True, range=[0, 100])
st.plotly_chart(fig4, use_container_width=True)

st.dataframe(
    df4.assign(
        total_paid=df4["total_paid"].map("{:,}".format),
        total_discount=df4["total_discount"].map("{:,}".format),
        total_price=df4["total_price"].map("{:,}".format),
    ),
    use_container_width=True, hide_index=True,
)

with st.expander("📋 SQL 보기"):
    st.code(sql4, language="sql")

st.info(
    "**인사이트:**  \n"
    "• **2022년 결제금액 1,523만원이 정점**, 이후 2023년 53만원, 2024년 36만원으로 **97% 급감**  \n"
    "• 동시에 **신청 건수는 2022년 3,254건 → 2023년 5,289건으로 오히려 62% 증가**  \n"
    "• **유료 강좌 비율: 2021년 94.4% → 2024년 0.3%** → 거의 모든 강좌가 무료로 전환  \n"
    "• 추정: **공공체육서비스 무상화 정책 전환** 또는 **취약계층 강습료 면제 확대**  \n"
    "• 매출 감소 = 운영 실패가 아니라 **공공성 강화의 결과**일 가능성 높음"
)

st.divider()

# ============================================================
# 차트 5: 성별·시간대 이용 패턴
# ============================================================
st.header("⑤ 성별 × 시간대 이용 패턴 — 누가 언제 오는가")

sql5 = """
SELECT gender, entry_hour, COUNT(*) AS visits
FROM entries
WHERE gender IN ('남','여') AND entry_hour BETWEEN 5 AND 22
GROUP BY gender, entry_hour
ORDER BY entry_hour, gender
"""
df5 = run_query(sql5)

col1, col2 = st.columns([1, 2])
with col1:
    gender_total = df5.groupby("gender")["visits"].sum().reset_index()
    fig5a = px.pie(
        gender_total, values="visits", names="gender", hole=0.5,
        color="gender", color_discrete_map={"여": "#E07A5F", "남": "#3D5A80"},
    )
    fig5a.update_traces(textinfo="label+percent", textfont_size=14)
    fig5a.update_layout(
        height=400, showlegend=False,
        margin=dict(l=10, r=10, t=30, b=10),
        title=dict(text="전체 입장객 성별 비율", x=0.5),
    )
    st.plotly_chart(fig5a, use_container_width=True)

with col2:
    fig5b = px.line(
        df5, x="entry_hour", y="visits", color="gender",
        markers=True,
        color_discrete_map={"여": "#E07A5F", "남": "#3D5A80"},
        labels={"entry_hour": "시간대", "visits": "입장 건수", "gender": "성별"},
    )
    fig5b.update_layout(
        height=400,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=10, r=10, t=30, b=10),
        title=dict(text="시간대별 성별 입장 패턴", x=0.5),
    )
    fig5b.update_xaxes(dtick=1)
    st.plotly_chart(fig5b, use_container_width=True)

with st.expander("📋 SQL 보기"):
    st.code(sql5, language="sql")

st.info(
    "**인사이트:**  \n"
    "• **여성 57.2% vs 남성 42.8%** — 공공체육시설 주 이용자는 여성  \n"
    "• **오전 6~10시 시간대는 여성 우위** (특히 10시 여성 2.6만:남성 1.3만으로 2배) → 주부·은퇴자 수영·아쿠아로빅 추정  \n"
    "• **저녁 19~21시는 남녀 비율 비슷** → 직장인 공통 이용 시간  \n"
    "• 정책 시사점: **오전 여성 프로그램** 다양화, **저녁 혼성 프로그램** 강화"
)

st.divider()

# ============================================================
# 차트 6: 강습 등록자 실제 이용 전환율 (퍼널)
# ============================================================
st.header("⑥ 강습 등록 → 실제 이용 전환율 — '유령 강습생'은 얼마나 될까")

sql6 = """
WITH visits_during_lesson AS (
    SELECT l.member_id, l.lesson_start, l.lesson_end,
           COUNT(DISTINCT e.entry_date) AS visit_days
    FROM lessons l
    LEFT JOIN entries e
      ON e.member_id   = l.member_id
     AND e.entry_date BETWEEN l.lesson_start AND l.lesson_end
    WHERE l.member_id > 0
    GROUP BY l.member_id, l.lesson_start, l.lesson_end
)
SELECT
    CASE
        WHEN visit_days = 0          THEN '0회 (등록만)'
        WHEN visit_days BETWEEN 1 AND 5  THEN '1-5회'
        WHEN visit_days BETWEEN 6 AND 15 THEN '6-15회'
        ELSE '16회 이상'
    END AS visit_bucket,
    COUNT(*) AS cnt
FROM visits_during_lesson
GROUP BY visit_bucket
ORDER BY
    CASE visit_bucket
        WHEN '0회 (등록만)' THEN 1
        WHEN '1-5회' THEN 2
        WHEN '6-15회' THEN 3
        ELSE 4 END
"""
df6 = run_query(sql6)
total = df6["cnt"].sum()
df6["pct"] = df6["cnt"] / total * 100

col1, col2 = st.columns([3, 2])
with col1:
    fig6 = go.Figure(go.Funnel(
        y=df6["visit_bucket"],
        x=df6["cnt"],
        textinfo="value+percent total",
        marker=dict(color=["#E63946", "#F4A261", "#2A9D8F", "#264653"]),
    ))
    fig6.update_layout(
        height=400, margin=dict(l=10, r=10, t=30, b=10),
    )
    st.plotly_chart(fig6, use_container_width=True)

with col2:
    st.markdown("##### 강습 기간 중 실제 이용일수 분포")
    df6_show = df6.copy()
    df6_show["cnt"] = df6_show["cnt"].map("{:,}".format)
    df6_show["pct"] = df6_show["pct"].map("{:.1f}%".format)
    df6_show.columns = ["이용일수 구간", "강습 등록", "비율"]
    st.dataframe(df6_show, use_container_width=True, hide_index=True)

    avg = run_query("""
    WITH v AS (
      SELECT l.member_id, l.lesson_start, l.lesson_end,
             COUNT(DISTINCT e.entry_date) AS d
      FROM lessons l
      LEFT JOIN entries e
        ON e.member_id = l.member_id
       AND e.entry_date BETWEEN l.lesson_start AND l.lesson_end
      WHERE l.member_id > 0
      GROUP BY l.member_id, l.lesson_start, l.lesson_end
    )
    SELECT ROUND(AVG(d), 1) AS avg_days FROM v
    """)
    st.metric("강습 1건당 평균 이용일수", f"{avg['avg_days'][0]} 일")

with st.expander("📋 SQL 보기"):
    st.code(sql6, language="sql")

st.info(
    "**인사이트:**  \n"
    "• **6.6%(1,678건)는 강습 등록 후 단 한 번도 입장하지 않은 '유령 강습생'**  \n"
    "• 강습 1건당 **평균 16.4일** 이용 — 일반적인 1개월 강좌 기준 출석률 약 55% 수준  \n"
    "• **40%(10,338건)는 16회 이상 성실 이용** → 핵심 충성 회원층  \n"
    "• 정책 시사점: 무료 강좌 비중이 큰 만큼 **출석률 관리 시스템 필요** (장기 미출석자 자동 알림 등)"
)

st.divider()

# ============================================================
# 푸터
# ============================================================
st.markdown("---")
st.markdown(
    "**데이터 출처**: 공공데이터포털 - 국민체육진흥공단 공공체육시설이용자현황  \n"
    "**대상 시설**: 보령국민체육센터 (충남 보령시)  \n"
    "**분석 도구**: SQLite · Pandas · Plotly · Streamlit"
)
