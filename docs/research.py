"""Reproducible measurements; output includes raw timings and explicit limitations."""
import hashlib
import json
import platform
from pathlib import Path
import statistics
import sys
import time
from collections import Counter
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parent.parent
sys.path[:0]=[str(ROOT),str(ROOT/'tests'),str(ROOT/'docs')]
from data import knowledge as K
from memory_kb import build_memory_index, memory_rules
from search.engine import KnowledgeIndex
from expert import infer
from evaluate import CONFIGS,evaluate


def distribution(values):
    ordered=sorted(values)
    return dict(median_ms=round(statistics.median(values),4),p95_ms=round(ordered[min(len(ordered)-1,int(.95*len(ordered)))],4),samples_ms=[round(x,4) for x in values])


def measure(fn,repeats=30):
    for _ in range(3): fn()
    samples=[]
    for _ in range(repeats):
        start=time.perf_counter();fn();samples.append((time.perf_counter()-start)*1000)
    return distribution(samples)


def expert_evaluation():
    fixture=json.loads((ROOT/'docs/expert_cases.json').read_text(encoding='utf-8'))
    rules=memory_rules();rows=[]
    for case in fixture['cases']:
        result=infer(rules,case['answers'])
        names=[r['name'] for r in result['recommended']]
        top_ok=(not names) if case.get('abstain') else bool(names and names[0] in case['top'])
        forbidden_ok=not(set(names)&set(case.get('forbidden',[])))
        facts_ok=all(result['facts'].get(k)==v for k,v in case.get('facts',{}).items())
        rows.append(dict(**case,actual=names,top_ok=top_ok,forbidden_ok=forbidden_ok,facts_ok=facts_ok,passed=top_ok and forbidden_ok and facts_ok,timing=measure(lambda:infer(rules,case['answers']))))
    return dict(method=fixture['method'],total=len(rows),passed=sum(r['passed'] for r in rows),pass_rate=sum(r['passed'] for r in rows)/len(rows),cases=rows)


def topology():
    names={c[0] for c in K.CONCEPTS};degree=Counter();out=Counter();neighbors={n:set() for n in names};duplicates=[];seen=set()
    for a,t,b in K.RELATIONS:
        degree[a]+=1;degree[b]+=1;out[a]+=1;neighbors[a].add(b);neighbors[b].add(a)
        if (a,t,b) in seen: duplicates.append((a,t,b))
        seen.add((a,t,b))
    remaining=set(names);components=[]
    while remaining:
        todo=[min(remaining)];part=set()
        while todo:
            n=todo.pop()
            if n in part:continue
            part.add(n);todo.extend(neighbors[n]-part)
        remaining-=part;components.append(sorted(part))
    return dict(nodes=len(names),relations=len(K.RELATIONS),mean_out_degree=len(K.RELATIONS)/len(names),mean_total_degree=sum(degree.values())/len(names),
                isolates=sorted(n for n in names if degree[n]==0),leaves=sorted(n for n in names if degree[n]==1),
                weak_components=sorted(components,key=len,reverse=True),duplicate_relations=duplicates,
                rule_duplicates=[a[0]+' / '+b[0] for i,a in enumerate(K.RULES) for b in K.RULES[i+1:] if sorted(a[1])==sorted(b[1]) and a[2]==b[2]],
                note='Степень учитывает входящие и исходящие типизированные связи; малое число связей само по себе не является ошибкой. Компоненты считаются без направления.')


def scaling():
    full=build_memory_index();docs=list(full.docs.values());cs=list(full.concepts.values());rows=[]
    queries=['газобетон','минвата','гипсакартон','гидроизоляция фундамента','из чего делают силикатный кирпич','абырвалг']
    rules=memory_rules()
    for size in [20,37,len(docs)]:
        subset=docs[:size]
        make=lambda:KnowledgeIndex(subset,cs,full.relations)
        index=make()
        rows.append(dict(articles=size,concepts=len(cs),relations=len(full.relations),build=measure(make,10),
            search=[dict(query=q,results=index.search(q)['total'],**measure(lambda q=q:index.search(q))) for q in queries],
            inference=measure(lambda:infer(rules,{'element':'Фундамент'})),rules=len(rules)))
    return dict(method='Рост числа статей 20 → 37 → полный корпус; справочник понятий и набор правил фиксированы. Шесть одинаковых запросов, включая опечатку и отсутствие результатов. Это небольшая учебная база, а не экстраполяция на миллионы записей. Время вывода при фиксированных правилах измерено как контроль, его рост от числа статей не ожидается.',stages=rows)


def run():
    quality={}
    for key,label in CONFIGS:
        by_kind,stats=evaluate(key)
        quality[key]=dict(label=label,by_kind=by_kind,stats=stats)
    fingerprint=hashlib.sha256(json.dumps([K.CONCEPTS,K.RELATIONS,K.ARTICLES,K.RULES],ensure_ascii=False,sort_keys=True).encode()).hexdigest()
    result=dict(generated_at=datetime.now(timezone.utc).isoformat(),dataset_sha256=fingerprint,
        environment=dict(python=platform.python_version(),os=platform.system(),architecture=platform.machine(),processor=platform.processor()),
        counts=dict(articles=len(K.ARTICLES),concepts=len(K.CONCEPTS),relations=len(K.RELATIONS),rules=len(K.RULES)),
        quality=quality,scaling=scaling(),expert=expert_evaluation(),graph=topology(),
        limitations=['Контрольные запросы размечены автором проекта, а не независимой экспертной комиссией. Список релевантных статей ограничен разметкой набора.',
            'CF — авторские веса учебной модели, а не вероятность; успешный тест не доказывает пригодность строительного решения.',
            'Сравнение Python и JavaScript проверяет эквивалентность реализации отдельно от контрольных рекомендаций.',
            'Время зависит от среды и прогрева. Для воспроизведения сохранены параметры и отдельные замеры.'])
    (ROOT/'docs/research-results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    (ROOT/'docs/evaluation.json').write_text(json.dumps(quality,ensure_ascii=False,indent=2),encoding='utf-8')
    from render_research import write_protocol
    write_protocol(result)
    print(json.dumps(dict(counts=result['counts'],expert_passed=result['expert']['passed'],expert_total=result['expert']['total'],isolates=result['graph']['isolates']),ensure_ascii=False))
    return result


if __name__=='__main__':run()
