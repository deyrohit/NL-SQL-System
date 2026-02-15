import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
import os
from dotenv import load_dotenv


def create_tables(cursor):
    """Create tables if they do not exist"""

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS vehicle_cards (
        card_id INT PRIMARY KEY,
        vehicle_type TEXT,
        manufacturer TEXT,
        model TEXT,
        manufacture_year INT,
        created_at DATE
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS damage_detections (
        damage_id INT PRIMARY KEY,
        card_id INT REFERENCES vehicle_cards(card_id) ON DELETE CASCADE,
        panel_name TEXT,
        damage_type TEXT,
        severity TEXT,
        confidence DOUBLE PRECISION,
        detected_at DATE
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS repairs (
        repair_id INT PRIMARY KEY,
        card_id INT REFERENCES vehicle_cards(card_id) ON DELETE CASCADE,
        panel_name TEXT,
        repair_action TEXT,
        repair_cost DOUBLE PRECISION,
        approved BOOLEAN,
        created_at DATE
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS quotes (
        quote_id INT PRIMARY KEY,
        card_id INT REFERENCES vehicle_cards(card_id) ON DELETE CASCADE,
        total_estimated_cost DOUBLE PRECISION,
        currency TEXT,
        generated_at DATE
    );
    """)


def import_excel_to_postgres(excel_file, db_config):
    print(f"Reading Excel file: {excel_file}")

    try:
        vehicle_cards_df = pd.read_excel(excel_file, sheet_name="vehicle_cards")
        damage_detection_df = pd.read_excel(excel_file, sheet_name="damage_detection")
        repairs_df = pd.read_excel(excel_file, sheet_name="repairs")
        quotes_df = pd.read_excel(excel_file, sheet_name="quotes")
    except Exception as e:
        print(f"Error reading Excel file: {e}")
        return False

    print("Excel file loaded successfully")

    try:
        conn = psycopg2.connect(**db_config)
        cursor = conn.cursor()
        print("Connected to database")
    except Exception as e:
        print(f"Database connection failed: {e}")
        return False

    try:
        # Create tables
        create_tables(cursor)
        conn.commit()
        print("Tables verified/created")

        # Clear old data
        cursor.execute("TRUNCATE vehicle_cards CASCADE;")
        conn.commit()
        print("Existing data cleared")

        # Insert vehicle_cards
        vehicle_data = [
            (
                int(r.card_id),
                r.vehicle_type,
                r.manufacturer,
                r.model,
                int(r.manufacture_year),
                pd.to_datetime(r.created_at).date(),
            )
            for r in vehicle_cards_df.itertuples(index=False)
        ]

        execute_values(
            cursor,
            """
            INSERT INTO vehicle_cards
            (card_id, vehicle_type, manufacturer, model, manufacture_year, created_at)
            VALUES %s
            """,
            vehicle_data,
        )

        # Insert damage_detections
        damage_data = [
            (
                int(r.damage_id),
                int(r.card_id),
                r.panel_name,
                r.damage_type,
                r.severity,
                float(r.confidence),
                pd.to_datetime(r.detected_at).date(),
            )
            for r in damage_detection_df.itertuples(index=False)
        ]

        execute_values(
            cursor,
            """
            INSERT INTO damage_detections
            (damage_id, card_id, panel_name, damage_type, severity, confidence, detected_at)
            VALUES %s
            """,
            damage_data,
        )

        # Insert repairs
        repairs_data = [
            (
                int(r.repair_id),
                int(r.card_id),
                r.panel_name,
                r.repair_action,
                float(r.repair_cost),
                bool(r.approved),
                pd.to_datetime(r.created_at).date(),
            )
            for r in repairs_df.itertuples(index=False)
        ]

        execute_values(
            cursor,
            """
            INSERT INTO repairs
            (repair_id, card_id, panel_name, repair_action, repair_cost, approved, created_at)
            VALUES %s
            """,
            repairs_data,
        )

        # Insert quotes
        quotes_data = [
            (
                int(r.quote_id),
                int(r.card_id),
                float(r.total_estimated_cost),
                r.currency,
                pd.to_datetime(r.generated_at).date(),
            )
            for r in quotes_df.itertuples(index=False)
        ]

        execute_values(
            cursor,
            """
            INSERT INTO quotes
            (quote_id, card_id, total_estimated_cost, currency, generated_at)
            VALUES %s
            """,
            quotes_data,
        )

        conn.commit()

        # Verify counts
        cursor.execute("""
            SELECT 'vehicle_cards', COUNT(*) FROM vehicle_cards
            UNION ALL
            SELECT 'damage_detections', COUNT(*) FROM damage_detections
            UNION ALL
            SELECT 'repairs', COUNT(*) FROM repairs
            UNION ALL
            SELECT 'quotes', COUNT(*) FROM quotes
            ORDER BY 1;
        """)

        print("\nFinal row counts:")
        for table, count in cursor.fetchall():
            print(f"{table}: {count}")

        cursor.close()
        conn.close()
        print("\nImport completed successfully!")
        return True

    except Exception as e:
        conn.rollback()
        cursor.close()
        conn.close()
        print(f"\nImport failed: {e}")
        return False


def main():
    load_dotenv()

    excel_file = r"C:\Users\deyro\Downloads\Clearquote\SQL.xlsx"

    db_config = {
        "host": os.getenv("DB_HOST"),
        "port": int(os.getenv("DB_PORT")),
        "database": os.getenv("DB_NAME"),
        "user": os.getenv("DB_USER"),
        "password": os.getenv("DB_PASSWORD", ""),
    }

    print("ClearQuote Excel Data Import")

    if not os.path.exists(excel_file):
        print(f"Excel file not found: {excel_file}")
        return

    import_excel_to_postgres(excel_file, db_config)

if __name__ == "__main__":
    main()
