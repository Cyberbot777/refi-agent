"""
Database tools for Streamline Government Refinance.
The agent gets ALL loan data in one call.
"""

import json
from typing import Any
from contextlib import contextmanager
from datetime import date, datetime
import psycopg2
from psycopg2.extras import RealDictCursor
from utils.config_loader import get_config


def get_connection():
    """Create a database connection using configuration."""
    config = get_config()
    return psycopg2.connect(config.database_url)


@contextmanager
def get_cursor():
    """Context manager for database cursor with automatic cleanup."""
    conn = get_connection()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        yield cursor
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cursor.close()
        conn.close()


def _serialize_value(value: Any) -> Any:
    """Serialize a value for JSON output."""
    if isinstance(value, (date, datetime)):
        return str(value)
    if hasattr(value, '__float__'):  # Decimal
        return float(value)
    return value


def _serialize_row(row: dict) -> dict:
    """Serialize all values in a row for JSON output."""
    return {k: _serialize_value(v) for k, v in row.items()}


def get_all_loan_data(refi_id: str) -> str:
    """
    Get ALL data for a refinance application in one call.
    Returns application details, payment history, and documents.
    
    The agent uses this data to reason through all eligibility checks.
    
    Args:
        refi_id: The refinance application ID (e.g., "REFI-FHA-001")
    
    Returns:
        JSON string with complete loan data including:
        - application: All loan details (rates, amounts, dates, etc.)
        - payment_history: Last 12 months of payments with summary stats
        - documents: List of documents and what's missing
    """
    result = {
        "refi_id": refi_id,
        "today": str(date.today())
    }
    
    with get_cursor() as cursor:
        # Get application data
        cursor.execute("""
            SELECT 
                refi_id, borrower_name, property_address,
                existing_loan_type, existing_loan_number,
                fha_case_number, va_loan_number,
                original_closing_date, first_payment_due_date,
                current_note_rate, current_annual_mip,
                current_monthly_pi, current_monthly_piti,
                current_loan_balance,
                new_note_rate, new_annual_mip,
                new_monthly_pi, new_monthly_piti,
                new_loan_amount, new_loan_term_months,
                total_closing_costs, va_funding_fee,
                taxes_amount, escrow_deposits,
                cash_to_borrower,
                rate_type_current, rate_type_new,
                loan_status
            FROM refi_applications 
            WHERE refi_id = %s
        """, (refi_id,))
        
        app = cursor.fetchone()
        
        if not app:
            return json.dumps({
                "error": f"No application found with ID: {refi_id}",
                "refi_id": refi_id
            }, indent=2)
        
        result["application"] = _serialize_row(dict(app))
        
        # Get payment history
        cursor.execute("""
            SELECT payment_date, payment_amount, days_late, status, forbearance_flag
            FROM payment_history 
            WHERE refi_id = %s
            ORDER BY payment_date DESC
            LIMIT 12
        """, (refi_id,))
        
        payments = cursor.fetchall()
        payment_list = [_serialize_row(dict(p)) for p in payments]
        
        # Calculate payment summary stats
        on_time = sum(1 for p in payment_list if p.get('days_late', 0) == 0)
        late_30 = sum(1 for p in payment_list if 0 < p.get('days_late', 0) < 60)
        late_60_plus = sum(1 for p in payment_list if p.get('days_late', 0) >= 60)
        
        consecutive = 0
        for p in payment_list:
            if p.get('days_late', 0) <= 30:
                consecutive += 1
            else:
                break
        
        result["payment_history"] = {
            "payments": payment_list,
            "total_payments": len(payment_list),
            "on_time": on_time,
            "late_30_day": late_30,
            "late_60_plus": late_60_plus,
            "consecutive_on_time": consecutive
        }
        
        # Get documents
        cursor.execute("""
            SELECT document_type, file_name, verified, notes
            FROM refi_documents 
            WHERE refi_id = %s
        """, (refi_id,))
        
        docs = cursor.fetchall()
        doc_list = [_serialize_row(dict(d)) for d in docs]
        doc_types = {d['document_type'] for d in doc_list}
        
        required = {'PAYOFF_STATEMENT', 'PAYMENT_HISTORY', 'CLOSING_DISCLOSURE',
                    'TITLE_EVIDENCE', 'INSURANCE_DECLARATION', 'BORROWER_ID'}
        missing = list(required - doc_types)
        
        result["documents"] = {
            "documents": doc_list,
            "present": list(doc_types),
            "missing": missing
        }
    
    return json.dumps(result, indent=2)


def save_decision(refi_id: str, decision: str, reasoning: str) -> str:
    """
    Save the agent's decision to the decision log.
    NOTE: Does NOT update loan_status to avoid feedback loops.
    
    Args:
        refi_id: The refinance application ID
        decision: APPROVED, DENIED, or NEEDS_REVIEW
        reasoning: The agent's explanation for the decision
    
    Returns:
        JSON confirmation
    """
    with get_cursor() as cursor:
        cursor.execute("""
            INSERT INTO refi_decision_log 
            (refi_id, decision, decision_type, confidence_score, reasoning, agent_name)
            VALUES (%s, %s, 'UNDERWRITING', 85, %s, 'streamline_refi_agent')
            RETURNING id, created_at
        """, (refi_id, decision, reasoning))
        
        result = cursor.fetchone()
        
        # Note: We intentionally do NOT update loan_status here
        # The loan_status field represents the current state of the EXISTING loan
        # not the agent's decision about the refinance application
        
        return json.dumps({
            "saved": True,
            "decision_id": result['id'],
            "message": f"Decision '{decision}' recorded for {refi_id}"
        })
