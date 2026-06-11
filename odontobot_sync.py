#!/usr/bin/env python3
import os
import re
import sys
import json
import sqlite3
import logging
import subprocess
from typing import List, Dict, Any

# Configure logging to console with premium aesthetics
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("odontobot_sync")

DEFAULT_API_BASE_URL = "https://link-5nu4fdmgma-od.a.run.app/v1"
TOMATO_CONFIG_PATH = "/Users/mateescu_m/Desktop/noma/sTomato/local_config.json"
SQLITE_DB_PATH = "/Users/mateescu_m/Desktop/RuntimeDento_6.9.8/Dnt_Decrypted_Sig.sqlite"

def load_config() -> tuple:
    """
    Loads API configurations (tenant_id, authorization token) from the sTomato local config.
    """
    logger.info("⚙️ Loading configuration credentials...")
    
    tenant_id = "demo_RO"
    auth_token = None
    api_base_url = os.getenv("ODONTOBOT_API_BASE_URL", DEFAULT_API_BASE_URL)
    
    if os.path.exists(TOMATO_CONFIG_PATH):
        try:
            with open(TOMATO_CONFIG_PATH, "r", encoding="utf-8") as f:
                config_data = json.load(f)
                tenant_id = config_data.get("tenant_id", tenant_id)
                auth_token = config_data.get("authorization")
                logger.info(f"   » Config loaded from parallel sTomato repository. Tenant ID: '{tenant_id}'")
        except Exception as e:
            logger.warning(f"⚠️ Failed to parse {TOMATO_CONFIG_PATH}: {e}. Using defaults.")
    else:
        logger.warning(f"⚠️ sTomato config file not found at {TOMATO_CONFIG_PATH}. Using default context.")

    # Fallback/Prompt if token is completely missing
    if not auth_token:
        # Check environment variable
        auth_token = os.getenv("ODONTOBOT_AUTH_TOKEN")
        if not auth_token:
            logger.error("❌ Critical: Authorization token is missing! Please provide it in sTomato local_config.json or as ODONTOBOT_AUTH_TOKEN env variable.")
            sys.exit(1)
            
    return tenant_id, auth_token, api_base_url

def ensure_extracted_data():
    """
    Checks if decrypted database is present. If not, triggers extractor.py to generate it.
    """
    if not os.path.exists(SQLITE_DB_PATH):
        logger.info(f"📁 Extracted database '{SQLITE_DB_PATH}' not found. Running extractor.py...")
        if os.path.exists("extractor.py"):
            try:
                res = subprocess.run([sys.executable, "extractor.py"], capture_output=True, text=True, check=True)
                logger.info("🎉 Extractor successfully ran! DB created.")
                logger.debug(res.stdout)
            except Exception as e:
                logger.error(f"❌ Failed to execute extractor.py: {e}")
                sys.exit(1)
        else:
            logger.error("❌ Critical: extractor.py script not found. Cannot auto-heal database state.")
            sys.exit(1)
    else:
        logger.info("📁 Verified existing decrypted database.")

