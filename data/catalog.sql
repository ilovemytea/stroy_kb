/* Каталог продукции — демонстрационные данные из лабораторной работы №7 */
INSERT INTO dbo.Manufacturer
    (manufacturer_name, city, foundation_year)
VALUES
    (N'ОАО «Керамика»',                   N'Минск',     1958),
    (N'ОАО «Красносельскстройматериалы»', N'Волковыск', 1951),
    (N'ООО «ГипсПром»',                   N'Гомель',    2001),
    (N'ЗАО «ТермоИзол»',                  N'Минск',     2005),
    (N'ООО «КровляСервис»',               N'Могилёв',   2008),
    (N'ООО «ЛесТорг»',                    N'Витебск',   1998);
GO

INSERT INTO dbo.Category
    (id_manufacturer, category_name, standard_year)
SELECT id_manufacturer, N'Кирпич', 2012
FROM dbo.Manufacturer WHERE manufacturer_name = N'ОАО «Керамика»'
UNION ALL
SELECT id_manufacturer, N'Тротуарная плитка', 2010
FROM dbo.Manufacturer WHERE manufacturer_name = N'ОАО «Керамика»'
UNION ALL
SELECT id_manufacturer, N'Цемент', 2015
FROM dbo.Manufacturer WHERE manufacturer_name = N'ОАО «Красносельскстройматериалы»'
UNION ALL
SELECT id_manufacturer, N'Гипсокартон', 2013
FROM dbo.Manufacturer WHERE manufacturer_name = N'ООО «ГипсПром»'
UNION ALL
SELECT id_manufacturer, N'Утеплитель', 2011
FROM dbo.Manufacturer WHERE manufacturer_name = N'ЗАО «ТермоИзол»'
UNION ALL
SELECT id_manufacturer, N'Кровельный материал', 2014
FROM dbo.Manufacturer WHERE manufacturer_name = N'ООО «КровляСервис»'
UNION ALL
SELECT id_manufacturer, N'Пиломатериалы', 2009
FROM dbo.Manufacturer WHERE manufacturer_name = N'ООО «ЛесТорг»';
GO

INSERT INTO dbo.Product
    (id_category, product_name, packaging_type, material_class, shelf_life_months)
SELECT id_category, N'Кирпич керамический М150', N'паллета', N'стандарт', NULL
FROM dbo.Category WHERE category_name = N'Кирпич'
UNION ALL
SELECT id_category, N'Плитка Брусчатка 200x100', N'паллета', N'стандарт', NULL
FROM dbo.Category WHERE category_name = N'Тротуарная плитка'
UNION ALL
SELECT id_category, N'Цемент М500 Д0', N'мешок', N'высшая марка', 6
FROM dbo.Category WHERE category_name = N'Цемент'
UNION ALL
SELECT id_category, N'ГКЛ Стандарт 12.5 мм', N'лист', N'стандарт', NULL
FROM dbo.Category WHERE category_name = N'Гипсокартон'
UNION ALL
SELECT id_category, N'Минеральная вата Лайт', N'рулон', N'эконом', NULL
FROM dbo.Category WHERE category_name = N'Утеплитель'
UNION ALL
SELECT id_category, N'Металлочерепица Монтеррей', N'лист', N'премиум', NULL
FROM dbo.Category WHERE category_name = N'Кровельный материал'
UNION ALL
SELECT id_category, N'Брус строительный 150x150', N'пачка', N'стандарт', NULL
FROM dbo.Category WHERE category_name = N'Пиломатериалы';
GO

INSERT INTO dbo.RawMaterial
    (raw_material_code, raw_material_type, density,
     thermal_conductivity, compressive_strength, service_life_years)
VALUES
    ('CER',  N'минеральное',    1700, 0.50, 15.0, 100),
    ('PAVE', N'минеральное',    2300, NULL, 30.0, 25),
    ('CEM',  N'минеральное',    1300, NULL, 50.0, NULL),
    ('GKL',  N'минеральное',     800, 0.21, NULL, 30),
    ('MW',   N'минеральное',      35, 0.04, NULL, 50),
    ('MET',  N'металлическое',  7850, 50.0, NULL, 50),
    ('WOOD', N'древесное',       500, 0.15, 40.0, 50);
GO

INSERT INTO dbo.Batch
    (id_product, id_raw_material, batch_name,
     delivery_type, packaging_unit, base_price)
