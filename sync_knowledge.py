"""Добавить знания и медиаданные в действующую SQL Server БД без пересоздания таблиц.

Существующие статьи, их ID, тексты редактора и просмотры сохраняются.
Все изменения выполняются одной транзакцией; повторный запуск безопасен.
"""
import json
from data import knowledge as K
from data.enrichment import guide_for
import db
import config

def sync():
    if '_Review_' not in config.SQL_DATABASE:
        raise RuntimeError('Эта экспериментальная копия обновляет только отдельную базу _Review_.')
    added = 0
    with db.connect() as conn:
        cur=conn.cursor()
        cur.execute("""IF OBJECT_ID(N'kb.ArticleGuide',N'U') IS NULL
            CREATE TABLE kb.ArticleGuide (
              id_material INT NOT NULL PRIMARY KEY,
              guide_json NVARCHAR(MAX) NOT NULL CHECK(ISJSON(guide_json)=1),
              CONSTRAINT FK_ArticleGuide_Material FOREIGN KEY(id_material)
                REFERENCES kb.Material(id_material) ON DELETE CASCADE)""")
        for name,cat,syn,definition in K.CONCEPTS:
            cur.execute("""IF NOT EXISTS(SELECT 1 FROM kb.Tag WHERE name=?)
                INSERT kb.Tag(id_category,name,synonyms,definition)
                SELECT id_category,?,?,? FROM kb.Category WHERE name=?""",
                name,name,'; '.join(syn),definition,cat)
        for src,typ,dst in K.RELATIONS:
            cur.execute("""INSERT kb.Relation(id_tag_from,id_tag_to,relation_type)
                SELECT a.id_tag,b.id_tag,? FROM kb.Tag a CROSS JOIN kb.Tag b
                WHERE a.name=? AND b.name=? AND NOT EXISTS(
                  SELECT 1 FROM kb.Relation r WHERE r.id_tag_from=a.id_tag
                  AND r.id_tag_to=b.id_tag AND r.relation_type=?)""",typ,src,dst,typ)
        for article in K.ARTICLES:
            title,typ,pub,country,date,tags,summary,body,video=article
            cur.execute('SELECT id_material FROM kb.Material WHERE title=?',title)
            row=cur.fetchone()
            if row:
                mid=row[0]
            else:
                cur.execute("""INSERT kb.Material(title,summary,body,publish_date,id_izdanie,id_type,id_country)
                    OUTPUT inserted.id_material
                    SELECT ?,?,?,?,p.id_izdanie,t.id_type,c.id_country
                    FROM kb.Publisher p CROSS JOIN kb.ContentType t CROSS JOIN kb.Country c
                    WHERE p.name=? AND t.name=? AND c.name=?""",title,summary,body,date,pub,typ,country)
                mid=cur.fetchone()[0]
                added+=1
                for tag,rel in tags:
                    cur.execute('INSERT kb.MaterialTag(id_material,id_tag,relevance) SELECT ?,id_tag,? FROM kb.Tag WHERE name=?',mid,rel,tag)
            guide=guide_for(article)
            encoded=json.dumps(guide,ensure_ascii=False)
            cur.execute('UPDATE kb.ArticleGuide SET guide_json=? WHERE id_material=?',encoded,mid)
            if cur.rowcount==0:
                cur.execute('INSERT kb.ArticleGuide(id_material,guide_json) VALUES(?,?)',mid,encoded)
            # Replace old search-results placeholders with real, attributed videos.
            if guide['videos']:
                v=guide['videos'][0]
                cur.execute("""UPDATE kb.VideoSource SET platform=?,url=?,duration_sec=NULL
                    WHERE id_material=? AND url LIKE '%youtube.com/results%'""",v['provider'],v['url'],mid)
                cur.execute("""IF NOT EXISTS(SELECT 1 FROM kb.VideoSource WHERE id_material=?)
                    INSERT kb.VideoSource(id_material,platform,url,duration_sec) VALUES(?,?,?,NULL)""",mid,mid,v['provider'],v['url'])
        cur.execute('EXEC kb.usp_RecalcRanks')
        print(f'Added {added} articles. Guide records updated: {len(K.ARTICLES)}. Existing articles preserved.')

if __name__=='__main__': sync()
