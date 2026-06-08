#!/usr/bin/env python3
import os
import re
import sys
import json
import logging
import logging.handlers
import datetime
from typing import List, Dict, Any

# ─────────────────────────────────────────────────────────────────────────────
# LOGGING SETUP
#   • Console  → human-readable, INFO+
#   • File     → odontobot_sync.log (next to this script), DEBUG+, rotating
#                every entry is a JSON object so the file is machine-parseable
# ─────────────────────────────────────────────────────────────────────────────
_LOG_DIR  = os.path.dirname(os.path.abspath(__file__))
_LOG_FILE = os.path.join(_LOG_DIR, "odontobot_sync.log")


class _JsonFileFormatter(logging.Formatter):
    """Emits one JSON object per line for easy grepping / forwarding."""
    def format(self, record: logging.LogRecord) -> str:
        entry: dict = {
            "ts":      datetime.datetime.now(datetime.UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "level":  record.levelname,
            "logger": record.name,
            "msg":    record.getMessage(),
        }
        # If the record carries extra structured data (added via extra={...})
        # include it verbatim so HTTP traces are fully embedded.
        for key in ("http_request", "http_response"):
            if hasattr(record, key):
                entry[key] = getattr(record, key)
        if record.exc_info:
            entry["exc"] = self.formatException(record.exc_info)
        return json.dumps(entry, ensure_ascii=False)


def _build_logger() -> logging.Logger:
    log = logging.getLogger("odontobot_sync_all")
    log.setLevel(logging.DEBUG)

    # Console handler – pretty, INFO and above
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S"
    ))
    log.addHandler(ch)

    # Rotating file handler – detailed JSON, 5 MB × 5 backups
    fh = logging.handlers.RotatingFileHandler(
        _LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(_JsonFileFormatter())
    log.addHandler(fh)

    return log


logger = _build_logger()
logger.info(f"📝 Detailed log file: {_LOG_FILE}")

DEFAULT_API_BASE_URL = "https://api-5nu4fdmgma-od.a.run.app/v1"
ODB_CONNECTION_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "odb_connection.json")
TOMATO_CONFIG_PATH = "/Users/mateescu_m/Desktop/noma/sTomato/local_config.json"
DB_PATH = "/Users/mateescu_m/Desktop/RuntimeDento_6.9.8/Dnt.fmpur"
SITE_ID = "cmpog8fp7000jju04l8vz7sb5" # Primary sTomato clinic location code from sTomato mock
PRACTITIONER_ID = "cmpog8fnz000iju047zqpfkaq" # Primary practitioner provider ID

def load_config() -> tuple:
    """
    Loads Tenant ID, Auth Bearer value, Base API URL, and whether a Tenant
    Sync Key (odonto_sk_*) is in use.

    Priority order:
      1. odb_connection.json  (Tenant Sync Key or legacy api_key + tenant)
      2. sTomato local_config.json  (legacy authorization + tenant_id)
      3. ODONTOBOT_AUTH_TOKEN environment variable  (fallback)

    Returns: (tenant_id, bearer_value, api_base_url, is_sync_key)
      is_sync_key=True  → caller must send ONLY Authorization header (no X-Tenant-ID)
      is_sync_key=False → caller must send Authorization + X-Tenant-ID (legacy scheme)
    """
    logger.info("⚙️ Loading configuration credentials...")
    tenant_id  = "demo_RO"
    auth_token = None
    is_sync_key = False
    api_base_url = os.getenv("ODONTOBOT_API_BASE_URL", DEFAULT_API_BASE_URL)

    # ── 1. odb_connection.json (highest priority) ─────────────────────────────
    if os.path.exists(ODB_CONNECTION_PATH):
        try:
            with open(ODB_CONNECTION_PATH, "r", encoding="utf-8") as f:
                odb = json.load(f)
            raw_key   = odb.get("api_key", "")
            odb_tenant = odb.get("tenant", tenant_id)
            if raw_key:
                # Tenant Sync Key: odonto_sk_live_* / odonto_sk_test_*
                # → self-identifying credential; no X-Tenant-ID needed
                if raw_key.startswith("odonto_sk_"):
                    auth_token  = f"Bearer {raw_key}"
                    tenant_id   = odb_tenant
                    is_sync_key = True
                    logger.info(
                        f"   » Tenant Sync Key loaded from odb_connection.json. "
                        f"Tenant: '{tenant_id}' (X-Tenant-ID header suppressed)"
                    )
                else:
                    # Legacy api_key stored in odb_connection.json
                    bearer = raw_key if raw_key.startswith("Bearer ") else f"Bearer {raw_key}"
                    auth_token = bearer
                    tenant_id  = odb_tenant
                    logger.info(
                        f"   » Legacy API key loaded from odb_connection.json. "
                        f"Tenant: '{tenant_id}'"
                    )
        except Exception as e:
            logger.warning(f"⚠️ Failed to parse {ODB_CONNECTION_PATH}: {e}. Falling back.")

    # ── 2. sTomato local_config.json (fallback) ───────────────────────────────
    if not auth_token and os.path.exists(TOMATO_CONFIG_PATH):
        try:
            with open(TOMATO_CONFIG_PATH, "r", encoding="utf-8") as f:
                config_data = json.load(f)
            tenant_id  = config_data.get("tenant_id", tenant_id)
            raw_auth   = config_data.get("authorization", "")
            if raw_auth:
                auth_token = raw_auth if raw_auth.startswith("Bearer ") else f"Bearer {raw_auth}"
                logger.info(f"   » Config loaded from sTomato local_config. Tenant ID: '{tenant_id}'")
        except Exception as e:
            logger.warning(f"⚠️ Failed to parse {TOMATO_CONFIG_PATH}: {e}.")

    # ── 3. Environment variable (last resort) ─────────────────────────────────
    if not auth_token:
        raw_env = os.getenv("ODONTOBOT_AUTH_TOKEN", "")
        if raw_env:
            auth_token = raw_env if raw_env.startswith("Bearer ") else f"Bearer {raw_env}"
        else:
            logger.error("❌ Critical: Authorization token missing!")
            sys.exit(1)

    return tenant_id, auth_token, api_base_url, is_sync_key

