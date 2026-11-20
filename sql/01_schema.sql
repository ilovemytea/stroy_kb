/* ============================================================
   КУРСОВОЙ ПРОЕКТ
   Тема: «Проектирование базы знаний по строительным материалам»
   Информационно-поисковый портал «СтройМир»
   СУБД: Microsoft SQL Server 2019+
   Автор: Дусов А.Э.

   Скрипт 1 из 3: создание базы данных и таблиц.
   Можно запускать повторно (F5 в SSMS или sqlcmd -i).

   Схема dbo — каталог продукции (из лабораторных работ №5–11):
     Manufacturer 1:N Category 1:N Product 1:N Batch N:1 RawMaterial
     Batch 1:N Delivery
   Схема kb — база знаний (ER-модель курсового проекта):
     Country 1:N Publisher 1:N Material N:1 ContentType
     Country 1:N Material
     Material 1:N MaterialTag N:1 Tag N:1 Category
     Material 1:0..1 VideoSource
   Расширение базы знаний:
     Tag 1:N Relation N:1 Tag          — семантическая сеть (онтология)
     Question, Rule 1:N RuleCondition   — продукционная экспертная система
     SearchLog                          — журнал поисковых запросов
   ============================================================ */

USE master;
GO

IF DB_ID(N'StroyMir_KB_Review_20261121') IS NULL
    CREATE DATABASE StroyMir_KB_Review_20261121 COLLATE Cyrillic_General_CI_AS;
GO

USE StroyMir_KB_Review_20261121;
GO

IF SCHEMA_ID(N'kb') IS NULL
    EXEC(N'CREATE SCHEMA kb');
GO

/* Очистка при повторном запуске: дочерние таблицы раньше родительских */
DROP TABLE IF EXISTS kb.MaterialProperty;
DROP TABLE IF EXISTS kb.PropertyDefinition;
DROP TABLE IF EXISTS kb.RuleProvenance;
DROP TABLE IF EXISTS kb.ArticleGuide;
DROP TABLE IF EXISTS kb.SearchLog;
DROP TABLE IF EXISTS kb.RuleCondition;
DROP TABLE IF EXISTS kb.[Rule];
DROP TABLE IF EXISTS kb.Question;
DROP TABLE IF EXISTS kb.Relation;
DROP TABLE IF EXISTS kb.VideoSource;
DROP TABLE IF EXISTS kb.MaterialTag;
DROP TABLE IF EXISTS kb.Material;
DROP TABLE IF EXISTS kb.Tag;
DROP TABLE IF EXISTS kb.Category;
DROP TABLE IF EXISTS kb.ContentType;
DROP TABLE IF EXISTS kb.Publisher;
DROP TABLE IF EXISTS kb.Country;

DROP TABLE IF EXISTS dbo.Delivery;
DROP TABLE IF EXISTS dbo.Batch;
DROP TABLE IF EXISTS dbo.RawMaterial;
DROP TABLE IF EXISTS dbo.Product;
DROP TABLE IF EXISTS dbo.Category;
DROP TABLE IF EXISTS dbo.Manufacturer;
GO

/* ============================================================
   КАТАЛОГ ПРОДУКЦИИ (схема dbo, из лабораторной работы №7)
   ============================================================ */
CREATE TABLE dbo.Manufacturer
(
    id_manufacturer   INT IDENTITY(1,1) NOT NULL,
    manufacturer_name NVARCHAR(100) NOT NULL,
    city              NVARCHAR(80) NULL,
    foundation_year   SMALLINT NULL,
    CONSTRAINT PK_Manufacturer PRIMARY KEY (id_manufacturer),
    CONSTRAINT UQ_Manufacturer_name UNIQUE (manufacturer_name),
    CONSTRAINT CK_Manufacturer_year
        CHECK (foundation_year IS NULL OR foundation_year BETWEEN 1800 AND 2100)
);

CREATE TABLE dbo.Category
(
    id_category       INT IDENTITY(1,1) NOT NULL,
    id_manufacturer   INT NOT NULL,
    category_name     NVARCHAR(80) NOT NULL,
    standard_year     SMALLINT NULL,
    CONSTRAINT PK_Category PRIMARY KEY (id_category),
    CONSTRAINT UQ_Category_name UNIQUE (category_name),
    CONSTRAINT FK_Category_Manufacturer FOREIGN KEY (id_manufacturer)
        REFERENCES dbo.Manufacturer(id_manufacturer),
    CONSTRAINT CK_Category_year
        CHECK (standard_year IS NULL OR standard_year BETWEEN 1800 AND 2100)
);

