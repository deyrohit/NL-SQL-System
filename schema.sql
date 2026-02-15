-- ClearQuote Database Schema 
-- Drop existing tables if they exist (for clean setup)
DROP TABLE IF EXISTS quotes CASCADE;
DROP TABLE IF EXISTS repairs CASCADE;
DROP TABLE IF EXISTS damage_detections CASCADE;
DROP TABLE IF EXISTS vehicle_cards CASCADE;

-- Drop sequences if they exist
DROP SEQUENCE IF EXISTS vehicle_cards_card_id_seq CASCADE;
DROP SEQUENCE IF EXISTS damage_detections_damage_id_seq CASCADE;
DROP SEQUENCE IF EXISTS repairs_repair_id_seq CASCADE;
DROP SEQUENCE IF EXISTS quotes_quote_id_seq CASCADE;

-- =============================================
-- Table: vehicle_cards
-- =============================================
CREATE TABLE vehicle_cards (
    card_id INTEGER PRIMARY KEY,
    vehicle_type VARCHAR(50) NOT NULL,
    manufacturer VARCHAR(100) NOT NULL,
    model VARCHAR(100) NOT NULL,
    manufacture_year INTEGER NOT NULL CHECK (manufacture_year >= 1900 AND manufacture_year <= EXTRACT(YEAR FROM CURRENT_DATE) + 1),
    created_at DATE NOT NULL
);

-- Indexes for vehicle_cards
CREATE INDEX idx_vehicle_cards_created_at ON vehicle_cards(created_at);
CREATE INDEX idx_vehicle_cards_manufacturer ON vehicle_cards(manufacturer);
CREATE INDEX idx_vehicle_cards_model ON vehicle_cards(model);
CREATE INDEX idx_vehicle_cards_vehicle_type ON vehicle_cards(vehicle_type);
CREATE INDEX idx_vehicle_cards_manufacture_year ON vehicle_cards(manufacture_year);

-- =============================================
-- Table: damage_detections
-- =============================================
CREATE TABLE damage_detections (
    damage_id INTEGER PRIMARY KEY,
    card_id INTEGER NOT NULL,
    panel_name VARCHAR(100) NOT NULL,
    damage_type VARCHAR(50) NOT NULL,
    severity VARCHAR(20) NOT NULL,
    confidence DECIMAL(5,4) CHECK (confidence >= 0 AND confidence <= 1),
    detected_at DATE NOT NULL,
    
    -- Foreign key constraint
    CONSTRAINT fk_damage_card FOREIGN KEY (card_id) 
        REFERENCES vehicle_cards(card_id) ON DELETE CASCADE
);

-- Indexes for damage_detections
CREATE INDEX idx_damage_card_id ON damage_detections(card_id);
CREATE INDEX idx_damage_panel_name ON damage_detections(panel_name);
CREATE INDEX idx_damage_type ON damage_detections(damage_type);
CREATE INDEX idx_damage_severity ON damage_detections(severity);
CREATE INDEX idx_damage_detected_at ON damage_detections(detected_at);
CREATE INDEX idx_damage_card_detected ON damage_detections(card_id, detected_at);

-- =============================================
-- Table: repairs
-- =============================================
CREATE TABLE repairs (
    repair_id INTEGER PRIMARY KEY,
    card_id INTEGER NOT NULL,
    panel_name VARCHAR(100) NOT NULL,
    repair_action VARCHAR(50) NOT NULL,
    repair_cost DECIMAL(10,2) NOT NULL DEFAULT 0,
    approved BOOLEAN NOT NULL DEFAULT FALSE,
    created_at DATE NOT NULL,
    
    -- Foreign key constraint
    CONSTRAINT fk_repair_card FOREIGN KEY (card_id) 
        REFERENCES vehicle_cards(card_id) ON DELETE CASCADE
);

-- Indexes for repairs
CREATE INDEX idx_repairs_card_id ON repairs(card_id);
CREATE INDEX idx_repairs_panel_name ON repairs(panel_name);
CREATE INDEX idx_repairs_created_at ON repairs(created_at);
CREATE INDEX idx_repairs_approved ON repairs(approved);
CREATE INDEX idx_repairs_cost ON repairs(repair_cost);
CREATE INDEX idx_repairs_card_created ON repairs(card_id, created_at);

