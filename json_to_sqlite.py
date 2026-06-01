#!/usr/bin/env python3
import json
import sqlite3
import re
import os

JSON_PATH = "/Users/mateescu_m/Desktop/RuntimeDento_6.9.8/Dnt_Decrypted.json"
SQLITE_PATH = "/Users/mateescu_m/Desktop/RuntimeDento_6.9.8/Dnt_Decrypted.sqlite"

def sanitize_name(name):
    # Replace spaces and special characters with underscores
    sanitized = re.sub(r'[^a-zA-Z0-9_]', '_', name)
    # Ensure it doesn't start with a number
    if sanitized and sanitized[0].isdigit():
        sanitized = "_" + sanitized
    return sanitized

def migrate():
    print(f"Loading decrypted JSON database from: {JSON_PATH}")
    if not os.path.exists(JSON_PATH):
        print(f"Error: {JSON_PATH} not found!")
        return

    with open(JSON_PATH, "r", encoding="utf-8", errors="ignore") as f:
        database = json.load(f)
        
    print(f"Loaded {len(database)} tables. Creating SQLite database: {SQLITE_PATH}")
    if os.path.exists(SQLITE_PATH):
        os.remove(SQLITE_PATH)
        
    conn = sqlite3.connect(SQLITE_PATH)
    cursor = conn.cursor()
    
    for table in database:
        table_name = sanitize_name(table["name"])
        columns_list = table["columns"]
        values_list = table.get("values", [])
        
        if not columns_list:
            continue
            
        # Sanitize column names and handle duplicates
        seen_cols = set()
        sanitized_columns = []
        for col in columns_list:
            colname = sanitize_name(col["name"])
            if not colname:
                colname = "empty_column"
            
            # De-duplicate column name (case-insensitive)
            orig_colname = colname
            counter = 2
            while colname.lower() in seen_cols:
                colname = f"{orig_colname}_{counter}"
                counter += 1
            
            seen_cols.add(colname.lower())
            sanitized_columns.append((col["name"], colname))
            
        print(f"Creating table '{table_name}' with {len(sanitized_columns)} columns and {len(values_list)} records...")
        
        # Build CREATE TABLE SQL statement
        col_defs = ", ".join([f'"{col[1]}" TEXT' for col in sanitized_columns])
        create_sql = f'CREATE TABLE "{table_name}" ({col_defs});'
        try:
            cursor.execute(create_sql)
        except sqlite3.OperationalError as e:
            print(f"  SQL Error creating table {table_name}: {e}")
            continue
            
        if not values_list:
            continue
            
        # Build INSERT SQL statement
        col_names_str = ", ".join([f'"{col[1]}"' for col in sanitized_columns])
        placeholders = ", ".join(["?" for _ in sanitized_columns])
        insert_sql = f'INSERT INTO "{table_name}" ({col_names_str}) VALUES ({placeholders});'
        
        # Prepare data for insertion
        rows_to_insert = []
        for row_dict in values_list:
            row_data = []
            for orig_name, _ in sanitized_columns:
                val = row_dict.get(orig_name, "")
                row_data.append(str(val) if val is not None else "")
            rows_to_insert.append(row_data)
            
        try:
            cursor.executemany(insert_sql, rows_to_insert)
        except sqlite3.OperationalError as e:
            print(f"  SQL Error inserting data into table {table_name}: {e}")
            
    conn.commit()
    conn.close()
    print("\nMigration to SQLite completed successfully!")
    print(f"Relational SQLite file created at: {SQLITE_PATH}")

if __name__ == "__main__":
    migrate()