CREATE TABLE dbo.Product
(
    id_product         INT IDENTITY(1,1) NOT NULL,
    id_category        INT NOT NULL,
    product_name       NVARCHAR(100) NOT NULL,
    packaging_type     NVARCHAR(40) NOT NULL,
    material_class     NVARCHAR(40) NULL,
    shelf_life_months  SMALLINT NULL,
    CONSTRAINT PK_Product PRIMARY KEY (id_product),
    CONSTRAINT UQ_Product_category_name UNIQUE (id_category, product_name),
    CONSTRAINT FK_Product_Category FOREIGN KEY (id_category)
        REFERENCES dbo.Category(id_category),
    CONSTRAINT CK_Product_shelf_life
        CHECK (shelf_life_months IS NULL OR shelf_life_months BETWEEN 1 AND 120)
);

CREATE TABLE dbo.RawMaterial
(
    id_raw_material      INT IDENTITY(1,1) NOT NULL,
    raw_material_code    VARCHAR(30) NOT NULL,
    raw_material_type    NVARCHAR(30) NOT NULL,
    density              INT NULL,
    thermal_conductivity DECIMAL(4,2) NULL,
    compressive_strength DECIMAL(6,1) NULL,
    service_life_years   INT NULL,
    CONSTRAINT PK_RawMaterial PRIMARY KEY (id_raw_material),
    CONSTRAINT UQ_RawMaterial_code UNIQUE (raw_material_code),
    CONSTRAINT CK_RawMaterial_type CHECK (raw_material_type IN
        (N'минеральное', N'древесное', N'металлическое', N'полимерное')),
    CONSTRAINT CK_RawMaterial_density CHECK (density IS NULL OR density > 0)
);

CREATE TABLE dbo.Batch
(
    id_batch         INT IDENTITY(1,1) NOT NULL,
    id_product       INT NOT NULL,
    id_raw_material  INT NOT NULL,
    batch_name       NVARCHAR(80) NOT NULL,
    delivery_type    NVARCHAR(20) NOT NULL,
    packaging_unit   NVARCHAR(30) NOT NULL,
    base_price       DECIMAL(12,2) NOT NULL,
    CONSTRAINT PK_Batch PRIMARY KEY (id_batch),
    CONSTRAINT UQ_Batch_product_name UNIQUE (id_product, batch_name),
    CONSTRAINT FK_Batch_Product FOREIGN KEY (id_product) REFERENCES dbo.Product(id_product),
    CONSTRAINT FK_Batch_RawMaterial FOREIGN KEY (id_raw_material)
        REFERENCES dbo.RawMaterial(id_raw_material),
    CONSTRAINT CK_Batch_delivery CHECK (delivery_type IN (N'доставка', N'самовывоз')),
    CONSTRAINT CK_Batch_price CHECK (base_price > 0)
);

CREATE TABLE dbo.Delivery
(
    id_delivery      INT IDENTITY(1,1) NOT NULL,
    id_batch         INT NOT NULL,
    delivery_date    DATE NOT NULL,
    object_name      NVARCHAR(80) NOT NULL,
    quantity         INT NOT NULL CONSTRAINT DF_Delivery_quantity DEFAULT (1),
    delivery_price   DECIMAL(12,2) NOT NULL,
    CONSTRAINT PK_Delivery PRIMARY KEY (id_delivery),
    CONSTRAINT FK_Delivery_Batch FOREIGN KEY (id_batch) REFERENCES dbo.Batch(id_batch),
    CONSTRAINT CK_Delivery_quantity CHECK (quantity > 0),
    CONSTRAINT CK_Delivery_price CHECK (delivery_price > 0)
);
GO

/* ============================================================
   БАЗА ЗНАНИЙ (схема kb) — по ER-модели курсового проекта
   ============================================================ */

