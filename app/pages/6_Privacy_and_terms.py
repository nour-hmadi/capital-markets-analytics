import streamlit as st

st.set_page_config(page_title="Privacy and terms", page_icon="🔒", layout="wide")
st.title("Privacy and terms")
st.caption("Capital Markets Analytics is a portfolio project by Nour Hmadi. Last updated: 29 October 2026.")

st.header("Privacy policy", anchor="privacy")
st.markdown("""
- **What the app receives.** When you sign in with Google, Google shares your name, email address and
  profile picture. Only your email address is stored: it labels the trades you book on the Trade desk.
- **What is stored.** Your trades (instrument, direction, quantity, date, counterparty) and your email,
  in a PostgreSQL database hosted by Neon.
- **What is never done.** Your Google password is never seen. Nothing is sold or shared, and there is
  no advertising or tracking.
- **Guests.** Without signing in, nothing personal is collected, and guest trades are deleted every morning.
- **Deleting your data.** Delete your trades on the Trade desk at any time, or email the contact below
  to remove everything linked to your email.
- **Contact:** nour.hmadi.a@outlook.com
""")

st.header("Terms of use", anchor="terms")
st.markdown("""
- This is a learning and demonstration project. All market data is synthetic, and nothing here is
  financial advice.
- The app is provided as is, without any guarantee, and its data can be reset at any time.
- Each person can keep up to 20 trades. Please don't misuse or overload the service.
""")
