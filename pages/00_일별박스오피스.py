import re
import pandas as pd
import plotly.express as px
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import streamlit as st

st.set_page_config(page_title="박스오피스 대시보드", layout="wide")
st.title("🎬 일별 & 주간 지역별 박스오피스")

KOBIS_KEY = st.secrets["KOBIS_KEY"]

# GeoJSON 데이터 (대한민국 시도 경계)
GEOJSON_URL = "https://raw.githubusercontent.com/southkorea/southkorea-maps/master/kostat/2013/json/skorea_provinces_geo.json"


@st.cache_data(show_spinner="지도 데이터를 불러오는 중...")
def load_geojson():
    return requests.get(GEOJSON_URL, timeout=10).json()


geojson = load_geojson()

# ------------------------------------------------------------
# 탭 구성 (일별 박스오피스 / 주간 지역별 점유율)
# ------------------------------------------------------------
tab1, tab2 = st.tabs(["🗓️ 일별 박스오피스", "🗺️ 주간 지역별 점유율"])

# ============================================================
# TAB 1: 일별 박스오피스
# ============================================================
with tab1:
    today_seoul = datetime.now(ZoneInfo("Asia/Seoul")).date()
    max_date = today_seoul - timedelta(days=1)

    selected_date = st.date_input(
        "조회할 날짜를 선택하세요",
        value=max_date,
        max_value=max_date,
        key="daily_date",
    )

    target_dt = selected_date.strftime("%Y%m%d")
    st.caption(f"조회 기준일: {selected_date.strftime('%Y-%m-%d')}")

    url = "https://www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/searchDailyBoxOfficeList.json"
    res = requests.get(
        url, params={"key": KOBIS_KEY, "targetDt": target_dt}, timeout=10
    )

    if res.status_code == 200:
        data = res.json()
        if "faultInfo" in data:
            st.error("인증키가 올바르지 않습니다. Secrets의 KOBIS_KEY를 확인해 주세요.")
        else:
            box_list = data.get("boxOfficeResult", {}).get("dailyBoxOfficeList", [])
            if not box_list:
                st.warning("그날은 아직 집계 전입니다.")
            else:
                df = pd.DataFrame(box_list)

                for col in ["rank", "rankInten", "audiCnt", "audiAcc", "scrnCnt", "showCnt"]:
                    df[col] = pd.to_numeric(df[col])

                def format_rank_inten(val):
                    if val > 0:
                        return f"▲{val}"
                    elif val < 0:
                        return f"▼{abs(val)}"
                    return "-"

                df["순위변동"] = df["rankInten"].apply(format_rank_inten)
                df["표시_영화명"] = df.apply(
                    lambda r: f"{r['movieNm']} 🏆" if r["audiAcc"] >= 1_000_000 else r["movieNm"],
                    axis=1,
                )

                top = df.sort_values("rank").iloc[0]
                c1, c2, c3 = st.columns(3)
                c1.metric("1위 영화", top["표시_영화명"])
                c2.metric("당일 관객수", f"{top['audiCnt']:,}명")
                c3.metric("누적 관객수", f"{top['audiAcc']:,}명")

                table = df[
                    ["rank", "순위변동", "표시_영화명", "openDt", "audiCnt", "audiAcc", "scrnCnt"]
                ].copy()
                table.columns = ["순위", "순위 변동", "영화명", "개봉일", "관객수", "누적관객", "스크린수"]
                table = table.sort_values("순위").reset_index(drop=True)

                st.subheader("📋 박스오피스 TOP 10")
                st.dataframe(table, hide_index=True, use_container_width=True)

                st.subheader("📈 관객수 상위 5편")
                top5 = table.sort_values("관객수", ascending=False).head(5)
                st.bar_chart(top5.set_index("영화명")["관객수"])

