from io import BytesIO
import json

from openai import OpenAI
from supabase import Client, create_client
import streamlit as st
from pypdf import PdfReader


st.set_page_config(
    page_title="PDF 문서 뷰어",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
        :root { --ink: #172033; --muted: #6d7788; --line: #e7ebf1; --soft: #f6f8fb; --brand: #5b5bd6; }
        .stApp { background: #f7f8fc; }
        [data-testid="stSidebar"] { background: #ffffff; border-right: 1px solid var(--line); }
        [data-testid="stSidebar"] > div:first-child { padding: 2rem 1.25rem; }
        .brand { display: flex; align-items: center; gap: .7rem; margin-bottom: 2.5rem; }
        .brand-mark { display: grid; width: 2.25rem; height: 2.25rem; place-items: center; color: white; background: var(--brand); border-radius: .7rem; font-size: 1.1rem; }
        .brand-name { color: var(--ink); font-size: 1rem; font-weight: 800; letter-spacing: -.03em; }
        .sidebar-section-label { margin: 0 0 .65rem; color: var(--muted); font-size: .72rem; font-weight: 800; letter-spacing: .08em; text-transform: uppercase; }
        .document-card { margin-top: 1rem; padding: 1rem; background: var(--soft); border: 1px solid var(--line); border-radius: .8rem; }
        .document-name { overflow: hidden; color: var(--ink); font-size: .9rem; font-weight: 700; text-overflow: ellipsis; white-space: nowrap; }
        .document-meta { margin-top: .35rem; color: var(--muted); font-size: .8rem; }
        .hero-kicker { margin: 0 0 .45rem; color: var(--brand); font-size: .75rem; font-weight: 800; letter-spacing: .1em; text-transform: uppercase; }
        .hero-title { margin: 0; color: var(--ink); font-size: clamp(1.8rem, 4vw, 2.6rem); font-weight: 800; letter-spacing: -.06em; }
        .hero-description { margin: .65rem 0 2rem; color: var(--muted); font-size: .95rem; }
        [data-testid="stMetric"] { padding: 1rem; background: white; border: 1px solid var(--line); border-radius: .8rem; }
        div[data-testid="stExpander"] { overflow: hidden; margin-bottom: .7rem; background: white; border: 1px solid var(--line); border-radius: .75rem; }
        div[data-testid="stExpander"] summary p { color: var(--ink); font-weight: 700; }
        .empty-state { padding: 4rem 1rem; color: var(--muted); background: white; border: 1px dashed #cfd6e2; border-radius: .9rem; text-align: center; }
        .empty-state-icon { margin-bottom: .8rem; font-size: 2.2rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

if "summary_result" not in st.session_state:
    st.session_state.summary_result = None
if "summary_document_key" not in st.session_state:
    st.session_state.summary_document_key = None
if "summary_record_id" not in st.session_state:
    st.session_state.summary_record_id = None
if "quiz_result" not in st.session_state:
    st.session_state.quiz_result = None


@st.cache_resource
def get_supabase_client() -> Client:
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])


def update_saved_quiz(quiz_result: dict) -> None:
    get_supabase_client().table("summaries").update(
        {"quiz": quiz_result}
    ).eq("id", st.session_state.summary_record_id).execute()


with st.sidebar:
    st.markdown(
        '<div class="brand"><div class="brand-mark">▤</div><div class="brand-name">PDF 문서 뷰어</div></div>',
        unsafe_allow_html=True,
    )
    st.markdown('<p class="sidebar-section-label">문서 업로드</p>', unsafe_allow_html=True)
    uploaded_file = st.file_uploader(
        "PDF 업로드", type=["pdf"], accept_multiple_files=False, label_visibility="collapsed"
    )

    page_count = 0
    reader = None
    if uploaded_file is not None:
        try:
            reader = PdfReader(BytesIO(uploaded_file.getvalue()))
            page_count = len(reader.pages)
            st.markdown(
                f'<div class="document-card"><div class="document-name" title="{uploaded_file.name}">📄 {uploaded_file.name}</div><div class="document-meta">총 {page_count}페이지</div></div>',
                unsafe_allow_html=True,
            )
        except Exception as error:
            st.error(f"PDF를 읽는 중 문제가 발생했습니다: {error}")
    else:
        st.caption("분석할 PDF 파일을 선택해주세요.")


page_texts = []
if reader is not None:
    page_texts = [(page.extract_text() or "").strip() for page in reader.pages]
    document_key = f"{uploaded_file.name}:{uploaded_file.size}"
    if st.session_state.summary_document_key != document_key:
        st.session_state.summary_document_key = document_key
        st.session_state.summary_result = None
        st.session_state.summary_record_id = None
        st.session_state.quiz_result = None


st.markdown('<p class="hero-kicker">DOCUMENT WORKSPACE</p>', unsafe_allow_html=True)
st.markdown('<h1 class="hero-title">문서 원문</h1>', unsafe_allow_html=True)
st.markdown(
    '<p class="hero-description">업로드한 PDF의 텍스트를 페이지별로 확인할 수 있습니다.</p>',
    unsafe_allow_html=True,
)

tab_summary, tab_quiz, tab_original, tab_history = st.tabs(
    ["요약", "퀴즈", "원문", "저장 기록"]
)

with tab_summary:
    if reader is None:
        st.markdown(
            '<div class="empty-state"><div class="empty-state-icon">✨</div><div>사이드바에서 PDF를 업로드하면<br>AI 요약을 확인할 수 있습니다.</div></div>',
            unsafe_allow_html=True,
        )
    else:
        st.subheader("AI 요약")
        st.caption("PDF 전체 텍스트를 gpt-4o-mini로 분석합니다.")

        if st.button("요약하기", type="primary"):
            full_text = "\n\n".join(
                f"[페이지 {page_number}]\n{page_text}"
                for page_number, page_text in enumerate(page_texts, start=1)
                if page_text
            )

            if not full_text:
                st.warning("요약할 수 있는 텍스트가 없습니다.")
            else:
                system_prompt = """
PDF 본문을 분석하고 반드시 유효한 JSON 객체만 반환하세요.
JSON에는 다음 세 가지 키를 포함해야 합니다.
- "핵심 요약": 문장 3개로 작성한 핵심 요약
- "주요 키워드": 핵심 키워드 5개의 배열
- "난이도": "상", "중", "하" 중 하나
""".strip()

                try:
                    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
                    response = client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": full_text},
                        ],
                        response_format={"type": "json_object"},
                    )
                    st.session_state.summary_result = json.loads(
                        response.choices[0].message.content or "{}"
                    )
                except KeyError:
                    st.error("OpenAI API 키가 설정되지 않았습니다. .streamlit/secrets.toml을 확인해주세요.")
                except Exception as error:
                    st.error(f"요약을 생성하는 중 문제가 발생했습니다: {error}")

        if st.session_state.summary_result is not None:
            summary = st.session_state.summary_result
            st.markdown("### 핵심 요약")
            st.write(summary.get("핵심 요약", "요약 내용이 없습니다."))

            st.markdown("### 주요 키워드")
            keywords = summary.get("주요 키워드", [])
            st.write(" · ".join(keywords) if isinstance(keywords, list) else keywords)

            st.markdown("### 난이도")
            st.info(summary.get("난이도", "정보 없음"))

            if st.button("저장", type="secondary"):
                try:
                    inserted = get_supabase_client().table("summaries").insert(
                        {
                            "filename": uploaded_file.name,
                            "summary": summary,
                            "quiz": None,
                        }
                    ).select("id").execute()
                    st.session_state.summary_record_id = inserted.data[0]["id"]
                    if st.session_state.quiz_result is not None:
                        update_saved_quiz(st.session_state.quiz_result)
                    st.success("요약 결과를 저장했습니다.")
                except Exception as error:
                    st.error(f"요약을 저장하는 중 문제가 발생했습니다: {error}")

with tab_quiz:
    if reader is None:
        st.markdown(
            '<div class="empty-state"><div class="empty-state-icon">🧠</div><div>사이드바에서 PDF를 업로드하면<br>퀴즈를 만들 수 있습니다.</div></div>',
            unsafe_allow_html=True,
        )
    elif st.session_state.summary_result is None:
        st.info("먼저 요약 탭에서 요약을 만들어주세요.")
    else:
        st.subheader("학습 퀴즈")
        if st.button("퀴즈 만들기", type="primary"):
            quiz_system_prompt = """당신은 학습 퀴즈를 만드는 도우미입니다.
주어진 요약을 바탕으로 4지선다 퀴즈 3문항을 만드세요.
각 문항은 question, options(4개), answer(정답 인덱스, 0부터 시작), explanation을 포함해야 합니다.
결과는 {"questions": [...]} 형태의 JSON으로 반환하세요."""
            summary_input = json.dumps(st.session_state.summary_result, ensure_ascii=False)

            try:
                client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": quiz_system_prompt},
                        {"role": "user", "content": summary_input},
                    ],
                    response_format={"type": "json_object"},
                )
                st.session_state.quiz_result = json.loads(
                    response.choices[0].message.content or "{}"
                )

                if st.session_state.summary_record_id is not None:
                    update_saved_quiz(st.session_state.quiz_result)
                else:
                    st.info("퀴즈는 만들어졌습니다. 저장된 요약이 없어 먼저 저장해주세요.")
            except KeyError:
                st.error("OpenAI API 키가 설정되지 않았습니다. .streamlit/secrets.toml을 확인해주세요.")
            except Exception as error:
                st.error(f"퀴즈를 생성하는 중 문제가 발생했습니다: {error}")

        if st.session_state.quiz_result is not None:
            questions = st.session_state.quiz_result.get("questions", [])
            for question_number, question in enumerate(questions, start=1):
                st.markdown(f"### {question_number}. {question.get('question', '문제 내용 없음')}")
                options = question.get("options", [])
                selected_index = st.radio(
                    "보기",
                    options=list(range(len(options))),
                    format_func=lambda option_index: options[option_index],
                    index=None,
                    key=f"quiz-option-{question_number}",
                    label_visibility="collapsed",
                )

                if selected_index is not None:
                    answer_index = int(question.get("answer", -1))
                    if selected_index == answer_index:
                        st.success("정답입니다!")
                    else:
                        correct_answer = options[answer_index] if 0 <= answer_index < len(options) else "확인할 수 없음"
                        st.error(f"오답입니다. 정답: {correct_answer}")
                    st.caption(f"해설: {question.get('explanation', '해설이 없습니다.')}")

