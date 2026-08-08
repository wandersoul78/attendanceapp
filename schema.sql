-- ============================================================
-- Attendance & Payroll App Database Schema for Supabase (PostgreSQL)
-- Copy and run this script in your Supabase SQL Editor.
-- ============================================================

-- 1. Employees Table
CREATE TABLE IF NOT EXISTS employees (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT UNIQUE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 2. Employee Salary History Table (Tracks salary changes over time)
CREATE TABLE IF NOT EXISTS employee_salary_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id UUID REFERENCES employees(id) ON DELETE CASCADE,
    monthly_salary NUMERIC(10, 2) NOT NULL,
    effective_from DATE NOT NULL,
    effective_to DATE, -- NULL means currently active salary
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 3. Attendance Log Table
CREATE TABLE IF NOT EXISTS attendance (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id UUID REFERENCES employees(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    check_in TIMESTAMP WITH TIME ZONE,
    check_out TIMESTAMP WITH TIME ZONE,
    overtime_hours NUMERIC(4, 2) DEFAULT 0.00,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(employee_id, date)
);

-- 4. Monthly Extra Holidays Configuration Table (Global Company Default)
CREATE TABLE IF NOT EXISTS monthly_holidays (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    year_month VARCHAR(7) UNIQUE NOT NULL, -- Format: 'YYYY-MM' e.g. '2026-08'
    other_holidays_count INT DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 5. Employee Monthly Weekly Off Overrides Table (Allows editing Tuesdays per employee)
CREATE TABLE IF NOT EXISTS employee_weekly_off_overrides (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id UUID REFERENCES employees(id) ON DELETE CASCADE,
    year_month VARCHAR(7) NOT NULL, -- Format: 'YYYY-MM' e.g. '2026-08'
    weekly_offs INT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(employee_id, year_month)
);

-- 6. Employee Monthly Extra Holidays Overrides Table (Allows editing extra holidays per employee)
CREATE TABLE IF NOT EXISTS employee_extra_holiday_overrides (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id UUID REFERENCES employees(id) ON DELETE CASCADE,
    year_month VARCHAR(7) NOT NULL, -- Format: 'YYYY-MM' e.g. '2026-08'
    extra_holidays INT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(employee_id, year_month)
);

-- ============================================================
-- ROW LEVEL SECURITY (RLS) & POLICIES FOR SUPABASE
-- Run these commands in Supabase SQL Editor to enable RLS without breaking access.
-- ============================================================

-- Enable RLS on all 6 tables
ALTER TABLE employees ENABLE ROW LEVEL SECURITY;
ALTER TABLE employee_salary_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE attendance ENABLE ROW LEVEL SECURITY;
ALTER TABLE monthly_holidays ENABLE ROW LEVEL SECURITY;
ALTER TABLE employee_weekly_off_overrides ENABLE ROW LEVEL SECURITY;
ALTER TABLE employee_extra_holiday_overrides ENABLE ROW LEVEL SECURITY;

-- 1. Employees Policies
DROP POLICY IF EXISTS "Allow full access on employees" ON employees;
CREATE POLICY "Allow full access on employees" ON employees FOR ALL USING (true) WITH CHECK (true);

-- 2. Employee Salary History Policies
DROP POLICY IF EXISTS "Allow full access on employee_salary_history" ON employee_salary_history;
CREATE POLICY "Allow full access on employee_salary_history" ON employee_salary_history FOR ALL USING (true) WITH CHECK (true);

-- 3. Attendance Policies
DROP POLICY IF EXISTS "Allow full access on attendance" ON attendance;
CREATE POLICY "Allow full access on attendance" ON attendance FOR ALL USING (true) WITH CHECK (true);

-- 4. Monthly Holidays Policies
DROP POLICY IF EXISTS "Allow full access on monthly_holidays" ON monthly_holidays;
CREATE POLICY "Allow full access on monthly_holidays" ON monthly_holidays FOR ALL USING (true) WITH CHECK (true);

-- 5. Employee Weekly Off Overrides Policies
DROP POLICY IF EXISTS "Allow full access on employee_weekly_off_overrides" ON employee_weekly_off_overrides;
CREATE POLICY "Allow full access on employee_weekly_off_overrides" ON employee_weekly_off_overrides FOR ALL USING (true) WITH CHECK (true);

-- 6. Employee Extra Holiday Overrides Policies
DROP POLICY IF EXISTS "Allow full access on employee_extra_holiday_overrides" ON employee_extra_holiday_overrides;
CREATE POLICY "Allow full access on employee_extra_holiday_overrides" ON employee_extra_holiday_overrides FOR ALL USING (true) WITH CHECK (true);

