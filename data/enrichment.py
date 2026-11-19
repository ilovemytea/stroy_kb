"""Структурированные объяснения, изображения и проверенные внешние видео."""
import json
from pathlib import Path

MEDIA = json.loads((Path(__file__).with_name('media_catalog.json')).read_text(encoding='utf-8'))

TOPICS = {
 'walls': {'name':'Стены и перегородки', 'description':'Кирпич, блоки, каркас и защита от шума.', 'tags':['Кирпич','Керамический кирпич','Силикатный кирпич','Газобетон','Пенобетон','Керамический блок','Перегородки','Звукоизоляция','Гипсокартон'], 'image':'blocks.jpg', 'diagram':'wall.svg',
 'caption':'Кладка из блоков: перевязка и ровность рядов. Схема условная, размеры и армирование задаёт проект.',
 'steps':['Определите назначение стены: несущая, перегородка или облицовка.','Сверьте геометрию, прочность и примыкания с проектом или альбомом системы.','Проверьте первый ряд, перевязку, швы и качество каждого этапа до отделки.'],
 'mistakes':['Выбирать материал только по цене за штуку, не считая стену целиком.','Менять крепёж, профили и элементы системы без проверки совместимости.'], 'videos':['knauf112','knauf-single'], 'sources':['https://www.knauf.ru/']},
 'insulation': {'name':'Утепление дома', 'description':'Вата, плиты, влажность и тепловые мосты.', 'tags':['Утеплитель','Минеральная вата','Пенополистирол','Экструдированный пенополистирол','Стекловата','Теплопроводность','Мостик холода','Утепление фасада'], 'image':'wool.jpg', 'diagram':'insulation.svg',
 'caption':'Непрерывный слой утепления уменьшает тепловые мосты. Фасадные слои и крепления выбирают как одну систему.',
 'steps':['Выберите материал, разрешённый для конкретной конструкции и нагрузки.','Проверьте непрерывность утепления на откосах, цоколе и примыканиях.','Защитите материал от намокания и проверьте крепление до закрытия слоя.'],
 'mistakes':['Сравнивать только плотность без назначения продукта.','Оставлять щели между плитами или закрывать мокрый утеплитель.'], 'videos':['facade','roof'], 'sources':['https://www.tn.ru/']},
 'roof': {'name':'Кровля и мансарда', 'description':'Покрытие, утепление, плёнки и вентиляция.', 'tags':['Кровля','Пароизоляция','Диффузионная мембрана','Металлочерепица','Профнастил','Мягкая кровля'], 'image':'roof.jpg', 'diagram':'roof.svg',
 'caption':'Условная схема утеплённой мансарды: пароизоляция внутри, утеплитель, наружная мембрана и вентилируемый зазор.',
 'steps':['Проверьте проектный состав кровли и назначение каждой плёнки.','Герметично выполните внутренние примыкания и проходки.','Сохраните предусмотренные вентиляционные зазоры и путь выхода воздуха.'],
 'mistakes':['Поменять местами пароизоляцию и диффузионную мембрану.','Перекрыть выход воздуха утеплителем или отделкой.'], 'videos':['roof'], 'sources':['https://www.tn.ru/']},
 'water': {'name':'Влага и фундамент', 'description':'Бетон, уход и непрерывная гидроизоляция.', 'tags':['Фундамент','Бетон','Железобетон','Гидроизоляция','Рулонная гидроизоляция','Уход за бетоном','Усадка'], 'image':'foundation.svg', 'diagram':'foundation.svg',
 'caption':'Защита подземной части: непрерывная гидроизоляция и предусмотренный проектом отвод воды. Схема не задаёт конструкцию фундамента.',
 'steps':['Определите источник воды и требования проекта к конструкции.','Подготовьте основание, примыкания и проходки до основного покрытия.','Проверьте сплошность защиты до обратной засыпки или закрытия отделкой.'],
 'mistakes':['Подменять гидроизоляцию обычным плиточным клеем.','Нагружать свежий бетон по календарю без оценки набранной прочности.'], 'videos':['foundation'], 'sources':['https://www.tn.ru/']},
 'finish': {'name':'Ремонт и отделка', 'description':'Ванная, плитка, грунтование и тёплый пол.', 'tags':['Плиточный клей','Керамическая плитка','Керамогранит','Обмазочная гидроизоляция','Гидроизоляционная лента','Грунтовка','Штукатурка','Шпатлёвка','Пол','Гипсовая штукатурка','Подготовка основания','Адгезия','Деформационный шов'], 'image':'finish.svg', 'diagram':'finish.svg',
 'caption':'Под плиткой: прочное основание, подготовка, гидроизоляция в мокрой зоне, совместимый клей и облицовка.',
 'steps':['Проверьте прочность, ровность и влажность основания.','Подберите совместимые грунт, выравнивание, защиту и финишное покрытие.','Соблюдайте толщину слоёв и выдержки из технических листов.'],
 'mistakes':['Пытаться укрепить осыпающуюся стену одним слоем грунта.','Путать время жизни раствора с открытым временем на стене.'], 'videos':['waterproof','prime','tile','grout'], 'sources':['https://www.ceresit.by/service/how-to/how-to-make-waterproofing.html','https://www.ceresit.by/service/how-to/how-to-prime.html']},
 'garden': {'name':'Дорожки и участок', 'description':'Плитка, щебень, разделение слоёв и вода.', 'tags':['Благоустройство','Тротуарная плитка','Геотекстиль','Щебень'], 'image':'paving.svg', 'diagram':'paving.svg',
 'caption':'Основание дорожки: покрытие, выравнивающий слой, уплотнённый щебень, разделение и грунт. Толщины зависят от нагрузки и грунта.',
 'steps':['Определите нагрузку и направление стока воды.','Разделите грунт и основание подходящим геотекстилем, если он предусмотрен.','Уплотняйте основание послойно и контролируйте уклон до укладки покрытия.'],
 'mistakes':['Уплотнять один толстый слой щебня вместо нескольких тонких.','Направлять сток к дому или на соседний участок.'], 'videos':[], 'sources':[]},
}

