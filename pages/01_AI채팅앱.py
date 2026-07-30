import io
from gtts import gTTS
import streamlit as st
from openai import OpenAI

# 페이지 기본 설정
st.set_page_config(page_title="AI 정보 선생님", page_icon="🤖", layout="wide")
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

# 대화 기록 저장소 생성
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "system", "content": SYSTEM_PROMPT}]

# [기능 1] 사이드바 - 대화 초기화 버튼
with st.sidebar:
    st.header("⚙️ 설정 및 메뉴")
    if st.button("🔄 대화 내용 초기화", use_container_width=True):
        st.session_state.messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        st.rerun()

# [기능 2] 메인 화면 - 추천 질문 버튼
st.caption("💡 궁금한 추천 질문을 클릭하거나 직접 질문을 입력해 보세요!")
col1, col2, col3 = st.columns(3)

prompt_to_send = None

if col1.button("🤖 인공지능이 뭐야?", use_container_width=True):
    prompt_to_send = "인공지능이 무엇인지 중학생도 이해하기 쉽게 알려줘."
if col2.button("🔍 알고리즘이란?", use_container_width=True):
    prompt_to_send = "알고리즘이 쉽게 말해서 무슨 뜻이야?"
if col3.button("🔐 개인정보가 왜 중요해?", use_container_width=True):
    prompt_to_send = "인터넷에서 개인정보를 왜 지켜야 하는지 알려줘."

# 이전 대화 내용들을 화면에 말풍선 형태로 출력 (system 프롬프트는 숨김)
for msg in st.session_state.messages:
    if msg["role"] != "system":
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

# 채팅 입력창
user_input = st.chat_input("궁금한 것을 물어보세요!")

# 추천 버튼을 눌렀거나 직접 질문을 입력했을 때 처리
if user_input:
    prompt_to_send = user_input

if prompt_to_send:
    # 1. 사용자의 질문을 대화 기록에 저장하고 화면에 즉시 표시
    st.session_state.messages.append({"role": "user", "content": prompt_to_send})
    with st.chat_message("user"):
        st.markdown(prompt_to_send)

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

            # AI의 답변도 대화 기록에 추가
            st.session_state.messages.append({"role": "assistant", "content": answer})

            # [기능 5] 음성 읽어주기 (TTS)
            if answer:
                sound_file = io.BytesIO()
                tts = gTTS(text=answer, lang="ko")
                tts.write_to_fp(sound_file)
                st.audio(sound_file, format="audio/mp3")

        except Exception:
            # 에러 발생 시 커스텀 안내 문구 표시
            st.error("응답을 받지 못했습니다. 잠시 후 다시 보내 주세요.")