/* СТРАНА */
CREATE TABLE kb.Country
(
    id_country  INT IDENTITY(1,1) NOT NULL,
    name        NVARCHAR(60) NOT NULL,
    iso_code    CHAR(2) NOT NULL,
    CONSTRAINT PK_Country PRIMARY KEY (id_country),
    CONSTRAINT UQ_Country_name UNIQUE (name),
    CONSTRAINT UQ_Country_iso UNIQUE (iso_code)
);

/* ИЗДАНИЕ: Country 1:N Publisher */
CREATE TABLE kb.Publisher
(
    id_izdanie  INT IDENTITY(1,1) NOT NULL,
    name        NVARCHAR(120) NOT NULL,
    id_country  INT NOT NULL,
    site        NVARCHAR(200) NULL,
    CONSTRAINT PK_Publisher PRIMARY KEY (id_izdanie),
    CONSTRAINT UQ_Publisher_name UNIQUE (name),
    CONSTRAINT FK_Publisher_Country FOREIGN KEY (id_country) REFERENCES kb.Country(id_country)
);

/* ТИП_МАТЕРИАЛА */
CREATE TABLE kb.ContentType
(
    id_type      INT IDENTITY(1,1) NOT NULL,
    name         NVARCHAR(60) NOT NULL,
    description  NVARCHAR(300) NULL,
    CONSTRAINT PK_ContentType PRIMARY KEY (id_type),
    CONSTRAINT UQ_ContentType_name UNIQUE (name)
);

/* КАТЕГОРИЯ (тегов) */
CREATE TABLE kb.Category
(
    id_category  INT IDENTITY(1,1) NOT NULL,
    name         NVARCHAR(60) NOT NULL,
    description  NVARCHAR(300) NULL,
    CONSTRAINT PK_KbCategory PRIMARY KEY (id_category),
    CONSTRAINT UQ_KbCategory_name UNIQUE (name)
);

/* ТЕГ = понятие онтологии. Category 1:N Tag.
   synonyms — синонимы через «;», используются для расширения запроса. */
CREATE TABLE kb.Tag
(
    id_tag       INT IDENTITY(1,1) NOT NULL,
    id_category  INT NOT NULL,
    name         NVARCHAR(100) NOT NULL,
    synonyms     NVARCHAR(500) NULL,
    definition   NVARCHAR(600) NULL,
    CONSTRAINT PK_Tag PRIMARY KEY (id_tag),
    CONSTRAINT UQ_Tag_name UNIQUE (name),
    CONSTRAINT FK_Tag_Category FOREIGN KEY (id_category) REFERENCES kb.Category(id_category)
);

/* МАТЕРИАЛ (статья базы знаний) */
CREATE TABLE kb.Material
(
    id_material   INT IDENTITY(1,1) NOT NULL,
    title         NVARCHAR(200) NOT NULL,
    summary       NVARCHAR(500) NULL,
    body          NVARCHAR(MAX) NOT NULL,
    publish_date  DATE NOT NULL CONSTRAINT DF_Material_date DEFAULT (CAST(GETDATE() AS DATE)),
    id_izdanie    INT NOT NULL,
    id_type       INT NOT NULL,
    id_country    INT NULL,
    views         INT NOT NULL CONSTRAINT DF_Material_views DEFAULT (0),
    updated_at    DATETIME2(0) NOT NULL CONSTRAINT DF_Material_updated DEFAULT (SYSDATETIME()),
    CONSTRAINT PK_Material PRIMARY KEY (id_material),
    CONSTRAINT UQ_Material_title UNIQUE (title),
    CONSTRAINT FK_Material_Publisher FOREIGN KEY (id_izdanie) REFERENCES kb.Publisher(id_izdanie),
    CONSTRAINT FK_Material_ContentType FOREIGN KEY (id_type) REFERENCES kb.ContentType(id_type),
    CONSTRAINT FK_Material_Country FOREIGN KEY (id_country) REFERENCES kb.Country(id_country),
    CONSTRAINT CK_Material_body CHECK (LEN(body) >= 50)
);

