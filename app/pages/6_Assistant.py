import streamlit as st

from app_data import ask_database, ask_desk, secret, send, signed_in_email   # first: it makes src/ importable
from assistant import MAX_QUESTIONS, build_agent, reply

st.set_page_config(page_title="Assistant", page_icon="💬", layout="wide")
st.title("Assistant")
st.caption("Ask about capital markets or the project's data, in plain English. An AI agent (LangChain) on "
           "Google Gemini explains concepts from the Learn notes, writes SQL that the API runs on the database "
           "as a read-only user, and drafts trades that only you can book.")
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


def describe(draft):
    tenor = f" · {draft['tenor_months']} months" if draft["tenor_months"] else ""
    return (f"**{draft['direction']} {draft['quantity']:,} {draft['underlying']}** · {draft['trade_date']} · "
            f"{draft['counterparty']}{tenor}")


def book(message):
    """The visitor's click books the draft, through the same API as the Trade desk page. The AI can't."""
    ok, result = send("POST", "/desk/trades", message["draft"], user=signed_in_email())
    message["status"] = (f"Booked {result['trade_id']} at {result['trade_price']:,}: "
                         "see it on the Trade desk page." if ok else f"Not booked: {result}")
    st.rerun()


def show(message, index):
    """One chat bubble, with what the answer is based on (SQL, Learn lessons) and any trade to confirm."""
    with st.chat_message(message["role"]):
        st.markdown(md(message["content"]))
        if message.get("sql"):
            with st.expander("The SQL behind this answer"):
                for query in message["sql"]:
                    st.code(query, language="sql")
        if message.get("lessons"):
            with st.expander("From the Learn notes"):
                st.markdown("\n".join(f"- {lesson}" for lesson in message["lessons"]))
        if message.get("draft"):
            st.info(f"Trade to confirm: {describe(message['draft'])}")
            if message.get("status"):
                st.markdown(message["status"])
            elif index == len(st.session_state.chat) - 1:          # only the latest draft can be booked
                left, right, _ = st.columns([1, 1, 4])
                if left.button("Book", key=f"book-{index}", type="primary"):
                    book(message)
                if right.button("Cancel", key=f"cancel-{index}"):
                    message["status"] = "Cancelled: nothing was booked."
                    st.rerun()


key = secret("GOOGLE_API_KEY")
if not key:
    st.info("The assistant isn't set up here: GOOGLE_API_KEY is missing from the app's secrets.")
    st.stop()

if "chat" not in st.session_state:
    st.session_state.chat = []                      # the whole conversation, re-sent with every question
    visitor = st.session_state.visitor = {}         # who is asking: the tools can't see st.user from their thread
    st.session_state.agent = build_agent(api_key=key, database=ask_database, desk=lambda method, path, body=None:
                                         ask_desk(method, path, body, user=visitor.get("email")))
if st.session_state.chat and st.session_state.chat[-1]["role"] == "user":
    st.session_state.chat.pop()                     # a question interrupted by a newer one: drop it

for index, message in enumerate(st.session_state.chat):
    show(message, index)

asked = sum(message["role"] == "user" for message in st.session_state.chat)
if asked >= MAX_QUESTIONS:
    st.info(f"That's {MAX_QUESTIONS} questions for this visit. Thank you for trying the assistant!")
    st.stop()

question = st.chat_input("Ask a question, for example: Which desk lost the most money?")
if question:
    st.session_state.chat.append({"role": "user", "content": question})
    show(st.session_state.chat[-1], len(st.session_state.chat) - 1)
    st.session_state.setdefault("visitor", {})["email"] = signed_in_email()      # read here, in Streamlit's thread
    try:
        with st.spinner("Thinking… (the first question about the data can take up to a minute)"):
            answer = reply(st.session_state.agent, st.session_state.chat)
    except Exception as error:                      # drop the question, so the visitor can ask again
        st.session_state.chat.pop()
        st.error(explain(error))
        st.stop()
    st.session_state.chat.append(answer)
    show(answer, len(st.session_state.chat) - 1)