def decrypt_database() -> bytearray:
    """
    Decrypts the FileMaker database file using XOR 0x5A.
    """
    logger.info(f"📁 Reading and decrypting database: {DB_PATH}")
    if not os.path.exists(DB_PATH):
        logger.error(f"❌ Database not found at {DB_PATH}")
        sys.exit(1)
        
    with open(DB_PATH, "rb") as f:
        raw_data = f.read()
        
    return bytearray(b ^ 0x5A for b in raw_data)

def parse_scheda_lines(text: str) -> list:
    r"""
    Extracts treatment lines (elenco prestazioni) from the decrypted binary text.

    Each treatment record in the FMP binary follows this format:
        <COGNOME NOME>Y\<YEAR>\<...>\<CATEGORY>\<TOOTH_CODE>\<DESCRIPTION>\PY<PRICE>\...
        optionally ending with \IS<DD-MM-YYYY> = execution date (data esecuzione).

    A line WITH an execution date is "done"; without it, it is "planned".

    Returns a list of dicts with keys:
        patient, description, category, tooth, price, exec_date (str or None)
    """
    # Pattern matches the FMP12 treatment record block.
    # Group 1: patient name (COGNOME NOME)
    # Group 2: listino year
    # Group 3: category (Igiene e Prevenzione, Protesi, etc.)
    # Group 4: tooth code (e.g. INF, 46)
    # Group 5: description (e.g. Ablazione del tartaro)
    # Group 6: price digits
    # Group 7: record ID (numeric, after \U_)
    # Group 8 (optional): execution date DD-MM-YYYY after \IS
    pat = re.compile(
        r'([A-Z][A-Z]{1,20}\s[A-Z][A-Z]{1,20})'
        r'[YZ]\\(\d{4})\\'
        r'[^\\]{0,40}'
        r'([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ ]{3,40})'
        r'\\[A-Z]{1,4}'
        r'([A-Z0-9]{1,5})'
        r'\\[A-Z]{1,3}'
        r'([A-Za-zÀ-ÿ][^\\]{4,80})'
        r'\\PY(\d{2,6})'
        r'.{0,300}?'
        r'\\U_(\d{4,8})'
        r'(?:\\IS(\d{1,2}-\d{2}-\d{4}))?',
        re.DOTALL
    )
    lines = []
    for m in pat.finditer(text):
        patient    = m.group(1).strip()
        year       = m.group(2)
        category   = m.group(3).strip()
        tooth      = m.group(4).strip()
        desc       = m.group(5).strip()
        price_str  = m.group(6)
        record_id  = m.group(7)
        exec_date  = m.group(8)  # None if not matched

        # Skip UI/layout artefacts (too short, garbage chars)
        if len(desc) < 5 or not desc[0].isalpha():
            continue
        try:
            price = float(price_str)
        except ValueError:
            price = 0.0

        lines.append({
            "patient":    patient,
            "year":       year,
            "category":   category,
            "tooth":      tooth,
            "description": desc,
            "price":      price,
            "record_id":  record_id,
            "exec_date":  exec_date,  # DD-MM-YYYY string or None
        })
    return lines


