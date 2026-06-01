#!/usr/bin/env python3
import sqlite3

DB_PATH = "/Users/mateescu_m/Desktop/RuntimeDento_6.9.8/Dnt_Decrypted.sqlite"

def search_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cursor.fetchall()]
    
    print(f"Searching {len(tables)} tables for 'DELPONTE'...")
    
    found_any = False
    for table in tables:
        # Get column names
        cursor.execute(f"PRAGMA table_info(\"{table}\");")
        cols = [row[1] for row in cursor.fetchall()]
        if not cols:
            continue
            
        # We query for any row containing 'DELPONTE' or 'Delponte'
        where_clauses = [f"\"{col}\" LIKE '%DELPONTE%'" for col in cols]
        where_sql = " OR ".join(where_clauses)
        
        query = f"SELECT * FROM \"{table}\" WHERE {where_sql};"
        try:
            cursor.execute(query)
            rows = cursor.fetchall()
            if rows:
                print(f"\n[+] Found in table '{table}': {len(rows)} matching rows!")
                for r in rows:
                    # Zip with column names and print non-empty fields
                    row_details = {cols[idx]: r[idx] for idx in range(len(cols)) if r[idx]}
                    print(f"  Row details: {row_details}")
                found_any = True
        except sqlite3.OperationalError as e:
            # Handle some system tables that can't be queried this way
            continue
            
    if not found_any:
        print("\n[!] No records matching 'DELPONTE' found in relational SQLite tables yet.")
        
    conn.close()

if __name__ == "__main__":
    search_db()
