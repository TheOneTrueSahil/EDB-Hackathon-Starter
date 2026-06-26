#!/usr/bin/env python3
import json
import sqlite3
from pathlib import Path
import yaml

REPO_ROOT = Path(__file__).parent
DATASETS_DIR = REPO_ROOT / "datasets"
DB_PATH = REPO_ROOT / "bank_data.db"

def main():
    print(f"Initializing SQLite database at: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    yaml_file = DATASETS_DIR / "bank.yaml"
    if not yaml_file.exists():
        print(f"Error: {yaml_file} not found.")
        return

    with open(yaml_file) as f:
        config = yaml.safe_load(f)

    for table in config.get("tables", []):
        table_name = table["name"]
        schema = table["schema"]
        
        # Build SQL table creation statement
        columns_sql = []
        for col in schema:
            col_name = col["name"]
            col_type = col["type"]
            # Map BigQuery types to SQLite types
            sqlite_type = "TEXT"
            if col_type == "INTEGER":
                sqlite_type = "INTEGER"
            elif col_type == "FLOAT":
                sqlite_type = "REAL"
            elif col_type == "BOOLEAN":
                sqlite_type = "INTEGER"
            
            columns_sql.append(f"{col_name} {sqlite_type}")
        
        create_sql = f"CREATE TABLE IF NOT EXISTS {table_name} ({', '.join(columns_sql)});"
        
        cursor.execute(f"DROP TABLE IF EXISTS {table_name};")
        cursor.execute(create_sql)
        print(f"Created table: {table_name}")

        # Seed data
        seed_file = table.get("seed_file")
        if seed_file:
            seed_path = REPO_ROOT / seed_file
            if seed_path.exists():
                inserted_count = 0
                with open(seed_path) as sf:
                    for line in sf:
                        line = line.strip()
                        if not line:
                            continue
                        row = json.loads(line)
                        
                        cols = list(row.keys())
                        vals = list(row.values())
                        placeholders = ", ".join(["?"] * len(vals))
                        
                        insert_sql = f"INSERT INTO {table_name} ({', '.join(cols)}) VALUES ({placeholders});"
                        cursor.execute(insert_sql, vals)
                        inserted_count += 1
                print(f"  Loaded {inserted_count} rows into {table_name}")
            else:
                print(f"  Warning: Seed file {seed_file} not found.")

    conn.commit()
    conn.close()
    print("Database seeding completed successfully!")

if __name__ == "__main__":
    main()
