-- 0019__property_amenities.sql
-- Удобства объекта. jsonb, не отдельная таблица: список плоский, фильтрация по
-- нему пока не нужна, а адрес уже лежит jsonb — один стиль на оба.
-- Значения приходят из справочника в коде (AMENITY_CATALOG), чтобы каталог и
-- UI не разъехались; БД хранит любой массив ключей, какие ни пришлёт партнёр.

ALTER TABLE property ADD COLUMN IF NOT EXISTS amenities jsonb
    NOT NULL DEFAULT '[]' CHECK (jsonb_typeof(amenities) = 'array');

COMMENT ON COLUMN property.amenities IS 'Ключи удобств из справочника app.config.amenities';
