import streamlit as st

from learn_content import load_topics

st.set_page_config(page_title="Learn", page_icon="📘", layout="wide")
st.title("Learn")
st.caption("The trading basics behind each page of this app, with a short quiz at the end of each topic.")


def md(text):
    """Show dollar amounts as text: Streamlit would read $...$ as a math formula."""
    return text.replace("$", "\\$")


topics = load_topics()
for tab, topic in zip(st.tabs([topic.title for topic in topics]), topics):
    with tab:
        st.markdown(md(topic.lesson))
        st.subheader("Quiz")
        score = 0
        for number, question in enumerate(topic.quiz, start=1):
            choice = st.radio(md(f"{number}. {question.text}"), list(question.options), index=None,
                              format_func=lambda letter, q=question: md(q.options[letter]),
                              key=f"{topic.title}-{number}")
            if choice is None:
                continue
            if choice == question.answer:
                score += 1
                st.success(md(f"Correct. {question.why}"))
            else:
                st.error(md(f"Not quite: the answer is \"{question.options[question.answer]}\". {question.why}"))
        st.caption(f"Score: {score} / {len(topic.quiz)}")