SELECT pr.id_product, rm.id_raw_material, N'Паллета 350 шт', N'доставка', N'паллета', 420
FROM dbo.Product pr
JOIN dbo.Category c ON c.id_category = pr.id_category
CROSS JOIN dbo.RawMaterial rm
WHERE c.category_name = N'Кирпич' AND pr.product_name = N'Кирпич керамический М150' AND rm.raw_material_code = 'CER'
UNION ALL
SELECT pr.id_product, rm.id_raw_material, N'Паллета 10 м2', N'доставка', N'м2', 45
FROM dbo.Product pr
JOIN dbo.Category c ON c.id_category = pr.id_category
CROSS JOIN dbo.RawMaterial rm
WHERE c.category_name = N'Тротуарная плитка' AND pr.product_name = N'Плитка Брусчатка 200x100' AND rm.raw_material_code = 'PAVE'
UNION ALL
SELECT pr.id_product, rm.id_raw_material, N'Мешок 50 кг', N'доставка', N'мешок', 18
FROM dbo.Product pr
JOIN dbo.Category c ON c.id_category = pr.id_category
CROSS JOIN dbo.RawMaterial rm
WHERE c.category_name = N'Цемент' AND pr.product_name = N'Цемент М500 Д0' AND rm.raw_material_code = 'CEM'
UNION ALL
SELECT pr.id_product, rm.id_raw_material, N'Пачка 10 листов', N'доставка', N'лист', 9
FROM dbo.Product pr
JOIN dbo.Category c ON c.id_category = pr.id_category
CROSS JOIN dbo.RawMaterial rm
WHERE c.category_name = N'Гипсокартон' AND pr.product_name = N'ГКЛ Стандарт 12.5 мм' AND rm.raw_material_code = 'GKL'
UNION ALL
SELECT pr.id_product, rm.id_raw_material, N'Упаковка 6 м2', N'доставка', N'упаковка', 35
FROM dbo.Product pr
JOIN dbo.Category c ON c.id_category = pr.id_category
CROSS JOIN dbo.RawMaterial rm
WHERE c.category_name = N'Утеплитель' AND pr.product_name = N'Минеральная вата Лайт' AND rm.raw_material_code = 'MW'
UNION ALL
SELECT pr.id_product, rm.id_raw_material, N'Лист 2250x1100', N'доставка', N'лист', 28
FROM dbo.Product pr
JOIN dbo.Category c ON c.id_category = pr.id_category
CROSS JOIN dbo.RawMaterial rm
WHERE c.category_name = N'Кровельный материал' AND pr.product_name = N'Металлочерепица Монтеррей' AND rm.raw_material_code = 'MET'
UNION ALL
SELECT pr.id_product, rm.id_raw_material, N'Пачка 3 м3', N'самовывоз', N'м3', 260
FROM dbo.Product pr
JOIN dbo.Category c ON c.id_category = pr.id_category
CROSS JOIN dbo.RawMaterial rm
WHERE c.category_name = N'Пиломатериалы' AND pr.product_name = N'Брус строительный 150x150' AND rm.raw_material_code = 'WOOD';
GO

INSERT INTO dbo.Delivery
    (id_batch, delivery_date, object_name, quantity, delivery_price)
SELECT id_batch, '2026-09-01', N'ЖК «Сосновый Бор», Минск', 40, 410
FROM dbo.Batch WHERE batch_name = N'Паллета 350 шт'
UNION ALL
SELECT id_batch, '2026-09-03', N'Двор по ул. Богдановича, Гродно', 120, 44
FROM dbo.Batch WHERE batch_name = N'Паллета 10 м2'
UNION ALL
SELECT id_batch, '2026-09-05', N'Склад ИП Петрова, Брест', 500, 17.5
FROM dbo.Batch WHERE batch_name = N'Мешок 50 кг'
UNION ALL
SELECT id_batch, '2026-09-07', N'Офисный центр, Минск', 200, 8.7
FROM dbo.Batch WHERE batch_name = N'Пачка 10 листов'
UNION ALL
SELECT id_batch, '2026-09-10', N'Коттедж, Гродно', 30, 34
FROM dbo.Batch WHERE batch_name = N'Упаковка 6 м2'
UNION ALL
SELECT id_batch, '2026-09-12', N'Частный дом, Минск', 60, 27
FROM dbo.Batch WHERE batch_name = N'Лист 2250x1100'
UNION ALL
SELECT id_batch, '2026-09-15', N'Баня, Витебск', 5, 255
FROM dbo.Batch WHERE batch_name = N'Пачка 3 м3';
GO

/* Дополнительные позиции каталога для курсового проекта */
INSERT INTO dbo.Manufacturer (manufacturer_name, city, foundation_year)
VALUES (N'ООО «ГазоБлок»', N'Гродно', 2007),
       (N'ООО «СиликатСтрой»', N'Брест', 1996),
       (N'ООО «ПолимерИзол»', N'Минск', 2012);
