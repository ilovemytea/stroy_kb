/* ============================================================
   КУРСОВОЙ ПРОЕКТ «СтройМир» — скрипт 3 из 3
   Представления, функции, хранимые процедуры и триггеры
   ============================================================ */
USE StroyMir_KB_Review_20261121;
GO

/* ---------- Представление: полная карточка статьи ---------- */
CREATE OR ALTER VIEW kb.v_MaterialCard
AS
SELECT m.id_material, m.title, m.summary, m.body, m.publish_date, m.views,
       ct.id_type, ct.name AS type_name,
       p.id_izdanie, p.name AS publisher_name,
       c.name AS country_name,
       v.platform AS video_platform, v.url AS video_url, v.duration_sec
FROM kb.Material AS m
JOIN kb.ContentType AS ct ON ct.id_type = m.id_type
JOIN kb.Publisher   AS p  ON p.id_izdanie = m.id_izdanie
LEFT JOIN kb.Country     AS c ON c.id_country = COALESCE(m.id_country, p.id_country)
LEFT JOIN kb.VideoSource AS v ON v.id_material = m.id_material;
GO

/* ---------- Представление: каталог продукции (цепочка из ЛР №7) ---------- */
CREATE OR ALTER VIEW dbo.v_ProductCatalog
AS
SELECT pr.id_product, pr.product_name, c.category_name, mf.manufacturer_name, mf.city,
       pr.packaging_type, pr.material_class,
       b.batch_name, b.packaging_unit, b.base_price, b.delivery_type,
       rm.raw_material_type, rm.density, rm.thermal_conductivity, rm.compressive_strength,
       rm.service_life_years
FROM dbo.Product AS pr
JOIN dbo.Category     AS c  ON c.id_category = pr.id_category
JOIN dbo.Manufacturer AS mf ON mf.id_manufacturer = c.id_manufacturer
LEFT JOIN dbo.Batch       AS b  ON b.id_product = pr.id_product
LEFT JOIN dbo.RawMaterial AS rm ON rm.id_raw_material = b.id_raw_material;
GO

/* ---------- Функция: соседи понятия в семантической сети ---------- */
CREATE OR ALTER FUNCTION kb.fn_ConceptNeighbors (@id_tag INT)
RETURNS TABLE
AS
RETURN
    SELECT r.relation_type, N'out' AS direction, t.id_tag, t.name
    FROM kb.Relation AS r JOIN kb.Tag AS t ON t.id_tag = r.id_tag_to
    WHERE r.id_tag_from = @id_tag
    UNION ALL
    SELECT r.relation_type, N'in', t.id_tag, t.name
    FROM kb.Relation AS r JOIN kb.Tag AS t ON t.id_tag = r.id_tag_from
    WHERE r.id_tag_to = @id_tag;
GO

/* ---------- Функция: все предки понятия по отношению «является»
   (рекурсивный CTE — транзитивное замыкание иерархии) ---------- */
CREATE OR ALTER FUNCTION kb.fn_ConceptAncestors (@id_tag INT)
RETURNS TABLE
AS
RETURN
    WITH chain AS
    (
        SELECT r.id_tag_to AS id_tag, 1 AS lvl
        FROM kb.Relation AS r
        WHERE r.id_tag_from = @id_tag AND r.relation_type = N'является'
        UNION ALL
        SELECT r.id_tag_to, ch.lvl + 1
        FROM chain AS ch
        JOIN kb.Relation AS r ON r.id_tag_from = ch.id_tag AND r.relation_type = N'является'
        WHERE ch.lvl < 10
    )
    SELECT DISTINCT ch.id_tag, t.name, ch.lvl
    FROM chain AS ch JOIN kb.Tag AS t ON t.id_tag = ch.id_tag;
GO

/* ---------- Функция: наследуемые свойства и применения понятия
   (то, что задано у предков, распространяется на потомка) ---------- */
CREATE OR ALTER FUNCTION kb.fn_InheritedFacts (@id_tag INT)
RETURNS TABLE
AS
RETURN
    SELECT a.name AS from_concept, a.lvl, r.relation_type, t.id_tag, t.name
    FROM kb.fn_ConceptAncestors(@id_tag) AS a
    JOIN kb.Relation AS r ON r.id_tag_from = a.id_tag
    JOIN kb.Tag      AS t ON t.id_tag = r.id_tag_to
    WHERE r.relation_type <> N'является';
GO

