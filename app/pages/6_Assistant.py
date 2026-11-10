import streamlit as st

from app_data import secret                 # import first: it makes src/ importable
from assistant import MAX_QUESTIONS, build_agent, reply

st.set_page_config(page_title="Assistant", page_icon="💬", layout="wide")
st.title("Assistant")
st.caption("Ask about capital markets in plain English. An AI agent (LangChain) on Google Gemini. "
           "Version 1 explains concepts; access to the project's data comes next.")
st.caption("Questions are sent to Google Gemini, which may review them: please don't type personal information.")


def md(text):
    """Show dollar amounts as text: Streamlit would read $...$ as a math formula."""
    return text.replace("$", "\\$")


def explain(error):
    """A clear message for the visitor when Google can't answer."""
    text = str(error)
    if "429" in text or "RESOURCE_EXHAUSTED" in text:
        return "Too many questions right now (free tier limit). Please try again later."
    if any(code in text for code in ("503", "504", "UNAVAILABLE", "DEADLINE_EXCEEDED")):
        return "Google's AI is busy right now. Please try again in a minute."
    return f"The assistant isn't available right now ({error.__class__.__name__})."


key = secret("GOOGLE_API_KEY")
if not key:
    st.info("The assistant isn't set up here: GOOGLE_API_KEY is missing from the app's secrets.")
    st.stop()

if "chat" not in st.session_state:
    st.session_state.chat = []                      # the whole conversation, re-sent with every question
    st.session_state.agent = build_agent(api_key=key)
if st.session_state.chat and st.session_state.chat[-1]["role"] == "user":
    st.session_state.chat.pop()                     # a question interrupted by a newer one: drop it

for message in st.session_state.chat:
    with st.chat_message(message["role"]):
        st.markdown(md(message["content"]))

asked = sum(message["role"] == "user" for message in st.session_state.chat)
if asked >= MAX_QUESTIONS:
    st.info(f"That's {MAX_QUESTIONS} questions for this visit. Thank you for trying the assistant!")
    st.stop()

question = st.chat_input("Ask a question, for example: What is a bond?")
if question:
    st.session_state.chat.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(md(question))
    with st.chat_message("assistant"):
        try:
            with st.spinner("Thinking…"):
                answer = reply(st.session_state.agent, st.session_state.chat)
        except Exception as error:                  # drop the question, so the visitor can ask again
            st.session_state.chat.pop()
            st.error(explain(error))
            st.stop()
        st.markdown(md(answer))
    st.session_state.chat.append({"role": "assistant", "content": answer})