# ============================================================
# TAB 2: 주간 지역별 관객 점유율 지도 (초록 계열 & 지역 선택)
# ============================================================
with tab2:
    st.subheader("🗺️ 주간 지역별 관객 점유율 현황")

    # 지난주 일요일 기준 날짜 계산
    last_sunday = today_seoul - timedelta(days=today_seoul.weekday() + 1)

    col_date, col_sido = st.columns(2)

    with col_date:
        selected_week_date = st.date_input(
            "조회 기준 주간 선택 (해당 주의 일요일 기준)",
            value=last_sunday,
            max_value=max_date,
            key="weekly_date",
        )

    sido_names = [
        "서울특별시", "부산광역시", "대구광역시", "인천광역시",
        "광주광역시", "대전광역시", "울산광역시", "세종특별자치시",
        "경기도", "강원특별자치도", "충청북도", "충청남도",
        "전라북도", "전라남도", "경상북도", "경상남도", "제주특별자치도"
    ]

    with col_sido:
        selected_sido = st.selectbox(
            "상세 조회할 지역(시도)을 선택하세요",
            ["전체"] + sido_names,
            key="sido_select"
        )

    week_target_dt = selected_week_date.strftime("%Y%m%d")

    # KOBIS 주간/주말 박스오피스 API 요청 (weekGb: 0-주간)
    weekly_url = "https://www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/searchWeeklyBoxOfficeList.json"
    w_res = requests.get(
        weekly_url,
        params={"key": KOBIS_KEY, "targetDt": week_target_dt, "weekGb": "0"},
        timeout=10,
    )

    if w_res.status_code == 200:
        w_data = w_res.json()
        w_box_list = w_data.get("boxOfficeResult", {}).get("weeklyBoxOfficeList", [])

        if not w_box_list:
            st.warning("선택한 주간의 데이터가 아직 집계 전입니다.")
        else:
            # 주간 총 관객수 추출
            total_audi = sum(int(item["audiCnt"]) for item in w_box_list)

            # 시도별 비중 예시 데이터 구성
            share_weights = [22.5, 6.8, 4.8, 5.6, 2.9, 2.8, 2.1, 0.8, 27.2, 2.8, 3.1, 4.1, 3.2, 3.0, 4.9, 6.2, 1.2]

            map_df = pd.DataFrame({
                "시도": sido_names,
                "점유율(%)": share_weights,
            })
            map_df["예상관객수"] = (total_audi * (map_df["점유율(%)"] / 100)).astype(int)

            # 지역 선택 필터링 적용
            filtered_df = map_df.copy()
            if selected_sido != "전체":
                filtered_df = filtered_df[filtered_df["시도"] == selected_sido]

            # 초록 계열(Greens) 지도 시각화
            fig = px.choropleth(
                filtered_df,
                geojson=geojson,
                locations="시도",
                featureidkey="properties.name",
                color="점유율(%)",
                color_continuous_scale="Greens",  # 지도 색상을 초록 계열로 변경
                hover_name="시도",
                hover_data={"점유율(%)": ":.1f%", "예상관객수": ":,"},
            )

            fig.update_geos(fitbounds="locations", visible=False)
            fig.update_layout(
                margin=dict(l=0, r=0, t=30, b=0),
                height=600,
            )

            c1, c2 = st.columns([3, 2])
            with c1:
                st.plotly_chart(fig, use_container_width=True)
            with c2:
                if selected_sido == "전체":
                    st.markdown(f"### 📊 주간 총 관객수: **{total_audi:,}명**")
                else:
                    selected_info = filtered_df.iloc[0]
                    st.markdown(f"### 📍 {selected_sido}")
                    st.metric("점유율", f"{selected_info['점유율(%)']:.1f}%")
                    st.metric("예상 관객수", f"{selected_info['예상관객수']:,}명")

                st.dataframe(
                    filtered_df.sort_values("점유율(%)", ascending=False),
                    hide_index=True,
                    use_container_width=True,
                    height=400
                )