def topic_for(tags):
    names = set(t[0] if isinstance(t, (tuple,list)) else t.get('name','') for t in tags)
    # Specific construction purpose takes priority over generic properties.
    if names & {'Гидроизоляционная лента','Влажные помещения','Грунтовка','Плиточный клей'}: return 'finish'
    if names & {'Кровля','Диффузионная мембрана','Пароизоляция'}: return 'roof'
    if names & {'Геотекстиль','Тротуарная плитка'}: return 'garden'
    if names & {'Фундамент','Уход за бетоном'}: return 'water'
    if names & {'Кирпич','Керамический кирпич','Силикатный кирпич','Газобетон','Пенобетон','Керамический блок','Гипсокартон'}: return 'walls'
    if names & {'Утеплитель','Минеральная вата','Теплопроводность','Мостик холода'}: return 'insulation'
    return max(TOPICS, key=lambda k:len(names & set(TOPICS[k]['tags'])))

def guide_for(article):
    title,typ,pub,country,date,tags,summary,body,video = article
    topic=topic_for(tags)
    t=TOPICS[topic]
    photo=MEDIA['photos'][t['image']]
    if topic=='walls': photo=MEDIA['photos']['blocks.jpg'] if 'Газобетон' in title or 'газобетон' in title else MEDIA['photos']['bricks.jpg']
    if topic in {'water','garden'} or (topic=='finish') or ('полистирол' in title.lower()):
        photo={'file':t['diagram'],'alt':t['caption'],'author':'Редакция ctroimir','license':'Авторская учебная схема','license_url':'http://dusovstroimir.mooo.com/about/','source':'http://dusovstroimir.mooo.com/about/'}
    if 'Гипсокартон' in title or 'гипсокартон' in title: photo=MEDIA['photos']['drywall.jpg']
    if 'OSB' in title or 'Пиломатериал' in title or 'Брус' in title: photo=MEDIA['photos']['osb.jpg']
    lower=title.lower()
    video_keys=[]
    if 'гипсокартон' in lower or 'гкл' in lower: video_keys=['knauf112','knauf-single']
    elif topic=='roof': video_keys=['roof']
    elif topic=='insulation': video_keys=['facade']
    elif topic=='water' and 'гидроизоляц' in lower: video_keys=['foundation']
    if topic=='finish':
        if 'грунтов' in lower: video_keys=['prime']
        elif 'гидроизоляц' in lower: video_keys=['waterproof']
        elif 'укладка плитки' in lower: video_keys=['waterproof','tile','grout']
        elif 'плитк' in lower or 'кле' in lower or 'керамогранит' in lower: video_keys=['tile']
    paragraphs=[p.strip() for p in body.splitlines() if p.strip()]
    return {'topic':topic,'topic_name':t['name'],'minutes':max(2,round(len(body.split())/170)),
            'plain':summary,'takeaways': [p.split('. ')[0]+('.' if not p.split('. ')[0].endswith('.') else '') for p in paragraphs[:3]],
            'steps':t['steps'],'mistakes':t['mistakes'],
            'image':photo,'diagram':{'file':t['diagram'],'alt':t['caption'],'caption':t['caption']},
            'videos':[MEDIA['videos'][key] for key in video_keys],
            'sources':list(dict.fromkeys(t['sources']+[MEDIA['videos'][key]['source'] for key in video_keys]))}

def collections(articles):
    return [dict(id=key,name=t['name'],description=t['description'],image=MEDIA['photos'][t['image']],
                 articles=[i for i,a in enumerate(articles,1) if guide_for(a)['topic']==key]) for key,t in TOPICS.items()]
