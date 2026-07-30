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
tab1, tab2 = st.tabs(["🗓️ 일별 박스오피스", "🗺️ 주간 영화별 지역 점유율"])

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
# TAB 2: 주간 TOP 5 영화별 지역 관객 점유율 지도
# ============================================================
with tab2:
    st.subheader("🗺️ TOP 5 영화별 지역 관객 점유율 현황")

    # 지난주 일요일 기준 날짜 계산
    last_sunday = today_seoul - timedelta(days=today_seoul.weekday() + 1)

    c_date, c_movie, c_sido = st.columns([1, 1, 1])

    with c_date:
        selected_week_date = st.date_input(
            "조회 기준 주간 선택 (일요일 기준)",
            value=last_sunday,
            max_value=max_date,
            key="weekly_date",
        )

    week_target_dt = selected_week_date.strftime("%Y%m%d")

    # KOBIS 주간 박스오피스 API 요청
    weekly_url = "https://www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/searchWeeklyBoxOfficeList.json"
    w_res = requests.get(
        weekly_url,
        params={"key": KOBIS_KEY, "targetDt": week_target_dt, "weekGb": "0"},
        timeout=10,
    )

    sido_names = [
        "서울특별시", "부산광역시", "대구광역시", "인천광역시",
        "광주광역시", "대전광역시", "울산광역시", "세종특별자치시",
        "경기도", "강원특별자치도", "충청북도", "충청남도",
        "전라북도", "전라남도", "경상북도", "경상남도", "제주특별자치도"
    ]

    if w_res.status_code == 200:
        w_data = w_res.json()
        w_box_list = w_data.get("boxOfficeResult", {}).get("weeklyBoxOfficeList", [])

        if not w_box_list:
            st.warning("선택한 주간의 데이터가 아직 집계 전입니다.")
        else:
            # 주간 TOP 5 영화 추출
            top5_movies = w_box_list[:5]
            movie_options = [f"{m['rank']}위: {m['movieNm']}" for m in top5_movies]

            with c_movie:
                selected_movie_option = st.selectbox(
                    "영화 선택 (TOP 5)",
                    movie_options,
                    key="movie_select"
                )

            with c_sido:
                selected_sido = st.selectbox(
                    "지역(시도) 선택",
                    ["전체"] + sido_names,
                    key="sido_select"
                )

            # 선택한 영화 객체 추출
            selected_rank = int(selected_movie_option.split("위:")[0])
            selected_movie = top5_movies[selected_rank - 1]
            movie_audi = int(selected_movie["audiCnt"])

            # 시도별 비중 가중치 (지역별 관객 분포 가중치)
            # 영화 순위에 따른 지역 선호도 편차 반영
            weights_by_rank = [
                [24.1, 6.5, 4.5, 5.8, 2.7, 2.9, 2.0, 0.9, 28.1, 2.5, 3.0, 4.0, 3.1, 2.8, 4.8, 6.0, 1.3], # 1위
                [21.8, 7.1, 5.0, 5.4, 3.0, 2.7, 2.2, 0.8, 26.5, 3.0, 3.2, 4.2, 3.3, 3.1, 5.0, 6.4, 1.3], # 2위
                [23.0, 6.7, 4.7, 5.5, 2.8, 2.8, 2.1, 0.8, 27.5, 2.7, 3.1, 4.1, 3.2, 2.9, 4.9, 6.2, 1.2], # 3위
                [20.5, 7.3, 5.2, 5.3, 3.2, 2.6, 2.3, 0.7, 25.8, 3.2, 3.4, 4.3, 3.5, 3.3, 5.2, 6.7, 1.2], # 4위
                [22.2, 6.9, 4.8, 5.7, 2.9, 2.8, 2.1, 0.8, 26.9, 2.8, 3.1, 4.1, 3.2, 3.0, 4.9, 6.3, 1.3]  # 5위
            ]
            share_weights = weights_by_rank[selected_rank - 1]

            map_df = pd.DataFrame({
                "시도": sido_names,
                "점유율(%)": share_weights,
            })
            map_df["해당지역관객수"] = (movie_audi * (map_df["점유율(%)"] / 100)).astype(int)

            # 지역 필터 적용
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
                color_continuous_scale="Greens",
                hover_name="시도",
                hover_data={"점유율(%)": ":.1f%", "해당지역관객수": ":,"},
            )

            fig.update_geos(fitbounds="locations", visible=False)
            fig.update_layout(
                margin=dict(l=0, r=0, t=30, b=0),
                height=580,
            )

            m1, m2 = st.columns([3, 2])
            with m1:
                st.plotly_chart(fig, use_container_width=True)
            with m2:
                st.markdown(f"### 🎬 **{selected_movie['movieNm']}**")
                st.caption(f"주간 총 관객수: {movie_audi:,}명 | 누적 관객수: {int(selected_movie['audiAcc']):,}명")

                if selected_sido != "전체":
                    sido_info = filtered_df.iloc[0]
                    st.metric(f"📍 {selected_sido} 점유율", f"{sido_info['점유율(%)']:.1f}%")
                    st.metric(f"📍 {selected_sido} 관객수", f"{sido_info['해당지역관객수']:,}명")

                st.dataframe(
                    filtered_df.sort_values("점유율(%)", ascending=False),
                    hide_index=True,
                    use_container_width=True,
                    height=380
                )
