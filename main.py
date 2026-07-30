import re
import requests
import pandas as pd
import streamlit as st
import plotly.express as px

# ------------------------------------------------------------
# 페이지 설정
# ------------------------------------------------------------
st.set_page_config(
    page_title="전국 시군구 고령화 지도",
    page_icon="🗺️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ------------------------------------------------------------
# CSS 스타일링
# ------------------------------------------------------------
st.markdown(
    """
<style>
.block-container {
    padding-top: 1rem;
    padding-bottom: 1rem;
    max-width: 1500px;
}
[data-testid="stSidebar"] {
    background: #f5f7fb;
}
[data-testid="metric-container"] {
    background: white;
    border-radius: 16px;
    padding: 18px;
    border: 1px solid #e6eaf2;
    box-shadow: 0 2px 10px rgba(0,0,0,.06);
}
h1 {
    font-weight: 700;
}
div[data-testid="stExpander"] {
    border-radius: 12px;
}
</style>
""",
    unsafe_allow_html=True,
)

# ------------------------------------------------------------
# 제목
# ------------------------------------------------------------
st.title("🗺️ 전국 시군구 고령화 지도")
st.caption("2015~2026년 시군구별 65세 이상 인구 비율")

# ------------------------------------------------------------
# 데이터 주소 및 로드
# ------------------------------------------------------------
POP_URL = "https://raw.githubusercontent.com/greatsong/modudata/main/data/population_yearly.csv.gz"
GEO_URL = "https://raw.githubusercontent.com/greatsong/modudata/main/data/boundaries/sigungu_kr.geojson"


@st.cache_data(show_spinner="인구 데이터를 불러오는 중...")
def load_population():
    return pd.read_csv(POP_URL, dtype={"코드": str})


@st.cache_data(show_spinner="지도 데이터를 불러오는 중...")
def load_geojson():
    return requests.get(GEO_URL, timeout=30).json()


df_raw = load_population()
geojson = load_geojson()

# ------------------------------------------------------------
# 사이드바 설정
# ------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ 설정")

    years = sorted(df_raw["연도"].unique())
    selected_year = st.slider(
        "연도 선택",
        min_value=int(min(years)),
        max_value=int(max(years)),
        value=int(max(years)),
    )

    sido_list = df_raw["시도"].dropna().sort_values().unique().tolist()
    selected_sido = st.selectbox("시도 선택", ["전체"] + sido_list)

    keyword = st.text_input("시군구 검색", placeholder="예) 청주")

    st.divider()
    st.info("지도에서 지역의 고령화율을 비교하고, 아래에서 상세 정보를 확인하세요.")

# ------------------------------------------------------------
# 데이터 가공 및 필터링
# ------------------------------------------------------------
# 1. 연도 필터링
df = df_raw[df_raw["연도"] == selected_year].copy()

if selected_sido != "전체":
    df = df[df["시도"] == selected_sido].copy()

# 2. 인구 컬럼 계산 (전체 인구 / 고령 인구)
total_cols = [c for c in df.columns if c.startswith("계_")]


def age_of(col):
    m = re.match(r"계_(\d+)세", col)
    return int(m.group(1)) if m else None


elderly_cols = []
for c in total_cols:
    age = age_of(c)
    if age is not None and age >= 65:
        elderly_cols.append(c)

if "계_100세 이상" in total_cols:
    elderly_cols.append("계_100세 이상")

df["전체인구"] = df[total_cols].sum(axis=1)
df["고령인구"] = df[elderly_cols].sum(axis=1)
df["시군구코드"] = df["코드"].str[:5]

# 3. 시군구 단위 집계
grouped = df.groupby("시군구코드")[["전체인구", "고령인구"]].sum().reset_index()

# 0으로 나누기 방지
grouped["고령화율"] = (
    (grouped["고령인구"] / grouped["전체인구"] * 100).fillna(0).round(2)
)

# 4. GeoJSON 이름 결합
names = pd.DataFrame(
    [
        {
            "시군구코드": str(f["properties"]["코드"]),
            "시군구": f["properties"]["시군구"],
            "시도": f["properties"]["시도"],
        }
        for f in geojson["features"]
    ]
)

merged = grouped.merge(names, on="시군구코드", how="left")
merged["지역"] = merged["시도"] + " " + merged["시군구"]

# 5. 검색어 필터링
if keyword:
    merged = merged[merged["지역"].str.contains(keyword, case=False, na=False)]

# ------------------------------------------------------------
# 데이터 예외 처리 및 KPI 출력
# ------------------------------------------------------------
if merged.empty:
    st.warning("⚠️ 선택한 조건에 해당하는 데이터가 없습니다. 검색어나 필터를 변경해 보세요.")
    st.stop()

national_rate = (
    (merged["고령인구"].sum() / merged["전체인구"].sum() * 100)
    if merged["전체인구"].sum() > 0
    else 0
)

highest = merged.loc[merged["고령화율"].idxmax()]
lowest = merged.loc[merged["고령화율"].idxmin()]

# 단계 구분 설정
BINS = [0, 19, 23, 28, 38, float("inf")]
LABELS = ["19% 미만", "19~23%", "23~28%", "28~38%", "38% 이상"]
COLORS = {
    "19% 미만": "#eff3ff",
    "19~23%": "#bdd7e7",
    "23~28%": "#6baed6",
    "28~38%": "#3182bd",
    "38% 이상": "#08519c",
}

merged["단계"] = pd.cut(
    merged["고령화율"], bins=BINS, labels=LABELS, right=False
)

# KPI 지표
k1, k2, k3, k4 = st.columns(4)
with k1:
    st.metric("🇰🇷 평균 고령화율", f"{national_rate:.1f}%")
with k2:
    st.metric(
        "📈 최고 지역",
        f"{highest['시도']} {highest['시군구']}",
        f"{highest['고령화율']:.1f}%",
    )
with k3:
    st.metric(
        "📉 최저 지역",
        f"{lowest['시도']} {lowest['시군구']}",
        f"{lowest['고령화율']:.1f}%",
    )
with k4:
    st.metric("🏙️ 분석 지역", selected_sido)

st.divider()

# ------------------------------------------------------------
# 탭 구성
# ------------------------------------------------------------
tab1, tab2, tab3, tab4 = st.tabs(
    ["🗺️ 지도", "📊 지역 분석", "🏆 순위", "📖 탐구 활동"]
)

# ------------------------------------------------------------
# Tab 1: 지도 Visualizing
# ------------------------------------------------------------
with tab1:
    st.subheader(f"🗺️ {selected_year}년 시군구별 고령화율")

    fig = px.choropleth(
        merged,
        geojson=geojson,
        locations="시군구코드",
        featureidkey="properties.코드",
        color="단계",
        category_orders={"단계": LABELS},
        color_discrete_map=COLORS,
        hover_name="시군구",
        hover_data={
            "시도": True,
            "고령화율": ":.2f",
            "전체인구": ":,",
            "고령인구": ":,",
            "시군구코드": False,
            "단계": False,
        },
        labels={"고령화율": "65세 이상 비율"},
    )

    fig.update_traces(marker_line_color="white", marker_line_width=0.6)
    fig.update_geos(fitbounds="locations", visible=False)
    fig.update_layout(
        margin=dict(l=0, r=0, t=0, b=0), height=780, legend_title="고령화율"
    )

    st.plotly_chart(fig, use_container_width=True)

# ------------------------------------------------------------
# Tab 2: 상세 지역 분석
# ------------------------------------------------------------
with tab2:
    st.subheader("📊 지역 상세 분석")

    region_list = merged["지역"].dropna().sort_values().tolist()
    if region_list:
        region = st.selectbox("시군구 선택", region_list)
        row = merged[merged["지역"] == region].iloc[0]

        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("고령화율", f"{row['고령화율']:.2f}%")
        with c2:
            st.metric("65세 이상 인구", f"{int(row['고령인구']):,}명")
        with c3:
            diff = row["고령화율"] - national_rate
            st.metric("전국 평균과 차이", f"{diff:+.2f}%p")

        st.divider()

        chart_df = pd.DataFrame(
            {
                "항목": ["전체인구", "65세 이상"],
                "인구": [row["전체인구"], row["고령인구"]],
            }
        )

        fig2 = px.bar(
            chart_df,
            x="항목",
            y="인구",
            text="인구",
            color="항목",
            color_discrete_sequence=["#1f77b4", "#ff7f0e"],
        )
        fig2.update_traces(
            texttemplate="%{y:,.0f}", textposition="outside"
        )
        fig2.update_layout(showlegend=False, height=450)

        st.plotly_chart(fig2, use_container_width=True)

# ------------------------------------------------------------
# Tab 3: 순위 및 데이터 다운로드
# ------------------------------------------------------------
with tab3:
    st.subheader("🏆 시군구 고령화율 순위")

    cols = ["시도", "시군구", "전체인구", "고령인구", "고령화율"]
    left, right = st.columns(2)

    with left:
        st.markdown("### 🔴 고령화율 높은 지역 TOP10")
        high = merged.sort_values("고령화율", ascending=False)[cols].head(10)
        st.dataframe(high, use_container_width=True, hide_index=True)

    with right:
        st.markdown("### 🔵 고령화율 낮은 지역 TOP10")
        low = merged.sort_values("고령화율", ascending=True)[cols].head(10)
        st.dataframe(low, use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("📋 전체 시군구")

    show = merged[cols].sort_values("고령화율", ascending=False)
    st.dataframe(show, use_container_width=True, hide_index=True, height=500)

    csv = show.to_csv(index=False, encoding="utf-8-sig")
    st.download_button(
        "📥 CSV 다운로드",
        csv,
        file_name=f"고령화율_{selected_year}.csv",
        mime="text/csv",
        use_container_width=True,
    )

# ------------------------------------------------------------
# Tab 4: 탐구 활동
# ------------------------------------------------------------
with tab4:
    st.subheader("📖 중학교 사회·지리 탐구 활동")

    with st.expander("💡 탐구 문제"):
        st.markdown(
            f"""
### {selected_year}년 우리나라 고령화 현황을 살펴봅시다.

#### ① 가장 고령화율이 높은 지역은 어디인가?
👉 지도에서 가장 진한 색을 찾아보고 이유를 생각해 보세요.

---

#### ② 수도권과 비수도권은 어떤 차이가 있나요?
👉 어떤 지역에서 고령화가 심한지 비교해 보세요.

---

#### ③ 농촌과 도시의 차이는 무엇일까요?
👉 고령화율을 비교하여 이유를 설명해 보세요.

---

#### ④ 우리 지역은 전국 평균보다 높은가요?
전국 평균 : **{national_rate:.2f}%**  
선택 지역과 비교해 보세요.

---

#### ⑤ 고령화가 심해지면 어떤 문제가 발생할까요?
- 학교 감소 / 노동력 부족 / 의료·복지 수요 증가 / 빈집 증가 / 대중교통 감소

---

#### ⑥ 해결 방법은 무엇일까요?
- 청년 일자리 확대 / 귀농·귀촌 지원 / 출산 지원 정책 / 의료·복지 확대 / 지역 산업 육성
"""
        )

    with st.expander("📝 예시 답안"):
        st.markdown(
            """
### 예시
① 농촌 지역의 고령화율이 가장 높다.  
② 수도권은 청년층이 많아 낮고, 비수도권은 높다.  
③ 농촌은 청년 인구 유출이 많아 노인 비율이 높다.  
④ 우리 지역이 전국 평균보다 높은지 확인해 본다.  
⑤ 노동력 감소, 학교 통폐합, 의료 문제 등이 발생할 수 있다.  
⑥ 청년 유입 정책과 복지 확대가 필요하다.  
"""
        )

    st.divider()
    st.success(
        "💡 연도 슬라이더를 움직이면 2015년부터 2026년까지 고령화율 변화를 비교할 수 있습니다."
    )
    st.info(
        "🖱️ 지도에 마우스를 올리면 해당 시군구의 고령화율과 인구를 확인할 수 있습니다."
    )

# ------------------------------------------------------------
# Footer
# ------------------------------------------------------------
st.divider()
st.caption(
    "자료 : 행정안전부 주민등록 인구통계 · GeoJSON : modudata · 제작 : Streamlit + Plotly"
)