GO

INSERT INTO dbo.Category (id_manufacturer, category_name, standard_year)
SELECT id_manufacturer, N'Газобетон', 2016 FROM dbo.Manufacturer WHERE manufacturer_name = N'ООО «ГазоБлок»'
UNION ALL
SELECT id_manufacturer, N'Силикатный кирпич', 2015 FROM dbo.Manufacturer WHERE manufacturer_name = N'ООО «СиликатСтрой»'
UNION ALL
SELECT id_manufacturer, N'Пенополистирол', 2014 FROM dbo.Manufacturer WHERE manufacturer_name = N'ООО «ПолимерИзол»';
GO

INSERT INTO dbo.Product (id_category, product_name, packaging_type, material_class, shelf_life_months)
SELECT id_category, N'Газобетонный блок D500 600x300x200', N'паллета', N'стандарт', NULL FROM dbo.Category WHERE category_name = N'Газобетон'
UNION ALL
SELECT id_category, N'Газобетонный блок перегородочный D500 600x100x200', N'паллета', N'стандарт', NULL FROM dbo.Category WHERE category_name = N'Газобетон'
UNION ALL
SELECT id_category, N'Кирпич силикатный утолщённый М150', N'паллета', N'стандарт', NULL FROM dbo.Category WHERE category_name = N'Силикатный кирпич'
UNION ALL
SELECT id_category, N'Экструдированный пенополистирол XPS 50 мм', N'упаковка', N'премиум', NULL FROM dbo.Category WHERE category_name = N'Пенополистирол'
UNION ALL
SELECT id_category, N'Пенополистирол ППС-15 100 мм', N'упаковка', N'эконом', NULL FROM dbo.Category WHERE category_name = N'Пенополистирол'
UNION ALL
SELECT id_category, N'ГКЛВ влагостойкий 12.5 мм', N'лист', N'стандарт', NULL FROM dbo.Category WHERE category_name = N'Гипсокартон'
UNION ALL
SELECT id_category, N'Профнастил С20 0.5 мм', N'лист', N'стандарт', NULL FROM dbo.Category WHERE category_name = N'Кровельный материал'
UNION ALL
SELECT id_category, N'Минеральная вата фасадная 100 кг/м3', N'упаковка', N'премиум', NULL FROM dbo.Category WHERE category_name = N'Утеплитель';
GO

INSERT INTO dbo.RawMaterial (raw_material_code, raw_material_type, density, thermal_conductivity, compressive_strength, service_life_years)
VALUES ('AAC', N'минеральное', 500, 0.12, 3.5, 100),
       ('SIL', N'минеральное', 1850, 0.80, 15.0, 50),
       ('EPS', N'полимерное', 15, 0.04, NULL, 40),
       ('XPS', N'полимерное', 33, 0.03, 0.3, 50);
GO

INSERT INTO dbo.Batch (id_product, id_raw_material, batch_name, delivery_type, packaging_unit, base_price)
SELECT pr.id_product, rm.id_raw_material, v.batch_name, v.delivery_type, v.unit, v.price
FROM (VALUES
    (N'Газобетонный блок D500 600x300x200', 'AAC', N'Паллета 1.8 м3', N'доставка', N'м3', 165),
    (N'Газобетонный блок перегородочный D500 600x100x200', 'AAC', N'Паллета 1.8 м3 (перегородочный)', N'доставка', N'м3', 170),
    (N'Кирпич силикатный утолщённый М150', 'SIL', N'Паллета 280 шт', N'доставка', N'паллета', 260),
    (N'Экструдированный пенополистирол XPS 50 мм', 'XPS', N'Упаковка 0.36 м3', N'самовывоз', N'упаковка', 62),
    (N'Пенополистирол ППС-15 100 мм', 'EPS', N'Упаковка 0.5 м3', N'самовывоз', N'упаковка', 38),
    (N'ГКЛВ влагостойкий 12.5 мм', 'GKL', N'Пачка 10 листов ГКЛВ', N'доставка', N'лист', 12),
    (N'Профнастил С20 0.5 мм', 'MET', N'Лист 2000x1150', N'доставка', N'лист', 22),
    (N'Минеральная вата фасадная 100 кг/м3', 'MW', N'Упаковка 2.4 м2', N'доставка', N'упаковка', 41)
) AS v(product_name, code, batch_name, delivery_type, unit, price)
JOIN dbo.Product AS pr ON pr.product_name = v.product_name
JOIN dbo.RawMaterial AS rm ON rm.raw_material_code = v.code;
GO
