-- عزوتك service catalog seed, migration 0002.
-- These are public catalog definitions only; no customer, provider, or payment data is seeded.

INSERT INTO service_categories (slug, name_ar, name_en, active)
VALUES
    ('home', 'المنزل', 'Home', TRUE),
    ('moving', 'النقل والشحن', 'Moving and delivery', TRUE),
    ('maintenance', 'الصيانة والترميم', 'Maintenance and renovation', TRUE),
    ('auto', 'السيارات', 'Automotive', TRUE),
    ('outdoors', 'الحدائق والمسابح', 'Outdoors', TRUE),
    ('events', 'المناسبات', 'Events', TRUE)
ON CONFLICT (slug) DO UPDATE
SET name_ar = EXCLUDED.name_ar,
    name_en = EXCLUDED.name_en,
    active = TRUE;

INSERT INTO services (category_id, slug, name_ar, name_en, minimum_amount_minor, currency, active)
SELECT categories.id, catalog.slug, catalog.name_ar, catalog.name_en,
       catalog.minimum_amount_minor, 'JOD', TRUE
FROM (
    VALUES
        ('home', 'home-maintenance', 'صيانة منزلية', 'Home maintenance', 1500),
        ('home', 'cleaning', 'تنظيف وتعقيم', 'Cleaning and sanitization', 1200),
        ('moving', 'moving-delivery', 'نقل وشحن', 'Moving and delivery', 2500),
        ('maintenance', 'electric-plumbing', 'كهرباء وسباكة', 'Electrical and plumbing', 1800),
        ('maintenance', 'painting-renovation', 'دهان وترميم', 'Painting and renovation', 3500),
        ('auto', 'car-maintenance', 'صيانة سيارات', 'Car maintenance', 2000),
        ('outdoors', 'gardens-pools', 'حدائق ومسابح', 'Gardens and pools', 1500),
        ('events', 'events', 'خدمات المناسبات', 'Events services', 3000)
) AS catalog(category_slug, slug, name_ar, name_en, minimum_amount_minor)
JOIN service_categories AS categories ON categories.slug = catalog.category_slug
ON CONFLICT (slug) DO UPDATE
SET category_id = EXCLUDED.category_id,
    name_ar = EXCLUDED.name_ar,
    name_en = EXCLUDED.name_en,
    minimum_amount_minor = EXCLUDED.minimum_amount_minor,
    currency = 'JOD',
    active = TRUE;