-- =============================================
-- Table: quotes
-- =============================================
CREATE TABLE quotes (
    quote_id INTEGER PRIMARY KEY,
    card_id INTEGER NOT NULL,
    total_estimated_cost DECIMAL(10,2) NOT NULL CHECK (total_estimated_cost >= 0),
    currency VARCHAR(3) NOT NULL DEFAULT 'INR',
    generated_at DATE NOT NULL,
    
    -- Foreign key constraint
    CONSTRAINT fk_quote_card FOREIGN KEY (card_id) 
        REFERENCES vehicle_cards(card_id) ON DELETE CASCADE
);

-- Indexes for quotes
CREATE INDEX idx_quotes_card_id ON quotes(card_id);
CREATE INDEX idx_quotes_generated_at ON quotes(generated_at);
CREATE INDEX idx_quotes_cost ON quotes(total_estimated_cost);

-- View: Recent damages with vehicle info
CREATE OR REPLACE VIEW v_recent_damages AS
SELECT 
    vc.card_id,
    vc.vehicle_type,
    vc.manufacturer,
    vc.model,
    vc.manufacture_year,
    dd.damage_id,
    dd.panel_name,
    dd.damage_type,
    dd.severity,
    dd.confidence,
    dd.detected_at
FROM vehicle_cards vc
JOIN damage_detections dd ON vc.card_id = dd.card_id;

-- View: Repair costs summary by vehicle
CREATE OR REPLACE VIEW v_repair_costs_summary AS
SELECT 
    vc.card_id,
    vc.vehicle_type,
    vc.manufacturer,
    vc.model,
    COUNT(r.repair_id) as total_repairs,
    SUM(r.repair_cost) as total_repair_cost,
    AVG(r.repair_cost) as avg_repair_cost,
    MIN(r.repair_cost) as min_repair_cost,
    MAX(r.repair_cost) as max_repair_cost
FROM vehicle_cards vc
LEFT JOIN repairs r ON vc.card_id = r.card_id
GROUP BY vc.card_id, vc.vehicle_type, vc.manufacturer, vc.model;

-- View: Damage and repair correlation
CREATE OR REPLACE VIEW v_damage_repair_analysis AS
SELECT 
    vc.card_id,
    vc.manufacturer,
    vc.model,
    COUNT(DISTINCT dd.damage_id) as total_damages,
    COUNT(DISTINCT r.repair_id) as total_repairs,
    SUM(r.repair_cost) as total_cost,
    AVG(dd.confidence) as avg_damage_confidence
FROM vehicle_cards vc
LEFT JOIN damage_detections dd ON vc.card_id = dd.card_id
LEFT JOIN repairs r ON vc.card_id = r.card_id
GROUP BY vc.card_id, vc.manufacturer, vc.model;

-- Create sequences for future inserts
CREATE SEQUENCE vehicle_cards_card_id_seq;
CREATE SEQUENCE damage_detections_damage_id_seq;
CREATE SEQUENCE repairs_repair_id_seq;
CREATE SEQUENCE quotes_quote_id_seq;

-- Set sequence ownership
ALTER SEQUENCE vehicle_cards_card_id_seq OWNED BY vehicle_cards.card_id;
ALTER SEQUENCE damage_detections_damage_id_seq OWNED BY damage_detections.damage_id;
ALTER SEQUENCE repairs_repair_id_seq OWNED BY repairs.repair_id;
ALTER SEQUENCE quotes_quote_id_seq OWNED BY quotes.quote_id;

-- Success message
DO $$
BEGIN
    RAISE NOTICE 'ClearQuote database schema created successfully!';
    RAISE NOTICE 'Tables created: vehicle_cards, damage_detections, repairs, quotes';
    RAISE NOTICE 'Views created: v_recent_damages, v_repair_costs_summary, v_damage_repair_analysis';
END $$;
