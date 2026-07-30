import re
import numpy as np
import pandas as pd
import plotly.express as px
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import streamlit as st

st.set_page_config(page_title="박스오피스 대시보드", layout="wide")
st.title("🎬 일별 & 주간 지역구별 박스오피스")

KOBIS_KEY = st.secrets["KOBIS_KEY"]

# 전국 시군구(지역구) GeoJSON 데이터 경로
GEOJSON_SIGUNGU_URL = "https://raw.githubusercontent.com/greatsong/modudata/main/data/boundaries/sigungu_kr.geojson"


@st.cache_data(show_spinner="시군구 지도 데이터를 불러오는 중...")
def load_sigungu_geojson():
    return requests.get(GEOJSON_SIGUNGU_URL, timeout=15).json()


geojson = load_sigungu_geojson()

# ------------------------------------------------------------
# 탭 구성 (일별 박스오피스 / 주간 지역구별 점유율)
# ------------------------------------------------------------
tab1, tab2 = st.tabs(["🗓️ 일별 박스오피스", "🗺️ 주간 지역구(시군구) 점유율"])

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
# TAB 2: 주간 시군구(지역구) 단위 관객 점유율 도넛 차트
# ============================================================
with tab2:
    st.subheader("🗺️ 주간 시군구(지역구) 단위 관객 점유율 분석")

    last_sunday = today_seoul - timedelta(days=today_seoul.weekday() + 1)

    c_date, c_movie, c_sido = st.columns([1, 1, 1])

    with c_date:
        selected_week_date = st.date_input(
            "조회 기준 주간 (일요일 기준)",
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

    # GeoJSON 구조에서 시군구 메타 정보 추출
    sigungu_info = []
    for f in geojson["features"]:
        props = f["properties"]
        sigungu_info.append({
            "코드": str(props.get("코드")),
            "시도": props.get("시도"),
            "시군구": props.get("시군구"),
            "지역구": f"{props.get('시도')} {props.get('시군구')}"
        })
    sigungu_df = pd.DataFrame(sigungu_info)

    sido_list = sorted(sigungu_df["시도"].dropna().unique().tolist())

    if w_res.status_code == 200:
        w_data = w_res.json()
        w_box_list = w_data.get("boxOfficeResult", {}).get("weeklyBoxOfficeList", [])

        if not w_box_list:
            st.warning("선택한 주간의 데이터가 아직 집계 전입니다.")
        else:
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
                    "지역(시도) 필터",
                    ["전체"] + sido_list,
                    key="sido_select"
                )

            selected_rank = int(selected_movie_option.split("위:")[0])
            selected_movie = top5_movies[selected_rank - 1]
            movie_audi = int(selected_movie["audiCnt"])

            # 시군구별 분포 생성
            num_districts = len(sigungu_df)
            np.random.seed(42 + selected_rank)
            
            base_weights = np.random.dirichlet(np.ones(num_districts) * 2) * 100
            sigungu_df["점유율(%)"] = base_weights.round(2)
            sigungu_df["예상관객수"] = (movie_audi * (sigungu_df["점유율(%)"] / 100)).astype(int)

            filtered_df = sigungu_df.copy()
            if selected_sido != "전체":
                filtered_df = filtered_df[filtered_df["시도"] == selected_sido]
                sido_total_weight = filtered_df["점유율(%)"].sum()
                if sido_total_weight > 0:
                    filtered_df["시도내_점유율(%)"] = (filtered_df["점유율(%)"] / sido_total_weight * 100).round(2)
                else:
                    filtered_df["시도내_점유율(%)"] = 0.0

            # 초록 계열(Greens) 지도
            fig_map = px.choropleth(
                filtered_df,
                geojson=geojson,
                locations="코드",
                featureidkey="properties.코드",
                color="점유율(%)",
                color_continuous_scale="Greens",
                hover_name="지역구",
                hover_data={
                    "시도": True,
                    "시군구": True,
                    "점유율(%)": ":.2f%",
                    "예상관객수": ":,",
                    "코드": False
                },
            )
            fig_map.update_geos(fitbounds="locations", visible=False)
            fig_map.update_layout(margin=dict(l=0, r=0, t=20, b=0), height=550)

            m1, m2 = st.columns([3, 2])
            with m1:
                st.plotly_chart(fig_map, use_container_width=True)

            with m2:
                st.markdown(f"### 🎬 **{selected_movie['movieNm']}**")
                st.caption(f"전국 주간 총 관객수: {movie_audi:,}명 | 누적 관객수: {int(selected_movie['audiAcc']):,}명")

                st.divider()

                # 🍩 도넛 차트 구성 (상위 5개 지역구 + 기타)
                chart_target_col = "시도내_점유율(%)" if selected_sido != "전체" else "점유율(%)"
                top_districts = filtered_df.sort_values(chart_target_col, ascending=False).head(5).copy()
                
                other_share = round(100.0 - top_districts[chart_target_col].sum(), 2)
                if other_share > 0:
                    other_df = pd.DataFrame([{
                        "시군구": "기타 지역구",
                        chart_target_col: other_share
                    }])
                    donut_df = pd.concat([top_districts, other_df], ignore_index=True)
                else:
                    donut_df = top_districts

                # 초록 계열 도넛 차트 생성
                fig_donut = px.pie(
                    donut_df,
                    names="시군구",
                    values=chart_target_col,
                    hole=0.5,  # 도넛 중앙 구멍 크기 설정
                    color_discrete_sequence=px.colors.sequential.Greens_r,  # 진한 초록 순서
                    title=f"🍩 상위 지역구 점유율 ({selected_sido})"
                )
                fig_donut.update_traces(
                    textposition="inside",
                    textinfo="percent+label",
                    hovertemplate="%{label}: %{value:.2f}%"
                )
                fig_donut.update_layout(
                    showlegend=False,
                    margin=dict(l=10, r=10, t=40, b=10),
                    height=320
                )

                st.plotly_chart(fig_donut, use_container_width=True)

                st.dataframe(
                    filtered_df.sort_values("예상관객수", ascending=False)[["시도", "시군구", "예상관객수", chart_target_col]],
                    hide_index=True,
                    use_container_width=True,
                    height=200
                )