with tab_original:
    if reader is None:
        st.markdown(
            '<div class="empty-state"><div class="empty-state-icon">📑</div><div>사이드바에서 PDF를 업로드하면<br>페이지별 원문이 여기에 표시됩니다.</div></div>',
            unsafe_allow_html=True,
        )
    else:
        metric_col, status_col = st.columns([1, 3])
        with metric_col:
            st.metric("총 페이지", f"{page_count}페이지")
        with status_col:
            st.info(f"현재 문서: {uploaded_file.name}")

        for page_number, page_text in enumerate(page_texts, start=1):
            with st.expander(f"페이지 {page_number}", expanded=page_count == 1):
                if page_text:
                    st.text_area(
                        f"페이지 {page_number} 텍스트",
                        value=page_text,
                        height=300,
                        key=f"page-text-{page_number}",
                        label_visibility="collapsed",
                    )
                else:
                    st.info("추출할 수 있는 텍스트가 없습니다. 이미지로 저장된 PDF인지 확인해주세요.")

with tab_history:
    st.subheader("저장 기록")
    try:
        records = (
            get_supabase_client()
            .table("summaries")
            .select("id, filename, summary, created_at")
            .order("created_at", desc=True)
            .execute()
            .data
        )
    except Exception as error:
        records = []
        st.error(f"저장 기록을 불러오는 중 문제가 발생했습니다: {error}")

    if records:
        for record in records:
            record_col, delete_col = st.columns([5, 1])
            with record_col:
                saved_summary = record.get("summary") or {}
                summary_preview = saved_summary.get("핵심 요약", "요약 내용이 없습니다.")
                if len(summary_preview) > 120:
                    summary_preview = f"{summary_preview[:120]}..."
                st.markdown(f"**{record.get('filename', '이름 없는 파일')}**")
                st.caption(f"{record.get('created_at', '저장 시각 없음')} · {summary_preview}")
            with delete_col:
                if st.button("삭제", key=f"delete-summary-{record['id']}"):
                    try:
                        get_supabase_client().table("summaries").delete().eq(
                            "id", record["id"]
                        ).execute()
                        st.rerun()
                    except Exception as error:
                        st.error(f"기록을 삭제하는 중 문제가 발생했습니다: {error}")
    else:
        st.info("저장된 요약 기록이 없습니다.")
