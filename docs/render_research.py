"""Human-readable repository protocol and HTML fragment from saved measurements."""
import html
import json
from pathlib import Path

esc=lambda x:html.escape(str(x),quote=True)


def research_fragment(r):
    if not r:return '<p>Сохранённое исследование ещё не выполнено.</p>'
    counts=r['counts'];expert=r['expert'];graph=r['graph']
    out='<section class="research-results"><h2>Сохранённое исследование</h2>'
    out+=f'<p>Дата UTC: {esc(r["generated_at"])}. Корпус: {counts["articles"]} статей, {counts["concepts"]} понятий, {counts["rules"]} правил.</p>'
    out+='<h3>Качество поиска</h3><p>P@1 — доля запросов с релевантным первым результатом; MRR — средняя обратная позиция первого релевантного результата; R@5 — полнота первых пяти относительно разметки контрольного набора.</p>'
    out+='<div class="table-wrap"><table class="grid"><tr><th>Вариант</th><th>Запросы</th><th>P@1</th><th>MRR</th><th>R@5</th></tr>'
    for cfg in r['quality'].values():
        for kind,v in cfg['by_kind'].items():out+=f'<tr><td>{esc(cfg["label"])}</td><td>{esc(kind)} · {len(v["queries"])}</td><td>{v["P@1"]:.3f}</td><td>{v["MRR"]:.3f}</td><td>{v["R@5"]:.3f}</td></tr>'
    out+='</table></div><h3>Рост корпуса</h3><p>'+esc(r['scaling']['method'])+'</p><div class="table-wrap"><table class="grid"><tr><th>Статей</th><th>Индекс, медиана мс</th><th>Поиск, среднее медиан мс</th><th>Вывод, медиана мс</th></tr>'
    for s in r['scaling']['stages']:
        search=sum(q['median_ms'] for q in s['search'])/len(s['search'])
        out+=f'<tr><td>{s["articles"]}</td><td>{s["build"]["median_ms"]:.3f}</td><td>{search:.3f}</td><td>{s["inference"]["median_ms"]:.3f}</td></tr>'
    out+='</table></div>'
    out+=f'<h3>Контроль экспертного подбора</h3><p>{expert["passed"]} из {expert["total"]} сценариев соответствуют заранее заданным ожиданиям. '+esc(expert['method'])+'</p>'
    out+='<details><summary>Входные данные, ожидаемые и полученные рекомендации</summary><div class="table-wrap"><table class="grid"><tr><th>Сценарий / вход</th><th>Ожидаемый первый результат</th><th>Получен первым</th><th>Проверка</th></tr>'
    for c in expert['cases']:
        expected=', '.join(c['top']) or 'Воздержаться от рекомендации'
        actual=c['actual'][0] if c['actual'] else 'Нет рекомендации'
        out+=f'<tr><td>{esc(c["id"])}<br><small>{esc(json.dumps(c["answers"],ensure_ascii=False))}</small></td><td>{esc(expected)}</td><td>{esc(actual)}</td><td>{"Пройдено" if c["passed"] else "Расхождение"}</td></tr>'
    out+='</table></div></details>'
    out+=f'<h3>Аудит графа</h3><p>{graph["nodes"]} узлов, {graph["relations"]} типизированных связей. Среднее исходящих: {graph["mean_out_degree"]:.2f}; средняя суммарная степень: {graph["mean_total_degree"]:.2f}. Изолированных узлов: {len(graph["isolates"])}. Компонент связности без направления: {len(graph["weak_components"])}.</p><p>'+esc(graph['note'])+'</p>'
    out+='<h3>Границы выводов</h3><ul>'+''.join('<li>'+esc(x)+'</li>' for x in r['limitations'])+'</ul><p>Повторение: <code>python docs/research.py</code>. Снимок корпуса: <code>'+esc(r['dataset_sha256'])+'</code>.</p></section>'
    return out


def write_protocol(r):
    root=Path(__file__).resolve().parent
    lines=['# Протокол исследования экспериментальной версии','',f'Дата UTC: {r["generated_at"]}.', '', '## Воспроизведение','', '`python docs/research.py`', '',
        'Исходная разметка поиска задана в `docs/evaluate.py`, ожидаемые рекомендации — в `docs/expert_cases.json`. Результат `docs/research-results.json` содержит отдельные замеры, а не только средние.', '',
        '## Методика и ограничения','',r['scaling']['method'],'',*['- '+x for x in r['limitations']],'',
        'Коэффициенты CF не перенастраивались по контрольным результатам. Источники производителей относятся к техническому контексту; численные веса CF назначены автором модели.', '',
        'Стемминг в варианте `no_stem` отключён и при индексации, и при запросах. После каждого варианта исходная функция и её кэш восстанавливаются.', '',
        '## Результаты','',f'Корпус: {r["counts"]["articles"]} статей, {r["counts"]["concepts"]} понятий, {r["counts"]["relations"]} связей, {r["counts"]["rules"]} правил.','']
    for cfg in r['quality'].values():
        lines+=['### '+cfg['label'],'']
        for kind,v in cfg['by_kind'].items():lines.append(f'- {kind}: запросов {len(v["queries"])}, P@1={v["P@1"]:.3f}, MRR={v["MRR"]:.3f}, R@5={v["R@5"]:.3f}.')
        lines.append('')
    lines+=['### Масштабирование','']
    for s in r['scaling']['stages']:
        search=sum(q['median_ms'] for q in s['search'])/len(s['search'])
        lines.append(f'- {s["articles"]} статей: построение индекса {s["build"]["median_ms"]:.3f} мс; среднее медиан поиска {search:.3f} мс; медиана вывода {s["inference"]["median_ms"]:.3f} мс.')
    lines+=['','### Подбор и граф','',f'Подбор: {r["expert"]["passed"]}/{r["expert"]["total"]} проверок. Это соответствие учебным ожиданиям, а не независимая оценка строительной безопасности.', '',
        f'Изолированные узлы: {r["graph"]["isolates"]}. Точные дубли правил: {r["graph"]["rule_duplicates"]}.', '',
        '## Интерпретация','',
        'На этом небольшом корпусе отключение отдельных механизмов не обязано ухудшать каждую метрику. Выводы следует делать по группам запросов и ошибкам, не объявляя алгоритм универсально лучшим.', '',
        'Масштабирование измеряет алгоритм в памяти, а не задержку сети и не максимальное число одновременных пользователей. При фиксированных правилах время экспертного вывода не должно зависеть от числа статей.', '',
        '## Качество числовых данных','',
        'Числовые атрибуты перенесены из учебного каталога с единицами и указанием источника. Условия измерения в исходнике отсутствуют. Изделие «Минеральная вата фасадная 100 кг/м3» связано с сырьём плотностью 35 кг/м³; такие записи помечены как противоречивые и не включены в структурированные числовые факты. Значения не подменялись выдуманными паспортными данными.', '',
        '## Среда','',json.dumps(r['environment'],ensure_ascii=False), '', 'SHA-256 корпуса: `'+r['dataset_sha256']+'`.','']
    (root/'RESEARCH.md').write_text('\n'.join(lines),encoding='utf-8')