/* МАТЕРИАЛ_ТЕГ: связь N:M Material–Tag с атрибутами ранжирования */
CREATE TABLE kb.MaterialTag
(
    id_material_tag      INT IDENTITY(1,1) NOT NULL,
    id_material          INT NOT NULL,
    id_tag               INT NOT NULL,
    relevance            DECIMAL(3,2) NOT NULL CONSTRAINT DF_MaterialTag_rel DEFAULT (0.50),
    position_in_results  INT NULL,
    final_rank           DECIMAL(9,4) NULL,
    CONSTRAINT PK_MaterialTag PRIMARY KEY (id_material_tag),
    CONSTRAINT UQ_MaterialTag UNIQUE (id_material, id_tag),
    CONSTRAINT FK_MaterialTag_Material FOREIGN KEY (id_material)
        REFERENCES kb.Material(id_material) ON DELETE CASCADE,
    CONSTRAINT FK_MaterialTag_Tag FOREIGN KEY (id_tag) REFERENCES kb.Tag(id_tag),
    CONSTRAINT CK_MaterialTag_rel CHECK (relevance BETWEEN 0 AND 1)
);

/* ВИДЕОРОЛИК: Material 1:0..1 VideoSource */
CREATE TABLE kb.VideoSource
(
    id_video     INT IDENTITY(1,1) NOT NULL,
    id_material  INT NOT NULL,
    platform     NVARCHAR(40) NOT NULL,
    url          NVARCHAR(400) NOT NULL,
    duration_sec INT NULL,
    CONSTRAINT PK_VideoSource PRIMARY KEY (id_video),
    CONSTRAINT UQ_VideoSource_material UNIQUE (id_material),
    CONSTRAINT FK_VideoSource_Material FOREIGN KEY (id_material)
        REFERENCES kb.Material(id_material) ON DELETE CASCADE,
    CONSTRAINT CK_VideoSource_duration CHECK (duration_sec IS NULL OR duration_sec > 0)
);
GO

/* ============================================================
   РАСШИРЕНИЕ: семантическая сеть, экспертная система, журнал
   ============================================================ */

/* СВЯЗЬ ПОНЯТИЙ: ориентированное ребро «понятие — отношение — понятие» */
CREATE TABLE kb.Relation
(
    id_relation    INT IDENTITY(1,1) NOT NULL,
    id_tag_from    INT NOT NULL,
    relation_type  NVARCHAR(30) NOT NULL,
    id_tag_to      INT NOT NULL,
    CONSTRAINT PK_Relation PRIMARY KEY (id_relation),
    CONSTRAINT UQ_Relation UNIQUE (id_tag_from, relation_type, id_tag_to),
    CONSTRAINT FK_Relation_From FOREIGN KEY (id_tag_from) REFERENCES kb.Tag(id_tag),
    CONSTRAINT FK_Relation_To FOREIGN KEY (id_tag_to) REFERENCES kb.Tag(id_tag),
    CONSTRAINT CK_Relation_type CHECK (relation_type IN
        (N'является', N'применяется_для', N'изготавливается_из', N'обладает_свойством',
         N'заменяет', N'регламентируется', N'несовместим_с', N'часть')),
    CONSTRAINT CK_Relation_self CHECK (id_tag_from <> id_tag_to)
);

/* ВОПРОС экспертной системы (атрибут рабочей памяти) */
CREATE TABLE kb.Question
(
    attribute      NVARCHAR(30) NOT NULL,
    question_text  NVARCHAR(200) NOT NULL,
    options        NVARCHAR(400) NOT NULL,      -- варианты через «;»
    cond_attribute NVARCHAR(30) NULL,           -- вопрос задаётся, только если
    cond_values    NVARCHAR(300) NULL,          -- cond_attribute IN (cond_values)
    sort_order     INT NOT NULL,
    CONSTRAINT PK_Question PRIMARY KEY (attribute)
);

/* ПРАВИЛО: ЕСЛИ <условия> ТО <факт | рекомендация> с коэффициентом уверенности CF */
CREATE TABLE kb.[Rule]
(
    id_rule        INT IDENTITY(1,1) NOT NULL,
    code           VARCHAR(10) NOT NULL,
    then_kind      VARCHAR(4) NOT NULL,          -- 'fact' или 'tag'
    then_attribute NVARCHAR(30) NULL,
    then_value     NVARCHAR(60) NULL,
    id_tag         INT NULL,
    cf             DECIMAL(3,2) NOT NULL,
    explanation    NVARCHAR(300) NOT NULL,
    CONSTRAINT PK_Rule PRIMARY KEY (id_rule),
    CONSTRAINT UQ_Rule_code UNIQUE (code),
    CONSTRAINT FK_Rule_Tag FOREIGN KEY (id_tag) REFERENCES kb.Tag(id_tag),
    CONSTRAINT CK_Rule_cf CHECK (cf BETWEEN -1 AND 1),
    CONSTRAINT CK_Rule_kind CHECK (
        (then_kind = 'fact' AND then_attribute IS NOT NULL AND then_value IS NOT NULL AND id_tag IS NULL)
     OR (then_kind = 'tag' AND id_tag IS NOT NULL))
);

