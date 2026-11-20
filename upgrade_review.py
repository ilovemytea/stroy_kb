"""Apply the optional model ONLY to a separately restored Review database."""
import json
from pathlib import Path
import config,db
from data import knowledge as K
from data.review_model import DEFINITIONS,property_records,rule_note
from web.build_public import catalog
from sync_knowledge import sync


def upgrade():
    if '_Review_' not in config.SQL_DATABASE:
        raise RuntimeError('Экспериментальная миграция разрешена только для отдельной базы с _Review_ в имени. Рабочая StroyMir_KB не изменена.')
    sync()
    with db.connect() as conn:
        c=conn.cursor()
        c.execute('''IF OBJECT_ID(N'kb.RuleProvenance',N'U') IS NULL
            CREATE TABLE kb.RuleProvenance(code NVARCHAR(20) NOT NULL PRIMARY KEY,notes NVARCHAR(MAX) NOT NULL CHECK(ISJSON(notes)=1));
            IF OBJECT_ID(N'kb.PropertyDefinition',N'U') IS NULL
            CREATE TABLE kb.PropertyDefinition(code NVARCHAR(40) NOT NULL PRIMARY KEY,name NVARCHAR(100) NOT NULL,unit NVARCHAR(40) NOT NULL);
            IF OBJECT_ID(N'kb.MaterialProperty',N'U') IS NULL
            CREATE TABLE kb.MaterialProperty(
                id_product INT NOT NULL REFERENCES dbo.Product(id_product),
                id_tag INT NOT NULL REFERENCES kb.Tag(id_tag),
                property_code NVARCHAR(40) NOT NULL REFERENCES kb.PropertyDefinition(code),
                numeric_value DECIMAL(14,4) NOT NULL CHECK(numeric_value>0),
                conditions NVARCHAR(500) NOT NULL,source_kind NVARCHAR(80) NOT NULL,source_url NVARCHAR(500) NOT NULL,
                PRIMARY KEY(id_product,property_code));''')
        for code,(name,unit) in DEFINITIONS.items():
            c.execute('IF NOT EXISTS(SELECT 1 FROM kb.PropertyDefinition WHERE code=?) INSERT kb.PropertyDefinition(code,name,unit) VALUES(?,?,?)',code,code,name,unit)
        for rule in K.RULES:
            code=rule[0];notes=json.dumps(rule_note(rule),ensure_ascii=False)
            c.execute('UPDATE kb.[Rule] SET explanation=? WHERE code=?',rule[-1],code)
            c.execute('UPDATE kb.RuleProvenance SET notes=? WHERE code=?',notes,code)
            if c.rowcount==0:c.execute('INSERT kb.RuleProvenance(code,notes) VALUES(?,?)',code,notes)
        for p in property_records(catalog(Path(__file__).parent)):
            c.execute('''IF NOT EXISTS(SELECT 1 FROM kb.MaterialProperty WHERE id_product=? AND property_code=?)
                INSERT kb.MaterialProperty(id_product,id_tag,property_code,numeric_value,conditions,source_kind,source_url)
                SELECT ?,id_tag,?,?,?,?,? FROM kb.Tag WHERE name=?''',
                p['product_id'],p['attribute'],p['product_id'],p['attribute'],p['value'],p['conditions'],p['source_kind'],p['source_url'],p['concept'])
    print('Review model applied to '+config.SQL_DATABASE+'; working database untouched.')


if __name__=='__main__':upgrade()
