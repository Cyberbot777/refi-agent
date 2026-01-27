"""
PostgreSQL database tools for Streamline Government Refinance.
Implements database operations against the local PostgreSQL instance.
"""

import json
from typing import Optional, List, Dict, Any
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


def get_refi_application(refi_id: str) -> str:
    """
    Query refinance application data from PostgreSQL.
    
    Args:
        refi_id: The refinance application ID (e.g., "REFI-001")
    
    Returns:
        JSON string with application data
    """
    with get_cursor() as cursor:
        cursor.execute("""
            SELECT 
                refi_id,
                borrower_name,
                property_address,
                existing_loan_type,
                existing_loan_number,
                fha_case_number,
                va_loan_number,
                original_closing_date,
                first_payment_due_date,
                current_note_rate,
                current_annual_mip,
                current_monthly_pi,
                current_monthly_piti,
                current_loan_balance,
                new_note_rate,
                new_annual_mip,
                new_monthly_pi,
                new_monthly_piti,
                new_loan_amount,
                new_loan_term_months,
                total_closing_costs,
                va_funding_fee,
                taxes_amount,
                escrow_deposits,
                cash_to_borrower,
                rate_type_current,
                rate_type_new,
                loan_status,
                created_at
            FROM refi_applications 
            WHERE refi_id = %s
        """, (refi_id,))
        
        result = cursor.fetchone()
        
        if not result:
            return json.dumps({
                "error": f"No refinance application found with ID: {refi_id}",
                "refi_id": refi_id
            })
        
        return json.dumps(_serialize_row(dict(result)), indent=2)


def get_payment_history(refi_id: str) -> str:
    """
    Query payment history for a refinance application.
    
    Args:
        refi_id: The refinance application ID
    
    Returns:
        JSON string with payment history (last 12 months)
    """
    with get_cursor() as cursor:
        cursor.execute("""
            SELECT 
                payment_date,
                payment_amount,
                days_late,
                status,
                forbearance_flag
            FROM payment_history 
            WHERE refi_id = %s
            ORDER BY payment_date DESC
            LIMIT 12
        """, (refi_id,))
        
        results = cursor.fetchall()
        
        if not results:
            return json.dumps({
                "refi_id": refi_id,
                "payments": [],
                "total_payments": 0,
                "message": "No payment history found"
            })
        
        payments = [_serialize_row(dict(row)) for row in results]
        
        # Calculate summary statistics
        on_time = sum(1 for p in payments if p.get('days_late', 0) == 0)
        late_30 = sum(1 for p in payments if 0 < p.get('days_late', 0) < 60)
        late_60_plus = sum(1 for p in payments if p.get('days_late', 0) >= 60)
        forbearance_months = sum(1 for p in payments if p.get('forbearance_flag'))
        
        # Check for consecutive payments
        consecutive = 0
        for p in payments:
            if p.get('days_late', 0) <= 30:
                consecutive += 1
            else:
                break
        
        return json.dumps({
            "refi_id": refi_id,
            "payments": payments,
            "total_payments": len(payments),
            "on_time_payments": on_time,
            "late_30_payments": late_30,
            "late_60_plus_payments": late_60_plus,
            "consecutive_on_time": consecutive,
            "forbearance_months": forbearance_months
        }, indent=2)


