-- MoodBite AI PostgreSQL + pgvector Schema (Spec 06 + Spec 04 enrichment fields)
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS restaurants (
    id VARCHAR(32) PRIMARY KEY,
    name VARCHAR(120) NOT NULL,
    rating NUMERIC(2,1) NOT NULL,
    lat DOUBLE PRECISION NOT NULL,
    lng DOUBLE PRECISION NOT NULL,
    base_prep_mins INT NOT NULL,
    is_open BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS menu_items (
    id VARCHAR(32) PRIMARY KEY,
    restaurant_id VARCHAR(32) NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    name VARCHAR(160) NOT NULL,
    category VARCHAR(32) NOT NULL, -- 'main_bowl', 'roll_wrap', 'biryani_rice', 'noodle_soup', 'comfort_plate', 'beverage', 'dessert'
    dietary_type VARCHAR(16) NOT NULL, -- 'veg', 'egg', 'non_veg'
    dietary_tags TEXT[] DEFAULT '{}',
    allergens TEXT[] DEFAULT '{}',
    price_inr INT NOT NULL,
    prep_time_mins INT NOT NULL DEFAULT 12,
    mood_tags TEXT[] NOT NULL,
    sensory_tags TEXT[] NOT NULL,
    effort_to_eat VARCHAR(24) NOT NULL, -- 'zero_mess', 'standard'
    dopamine_score DOUBLE PRECISION NOT NULL DEFAULT 0.75,
    heavy_index DOUBLE PRECISION NOT NULL DEFAULT 0.50,
    pairing_affinities TEXT[] DEFAULT '{}',
    mood_embedding vector(384),
    is_available BOOLEAN DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_menu_mood_embedding
    ON menu_items USING ivfflat (mood_embedding vector_cosine_ops)
    WITH (lists = 100);

CREATE INDEX IF NOT EXISTS idx_menu_dietary
    ON menu_items (dietary_type, is_available);

CREATE INDEX IF NOT EXISTS idx_menu_restaurant
    ON menu_items (restaurant_id);