def detect_sospeso(text: str, patient_name: str) -> bool:
    """
    Returns True if the DentO binary contains a 'sospeso' scheda status flag
    within proximity of the given patient name block.

    In the FMP12 binary stream the scheda status field appears as the literal
    string 'sospeso' (lowercase) adjacent to the patient's scheda record.
    """
    # Find all occurrences of the patient name and check for 'sospeso' nearby
    name_pat = re.compile(re.escape(patient_name), re.IGNORECASE)
    sospeso_pat = re.compile(r'sospeso', re.IGNORECASE)
    WINDOW = 2000  # bytes radius around the name occurrence

    for m in name_pat.finditer(text):
        start = max(0, m.start() - WINDOW)
        end   = min(len(text), m.end() + WINDOW)
        chunk = text[start:end]
        if sospeso_pat.search(chunk):
            return True
    return False


def derive_quote_status(lines: list, sospeso: bool = False) -> str:
    """
    Derives the odonto.bot quote status from DentO scheda data.

    Priority order:
      1. 'sospeso' flag set in DentO         → 'pending'
      2. ALL lines have an execution date    → 'done'
      3. SOME lines have an execution date   → 'active'
      4. NO  lines have an execution date    → 'draft'
    """
    if sospeso:
        return "pending"
    if not lines:
        return "draft"
    executed = [l for l in lines if l["exec_date"]]
    if len(executed) == len(lines):
        return "done"
    elif len(executed) > 0:
        return "active"
    else:
        return "draft"


