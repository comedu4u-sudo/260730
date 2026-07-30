import streamlit as st
from openai import OpenAI

# 페이지 기본 설정 (타이틀, 아이콘)
st.set_page_config(page_title="AI 정보 선생님", page_icon="🤖")
st.title("🤖 AI 정보 선생님")

# 비밀 금고(secrets)에서 API 키를 가져와 Upstage Solar API 접속 준비
client = OpenAI(
    api_key=st.secrets["SOLAR_API_KEY"],
    base_url="https://api.upstage.ai/v1",
)

# AI의 성격 설정 (화면에는 출력하지 않고 API 요청에만 전달)
SYSTEM_PROMPT = (
    "너는 중고등학생에게 설명하는 친절한 정보 선생님이야. "
    "어려운 말은 쉬운 말로 바꿔 주고, 반드시 순수 한국어로만 답해"
)

# 대화 기록 저장소 생성 (앱이 처음 실행될 때 한 번만 생성)
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "system", "content": SYSTEM_PROMPT}]

# 이전 대화 내용들을 화면에 말풍선 형태로 출력 (system 프롬프트는 숨김)
for msg in st.session_state.messages:
    if msg["role"] != "system":
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

# 질문 입력창 생성
user_input = st.chat_input("궁금한 것을 물어보세요!")

# 사용자가 입력창에 글을 남겼을 때 실행
if user_input:
    # 1. 사용자의 질문을 대화 기록에 저장하고 화면에 즉시 표시
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    # 2. AI 답변 생성 및 스트리밍 출력
    with st.chat_message("assistant"):
        try:
            # Solar API 요청 보내기
            stream = client.chat.completions.create(
                model="solar-open2",                 # 지정된 모델명 유지
                messages=st.session_state.messages,  # 전체 대화 히스토리 전달 (문맥 유지)
                reasoning_effort="none",             # 추론 기능 끄기 (빠른 응답)
                stream=True,                         # 실시간 스트리밍 출력
            )

            # 실시간으로 글자가 흘러나오도록 화면에 출력
            answer = st.write_stream(
                chunk.choices[0].delta.content or ""
                for chunk in stream
                if chunk.choices
            )

            # AI의 답변도 대화 기록에 추가하여 다음 질문 시 문맥 연결
            st.session_state.messages.append({"role": "assistant", "content": answer})

        except Exception:
            # 에러 발생 시 시스템 오류 창 대신 커스텀 안내 문구 표시
            st.error("응답을 받지 못했습니다. 잠시 후 다시 보내 주세요.")