/* ---------- Функция: популярные запросы ---------- */
CREATE OR ALTER FUNCTION kb.fn_PopularQueries (@top INT)
RETURNS TABLE
AS
RETURN
    SELECT TOP (@top) LOWER(query_text) AS query_text, COUNT(*) AS cnt
    FROM kb.SearchLog
    WHERE results_count > 0
    GROUP BY LOWER(query_text)
    ORDER BY COUNT(*) DESC, MAX(created_at) DESC;
GO

/* ---------- Процедура: запись запроса в журнал ---------- */
CREATE OR ALTER PROCEDURE kb.usp_SearchLog_Add
    @query_text    NVARCHAR(300),
    @query_kind    NVARCHAR(20),
    @words_count   TINYINT,
    @results_count INT,
    @elapsed_ms    DECIMAL(9,2),
    @corrected     NVARCHAR(300) = NULL
AS
BEGIN
    SET NOCOUNT ON;
    INSERT INTO kb.SearchLog (query_text, query_kind, words_count, results_count, elapsed_ms, corrected)
    VALUES (LEFT(@query_text, 300), @query_kind, @words_count, @results_count, @elapsed_ms, @corrected);
END;
GO

/* ---------- Процедура: открытие статьи (счётчик просмотров) ---------- */
CREATE OR ALTER PROCEDURE kb.usp_Material_View
    @id_material INT
AS
BEGIN
    SET NOCOUNT ON;
    UPDATE kb.Material SET views = views + 1 WHERE id_material = @id_material;
    SELECT * FROM kb.v_MaterialCard WHERE id_material = @id_material;
END;
GO

/* ---------- Процедура: пересчёт итогового ранга статей по тегу ----------
   final_rank = 0.7 · релевантность тега + 0.3 · нормированная популярность;
   position_in_results — место статьи в выдаче по данному тегу. */
CREATE OR ALTER PROCEDURE kb.usp_RecalcRanks
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @max_views INT = (SELECT NULLIF(MAX(views), 0) FROM kb.Material);

    UPDATE mt
    SET final_rank = CAST(0.7 * mt.relevance
                          + 0.3 * ISNULL(CAST(m.views AS DECIMAL(9,4)) / @max_views, 0) AS DECIMAL(9,4))
    FROM kb.MaterialTag AS mt
    JOIN kb.Material AS m ON m.id_material = mt.id_material;

    WITH ranked AS
    (
        SELECT position_in_results,
               ROW_NUMBER() OVER (PARTITION BY id_tag ORDER BY final_rank DESC, id_material) AS rn
        FROM kb.MaterialTag
    )
    UPDATE ranked SET position_in_results = rn;
END;
GO

/* ---------- Процедура: статистика поиска для исследования БЗ ---------- */
CREATE OR ALTER PROCEDURE kb.usp_SearchStats
AS
BEGIN
    SET NOCOUNT ON;
    SELECT query_kind,
           COUNT(*)                                   AS queries,
           CAST(AVG(elapsed_ms) AS DECIMAL(9,2))      AS avg_ms,
           CAST(MAX(elapsed_ms) AS DECIMAL(9,2))      AS max_ms,
           CAST(AVG(CAST(results_count AS DECIMAL(9,2))) AS DECIMAL(9,2)) AS avg_results,
           SUM(CASE WHEN results_count = 0 THEN 1 ELSE 0 END) AS empty_results,
           SUM(CASE WHEN corrected IS NOT NULL THEN 1 ELSE 0 END) AS corrected
    FROM kb.SearchLog
    GROUP BY query_kind
    ORDER BY MIN(words_count);
END;
GO

/* ---------- Триггер: дата изменения статьи ---------- */
CREATE OR ALTER TRIGGER kb.trg_Material_Updated
ON kb.Material
AFTER UPDATE
AS
BEGIN
    SET NOCOUNT ON;
    IF UPDATE(title) OR UPDATE(summary) OR UPDATE(body)
        UPDATE m SET updated_at = SYSDATETIME()
        FROM kb.Material AS m JOIN inserted AS i ON i.id_material = m.id_material;
END;
GO

/* ---------- Триггер: запрет циклов в иерархии «является» ----------
   Нельзя сделать понятие видом собственного потомка. */
CREATE OR ALTER TRIGGER kb.trg_Relation_NoCycle
ON kb.Relation
AFTER INSERT, UPDATE
AS
BEGIN
    SET NOCOUNT ON;
    IF EXISTS (
        SELECT 1
        FROM inserted AS i
        CROSS APPLY kb.fn_ConceptAncestors(i.id_tag_to) AS a
        WHERE i.relation_type = N'является' AND a.id_tag = i.id_tag_from
    )
    BEGIN
        RAISERROR (N'Связь «является» образует цикл в иерархии понятий.', 16, 1);
        ROLLBACK TRANSACTION;
    END;
END;
GO