def get_refi_documents(refi_id: str) -> str:
    """
    Query documents for a refinance application.
    
    Args:
        refi_id: The refinance application ID
    
    Returns:
        JSON string with document list
    """
    with get_cursor() as cursor:
        cursor.execute("""
            SELECT 
                document_type,
                file_name,
                verified,
                verified_at,
                notes
            FROM refi_documents 
            WHERE refi_id = %s
            ORDER BY document_type
        """, (refi_id,))
        
        results = cursor.fetchall()
        
        if not results:
            return json.dumps({
                "refi_id": refi_id,
                "documents": [],
                "message": "No documents found"
            })
        
        documents = [_serialize_row(dict(row)) for row in results]
        
        # Check for required document types
        doc_types = {d['document_type'] for d in documents}
        required_docs = {
            'PAYOFF_STATEMENT', 'PAYMENT_HISTORY', 'CLOSING_DISCLOSURE',
            'TITLE_EVIDENCE', 'INSURANCE_DECLARATION', 'BORROWER_ID'
        }
        missing = required_docs - doc_types
        
        return json.dumps({
            "refi_id": refi_id,
            "documents": documents,
            "total_documents": len(documents),
            "document_types_present": list(doc_types),
            "missing_required": list(missing) if missing else []
        }, indent=2)


def save_refi_decision(
    refi_id: str,
    decision: str,
    decision_type: str,
    confidence_score: float,
    reasoning: str,
    conditions: Optional[List[str]] = None,
    agent_name: str = "refi_decision_agent"
) -> str:
    """
    Save a refinance decision to the decision log.
    
    Args:
        refi_id: The refinance application ID
        decision: APPROVED, APPROVED_WITH_CONDITIONS, MANUAL_REVIEW_REQUIRED, DENIED
        decision_type: PREQUALIFICATION, UNDERWRITING, FINAL
        confidence_score: 0-100 confidence percentage
        reasoning: Explanation for the decision
        conditions: List of conditions (if applicable)
        agent_name: Name of the agent making the decision
    
    Returns:
        JSON string with save confirmation
    """
    with get_cursor() as cursor:
        cursor.execute("""
            INSERT INTO refi_decision_log 
            (refi_id, decision, decision_type, confidence_score, reasoning, conditions, agent_name)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id, created_at
        """, (
            refi_id, 
            decision, 
            decision_type,
            confidence_score, 
            reasoning, 
            json.dumps(conditions) if conditions else None,
            agent_name
        ))
        
        result = cursor.fetchone()
        
        # Update the application status
        cursor.execute("""
            UPDATE refi_applications 
            SET loan_status = %s, updated_at = CURRENT_TIMESTAMP
            WHERE refi_id = %s
        """, (decision, refi_id))
        
        return json.dumps({
            "success": True,
            "decision_id": result['id'],
            "created_at": str(result['created_at']),
            "message": f"Decision '{decision}' saved for {refi_id}"
        })


def get_borrower_comparison(refi_id: str) -> str:
    """
    Get borrower comparison for FHA credit-qualifying determination.
    
    Args:
        refi_id: The refinance application ID
    
    Returns:
        JSON string with old vs new borrower information
    """
    with get_cursor() as cursor:
        cursor.execute("""
            SELECT 
                old_borrowers,
                new_borrowers,
                borrower_changes,
                change_reason
            FROM refi_applications 
            WHERE refi_id = %s
        """, (refi_id,))
        
        result = cursor.fetchone()
        
        if not result:
            return json.dumps({
                "error": f"No application found: {refi_id}",
                "refi_id": refi_id
            })
        
        data = _serialize_row(dict(result))
        
        # Parse borrower arrays if they're stored as JSON strings
        old_borrowers = data.get('old_borrowers', [])
        new_borrowers = data.get('new_borrowers', [])
        
        if isinstance(old_borrowers, str):
            old_borrowers = json.loads(old_borrowers)
        if isinstance(new_borrowers, str):
            new_borrowers = json.loads(new_borrowers)
        
        # Determine if credit-qualifying is required
        borrowers_same = set(old_borrowers) == set(new_borrowers)
        credit_qualifying_required = not borrowers_same and data.get('change_reason') not in ['DEATH', 'DIVORCE']
        
        return json.dumps({
            "refi_id": refi_id,
            "old_borrowers": old_borrowers,
            "new_borrowers": new_borrowers,
            "borrowers_same": borrowers_same,
            "change_reason": data.get('change_reason'),
            "credit_qualifying_required": credit_qualifying_required
        }, indent=2)
