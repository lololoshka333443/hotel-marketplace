-- 0009__property_photos.sql
-- Property photos. Partners add objects in our cabinet and upload photos there;
-- the public catalog renders them. Empty array = no photos yet (placeholder UI).

ALTER TABLE property
    ADD COLUMN IF NOT EXISTS photos jsonb NOT NULL DEFAULT '[]'::jsonb;

COMMENT ON COLUMN property.photos IS 'Массив URL фотографий (главная — первая)';

-- Existing published listings keep working with no photos.
UPDATE property SET photos = '[]'::jsonb WHERE photos IS NULL;
