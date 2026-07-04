import os

import psycopg2
from dotenv import load_dotenv

# Load the secret variables
load_dotenv()


def view_ledger():
    try:
        db_url = os.getenv("DATABASE_URL")
        conn = psycopg2.connect(db_url)
        cursor = conn.cursor()

        # Fetch all records, sorted by newest first
        cursor.execute("SELECT * FROM firm_financials ORDER BY created_at DESC;")
        rows = cursor.fetchall()

        print("\n📊 --- FIRM FINANCIALS LEDGER ---")
        if not rows:
            print("No records found. The database is empty.")

        for row in rows:
            # Row indexes match your column order:
            # 0:id, 1:type, 2:amount, 3:party, 4:file, 5:description, 6:date
            print(
                f"ID: {row[0]} | Type: {row[1]} | Amount: ₹{row[2]} | Party: {row[3]}"
            )
            print(f"   Details: {row[5]}")
            print(f"   Date: {row[6]}")
            print("-" * 50)

        cursor.close()
        conn.close()

    except Exception as e:
        print(f"⚠️ Error reading database: {e}")


if __name__ == "__main__":
    view_ledger()
