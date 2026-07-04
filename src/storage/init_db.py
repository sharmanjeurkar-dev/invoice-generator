import os

import psycopg2
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")


def setup_database():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS firm_financials (
                id SERIAL PRIMARY KEY,
                transaction_type VARCHAR(50) NOT NULL, -- 'EARNING' or 'EXPENDITURE'
                amount NUMERIC NOT NULL,
                party_name VARCHAR(255),               -- Client Name or Vendor Name
                reference_file TEXT,                   -- The PDF filename or receipt
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.commit()
        cursor.close()
        conn.close()
        print("✅ PostgreSQL 'firm_financials' ledger initialized successfully!")
    except Exception as e:
        print(f"⚠️ Failed to connect to PostgreSQL: {e}")


if __name__ == "__main__":
    setup_database()
