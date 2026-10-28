"""Clear the guest sandbox: delete every trade booked by guests. The refresh workflow runs it every morning."""
from sqlalchemy import create_engine, text

from load_db import DATABASE_URL


def main():
    with create_engine(DATABASE_URL).begin() as conn:
        deleted = conn.execute(text("DELETE FROM desk_trades WHERE owner = 'guest'")).rowcount
    print(f"Cleared {deleted} guest trades")


if __name__ == "__main__":
    main()
