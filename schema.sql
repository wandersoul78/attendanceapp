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