def extract_patients() -> List[tuple]:
    """
    Extracts all patient records from local Dnt_Decrypted_Sig sqlite table.
    """
    logger.info(f"🔌 Connecting to SQLite database at {SQLITE_DB_PATH}...")
    try:
        conn = sqlite3.connect(SQLITE_DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='Pazienti';")
        if not cursor.fetchone():
            logger.error("❌ Table 'Pazienti' does not exist in decrypted database.")
            conn.close()
            sys.exit(1)
            
        cursor.execute("SELECT id, first_name, last_name, birth_date, address, city, zip_code FROM Pazienti;")
        rows = cursor.fetchall()
        conn.close()
        logger.info(f"   » Retrieved {len(rows)} patient rows from database.")
        return rows
    except Exception as e:
        logger.error(f"❌ Failed to query database: {e}")
        sys.exit(1)

def normalize_patient(row: tuple, tenant_id: str) -> Dict[str, Any]:
    """
    Normalizes a DentO patient record into the unified SyncPatient schema format.
    """
    patient_id, first_name, last_name, birth_date, address, city, zip_code = row
    
    first_name_clean = str(first_name).strip() if first_name else "Unknown"
    last_name_clean = str(last_name).strip() if last_name else "Unknown"
    if not first_name_clean: first_name_clean = "Unknown"
    if not last_name_clean: last_name_clean = "Unknown"
    
    # Safely convert Italian birth date DD/MM/YYYY into standard YYYY-MM-DD
    birth_date_iso = None
    if birth_date:
        birth_date_str = str(birth_date).strip()
        match = re.match(r'(\d{1,2})[/-](\d{1,2})[/-](\d{4})', birth_date_str)
        if match:
            day, month, year = match.groups()
            try:
                birth_date_iso = f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
            except Exception:
                pass
                
    # Normalize into standard SyncPatient schema
    return {
        "imported_id": str(patient_id),
        "home_site_id": "cmpog8fp7000jju04l8vz7sb5", # Using primary sTomato clinic location code from sTomato mock
        "first_name": first_name_clean,
        "last_name": last_name_clean,
        "birth_date": birth_date_iso,
        "phone": "",
        "email": "",
        "account_balance": 0.0,
        "external_system_id": str(patient_id),
        "external_system_code": "dento"
    }

def main():
    logger.info("========================================================================================================")
    logger.info("🦷 ODONTO.BOT OFFLINE PATIENT DATA SYNCHRONIZATION CONNECTOR 🦷")
    logger.info("========================================================================================================")
    
    # 1. Load configuration variables
    tenant_id, auth_token, api_base_url = load_config()
    
    # 2. Verify and extract database state
    ensure_extracted_data()
    raw_rows = extract_patients()
    
    if not raw_rows:
        logger.warning("⚠️ No patient records found to synchronize.")
        sys.exit(0)
        
    # 3. Normalize records
    logger.info("--------------------------------------------------------------------------------------------------------")
    logger.info("⚙️ RUNNING NORMALIZATION MIDDLEWARE: Mapping raw inputs to standardized SyncPatient schema...")
    
    normalized_patients = []
    for r in raw_rows:
        try:
            norm_p = normalize_patient(r, tenant_id)
            normalized_patients.append(norm_p)
            logger.info(f"   » Normalised Patient: {norm_p['first_name']} {norm_p['last_name']} -> ID: {norm_p['imported_id']}")
        except Exception as err:
            logger.error(f"❌ Normalisation failed for row ID {r[0] if r else 'unknown'}: {err}")
            
    if not normalized_patients:
        logger.error("❌ No successfully normalized patient records available.")
        sys.exit(1)
        
    # 4. Import requests library dynamically inside to report missing cleanly
    try:
        import requests
    except ImportError:
        logger.error("❌ Core module dependency 'requests' is missing! Please install it using: pip install requests")
        sys.exit(1)
        
    # 5. Push/Sync normalized patients to the Staging area
    sync_staging_url = f"{api_base_url.rstrip('/')}/sync/staging/patients"
    logger.info("--------------------------------------------------------------------------------------------------------")
    logger.info(f"🚀 STAGING PIPELINE STARTED: Sending {len(normalized_patients)} normalized patient records to Staging Gateway...")
    
    sync_headers = {
        "X-Tenant-ID": tenant_id,
        "Authorization": auth_token,
        "Content-Type": "application/json"
    }
    sync_payload = {
        "patients": normalized_patients
    }
    
    staged_successfully = False
    try:
        logger.info(f"👉 Outgoing HTTP Call: POST {sync_staging_url}")
        response = requests.post(sync_staging_url, json=sync_payload, headers=sync_headers, timeout=30)
        
        if response.status_code == 200:
            logger.info(f"🎉 PATIENTS STAGED SUCCESSFULLY: Batch upload completed. Response: {response.text}")
            staged_successfully = True
        elif response.status_code == 404:
            logger.warning("⚠️ Staging endpoint /v1/sync/staging/patients not found on this server (404).")
            logger.info("👉 FALLING BACK TO DIRECT SYNC: Sending batch patients to production gateway: POST /v1/sync/patients")
            direct_sync_url = f"{api_base_url.rstrip('/')}/sync/patients"
            logger.info(f"👉 Outgoing HTTP Call: POST {direct_sync_url}")
            response_direct = requests.post(direct_sync_url, json=sync_payload, headers=sync_headers, timeout=30)
            
            if response_direct.status_code == 200:
                logger.info(f"🎉 DIRECT PATIENT SYNC COMPLETED SUCCESSFULLY! Response: {response_direct.text}")
            else:
                logger.error(f"❌ DIRECT PATIENT SYNC FAILURE (Status {response_direct.status_code}): {response_direct.text}")
        else:
            masked_headers = sync_headers.copy()
            if "Authorization" in masked_headers:
                tok = masked_headers["Authorization"]
                masked_headers["Authorization"] = tok[:15] + "..." if len(tok) > 15 else "***"
            
            logger.error("❌ STAGING FAILURE DETAILS:")
            logger.error(f"   » Target Gateway Endpoint: POST {sync_staging_url}")
            logger.error(f"   » Response Status Code: {response.status_code}")
            logger.error(f"   » Outgoing Headers: {json.dumps(masked_headers, indent=2)}")
            logger.error(f"   » Outgoing Payload Body:\n{json.dumps(sync_payload, indent=2)}")
            logger.error(f"   » Response Raw Content:\n{response.text}")
            
    except Exception as push_err:
        logger.error(f"❌ Synchronization push exception occurred: {push_err}")
        
    # 6. Trigger Reconciliation CDC Promotion
    if staged_successfully:
        reconcile_url = f"{api_base_url.rstrip('/')}/sync/reconcile/patients"
        logger.info("--------------------------------------------------------------------------------------------------------")
        logger.info(f"🔄 TRIGGERING BQ RECONCILIATION: Invoking Change-Data-Capture (CDC) Promote Engine: {reconcile_url}")
        
        try:
            logger.info(f"👉 Outgoing HTTP Call: POST {reconcile_url}")
            rec_response = requests.post(reconcile_url, headers=sync_headers, timeout=60)
            
            if rec_response.status_code == 200:
                try:
                    reconcile_data = rec_response.json()
                    logger.info(f"🎉 RECONCILIATION COMPLETED: Promoted successfully. Breakdown:\n{json.dumps(reconcile_data, indent=2)}")
                except Exception:
                    logger.info(f"🎉 RECONCILIATION COMPLETED: Promoted successfully. Raw response: {rec_response.text}")
            else:
                logger.error(f"❌ RECONCILIATION GATEWAY FAILURE: Status {rec_response.status_code} - {rec_response.text}")
        except Exception as rec_err:
            logger.error(f"❌ Reconciliation trigger exception occurred: {rec_err}")

if __name__ == "__main__":
    main()