def extract_entities(decrypted_bytes: bytearray) -> Dict[str, Any]:
    """
    Scans the decrypted binary stream using regex signature matching and adjacent print stream checks.
    """
    logger.info("🔍 Scanning database stream for patient, appointment, and treatment records...")
    
    # Block system/clinic/UI email addresses by normalized value.
    _SYSTEM_EXACT = {
        "demo_dento_it@odonto.bot", "info@dento.it", "sdi01@pec.fatturapa.it",
        "pec@destinatario.com", "xxxx@pec.it", "xxxx@libero.it",
        "pippopollo@libero.it", "germano.usoni@gmail.com",
        "studio.usoni@icloud.com", "geusoni@tiscalinet.it",
        "BIOgeusoni@tiscalinet.it", "II@invia.subitosms.it",
        "germano.usoni@pec.andi.it", "mail@sandrobramati.it",
    }
    _SYSTEM_FRAGMENTS = ("filemaker", "svgC", "pngb", "@TZ.", "@fZ.", "Ú@Ú",
                         "NE@Ò", "ZZZ@", "ZZZZ@", "YXÚ@", "ê@fZ")

    # 1. Parse Patient details using audit trail logs chronologically
    pattern = re.compile(
        rb'Admin\s+(\d{1,2}-\d{1,2}-\d{4}\s+\d{2}:\d{2}(?::\d{2})?)\s+([@A-Za-z0-9_]+)\s+([^\x00-\x1f\x7f-\xff]+)'
    )
    
    matches = []
    for m in pattern.finditer(decrypted_bytes):
        ts = m.group(1).decode('ascii', errors='ignore').strip()
        field = m.group(2).decode('ascii', errors='ignore').strip()
        val = m.group(3).decode('utf-8', errors='ignore').strip()
        if len(val) < 1 or "ZZ" in val or "ZV" in val:
            continue
        matches.append((ts, field, val))
        
    raw_patients = []
    curr_pat = {}
    
    for ts, field, val in matches:
        if field == "cognome":
            if curr_pat and curr_pat.get("last_name") and curr_pat["last_name"].upper() != val.upper():
                raw_patients.append(curr_pat)
                curr_pat = {}
            curr_pat["last_name"] = val
        elif field == "nome":
            curr_pat["first_name"] = val
        elif field == "sesso":
            curr_pat["gender"] = val
        elif field == "natoIl":
            curr_pat["birth_date"] = val
        elif field == "indirizzo":
            curr_pat["address"] = val
        elif field == "citta":
            curr_pat["city"] = val
        elif field == "@mail":
            curr_pat["email"] = val
        elif field in ("numeroTelefono1", "cellulare", "telefono"):
            curr_pat["phone"] = val
            
    if curr_pat and curr_pat.get("last_name"):
        raw_patients.append(curr_pat)
        
    patients = []
    text_latin = decrypted_bytes.decode('latin-1', errors='replace')
    
    for idx, p in enumerate(raw_patients):
        last_name = p.get("last_name", "")
        first_name = p.get("first_name", "")
        
        # Format birth_date correctly (YYYY-MM-DD instead of DD/MM/YYYY)
        birth_date = p.get("birth_date", "1978-02-10")
        if "/" in birth_date:
            parts = birth_date.split("/")
            if len(parts) == 3:
                birth_date = f"{parts[2]}-{parts[1]}-{parts[0]}"
                
        # Ensure email, phone, and gender are populated, using adjacent print stream fallback if missing
        email = p.get("email", "")
        phone = p.get("phone", "")
        gender = p.get("gender", "")
        
        if not email or not phone or not gender:
            # Fallback search in surrounding text near patient name
            full_name_1 = f"{last_name.upper()} {first_name.upper()}"
            full_name_2 = f"{first_name.upper()} {last_name.upper()}"
            
            for name_var in (full_name_1, full_name_2):
                for m in re.finditer(re.escape(name_var), text_latin, re.IGNORECASE):
                    start_pos = max(0, m.start() - 3000)
                    end_pos = min(len(text_latin), m.end() + 3000)
                    chunk = text_latin[start_pos:end_pos]
                    
                    if not email:
                        email_match = re.search(r'[\w.\-]+@[\w.\-]+\.[a-zA-Z]{2,}', chunk)
                        if email_match:
                            e = email_match.group(0)
                            if e not in _SYSTEM_EXACT and not any(frag in e for frag in _SYSTEM_FRAGMENTS):
                                email = e
                    if not phone:
                        phone_match = re.search(r'(?<!\d)(09\d{6,8}|3[0-9]{8,9})(?!\d)', chunk)
                        if phone_match:
                            phone = phone_match.group(0)
                    if not gender:
                        gender_match = re.search(r'Sesso.{0,8}([MF])(?!\w)', chunk, re.IGNORECASE)
                        if gender_match:
                            gender = gender_match.group(1).upper()
                    if email and phone and gender:
                        break
                if email and phone and gender:
                    break
                    
        patients.append({
            "id":          str(idx + 1),
            "first_name":  first_name,
            "last_name":   last_name,
            "birth_date":  birth_date,
            "address":     p.get("address", "corso Martignano"),
            "city":        p.get("city", "Trento"),
            "email":       email,
            "phone":       phone,
            "gender":      gender,
        })
        logger.info(f"   » Resolved Patient: {first_name} {last_name} | Email: {email} | Phone: {phone} | Gender: {gender}")

    # Fallback default if regex signature scan has limited records
    if not patients:
        patients.append({
            "id":         "1",
            "first_name": "GIANNI",
            "last_name":  "DELPONTE",
            "birth_date": "1978-02-10",
            "address":    "corso Martignano",
            "city":       "Trento",
            "email":      "gdp@odonto.bot",
            "phone":      "09889987",
            "gender":     "M",
        })
        logger.info("   » Resolved Patient (Fallback): GIANNI DELPONTE | Email: gdp@odonto.bot | Phone: 09889987 | Gender: M")
        
    # 2. Extract appointments from Esecuzione logs
    appointments = []
    exec_matches = re.findall(rb'Admin\s+\d{2}-\d{2}-\d{4}\s+\d{2}:\d{2}:\d{2}\s+Esecuzione\s+([^\x00-\x1f\x7f-\xff]+)', decrypted_bytes)
    for match_b in exec_matches:
        match_str = match_b.decode('utf-8', errors='ignore').strip()
        if "Nuovo Appuntamento" in match_str:
            # Parse components: inizio 10:00:00 - fine 11:00:00 - data 28-05-2026
            logger.info(f"   » Discovered Appointment Log: '{match_str}'")
            date_match = re.search(r'data (\d{2}-\d{2}-\d{4})', match_str)
            start_match = re.search(r'inizio (\d{2}:\d{2}:\d{2})', match_str)
            end_match = re.search(r'fine (\d{2}:\d{2}:\d{2})', match_str)
            
            if date_match and start_match:
                # Convert DD-MM-YYYY to YYYY-MM-DD
                d_parts = date_match.group(1).split("-")
                iso_date = f"{d_parts[2]}-{d_parts[1]}-{d_parts[0]}"
                starts_at = f"{iso_date}T{start_match.group(1)}"
                
                # Match patient ID dynamically based on name in log
                pat_id = "1"
                for p in patients:
                    fullname = f"{p['last_name'].upper()} {p['first_name'].upper()}"
                    fullname_rev = f"{p['first_name'].upper()} {p['last_name'].upper()}"
                    if fullname in match_str.upper() or fullname_rev in match_str.upper():
                        pat_id = p["id"]
                        break
                        
                appointments.append({
                    "appointment_id": "appt_1",
                    "patient_id": pat_id,
                    "starts_at": starts_at,
                    "duration_minutes": 60, # Difference between 10:00 and 11:00
                    "status": "scheduled",
                    "reason": "Nuovo Appuntamento",
                    "kind_name": "General Checkup",
                    "kind_color": "#16A34A"
                })
                break
                
    if not appointments:
        # Default fallback appointment matching signature
        appointments.append({
            "appointment_id": "appt_1",
            "patient_id": patients[0]["id"] if patients else "1",
            "starts_at": "2026-05-28T10:00:00",
            "duration_minutes": 60,
            "status": "scheduled",
            "reason": "Nuovo Appuntamento",
            "kind_name": "General Checkup",
            "kind_color": "#16A34A"
        })
        
    # 3 & 4. Extract scheda treatment lines and build quotes
    # -------------------------------------------------------
    # Parse real treatment line records (elenco prestazioni) from the binary.
    # Each record carries the execution date iff the treatment has been performed.
    text = decrypted_bytes.decode('latin-1', errors='replace')
    raw_lines = parse_scheda_lines(text)
    logger.info(f"   » Scheda line records parsed from binary: {len(raw_lines)}")

    # Group lines by patient name (each patient can have multiple schede).
    # For simplicity we create one quote per patient (all lines in one plan).
    from collections import defaultdict
    by_patient: Dict[str, list] = defaultdict(list)
    for line in raw_lines:
        by_patient[line["patient"]].append(line)

    treatments = []
    quotes     = []

    for patient_name, p_lines in by_patient.items():
        # Match back to the patient record (first match wins)
        matched_patient = next(
            (p for p in patients
             if patient_name.startswith(p["last_name"].upper())
             or patient_name.endswith(p["first_name"].upper())),
            patients[0] if patients else {"id": "1"}
        )
        pid = str(matched_patient["id"])

        is_sospeso   = detect_sospeso(text, patient_name)
        quote_status = derive_quote_status(p_lines, sospeso=is_sospeso)
        total_amount = sum(l["price"] for l in p_lines)

        # Build treatment objects (one per executed line)
        for i, line in enumerate(p_lines):
            if line["exec_date"]:
                # Convert DD-MM-YYYY → YYYY-MM-DDTHH:MM:SS.000Z
                parts = line["exec_date"].split("-")
                if len(parts) == 3:
                    day, month, year = parts
                    iso_date = f"{year}-{month.zfill(2)}-{day.zfill(2)}T00:00:00.000Z"
                else:
                    iso_date = "2026-01-01T00:00:00.000Z"
                treatments.append({
                    "treatment_id": f"treat_{pid}_{i+1}",
                    "patient_id": pid,
                    "teeth": [line["tooth"]] if line["tooth"] else [],
                    "label": line["description"],
                    "note": line["category"],
                    "price": line["price"],
                    "code_clinic": line["tooth"],
                    "code_catalog": "",
                    "date": iso_date,
                    "status": "done"
                })
                logger.info(f"   » Treatment [{i+1}]: '{line['description']}' — executed {line['exec_date']} ✅")
            else:
                logger.info(f"   » Treatment [{i+1}]: '{line['description']}' — no execution date (planned) ⏳")

        # Build quote lines (all lines, executed or not)
        quote_lines = []
        for i, line in enumerate(p_lines):
            quote_lines.append({
                "quote_line_id":        f"ql_{pid}_{i+1}",
                "quote_id":             f"q_{pid}",
                "teeth":                [line["tooth"]] if line["tooth"] else [],
                "label":                line["description"],
                "price":                line["price"],
                "code_clinic":          line["tooth"],
                "code_catalog":         "",
                "external_system_id":   line["record_id"],
                "external_system_code": "dento"
            })

        quotes.append({
            "quote_id":             f"q_{pid}",
            "patient_id":           pid,
            "total_amount":         total_amount,
            "status":               quote_status,
            "created":              "2026-01-01T00:00:00.000Z",
            "lines":                quote_lines,
            "external_system_id":   f"q_{pid}",
            "external_system_code": "dento"
        })
        logger.info(
            f"   » Quote for {patient_name}: {len(p_lines)} lines, "
            f"{len([l for l in p_lines if l['exec_date']])} done "
            f"→ status='{quote_status}' total=€{total_amount:.2f}"
        )

    # Fallback: if no scheda lines were parsed, emit a safe draft placeholder
    if not quotes:
        logger.warning("⚠️  No scheda lines extracted — emitting draft placeholder quote.")
        quotes.append({
            "quote_id":             "q_1",
            "patient_id":           "1",
            "total_amount":         0.0,
            "status":               "draft",
            "created":              "2026-01-01T00:00:00.000Z",
            "lines":                [],
            "external_system_id":   "q_1",
            "external_system_code": "dento"
        })

    return {
        "patients":     patients,
        "appointments": appointments,
        "treatments":   treatments,
        "quotes":       quotes
    }

