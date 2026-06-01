#!/usr/bin/env python3
import os
import re
import sqlite3
import json

DB_PATH = "/Users/mateescu_m/Desktop/RuntimeDento_6.9.8/Dnt.fmpur"
SQLITE_OUT = "/Users/mateescu_m/Desktop/RuntimeDento_6.9.8/Dnt_Decrypted_Sig.sqlite"
JSON_OUT = "/Users/mateescu_m/Desktop/RuntimeDento_6.9.8/Dnt_Decrypted_Sig.json"

def decrypt_database():
    print(f"Reading database file: {DB_PATH}")
    if not os.path.exists(DB_PATH):
        raise FileNotFoundError(f"Could not find {DB_PATH}")
        
    with open(DB_PATH, "rb") as f:
        raw_data = f.read()
        
    print(f"XOR Decrypting {len(raw_data)} bytes with 0x5A...")
    # Fast in-place decryption
    decrypted = bytearray(b ^ 0x5A for b in raw_data)
    return decrypted

def parse_pazienti(decrypted_bytes):
    print("Extracting patient records using regex...")
    pattern = re.compile(
        rb'Admin\s+\d{2}-\d{2}-\d{4}\s+\d{2}:\d{2}:\d{2}\s+([A-Za-z_]+)\s+([^\x00-\x1f\x7f-\xff]+)'
    )
    
    matches = pattern.findall(decrypted_bytes)
    print(f"Found {len(matches)} raw signature fields.")
    
    records = {}
    for field_name_b, val_b in matches:
        field_name = field_name_b.decode('ascii', errors='ignore').strip()
        val = val_b.decode('utf-8', errors='ignore').strip()
        
        # Filter out junk words or control commands
        if len(val) < 2 or "ZZ" in val or "ZV" in val:
            continue
            
        if field_name not in records:
            records[field_name] = []
        records[field_name].append(val)
        
    # Clean and structure Pazienti
    patients = []
    cognomi = records.get("cognome", [])
    nomi = records.get("nome", [])
    indirizzi = records.get("indirizzo", [])
    citta = records.get("citta", [])
    cap = records.get("cap", [])
    born = records.get("natoIl", [])
    
    print(f"Details extracted: cognomi={len(cognomi)}, nomi={len(nomi)}, indirizzi={len(indirizzi)}")
    
    limit = min(len(cognomi), len(nomi))
    seen = set()
    for i in range(limit):
        key = (cognomi[i].upper(), nomi[i].upper())
        if key in seen:
            continue
        seen.add(key)
        
        patient = {
            "id": i + 1,
            "first_name": nomi[i],
            "last_name": cognomi[i],
            "birth_date": born[i] if i < len(born) else "",
            "address": indirizzi[i] if i < len(indirizzi) else "",
            "city": citta[i] if i < len(citta) else "",
            "zip_code": cap[i] if i < len(cap) else ""
        }
        patients.append(patient)
        
    return patients

def parse_invoices(decrypted_bytes):
    print("Extracting invoices...")
    cc_cognome = re.findall(rb'CC_cognome\x00+([^\x00-\x1f\x7f-\xff]+)', decrypted_bytes)
    dg_numero = re.findall(rb'DG_numero\x00+([^\x00-\x1f\x7f-\xff]+)', decrypted_bytes)
    dg_importo = re.findall(rb'DG_importo_totale\x00+([^\x00-\x1f\x7f-\xff]+)', decrypted_bytes)
    
    invoices = []
    limit = min(len(cc_cognome), len(dg_numero), len(dg_importo))
    for i in range(limit):
        invoices.append({
            "id": i + 1,
            "client_name": cc_cognome[i].decode('utf-8', errors='ignore').strip(),
            "invoice_number": dg_numero[i].decode('utf-8', errors='ignore').strip(),
            "amount": dg_importo[i].decode('utf-8', errors='ignore').strip()
        })
    return invoices

def save_to_sqlite(patients, invoices):
    print(f"Saving to SQLite: {SQLITE_OUT}")
    if os.path.exists(SQLITE_OUT):
        os.remove(SQLITE_OUT)
        
    conn = sqlite3.connect(SQLITE_OUT)
    cursor = conn.cursor()
    
    cursor.execute('''
    CREATE TABLE Pazienti (
        id INTEGER PRIMARY KEY,
        first_name TEXT,
        last_name TEXT,
        birth_date TEXT,
        address TEXT,
        city TEXT,
        zip_code TEXT
    )
    ''')
    for p in patients:
        cursor.execute('''
        INSERT INTO Pazienti (first_name, last_name, birth_date, address, city, zip_code)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', (p['first_name'], p['last_name'], p['birth_date'], p['address'], p['city'], p['zip_code']))
        
    cursor.execute('''
    CREATE TABLE Fatture (
        id INTEGER PRIMARY KEY,
        client_name TEXT,
        invoice_number TEXT,
        amount TEXT
    )
    ''')
    for inv in invoices:
        cursor.execute('''
        INSERT INTO Fatture (client_name, invoice_number, amount)
        VALUES (?, ?, ?)
        ''', (inv['client_name'], inv['invoice_number'], inv['amount']))
        
    conn.commit()
    conn.close()
    print("SQLite database created.")

def save_to_json(patients, invoices):
    data = {
        "pazienti": patients,
        "fatture": invoices
    }
    with open(JSON_OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    print("JSON file saved.")

def main():
    try:
        decrypted = decrypt_database()
        patients = parse_pazienti(decrypted)
        invoices = parse_invoices(decrypted)
        
        print(f"\n--- Extracted Summary ---")
        print(f"  Patients: {len(patients)}")
        print(f"  Invoices: {len(invoices)}")
        
        if patients:
            print("\nSample patient records:")
            for p in patients[:5]:
                print(f"  - {p['first_name']} {p['last_name']} (Born: {p['birth_date']}, Address: {p['address']})")
                
        save_to_sqlite(patients, invoices)
        save_to_json(patients, invoices)
    except Exception as e:
        print(f"Error during extraction: {e}")

if __name__ == "__main__":
    main()
