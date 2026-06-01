#!/usr/bin/env python3
import re

LOG_PATH = "/Users/mateescu_m/.gemini/antigravity-ide/brain/23529550-9eec-4b7b-baf4-6c30b4471174/.system_generated/tasks/task-576.log"

def analyze_log():
    print(f"Analyzing log file: {LOG_PATH}")
    tables = {}
    columns = {}
    records = {}

    current_path = None
    
    with open(LOG_PATH, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            
            # Check for path lines
            # Example: [4].[1].[7].[78].
            if line.startswith('[') and line.endswith('.'):
                parts = re.findall(r'\[([^\]]+)\]', line)
                current_path = []
                for p in parts:
                    try:
                        current_path.append(int(p))
                    except ValueError:
                        current_path.append(p)
                continue
                
            # Check for POP or PUSH lines
            if line.startswith('-- POP') or line.startswith('-- PUSH') or line.startswith('-- data simple'):
                continue
                
            # Check for field declarations
            # Example: -- field (0x06): [16] => "AnagraficheFormEsterni" --
            field_match = re.search(r'-- field \((0x[0-9A-Fa-f]+)\): \[(\d+)\] => (.*) --', line)
            if field_match and current_path:
                field_type = field_match.group(1)
                field_id = int(field_match.group(2))
                field_val = field_match.group(3).strip()
                
                # Check for table metadata: [4].[1].[7].[TableID]
                if len(current_path) == 4 and current_path[0] == 4 and current_path[1] == 1 and current_path[2] == 7:
                    table_id = current_path[3]
                    if isinstance(table_id, int) and field_id == 16:
                        # Clean up quotes
                        if field_val.startswith('"') and field_val.endswith('"'):
                            field_val = field_val[1:-1]
                        tables[table_id] = field_val
                        
                # Check for columns under [4].[5].[TableID].[5].[ColumnID]
                if len(current_path) == 5 and current_path[0] == 4 and current_path[1] == 5 and current_path[3] == 5:
                    table_id = current_path[2]
                    column_id = current_path[4]
                    if isinstance(table_id, int) and isinstance(column_id, int) and field_id == 1:
                        if field_val.startswith('"') and field_val.endswith('"'):
                            field_val = field_val[1:-1]
                        if table_id not in columns:
                            columns[table_id] = {}
                        columns[table_id][column_id] = field_val
                        
                # Let's check for any other paths of type [4].[5].[TableID]
                if len(current_path) == 3 and current_path[0] == 4 and current_path[1] == 5:
                    table_id = current_path[2]
                    if field_id == 16:
                        if field_val.startswith('"') and field_val.endswith('"'):
                            field_val = field_val[1:-1]
                        tables[table_id] = field_val

    out_file = "/Users/mateescu_m/Desktop/RuntimeDento_6.9.8/fmptools/schema_output.txt"
    print(f"\nWriting all schema details to: {out_file}")
    with open(out_file, "w", encoding="utf-8") as out:
        out.write(f"Database Schema Layout from task-576.log\n")
        out.write(f"=========================================\n\n")
        out.write(f"Found {len(tables)} tables in metadata. Listing all tables with columns:\n")
        
        for tid, cols in sorted(columns.items()):
            tname = tables.get(tid, "Unknown Table Name")
            out.write(f"\n[+] Table ID {tid}: {tname} ({len(cols)} columns)\n")
            for cid, cname in sorted(cols.items()):
                out.write(f"  - Col {cid}: {cname}\n")

if __name__ == "__main__":
    analyze_log()
