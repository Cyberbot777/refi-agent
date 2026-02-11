-- Streamline Government Refinance Agent - Database Schema
-- Local Development Environment
-- Test cases for FHA Streamline and VA IRRRL

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =====================================================
-- REFI APPLICATIONS TABLE
-- Core refinance application data
-- =====================================================
CREATE TABLE refi_applications (
    refi_id VARCHAR(50) PRIMARY KEY,
    borrower_name VARCHAR(255) NOT NULL,
    property_address TEXT NOT NULL,
    
    -- Existing loan information
    existing_loan_type VARCHAR(50) NOT NULL,  -- 'FHA' or 'VA'
    existing_loan_number VARCHAR(100),
    fha_case_number VARCHAR(50),              -- FHA only
    va_loan_number VARCHAR(100),              -- VA only
    original_closing_date DATE NOT NULL,
    first_payment_due_date DATE NOT NULL,
    
    -- Current (old) loan details
    current_note_rate DECIMAL(5,3) NOT NULL,
    current_annual_mip DECIMAL(5,3),          -- FHA only (e.g., 0.55 for 0.55%)
    current_monthly_pi DECIMAL(10,2) NOT NULL,
    current_monthly_piti DECIMAL(10,2) NOT NULL,
    current_loan_balance DECIMAL(12,2) NOT NULL,
    rate_type_current VARCHAR(20) DEFAULT 'FIXED',  -- FIXED or ARM
    
    -- New loan details
    new_note_rate DECIMAL(5,3) NOT NULL,
    new_annual_mip DECIMAL(5,3),              -- FHA only
    new_monthly_pi DECIMAL(10,2) NOT NULL,
    new_monthly_piti DECIMAL(10,2) NOT NULL,
    new_loan_amount DECIMAL(12,2) NOT NULL,
    new_loan_term_months INT DEFAULT 360,
    rate_type_new VARCHAR(20) DEFAULT 'FIXED',
    
    -- Closing costs (for VA recoupment)
    total_closing_costs DECIMAL(10,2) DEFAULT 0,
    va_funding_fee DECIMAL(10,2) DEFAULT 0,
    taxes_amount DECIMAL(10,2) DEFAULT 0,
    escrow_deposits DECIMAL(10,2) DEFAULT 0,
    cash_to_borrower DECIMAL(10,2) DEFAULT 0,
    
    -- Borrower changes (FHA credit-qualifying)
    old_borrowers TEXT,                       -- JSON array of names
    new_borrowers TEXT,                       -- JSON array of names
    borrower_changes BOOLEAN DEFAULT FALSE,
    change_reason VARCHAR(50),                -- 'DEATH', 'DIVORCE', or NULL
    
    -- Status
    loan_status VARCHAR(50) DEFAULT 'PENDING',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================
-- PAYMENT HISTORY TABLE
-- 12-month payment history for seasoning validation
-- =====================================================
CREATE TABLE payment_history (
    id SERIAL PRIMARY KEY,
    refi_id VARCHAR(50) REFERENCES refi_applications(refi_id) ON DELETE CASCADE,
    payment_date DATE NOT NULL,
    payment_amount DECIMAL(10,2) NOT NULL,
    days_late INT DEFAULT 0,                  -- 0 = on time
    status VARCHAR(20) DEFAULT 'CURRENT',     -- CURRENT, LATE_30, LATE_60, LATE_90
    forbearance_flag BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================
-- REFI DOCUMENTS TABLE
-- Document tracking for package validation
-- =====================================================
CREATE TABLE refi_documents (
    id SERIAL PRIMARY KEY,
    refi_id VARCHAR(50) REFERENCES refi_applications(refi_id) ON DELETE CASCADE,
    document_type VARCHAR(100) NOT NULL,      -- PAYOFF_STATEMENT, PAYMENT_HISTORY, etc.
    file_name VARCHAR(255),
    verified BOOLEAN DEFAULT FALSE,
    verified_at TIMESTAMP,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================
-- REFI DECISION LOG TABLE
-- Audit trail for all decisions
-- =====================================================
CREATE TABLE refi_decision_log (
    id SERIAL PRIMARY KEY,
    refi_id VARCHAR(50) REFERENCES refi_applications(refi_id) ON DELETE CASCADE,
    decision VARCHAR(50) NOT NULL,            -- APPROVED, DENIED, etc.
    decision_type VARCHAR(50),                -- PREQUALIFICATION, UNDERWRITING, FINAL
    confidence_score DECIMAL(5,2),
    reasoning TEXT,
    conditions TEXT,                          -- JSON array of conditions
    agent_name VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================
-- TEST CASE 1: FHA Streamline - SHOULD PASS
-- Good FHA loan, properly seasoned, rate drops 0.5%
-- =====================================================
INSERT INTO refi_applications (
    refi_id, borrower_name, property_address,
    existing_loan_type, fha_case_number, existing_loan_number,
    original_closing_date, first_payment_due_date,
    current_note_rate, current_annual_mip, current_monthly_pi, current_monthly_piti, current_loan_balance,
    new_note_rate, new_annual_mip, new_monthly_pi, new_monthly_piti, new_loan_amount,
    total_closing_costs, cash_to_borrower,
    old_borrowers, new_borrowers,
    loan_status
) VALUES (
    'REFI-FHA-001', 'Michael Johnson', '123 Oak Street, Irvine, CA 92618',
    'FHA', '123-4567890', 'FHA-2024-001',
    '2025-03-15', '2025-05-01',
    6.500, 0.55, 1896.20, 2350.00, 298500.00,
    5.875, 0.55, 1768.45, 2220.00, 300000.00,
    4500.00, 250.00,
    '["Michael Johnson"]', '["Michael Johnson"]',
    'CURRENT'
);

-- Payment history for REFI-FHA-001 (8 months, all on time)
INSERT INTO payment_history (refi_id, payment_date, payment_amount, days_late, status) VALUES
('REFI-FHA-001', '2025-05-01', 2350.00, 0, 'CURRENT'),
('REFI-FHA-001', '2025-06-01', 2350.00, 0, 'CURRENT'),
('REFI-FHA-001', '2025-07-01', 2350.00, 0, 'CURRENT'),
('REFI-FHA-001', '2025-08-01', 2350.00, 0, 'CURRENT'),
('REFI-FHA-001', '2025-09-01', 2350.00, 0, 'CURRENT'),
('REFI-FHA-001', '2025-10-01', 2350.00, 0, 'CURRENT'),
('REFI-FHA-001', '2025-11-01', 2350.00, 0, 'CURRENT'),
('REFI-FHA-001', '2025-12-01', 2350.00, 0, 'CURRENT');

-- Documents for REFI-FHA-001 (complete package)
INSERT INTO refi_documents (refi_id, document_type, file_name, verified) VALUES
('REFI-FHA-001', 'PAYOFF_STATEMENT', 'payoff_fha001.pdf', true),
('REFI-FHA-001', 'PAYMENT_HISTORY', 'payment_history_fha001.pdf', true),
('REFI-FHA-001', 'CLOSING_DISCLOSURE', 'cd_fha001.pdf', true),
('REFI-FHA-001', 'TITLE_EVIDENCE', 'title_fha001.pdf', true),
('REFI-FHA-001', 'INSURANCE_DECLARATION', 'insurance_fha001.pdf', true),
('REFI-FHA-001', 'BORROWER_ID', 'id_fha001.pdf', true);

-- =====================================================
-- TEST CASE 2: FHA Streamline - SHOULD FAIL (Seasoning)
-- FHA loan only 4 months old - fails 210 day requirement
-- =====================================================
INSERT INTO refi_applications (
    refi_id, borrower_name, property_address,
    existing_loan_type, fha_case_number, existing_loan_number,
    original_closing_date, first_payment_due_date,
    current_note_rate, current_annual_mip, current_monthly_pi, current_monthly_piti, current_loan_balance,
    new_note_rate, new_annual_mip, new_monthly_pi, new_monthly_piti, new_loan_amount,
    total_closing_costs, cash_to_borrower,
    old_borrowers, new_borrowers
) VALUES (
    'REFI-FHA-002', 'Sarah Williams', '456 Pine Avenue, Costa Mesa, CA 92627',
    'FHA', '234-5678901', 'FHA-2025-002',
    '2025-10-01', '2025-11-01',  -- Only 4 months ago
    7.000, 0.55, 1995.91, 2450.00, 299000.00,
    6.250, 0.55, 1845.00, 2300.00, 300000.00,
    4200.00, 0.00,
    '["Sarah Williams"]', '["Sarah Williams"]'
);

-- Payment history for REFI-FHA-002 (only 4 payments)
INSERT INTO payment_history (refi_id, payment_date, payment_amount, days_late, status) VALUES
('REFI-FHA-002', '2025-11-01', 2450.00, 0, 'CURRENT'),
('REFI-FHA-002', '2025-12-01', 2450.00, 0, 'CURRENT'),
('REFI-FHA-002', '2026-01-01', 2450.00, 0, 'CURRENT'),
('REFI-FHA-002', '2026-02-01', 2450.00, 0, 'CURRENT');

-- Documents for REFI-FHA-002
INSERT INTO refi_documents (refi_id, document_type, file_name, verified) VALUES
('REFI-FHA-002', 'PAYOFF_STATEMENT', 'payoff_fha002.pdf', true),
('REFI-FHA-002', 'PAYMENT_HISTORY', 'payment_history_fha002.pdf', true),
('REFI-FHA-002', 'CLOSING_DISCLOSURE', 'cd_fha002.pdf', true),
('REFI-FHA-002', 'TITLE_EVIDENCE', 'title_fha002.pdf', true),
('REFI-FHA-002', 'INSURANCE_DECLARATION', 'insurance_fha002.pdf', true),
('REFI-FHA-002', 'BORROWER_ID', 'id_fha002.pdf', true);

-- =====================================================
-- TEST CASE 3: FHA Streamline - SHOULD FAIL (No NTB)
-- Rate doesn't decrease enough - no net tangible benefit
-- =====================================================
INSERT INTO refi_applications (
    refi_id, borrower_name, property_address,
    existing_loan_type, fha_case_number, existing_loan_number,
    original_closing_date, first_payment_due_date,
    current_note_rate, current_annual_mip, current_monthly_pi, current_monthly_piti, current_loan_balance,
    new_note_rate, new_annual_mip, new_monthly_pi, new_monthly_piti, new_loan_amount,
    total_closing_costs, cash_to_borrower,
    old_borrowers, new_borrowers
) VALUES (
    'REFI-FHA-003', 'Robert Chen', '789 Maple Drive, Newport Beach, CA 92660',
    'FHA', '345-6789012', 'FHA-2024-003',
    '2025-01-15', '2025-03-01',
    5.750, 0.55, 1751.95, 2200.00, 300000.00,
    5.750, 0.55, 1751.95, 2200.00, 302000.00,  -- Same rate - lateral refi
    5000.00, 0.00,
    '["Robert Chen"]', '["Robert Chen"]'
);

-- Payment history for REFI-FHA-003 (10 months)
INSERT INTO payment_history (refi_id, payment_date, payment_amount, days_late, status) VALUES
('REFI-FHA-003', '2025-03-01', 2200.00, 0, 'CURRENT'),
('REFI-FHA-003', '2025-04-01', 2200.00, 0, 'CURRENT'),
('REFI-FHA-003', '2025-05-01', 2200.00, 0, 'CURRENT'),
('REFI-FHA-003', '2025-06-01', 2200.00, 0, 'CURRENT'),
('REFI-FHA-003', '2025-07-01', 2200.00, 0, 'CURRENT'),
('REFI-FHA-003', '2025-08-01', 2200.00, 0, 'CURRENT'),
('REFI-FHA-003', '2025-09-01', 2200.00, 0, 'CURRENT'),
('REFI-FHA-003', '2025-10-01', 2200.00, 0, 'CURRENT'),
('REFI-FHA-003', '2025-11-01', 2200.00, 0, 'CURRENT'),
('REFI-FHA-003', '2025-12-01', 2200.00, 0, 'CURRENT');

-- Documents for REFI-FHA-003
INSERT INTO refi_documents (refi_id, document_type, file_name, verified) VALUES
('REFI-FHA-003', 'PAYOFF_STATEMENT', 'payoff_fha003.pdf', true),
('REFI-FHA-003', 'PAYMENT_HISTORY', 'payment_history_fha003.pdf', true),
('REFI-FHA-003', 'CLOSING_DISCLOSURE', 'cd_fha003.pdf', true),
('REFI-FHA-003', 'TITLE_EVIDENCE', 'title_fha003.pdf', true),
('REFI-FHA-003', 'INSURANCE_DECLARATION', 'insurance_fha003.pdf', true),
('REFI-FHA-003', 'BORROWER_ID', 'id_fha003.pdf', true);

-- =====================================================
-- TEST CASE 4: VA IRRRL - SHOULD PASS
-- Good VA loan, 0.75% rate drop, recoupment in 24 months
-- =====================================================
INSERT INTO refi_applications (
    refi_id, borrower_name, property_address,
    existing_loan_type, va_loan_number, existing_loan_number,
    original_closing_date, first_payment_due_date,
    current_note_rate, current_monthly_pi, current_monthly_piti, current_loan_balance,
    new_note_rate, new_monthly_pi, new_monthly_piti, new_loan_amount,
    total_closing_costs, va_funding_fee, taxes_amount, escrow_deposits, cash_to_borrower,
    old_borrowers, new_borrowers,
    loan_status
) VALUES (
    'REFI-VA-001', 'James Thompson', '321 Veterans Way, San Diego, CA 92101',
    'VA', 'VA-2024-123456', 'VA-LOAN-001',
    '2025-02-01', '2025-04-01',
    6.750, 1947.50, 2400.00, 298000.00,
    6.000, 1798.65, 2250.00, 300000.00,
    6500.00, 2500.00, 500.00, 800.00, 0.00,  -- Recoupable: 6500-2500-500-800 = 2700
    '["James Thompson"]', '["James Thompson"]',
    'CURRENT'
);

-- Payment history for REFI-VA-001 (9 months, all on time)
INSERT INTO payment_history (refi_id, payment_date, payment_amount, days_late, status) VALUES
('REFI-VA-001', '2025-04-01', 2400.00, 0, 'CURRENT'),
('REFI-VA-001', '2025-05-01', 2400.00, 0, 'CURRENT'),
('REFI-VA-001', '2025-06-01', 2400.00, 0, 'CURRENT'),
('REFI-VA-001', '2025-07-01', 2400.00, 0, 'CURRENT'),
('REFI-VA-001', '2025-08-01', 2400.00, 0, 'CURRENT'),
('REFI-VA-001', '2025-09-01', 2400.00, 0, 'CURRENT'),
('REFI-VA-001', '2025-10-01', 2400.00, 0, 'CURRENT'),
('REFI-VA-001', '2025-11-01', 2400.00, 0, 'CURRENT'),
('REFI-VA-001', '2025-12-01', 2400.00, 0, 'CURRENT');

-- Documents for REFI-VA-001
INSERT INTO refi_documents (refi_id, document_type, file_name, verified) VALUES
('REFI-VA-001', 'PAYOFF_STATEMENT', 'payoff_va001.pdf', true),
('REFI-VA-001', 'PAYMENT_HISTORY', 'payment_history_va001.pdf', true),
('REFI-VA-001', 'CLOSING_DISCLOSURE', 'cd_va001.pdf', true),
('REFI-VA-001', 'TITLE_EVIDENCE', 'title_va001.pdf', true),
('REFI-VA-001', 'INSURANCE_DECLARATION', 'insurance_va001.pdf', true),
('REFI-VA-001', 'BORROWER_ID', 'id_va001.pdf', true),
('REFI-VA-001', 'VA_FORM_26_8923', 'va_8923_va001.pdf', true);

-- =====================================================
-- TEST CASE 5: VA IRRRL - SHOULD FAIL (Insufficient Rate Reduction)
-- Rate only drops 0.40% (need 0.50% for fixed-to-fixed)
-- =====================================================
INSERT INTO refi_applications (
    refi_id, borrower_name, property_address,
    existing_loan_type, va_loan_number, existing_loan_number,
    original_closing_date, first_payment_due_date,
    current_note_rate, current_monthly_pi, current_monthly_piti, current_loan_balance,
    new_note_rate, new_monthly_pi, new_monthly_piti, new_loan_amount,
    total_closing_costs, va_funding_fee, taxes_amount, escrow_deposits, cash_to_borrower,
    old_borrowers, new_borrowers
) VALUES (
    'REFI-VA-002', 'Patricia Davis', '555 Liberty Lane, Oceanside, CA 92054',
    'VA', 'VA-2024-234567', 'VA-LOAN-002',
    '2025-03-01', '2025-05-01',
    6.250, 1845.00, 2300.00, 299000.00,
    5.850, 1775.00, 2230.00, 300000.00,  -- Only 0.40% reduction
    5500.00, 2200.00, 450.00, 700.00, 0.00,
    '["Patricia Davis"]', '["Patricia Davis"]'
);

-- Payment history for REFI-VA-002 (8 months)
INSERT INTO payment_history (refi_id, payment_date, payment_amount, days_late, status) VALUES
('REFI-VA-002', '2025-05-01', 2300.00, 0, 'CURRENT'),
('REFI-VA-002', '2025-06-01', 2300.00, 0, 'CURRENT'),
('REFI-VA-002', '2025-07-01', 2300.00, 0, 'CURRENT'),
('REFI-VA-002', '2025-08-01', 2300.00, 0, 'CURRENT'),
('REFI-VA-002', '2025-09-01', 2300.00, 0, 'CURRENT'),
('REFI-VA-002', '2025-10-01', 2300.00, 0, 'CURRENT'),
('REFI-VA-002', '2025-11-01', 2300.00, 0, 'CURRENT'),
('REFI-VA-002', '2025-12-01', 2300.00, 0, 'CURRENT');

-- Documents for REFI-VA-002
INSERT INTO refi_documents (refi_id, document_type, file_name, verified) VALUES
('REFI-VA-002', 'PAYOFF_STATEMENT', 'payoff_va002.pdf', true),
('REFI-VA-002', 'PAYMENT_HISTORY', 'payment_history_va002.pdf', true),
('REFI-VA-002', 'CLOSING_DISCLOSURE', 'cd_va002.pdf', true),
('REFI-VA-002', 'TITLE_EVIDENCE', 'title_va002.pdf', true),
('REFI-VA-002', 'INSURANCE_DECLARATION', 'insurance_va002.pdf', true),
('REFI-VA-002', 'BORROWER_ID', 'id_va002.pdf', true);

-- =====================================================
-- TEST CASE 6: VA IRRRL - SHOULD FAIL (Recoupment > 36 months)
-- High closing costs, low savings = recoupment fails
-- =====================================================
INSERT INTO refi_applications (
    refi_id, borrower_name, property_address,
    existing_loan_type, va_loan_number, existing_loan_number,
    original_closing_date, first_payment_due_date,
    current_note_rate, current_monthly_pi, current_monthly_piti, current_loan_balance,
    new_note_rate, new_monthly_pi, new_monthly_piti, new_loan_amount,
    total_closing_costs, va_funding_fee, taxes_amount, escrow_deposits, cash_to_borrower,
    old_borrowers, new_borrowers
) VALUES (
    'REFI-VA-003', 'William Martinez', '777 Freedom Blvd, Carlsbad, CA 92008',
    'VA', 'VA-2024-345678', 'VA-LOAN-003',
    '2025-01-15', '2025-03-01',
    6.500, 1896.20, 2350.00, 299500.00,
    5.875, 1810.50, 2260.00, 302000.00,
    12000.00, 2800.00, 600.00, 900.00, 0.00,  -- Recoupable: 12000-2800-600-900 = 7700, savings ~86/mo = 89 months!
    '["William Martinez"]', '["William Martinez"]'
);

-- Payment history for REFI-VA-003 (10 months)
INSERT INTO payment_history (refi_id, payment_date, payment_amount, days_late, status) VALUES
('REFI-VA-003', '2025-03-01', 2350.00, 0, 'CURRENT'),
('REFI-VA-003', '2025-04-01', 2350.00, 0, 'CURRENT'),
('REFI-VA-003', '2025-05-01', 2350.00, 0, 'CURRENT'),
('REFI-VA-003', '2025-06-01', 2350.00, 0, 'CURRENT'),
('REFI-VA-003', '2025-07-01', 2350.00, 0, 'CURRENT'),
('REFI-VA-003', '2025-08-01', 2350.00, 0, 'CURRENT'),
('REFI-VA-003', '2025-09-01', 2350.00, 0, 'CURRENT'),
('REFI-VA-003', '2025-10-01', 2350.00, 0, 'CURRENT'),
('REFI-VA-003', '2025-11-01', 2350.00, 0, 'CURRENT'),
('REFI-VA-003', '2025-12-01', 2350.00, 0, 'CURRENT');

-- Documents for REFI-VA-003
INSERT INTO refi_documents (refi_id, document_type, file_name, verified) VALUES
('REFI-VA-003', 'PAYOFF_STATEMENT', 'payoff_va003.pdf', true),
('REFI-VA-003', 'PAYMENT_HISTORY', 'payment_history_va003.pdf', true),
('REFI-VA-003', 'CLOSING_DISCLOSURE', 'cd_va003.pdf', true),
('REFI-VA-003', 'TITLE_EVIDENCE', 'title_va003.pdf', true),
('REFI-VA-003', 'INSURANCE_DECLARATION', 'insurance_va003.pdf', true),
('REFI-VA-003', 'BORROWER_ID', 'id_va003.pdf', true);

-- =====================================================
-- TEST CASE 7: FHA - SHOULD REQUIRE CONDITIONS (Cash back near limit)
-- Good loan but cash back is $450 (close to $500 limit)
-- =====================================================
INSERT INTO refi_applications (
    refi_id, borrower_name, property_address,
    existing_loan_type, fha_case_number, existing_loan_number,
    original_closing_date, first_payment_due_date,
    current_note_rate, current_annual_mip, current_monthly_pi, current_monthly_piti, current_loan_balance,
    new_note_rate, new_annual_mip, new_monthly_pi, new_monthly_piti, new_loan_amount,
    total_closing_costs, cash_to_borrower,
    old_borrowers, new_borrowers
) VALUES (
    'REFI-FHA-004', 'Jennifer Lopez', '888 Sunrise Court, Laguna Beach, CA 92651',
    'FHA', '456-7890123', 'FHA-2024-004',
    '2025-02-01', '2025-04-01',
    7.125, 0.55, 2024.81, 2500.00, 300000.00,
    6.375, 0.55, 1876.50, 2350.00, 302000.00,
    4800.00, 450.00,  -- Cash back at $450 - within limit but close
    '["Jennifer Lopez"]', '["Jennifer Lopez"]'
);

-- Payment history for REFI-FHA-004 (9 months, one 15-day late - still OK)
INSERT INTO payment_history (refi_id, payment_date, payment_amount, days_late, status) VALUES
('REFI-FHA-004', '2025-04-01', 2500.00, 0, 'CURRENT'),
('REFI-FHA-004', '2025-05-01', 2500.00, 0, 'CURRENT'),
('REFI-FHA-004', '2025-06-01', 2500.00, 15, 'CURRENT'),  -- 15 days late - still acceptable
('REFI-FHA-004', '2025-07-01', 2500.00, 0, 'CURRENT'),
('REFI-FHA-004', '2025-08-01', 2500.00, 0, 'CURRENT'),
('REFI-FHA-004', '2025-09-01', 2500.00, 0, 'CURRENT'),
('REFI-FHA-004', '2025-10-01', 2500.00, 0, 'CURRENT'),
('REFI-FHA-004', '2025-11-01', 2500.00, 0, 'CURRENT'),
('REFI-FHA-004', '2025-12-01', 2500.00, 0, 'CURRENT');

-- Documents for REFI-FHA-004
INSERT INTO refi_documents (refi_id, document_type, file_name, verified) VALUES
('REFI-FHA-004', 'PAYOFF_STATEMENT', 'payoff_fha004.pdf', true),
('REFI-FHA-004', 'PAYMENT_HISTORY', 'payment_history_fha004.pdf', true),
('REFI-FHA-004', 'CLOSING_DISCLOSURE', 'cd_fha004.pdf', true),
('REFI-FHA-004', 'TITLE_EVIDENCE', 'title_fha004.pdf', true),
('REFI-FHA-004', 'INSURANCE_DECLARATION', 'insurance_fha004.pdf', true),
('REFI-FHA-004', 'BORROWER_ID', 'id_fha004.pdf', true);

-- =====================================================
-- TEST CASE 8: VA IRRRL - 20% PITI TRIGGER
-- PITI increases significantly due to escrow/tax changes
-- =====================================================
INSERT INTO refi_applications (
    refi_id, borrower_name, property_address,
    existing_loan_type, va_loan_number, existing_loan_number,
    original_closing_date, first_payment_due_date,
    current_note_rate, current_monthly_pi, current_monthly_piti, current_loan_balance,
    new_note_rate, new_monthly_pi, new_monthly_piti, new_loan_amount,
    total_closing_costs, va_funding_fee, taxes_amount, escrow_deposits, cash_to_borrower,
    old_borrowers, new_borrowers,
    loan_status
) VALUES (
    'REFI-VA-004', 'David Wilson', '999 Honor Drive, El Cajon, CA 92020',
    'VA', 'VA-2024-456789', 'VA-LOAN-004',
    '2025-01-01', '2025-03-01',
    7.000, 1995.91, 2200.00, 299000.00,  -- Old PITI: $2200
    6.250, 1845.00, 2700.00, 301000.00,  -- New PITI: $2700 (22.7% increase due to escrow)
    5800.00, 2300.00, 480.00, 750.00, 0.00,
    '["David Wilson"]', '["David Wilson"]',
    'CURRENT'
);

-- Payment history for REFI-VA-004 (10 months)
INSERT INTO payment_history (refi_id, payment_date, payment_amount, days_late, status) VALUES
('REFI-VA-004', '2025-03-01', 2200.00, 0, 'CURRENT'),
('REFI-VA-004', '2025-04-01', 2200.00, 0, 'CURRENT'),
('REFI-VA-004', '2025-05-01', 2200.00, 0, 'CURRENT'),
('REFI-VA-004', '2025-06-01', 2200.00, 0, 'CURRENT'),
('REFI-VA-004', '2025-07-01', 2200.00, 0, 'CURRENT'),
('REFI-VA-004', '2025-08-01', 2200.00, 0, 'CURRENT'),
('REFI-VA-004', '2025-09-01', 2200.00, 0, 'CURRENT'),
('REFI-VA-004', '2025-10-01', 2200.00, 0, 'CURRENT'),
('REFI-VA-004', '2025-11-01', 2200.00, 0, 'CURRENT'),
('REFI-VA-004', '2025-12-01', 2200.00, 0, 'CURRENT');

-- Documents for REFI-VA-004
INSERT INTO refi_documents (refi_id, document_type, file_name, verified) VALUES
('REFI-VA-004', 'PAYOFF_STATEMENT', 'payoff_va004.pdf', true),
('REFI-VA-004', 'PAYMENT_HISTORY', 'payment_history_va004.pdf', true),
('REFI-VA-004', 'CLOSING_DISCLOSURE', 'cd_va004.pdf', true),
('REFI-VA-004', 'TITLE_EVIDENCE', 'title_va004.pdf', true),
('REFI-VA-004', 'INSURANCE_DECLARATION', 'insurance_va004.pdf', true),
('REFI-VA-004', 'BORROWER_ID', 'id_va004.pdf', true);

-- =====================================================
-- INDEXES for performance
-- =====================================================
CREATE INDEX idx_payment_history_refi_id ON payment_history(refi_id);
CREATE INDEX idx_payment_history_date ON payment_history(payment_date);
CREATE INDEX idx_refi_documents_refi_id ON refi_documents(refi_id);
CREATE INDEX idx_refi_documents_type ON refi_documents(document_type);
CREATE INDEX idx_refi_decision_log_refi_id ON refi_decision_log(refi_id);
CREATE INDEX idx_refi_applications_status ON refi_applications(loan_status);
CREATE INDEX idx_refi_applications_type ON refi_applications(existing_loan_type);

-- =====================================================
-- TEST CASE SUMMARY VIEW
-- =====================================================
CREATE VIEW v_test_case_summary AS
SELECT 
    r.refi_id,
    r.borrower_name,
    r.existing_loan_type as program,
    r.current_note_rate as old_rate,
    r.new_note_rate as new_rate,
    (r.current_note_rate - r.new_note_rate) as rate_reduction,
    r.current_monthly_pi as old_pi,
    r.new_monthly_pi as new_pi,
    (r.current_monthly_pi - r.new_monthly_pi) as pi_savings,
    r.cash_to_borrower,
    r.loan_status,
    (SELECT COUNT(*) FROM payment_history ph WHERE ph.refi_id = r.refi_id) as payment_count,
    CASE 
        WHEN r.refi_id = 'REFI-FHA-001' THEN 'SHOULD PASS'
        WHEN r.refi_id = 'REFI-FHA-002' THEN 'SHOULD FAIL - Seasoning'
        WHEN r.refi_id = 'REFI-FHA-003' THEN 'SHOULD FAIL - No NTB'
        WHEN r.refi_id = 'REFI-VA-001' THEN 'SHOULD PASS'
        WHEN r.refi_id = 'REFI-VA-002' THEN 'SHOULD FAIL - Rate Reduction'
        WHEN r.refi_id = 'REFI-VA-003' THEN 'SHOULD FAIL - Recoupment'
        WHEN r.refi_id = 'REFI-FHA-004' THEN 'SHOULD PASS WITH CONDITIONS'
        WHEN r.refi_id = 'REFI-VA-004' THEN 'MANUAL REVIEW - 20% PITI'
        ELSE 'UNKNOWN'
    END as expected_outcome
FROM refi_applications r
ORDER BY r.refi_id;

COMMIT;
