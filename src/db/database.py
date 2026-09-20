import os
import sqlite3
import json
from datetime import datetime
from typing import Dict, Any, Optional

DB_PATH = os.path.join("data", "gigease_oltp.db")

def get_connection():
    """Returns SQLite connection with row factory enabled."""
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initializes Layer 1 Transactional Core Schema (19 logical entities compressed to 7 core tables)."""
    conn = get_connection()
    cursor = conn.cursor()

    # 1. Workers table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS workers (
        worker_id TEXT PRIMARY KEY,
        zone_id TEXT NOT NULL,
        city TEXT NOT NULL,
        zone_tier TEXT NOT NULL,
        persona_category TEXT NOT NULL,
        vehicle_type TEXT NOT NULL,
        vulnerability_score REAL NOT NULL,
        tenure_days INTEGER NOT NULL,
        work_pattern_type TEXT NOT NULL,
        avg_active_hours_per_week REAL NOT NULL,
        historical_weekly_income REAL NOT NULL,
        rating REAL NOT NULL,
        aadhaar_hash TEXT UNIQUE NOT NULL,
        upi_id TEXT NOT NULL,
        fraud_score REAL DEFAULT 0.0,
        status TEXT DEFAULT 'ACTIVE',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 2. Policies table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS policies (
        policy_id TEXT PRIMARY KEY,
        worker_id TEXT NOT NULL,
        zone_id TEXT NOT NULL,
        coverage_amount REAL NOT NULL,
        base_monthly_premium REAL NOT NULL,
        weekly_premium REAL NOT NULL,
        payout_beta REAL DEFAULT 0.70,
        ncd_discount_pct REAL DEFAULT 0.0,
        claim_loading_pct REAL DEFAULT 0.0,
        consecutive_clean_weeks INTEGER DEFAULT 0,
        status TEXT DEFAULT 'ACTIVE',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (worker_id) REFERENCES workers(worker_id)
    );
    """)

    # 3. Claims table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS claims (
        claim_id TEXT PRIMARY KEY,
        worker_id TEXT NOT NULL,
        zone_id TEXT NOT NULL,
        week_start_date TEXT NOT NULL,
        disruption_event_type TEXT NOT NULL,
        claimed_loss_amount REAL NOT NULL,
        approved_payout_amount REAL NOT NULL,
        fraud_score REAL NOT NULL,
        claim_status TEXT NOT NULL, -- APPROVED | SOFT_FLAG | HARD_FLAG | REJECTED | QUEUED
        utr_number TEXT,
        llm_explanation TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (worker_id) REFERENCES workers(worker_id)
    );
    """)

    # 4. Earnings table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS earnings (
        earning_id INTEGER PRIMARY KEY AUTOINCREMENT,
        worker_id TEXT NOT NULL,
        week_start_date TEXT NOT NULL,
        gross_earnings REAL NOT NULL,
        order_earnings REAL NOT NULL,
        bonuses REAL NOT NULL,
        w_expected REAL NOT NULL,
        w_actual REAL NOT NULL,
        FOREIGN KEY (worker_id) REFERENCES workers(worker_id)
    );
    """)

    # 5. GPS & Hardware Audit Logs table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS gps_logs (
        log_id INTEGER PRIMARY KEY AUTOINCREMENT,
        worker_id TEXT NOT NULL,
        lat REAL NOT NULL,
        lon REAL NOT NULL,
        accuracy_m REAL NOT NULL,
        speed_kmh REAL NOT NULL,
        is_mocked INTEGER DEFAULT 0,
        device_id TEXT NOT NULL,
        cell_tower_id TEXT,
        ip_address TEXT,
        recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 6. Mutual Pool Financials table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS pool_financials (
        record_id INTEGER PRIMARY KEY AUTOINCREMENT,
        total_pool_balance REAL NOT NULL,
        total_active_coverage REAL NOT NULL,
        minimum_reserve_threshold REAL NOT NULL,
        incurred_claim_ratio REAL NOT NULL,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Initialize Pool Financials if empty
    cursor.execute("SELECT COUNT(*) FROM pool_financials;")
    if cursor.fetchone()[0] == 0:
        cursor.execute("""
        INSERT INTO pool_financials (total_pool_balance, total_active_coverage, minimum_reserve_threshold, incurred_claim_ratio)
        VALUES (4287500.0, 6750000.0, 2025000.0, 0.65);
        """)

    # 7. Audit Logs table (IRDAI compliance)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS audit_logs (
        audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
        entity_name TEXT NOT NULL,
        action_type TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    conn.commit()
    conn.close()
    print("[PASSED] SQLite OLTP Database & Schema initialized successfully.")

def commit_atomic_payout_transaction(claim_record: Dict[str, Any], updated_policy: Dict[str, Any], pool_update: Dict[str, Any]) -> bool:
    """Executes atomic 5-table transaction commit for zero-touch claim disbursement."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("BEGIN TRANSACTION;")

        # 1. Insert Claim Record
        cursor.execute("""
        INSERT INTO claims (claim_id, worker_id, zone_id, week_start_date, disruption_event_type, claimed_loss_amount, approved_payout_amount, fraud_score, claim_status, utr_number, llm_explanation)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            claim_record["claim_id"], claim_record["worker_id"], claim_record["zone_id"],
            claim_record["week_start_date"], claim_record["disruption_event_type"],
            claim_record["claimed_loss_amount"], claim_record["approved_payout_amount"],
            claim_record["fraud_score"], claim_record["claim_status"],
            claim_record.get("utr_number", ""), claim_record.get("llm_explanation", "")
        ))

        # 2. Update Policy Status (Loading + NCD reset)
        cursor.execute("""
        UPDATE policies
        SET claim_loading_pct = ?, ncd_discount_pct = 0.0, consecutive_clean_weeks = 0
        WHERE worker_id = ?;
        """, (updated_policy["claim_loading_pct"], updated_policy["worker_id"]))

        # 3. Update Pool Financials Balance
        cursor.execute("""
        UPDATE pool_financials
        SET total_pool_balance = ?, incurred_claim_ratio = ?
        WHERE record_id = (SELECT MAX(record_id) FROM pool_financials);
        """, (pool_update["new_pool_balance"], pool_update["new_icr"]))

        # 4. Insert Audit Log
        audit_payload = json.dumps({"claim": claim_record, "pool": pool_update})
        cursor.execute("""
        INSERT INTO audit_logs (entity_name, action_type, payload_json)
        VALUES ('CLAIM', 'ATOMIC_DISBURSEMENT', ?);
        """, (audit_payload,))

        conn.commit()
        conn.close()
        return True
    except Exception as e:
        conn.rollback()
        conn.close()
        print(f"[ERROR] Atomic Payout Transaction Failed: {e}")
        return False

if __name__ == "__main__":
    init_db()
