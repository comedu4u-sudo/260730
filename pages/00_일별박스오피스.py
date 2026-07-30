import pandas as pd
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import streamlit as st

st.set_page_config(page_title="박스오피스 대시보드", layout="wide")
st.title("🎬 일별 박스오피스 대시보드")

KOBIS_KEY = st.secrets["KOBIS_KEY"]

# ------------------------------------------------------------
# 날짜 선택 (오늘 이전인 '어제'까지만 선택 가능)
# ------------------------------------------------------------
today_seoul = datetime.now(ZoneInfo("Asia/Seoul")).date()
max_date = today_seoul - timedelta(days=1)

selected_date = st.date_input(
    "조회할 날짜를 선택하세요",
    value=max_date,
    max_value=max_date,
)

target_dt = selected_date.strftime("%Y%m%d")
st.caption(f"조회 기준일: {selected_date.strftime('%Y-%m-%d')}")

# ------------------------------------------------------------
# API 요청
# ------------------------------------------------------------
url = "https://www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/searchDailyBoxOfficeList.json"
res = requests.get(
    url, params={"key": KOBIS_KEY, "targetDt": target_dt}, timeout=10
)

if res.status_code != 200:
    st.error(f"요청이 실패했습니다 (상태코드: {res.status_code})")
    st.stop()

data = res.json()

if "faultInfo" in data:
    st.error(
        "인증키가 올바르지 않습니다. 금고(Secrets)의 KOBIS_KEY를 확인해 주세요."
    )
    st.stop()

box_list = data.get("boxOfficeResult", {}).get("dailyBoxOfficeList", [])

# 데이터가 비어있을 경우 예외 처리
if not box_list:
    st.warning("그날은 아직 집계 전입니다.")
    st.stop()

df = pd.DataFrame(box_list)

# 수치형 컬럼 변환 (rankInten 추가)
for col in ["rank", "rankInten", "audiCnt", "audiAcc", "scrnCnt", "showCnt"]:
    df[col] = pd.to_numeric(df[col])

# ------------------------------------------------------------
# 데이터 가공 (순위 증감 화살표 & 100만 관객 트로피)
# ------------------------------------------------------------


# 1. 순위 증감 텍스트 생성
def format_rank_inten(val):
    if val > 0:
        return f"▲{val}"
    elif val < 0:
        return f"▼{abs(val)}"
    return "-"


df["순위변동"] = df["rankInten"].apply(format_rank_inten)


# 2. 누적 관객 100만 명 이상 트로피 이모지 추가
def format_movie_name(row):
    name = row["movieNm"]
    if row["audiAcc"] >= 1_000_000:
        return f"{name} 🏆"
    return name


df["표시_영화명"] = df.apply(format_movie_name, axis=1)

# ------------------------------------------------------------
# 상단 KPI 지표
# ------------------------------------------------------------
top = df.sort_values("rank").iloc[0]
c1, c2, c3 = st.columns(3)
c1.metric("1위 영화", top["표시_영화명"])
c2.metric("당일 관객수", f"{top['audiCnt']:,}명")
c3.metric("누적 관객수", f"{top['audiAcc']:,}명")

# ------------------------------------------------------------
# 테이블 데이터 구성
# ------------------------------------------------------------
table = df[
    [
        "rank",
        "순위변동",
        "표시_영화명",
        "openDt",
        "audiCnt",
        "audiAcc",
        "scrnCnt",
    ]
].copy()
table.columns = [
    "순위",
    "순위 변동",
    "영화명",
    "개봉일",
    "관객수",
    "누적관객",
    "스크린수",
]
table = table.sort_values("순위").reset_index(drop=True)

st.subheader("📋 박스오피스 TOP 10")

# Streamlit의 column_config를 활용하여 순위 변동 컬럼 색상 적용
st.dataframe(
    table,
    column_config={
        "순위 변동": st.column_config.TextColumn(
            "순위 변동",
            help="전일 대비 순위 변동",
        )
    },
    hide_index=True,
    use_container_width=True,
)

# ------------------------------------------------------------
# 차트 출력
# ------------------------------------------------------------
st.subheader("📈 관객수 상위 5편")
top5 = table.sort_values("관객수", ascending=False).head(5)
st.bar_chart(top5.set_index("영화명")["관객수"])