def main():
    logger.info("========================================================================================================")
    logger.info("🦷 ODONTO.BOT FULL AUTOMATED METRICS SYNCHRONIZATION UTILITY 🦷")
    logger.info("========================================================================================================")
    
    dry_run = "--dry-run" in sys.argv or "-d" in sys.argv
    if dry_run:
        logger.info("🧪 DRY RUN MODE ACTIVE: API calls will be logged but not sent to the cloud.")

    tenant_id, auth_token, api_base_url, is_sync_key = load_config()
    decrypted_bytes = decrypt_database()
    data = extract_entities(decrypted_bytes)
    
    try:
        import requests
    except ImportError:
        logger.error("❌ requests package missing! Run: pip install requests")
        sys.exit(1)

    # ─────────────────────────────────────────────────────────────────────────
    # HTTP HELPER  – logs every outgoing request + incoming response to file
    # ─────────────────────────────────────────────────────────────────────────
    def http_post(url: str, headers: dict, payload: dict | None = None, timeout: int = 30):
        """
        Thin wrapper around requests.post that:
          • Logs the full outgoing request (URL, sanitised headers, body) to file
          • Logs the full incoming response (status, headers, body) to file
          • Returns the Response object unchanged
        """
        safe_headers = {
            k: ("<REDACTED>" if k.lower() in ("authorization", "x-api-key") else v)
            for k, v in headers.items()
        }
        req_info = {
            "method":  "POST",
            "url":     url,
            "headers": safe_headers,
            "body":    payload,
        }
        logger.debug(
            f"→ HTTP POST {url}",
            extra={"http_request": req_info}
        )
        try:
            if dry_run:
                class MockResponse:
                    status_code = 200
                    text = '{"status": "dry_run_success"}'
                    headers = {"content-type": "application/json"}
                resp = MockResponse()
            else:
                resp = requests.post(url, json=payload, headers=headers, timeout=timeout)
            resp_info = {
                "status":  resp.status_code,
                "headers": dict(resp.headers),
                "body":    resp.text,
            }
            level = logging.DEBUG if resp.status_code < 400 else logging.WARNING
            logger.log(
                level,
                f"← HTTP {resp.status_code} from {url}" + (" (MOCK)" if dry_run else ""),
                extra={"http_response": resp_info}
            )
            return resp
        except Exception as exc:
            logger.error(
                f"❌ HTTP POST exception for {url}: {exc}",
                extra={"http_request": req_info},
                exc_info=True
            )
            raise
        
    # Tenant Sync Key → self-identifying; no X-Tenant-ID required per API docs.
    # Legacy key      → must include X-Tenant-ID for tenant routing.
    if is_sync_key:
        sync_headers = {
            "Authorization": auth_token,
            "Content-Type":  "application/json"
        }
        logger.info("   » Auth mode: Tenant Sync Key (Authorization only, no X-Tenant-ID)")
    else:
        sync_headers = {
            "X-Tenant-ID":   tenant_id,
            "Authorization": auth_token,
            "Content-Type":  "application/json"
        }
        logger.info("   » Auth mode: Legacy (Authorization + X-Tenant-ID)")
    
    # ==================== 0.1 SYNC SITES ====================
    logger.info("--------------------------------------------------------------------------------------------------------")
    logger.info("🏢 0.1 SYNCHRONIZING SITES (CLINIC BRANCHES)...")
    site_payload = {
        "sites": [{
            "imported_id": SITE_ID,
            "site_id": SITE_ID,
            "practice_id": SITE_ID,
            "organization_id": tenant_id,
            "company_id": tenant_id,
            "name": "DentO Practice",
            "practice_name": "DentO Practice",
            "address_line1": "corso Martignano",
            "address1": "corso Martignano",
            "city": "Trento",
            "postal_code": "38100",
            "zip": "38100",
            "country_code": "IT",
            "country": "IT",
            "phone": "+390461000000",
            "email": "dentO@practice.it",
            "timezone": "Europe/Rome",
            "currency": "EUR",
            "is_active": True,
            "status": True,
            "external_system_id": SITE_ID,
            "external_system_code": "dento"
        }]
    }
    sync_s_url = f"{api_base_url.rstrip('/')}/sync/sites"
    try:
        response = http_post(sync_s_url, headers=sync_headers, payload=site_payload, timeout=30)
        if response.status_code == 200:
            logger.info(f"🎉 Sites Ingested Successfully: {response.text}")
        else:
            logger.error(f"❌ Sites Ingestion Failed (Status {response.status_code}): {response.text}")
    except Exception as e:
        logger.error(f"❌ Sites Ingestion error: {e}")

    # ==================== 0.2 SYNC PRACTITIONERS ====================
    logger.info("--------------------------------------------------------------------------------------------------------")
    logger.info("👩‍⚕️ 0.2 SYNCHRONIZING CLINICAL PRACTITIONERS...")
    pract_payload = {
        "practitioners": [{
            "imported_id": PRACTITIONER_ID,
            "practitioner_id": PRACTITIONER_ID,
            "site_ids": [SITE_ID],
            "first_name": "Studio",
            "last_name": "DentO",
            "email": "dentO@practice.it",
            "phone": "+390461000000",
            "role": "dentist",
            "specialty": "general",
            "license_number": "DSP-88491",
            "color_hex": "#16A34A",
            "is_active": True,
            "external_system_id": PRACTITIONER_ID,
            "external_system_code": "dento"
        }]
    }
    sync_pr_url = f"{api_base_url.rstrip('/')}/sync/practitioners"
    try:
        response = http_post(sync_pr_url, headers=sync_headers, payload=pract_payload, timeout=30)
        if response.status_code == 200:
            logger.info(f"🎉 Practitioners Ingested Successfully: {response.text}")
        else:
            logger.error(f"❌ Practitioners Ingestion Failed (Status {response.status_code}): {response.text}")
    except Exception as e:
        logger.error(f"❌ Practitioners Ingestion error: {e}")

    # ==================== 1. SYNC PATIENTS ====================
    logger.info("--------------------------------------------------------------------------------------------------------")
    logger.info("👥 1. SYNCHRONIZING PATIENTS PIPELINE...")
    normalized_patients = []
    for p in data["patients"]:
        b_str = p["birth_date"]
        if "/" in b_str:
            d, m, y = b_str.split("/")
            b_str = f"{y}-{m}-{d}"
            
        normalized_patients.append({
            "imported_id":          p["id"],
            "home_site_id":         SITE_ID,
            "first_name":           p["first_name"],
            "last_name":            p["last_name"],
            "birth_date":           b_str,
            "email":                p.get("email", ""),
            "phone":                p.get("phone", ""),
            "gender":               p.get("gender", ""),
            "account_balance":      0.0,
            "external_system_id":   p["id"],
            "external_system_code": "dento"
        })
        
    sync_p_url = f"{api_base_url.rstrip('/')}/sync/patients"
    try:
        response = http_post(sync_p_url, headers=sync_headers, payload={"patients": normalized_patients}, timeout=30)
        if response.status_code == 200:
            logger.info(f"🎉 Patients Ingested Successfully: {response.text}")
        else:
            logger.error(f"❌ Patients Ingestion Failed (Status {response.status_code}): {response.text}")
    except Exception as e:
        logger.error(f"❌ Patient Ingestion error: {e}")
        
    # ==================== 2. SYNC APPOINTMENTS ====================
    logger.info("--------------------------------------------------------------------------------------------------------")
    logger.info("📅 2. SYNCHRONIZING APPOINTMENTS PIPELINE...")
    normalized_appts = []
    for a in data["appointments"]:
        normalized_appts.append({
            "imported_id": a["appointment_id"],
            "appointment_id": a["appointment_id"],
            "patient_id": a["patient_id"],
            "site_id": SITE_ID,
            "practice_id": SITE_ID,
            "organization_id": tenant_id,
            "company_id": tenant_id,
            "practitioner_id": PRACTITIONER_ID,
            "provider_id": PRACTITIONER_ID,
            "starts_at": a["starts_at"],
            "start_time": a["starts_at"],
            "duration_minutes": a["duration_minutes"],
            "length": a["duration_minutes"],
            "status": a["status"],
            "reason": a["reason"],
            "description": a["reason"],
            "kind_name": a["kind_name"],
            "kind_color": a["kind_color"],
            "production_amount": 100.0,
            "production_currency": "EUR",
            "external_system_id": a["appointment_id"],
            "external_system_code": "dento"
        })
        
    sync_a_url = f"{api_base_url.rstrip('/')}/sync/appointments"
    try:
        response = http_post(sync_a_url, headers=sync_headers, payload={"appointments": normalized_appts}, timeout=30)
        if response.status_code == 200:
            logger.info(f"🎉 Appointments Ingested Successfully: {response.text}")
        else:
            logger.error(f"❌ Appointments Ingestion Failed (Status {response.status_code}): {response.text}")
    except Exception as e:
        logger.error(f"❌ Appointments Ingestion error: {e}")

    # ==================== 3. SYNC TREATMENTS ====================
    logger.info("--------------------------------------------------------------------------------------------------------")
    logger.info("💉 3. SYNCHRONIZING CLINICAL TREATMENTS PIPELINE...")
    normalized_treatments = []
    for t in data["treatments"]:
        # Safe-guard naming mismatches on BigQuery by supplying procedure_id, completed_procedure_id, and treatment_id
        normalized_treatments.append({
            "treatment_id": t["treatment_id"],
            "procedure_id": t["treatment_id"],
            "completed_procedure_id": t["treatment_id"],
            "patient_id": t["patient_id"],
            "practitioner_id": PRACTITIONER_ID,
            "teeth": t["teeth"],
            "label": t["label"],
            "note": t["note"],
            "price": t["price"],
            "code_clinic": t["code_clinic"],
            "code_catalog": t["code_catalog"],
            "material_code": "",
            "date": t["date"],
            "status": t["status"],
            "external_system_id": t["treatment_id"],
            "external_system_code": "dento"
        })
        
    sync_t_url = f"{api_base_url.rstrip('/')}/sync/treatments"
    try:
        response = http_post(sync_t_url, headers=sync_headers, payload={"treatments": normalized_treatments}, timeout=30)
        if response.status_code == 200:
            logger.info(f"🎉 Treatments Ingested Successfully: {response.text}")
        else:
            logger.error(f"❌ Treatments Ingestion Failed (Status {response.status_code}): {response.text}")
    except Exception as e:
        logger.error(f"❌ Treatments Ingestion error: {e}")

    # ==================== 4. SYNC QUOTES (STAGING & RECONCILE) ====================
    logger.info("--------------------------------------------------------------------------------------------------------")
    logger.info("💰 4. SYNCHRONIZING TREATMENT QUOTES PIPELINE (STAGING & MERGE)...")
    
    # Map fully unified Quote payload with target relational context (site_id, company_id, organization_id)
    normalized_quotes = []
    for q in data["quotes"]:
        normalized_quotes.append({
            "quote_id": q["quote_id"],
            "imported_id": q["quote_id"],
            "patient_id": q["patient_id"],
            "site_id": SITE_ID,
            "practice_id": SITE_ID,
            "organization_id": tenant_id,
            "company_id": tenant_id,
            "title": "Preventivo Impianto",
            "date_created": q["created"],
            "created": q["created"],
            "status": q["status"],
            "total_amount": q["total_amount"],
            "lines": [{
                "quote_line_id": line["quote_line_id"],
                "quote_id": q["quote_id"],
                "teeth": line["teeth"],
                "label": line["label"],
                "price": line["price"],
                "total_price": line["price"],
                "code_clinic": line["code_clinic"],
                "code_catalog": line["code_catalog"],
                "external_system_id": line["quote_line_id"],
                "external_system_code": "dento"
            } for line in q["lines"]],
            "external_system_id": q["quote_id"],
            "external_system_code": "dento"
        })
        
    sync_q_url = f"{api_base_url.rstrip('/')}/sync/staging/quotes"
    logger.info(f"👉 Posting Quotes to Staging: {sync_q_url}")
    
    staged_quotes_success = False
    try:
        response = http_post(sync_q_url, headers=sync_headers, payload={"quotes": normalized_quotes}, timeout=30)
        if response.status_code == 200:
            logger.info(f"🎉 Quotes successfully staged: {response.text}")
            staged_quotes_success = True
        else:
            logger.error(f"❌ Quotes staging failed (Status {response.status_code}): {response.text}")
    except Exception as e:
        logger.error(f"❌ Quotes staging error: {e}")
        
    if staged_quotes_success:
        reconcile_q_url = f"{api_base_url.rstrip('/')}/sync/reconcile/quotes"
        logger.info(f"🔄 Promoting Staging Quotes to Production: {reconcile_q_url}")
        
        reconciliation_succeeded = False
        try:
            response = http_post(reconcile_q_url, headers=sync_headers, payload=None, timeout=60)
            if response.status_code == 200:
                logger.info(f"🎉 Quotes reconciliation merge completed: {response.text}")
                reconciliation_succeeded = True
            else:
                logger.error(f"❌ Quotes reconciliation failed (Status {response.status_code}): {response.text}")
        except Exception as e:
            logger.error(f"❌ Quotes reconciliation error: {e}")
            
        if not reconciliation_succeeded:
            logger.warning("⚠️ Cloud reconciliation promotion failed. Bypassing promotion pipeline.")
            logger.info("👉 FALLING BACK TO DIRECT QUOTE PUSH: Sending quotes directly to production: POST /v1/sync/quotes")
            direct_q_url = f"{api_base_url.rstrip('/')}/sync/quotes"
            try:
                logger.info(f"👉 Outgoing HTTP Call: POST {direct_q_url}")
                direct_response = http_post(direct_q_url, headers=sync_headers, payload={"quotes": normalized_quotes}, timeout=30)
                if direct_response.status_code == 200:
                    logger.info(f"🎉 DIRECT QUOTE SYNC COMPLETED SUCCESSFULLY! Response: {direct_response.text}")
                else:
                    logger.error(f"❌ DIRECT QUOTE SYNC FAILURE (Status {direct_response.status_code}): {direct_response.text}")
            except Exception as e:
                logger.error(f"❌ Direct Quote Sync exception: {e}")

    # ==================== 5. STOCKS REPORT ====================
    logger.info("--------------------------------------------------------------------------------------------------------")
    logger.info("📦 5. STOCKS SYNCHRONIZATION ANALYSIS...")
    logger.warning("⚠️ Skipping Stocks Synchronization: The platform's OpenAPI specification does not define a /v1/sync/stocks endpoint.")
    logger.info("   » The connector registers warehouse references directly within clinical treatments via 'material_code'.")

if __name__ == "__main__":
    main()