CREATE TABLE kb.RuleCondition
(
    id_condition  INT IDENTITY(1,1) NOT NULL,
    id_rule       INT NOT NULL,
    attribute     NVARCHAR(30) NOT NULL,
    value         NVARCHAR(60) NOT NULL,
    CONSTRAINT PK_RuleCondition PRIMARY KEY (id_condition),
    CONSTRAINT FK_RuleCondition_Rule FOREIGN KEY (id_rule)
        REFERENCES kb.[Rule](id_rule) ON DELETE CASCADE
);

/* ЖУРНАЛ ПОИСКА — для подсказок и исследования характеристик БЗ */
CREATE TABLE kb.SearchLog
(
    id_log        BIGINT IDENTITY(1,1) NOT NULL,
    query_text    NVARCHAR(300) NOT NULL,
    query_kind    NVARCHAR(20) NOT NULL,
    words_count   TINYINT NOT NULL,
    results_count INT NOT NULL,
    elapsed_ms    DECIMAL(9,2) NOT NULL,
    corrected     NVARCHAR(300) NULL,
    created_at    DATETIME2(0) NOT NULL CONSTRAINT DF_SearchLog_created DEFAULT (SYSDATETIME()),
    CONSTRAINT PK_SearchLog PRIMARY KEY (id_log),
    CONSTRAINT CK_SearchLog_words CHECK (words_count BETWEEN 0 AND 15)
);
GO

/* Индексы для частых соединений и выборок */
CREATE INDEX IX_Material_type      ON kb.Material(id_type);
CREATE INDEX IX_Material_publisher ON kb.Material(id_izdanie);
CREATE INDEX IX_MaterialTag_tag    ON kb.MaterialTag(id_tag) INCLUDE (relevance);
CREATE INDEX IX_Tag_category       ON kb.Tag(id_category);
CREATE INDEX IX_Relation_to        ON kb.Relation(id_tag_to, relation_type);
CREATE INDEX IX_RuleCondition_rule ON kb.RuleCondition(id_rule);
CREATE INDEX IX_SearchLog_created  ON kb.SearchLog(created_at);
CREATE INDEX IX_SearchLog_query    ON kb.SearchLog(query_text);
GO

IF OBJECT_ID(N'kb.ArticleGuide',N'U') IS NULL
CREATE TABLE kb.ArticleGuide (
    id_material INT NOT NULL PRIMARY KEY,
    guide_json NVARCHAR(MAX) NOT NULL CHECK(ISJSON(guide_json)=1),
    CONSTRAINT FK_ArticleGuide_Material FOREIGN KEY(id_material)
        REFERENCES kb.Material(id_material) ON DELETE CASCADE
);
GO

/* Optional review model: typed facts and rule provenance. */
CREATE TABLE kb.RuleProvenance(code NVARCHAR(20) NOT NULL PRIMARY KEY,notes NVARCHAR(MAX) NOT NULL CHECK(ISJSON(notes)=1));
CREATE TABLE kb.PropertyDefinition(code NVARCHAR(40) NOT NULL PRIMARY KEY,name NVARCHAR(100) NOT NULL,unit NVARCHAR(40) NOT NULL);
CREATE TABLE kb.MaterialProperty(
    id_product INT NOT NULL REFERENCES dbo.Product(id_product),
    id_tag INT NOT NULL REFERENCES kb.Tag(id_tag),
    property_code NVARCHAR(40) NOT NULL REFERENCES kb.PropertyDefinition(code),
    numeric_value DECIMAL(14,4) NOT NULL CHECK(numeric_value>0),
    conditions NVARCHAR(500) NOT NULL,source_kind NVARCHAR(80) NOT NULL,source_url NVARCHAR(500) NOT NULL,
    PRIMARY KEY(id_product,property_code));
GO
