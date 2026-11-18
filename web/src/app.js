import {KnowledgeIndex, infer, tokenize, stem, escapeHTML as esc} from './engine.js';
import {mountGraph} from './graph.js';

const main=document.getElementById('content');
let data,ix,disposeGraph=null,routeAbort=null;
const examples=['минвата','гипсакартон','кирпич для фундамента','чем заменить газобетон',
  'какой утеплитель выбрать для бани чтобы он не горел',
  'какой бетон нужен для ленточного фундамента частного дома из газобетона'];
const APP_BASE = new URL('.', import.meta.url);
const href=(path,params={})=>APP_BASE.pathname+path.replace(/^\/+|\/+$/g,'')+(path==='/'?'':'/')+(Object.keys(params).length?'?'+new URLSearchParams(params):'');
function navigate(path,params={}) { history.pushState(null,'',href(path,params)); render(); }
function routePath(url) { return '/'+url.pathname.slice(APP_BASE.pathname.length).replace(/(?:^|\/)index\.html$/,'').replace(/^\/+|\/+$/g,''); }
const publishedBase = document.querySelector('meta[name="site-root"]')?.content;
if(publishedBase)for(const a of document.querySelectorAll('a[href]')) {
  const u=new URL(a.href),base=new URL(publishedBase);
  if(u.origin===base.origin&&u.pathname.startsWith(base.pathname))a.href=APP_BASE.pathname+u.pathname.slice(base.pathname.length)+u.search+u.hash;
}
const link=(path,label,params={},className='')=>`<a ${className?`class="${className}"`:''} href="${esc(href(path,params))}">${esc(label)}</a>`;
const conceptLink=c=>link('/concept/'+c.id,c.name,{},'chip tag');
const safeURL=value=>{try {const u=new URL(value);return ['https:','http:'].includes(u.protocol)?u.href:'#';}catch{return '#';}};
const storage={
  get(key,fallback){try{return JSON.parse(localStorage.getItem('dusovstroimir:'+key))??fallback;}catch{return fallback;}},
  set(key,value){try{localStorage.setItem('dusovstroimir:'+key,JSON.stringify(value));}catch{/* private browsing remains usable */}}
};
function toast(message){const t=document.getElementById('toast');t.textContent=message;t.hidden=false;setTimeout(()=>t.hidden=true,3000);}
function pageHead(title,description=''){document.title=title+' — dusovstroimir';return `<div class="page-head"><h1>${esc(title)}</h1>${description?`<p>${esc(description)}</p>`:''}</div>`;}
function searchbox(q='',label='Поиск по базе знаний'){
  return `<div class="searchbox"><form class="search-form" role="search"><input type="search" name="q" value="${esc(q)}" placeholder="Например, чем утеплить фасад" aria-label="${esc(label)}" autocomplete="off" maxlength="500"><button type="submit">Найти</button></form><ul class="suggest" aria-label="Подсказки"></ul><div class="counter" aria-live="polite">До 15 слов · можно задать вопрос целиком</div></div>`;
}
function statsTiles(){return `<div class="tiles">${[[data.documents.length,'статей'],[data.concepts.length,'понятий онтологии'],[data.relations.length,'связей'],[data.rules.length,'экспертных правил']].map(([n,l])=>`<div class="tile"><div class="n">${n}</div><div class="l">${l}</div></div>`).join('')}</div>`;}
function home(){
  document.title='dusovstroimir — база знаний по строительным материалам';
  return `<section class="hero"><p class="eyebrow">СтройМир · база знаний Дусова А.Э.</p><h1>Разберитесь в материалах.<br><span>Выберите подходящий.</span></h1><p class="intro">dusovstroimir — база знаний по строительным материалам. Найдите ответ на свой вопрос или подберите материал с объяснением выбора.</p>${searchbox()}<div class="examples">${examples.slice(0,4).map(q=>link('/search',q,{q},'chip')).join('')}</div><div class="quick-links">${link('/expert','Подобрать материал',{},'btn')}${link('/concepts','Открыть базу знаний',{},'btn secondary')}</div></section>${statsTiles()}<div class="section-head"><h2>С чего начать</h2>${link('/about','О проекте и сценарии проверки')}</div><div class="article-list">${data.documents.filter(d=>[3,5,10,13,24,32].includes(d.id)).map(articleCard).join('')}</div><div class="section-head"><h2>Разделы базы знаний</h2>${link('/concepts','Все понятия')}</div>${data.categories.map(cat=>`<section class="concept-section"><h3>${esc(cat.name)}</h3><div class="examples">${data.concepts.filter(c=>c.category_id===cat.id).slice(0,12).map(conceptLink).join('')}</div></section>`).join('')}`;
}
function articleCard(d){return `<article class="article-card"><small>${esc(d.type)}</small><h3>${link('/material/'+d.id,d.title)}</h3><p>${esc(d.summary)}</p></article>`;}
function conceptGroups(cid){
  const groups=new Map();
  const add=(label,id)=>{if(!groups.has(label))groups.set(label,[]);groups.get(label).push(ix.concepts.get(id));};
  for(const r of ix.out.get(cid)||[])add(data.labels[r.type]?.[0]||r.type,r.to);
  for(const r of ix.in.get(cid)||[])add(data.labels[r.type]?.[1]||r.type,r.from);
  return groups;
}
function conceptCard(c,intent=null){
  const groups=conceptGroups(c.id);let focus=null;
  for(const label of data.labels[intent?.[1]]||[])if(groups.has(label)){focus=label;break;}
  return `<div class="card"><div class="cat">${esc(c.category)}</div><h3>${link('/concept/'+c.id,c.name)}</h3><p>${esc(c.description)}</p>${c.synonyms.length?`<small>Также: ${esc(c.synonyms.join(', '))}</small>`:''}<dl>${[...groups].sort(([a],[b])=>Number(b===focus)-Number(a===focus)).map(([name,cs])=>`<dt class="${name===focus?'focus':''}">${esc(name===focus?intent[2]:name)}</dt><dd>${cs.slice(0,6).map(c=>link('/concept/'+c.id,c.name)).join(', ')}</dd>`).join('')}</dl></div>`;
}
function searchPage(params){
  const q=(params.get('q')||'').trim(),type=Number(params.get('type'))||null,cat=Number(params.get('cat'))||null;
  let html=pageHead('Поиск по базе знаний')+searchbox(q)+`<div class="filters"><label>Тип материала<select id="filter-type"><option value="">Все типы</option>${data.types.map(t=>`<option value="${t.id}" ${t.id===type?'selected':''}>${esc(t.name)}</option>`).join('')}</select></label><label>Раздел<select id="filter-cat"><option value="">Все разделы</option>${data.categories.map(c=>`<option value="${c.id}" ${c.id===cat?'selected':''}>${esc(c.name)}</option>`).join('')}</select></label></div>`;
  if(!q)return html+`<p class="muted">Введите название материала, свойство или вопрос.</p><div class="examples">${examples.map(q=>link('/search',q,{q},'chip')).join('')}</div>`;
  const res=ix.search(q,{type_id:type,category_id:cat}),pq=res.query;
  const recent=storage.get('recent',[]);recent.unshift({q,kind:pq.kind,words:pq.words.length,total:res.total,ms:res.took_ms,at:new Date().toISOString(),corrected:pq.corrected});storage.set('recent',recent.slice(0,100));
  html+=`<p class="qinfo result-count"><span class="kind">${esc(pq.kind)}</span> · ${pq.words.length} сл. · ${res.total} результатов · ${res.took_ms} мс</p>`;
  if(pq.truncated)html+='<p class="notice warn">Запрос длиннее 15 слов. Учтены первые 15 слов.</p>';
  if(pq.corrected)html+=`<p class="notice">Исправили опечатку: ${link('/search',pq.corrected,{q:pq.corrected})}</p>`;
  html+='<div class="results-layout"><section aria-label="Результаты поиска">';
  if(res.answer)html+=`<div class="answer"><div class="label">Быстрый ответ</div><p>${res.answer.text_html}</p><small>Источник: ${link('/material/'+res.answer.doc.id,res.answer.doc.title,{hl:q})}</small></div>`;
  html+=res.results.length?res.results.map(r=>`<article class="result"><div class="crumbs">${esc(r.doc.type)} · ${esc(r.doc.publisher)}</div><h3><a href="${esc(href('/material/'+r.doc.id,{hl:q}))}">${r.title_html}</a></h3><p>${r.snippet_html}</p><div class="tags">${r.doc.tags.slice(0,5).map(t=>conceptLink(ix.concepts.get(t.id))).join('')}</div><details class="why"><summary>Почему найдено</summary><p>BM25F: ${r.explain.bm25}; покрытие запроса: ${Math.round(r.explain.coverage*100)}%; близость: ${r.explain.proximity}; итоговый балл: ${r.score}.</p><p>Совпали: ${esc(r.explain.matched.join(', '))}.</p></details></article>`).join(''):`<div class="empty"><h2>Материалы не найдены</h2><p>Попробуйте другое название или уточните запрос. Также можно воспользоваться ${link('/expert','подбором материалов')}.</p></div>`;
  html+='</section><aside aria-label="Понятия запроса">'+pq.concepts.slice(0,2).map(id=>conceptCard(ix.concepts.get(id),pq.intent)).join('');
  const wanted=new Map(pq.terms.filter(t=>['query','synonym'].includes(t.origin)).map(t=>[t.stem,t.weight]));
  const products=data.products.map(p=>({p,score:[...new Set(ix.content(p.name+' '+p.category))].reduce((n,s)=>n+(wanted.get(s)||0),0)})).filter(r=>r.score>0).sort((a,b)=>b.score-a.score).slice(0,5);
  if(products.length)html+=`<div class="card"><div class="cat">Из учебного каталога</div><ul>${products.map(({p})=>`<li>${link('/catalog',p.name)}<br><small>${p.price} BYN/${esc(p.unit)}</small></li>`).join('')}</ul></div>`;
  html+=`<details class="card"><summary>Как понят запрос</summary><p>${pq.intent?'Намерение: '+esc(pq.intent[2]):'Поиск по словам и понятиям'}</p><ul>${pq.terms.map(t=>`<li>${esc(t.label)} · ${esc(t.origin)} · вес ${t.weight}</li>`).join('')}</ul></details></aside></div>`;
  return html;
}
function materialPage(id,params){
  const d=ix.docs.get(id);if(!d)return notFound();
  const views=storage.get('views',{});views[id]=(views[id]||0)+1;storage.set('views',views);
  const hl=params.get('hl')||'',terms=new Set(hl?ix.parse(hl).terms.filter(t=>t.origin!=='intent').map(t=>t.stem):[]);
  document.title=d.title+' — dusovstroimir';
  return `<div class="page-actions">${link('/search',hl?'К результатам поиска':'Поиск материалов',hl?{q:hl}:{},'btn secondary')}<button class="btn secondary" id="share-page">Скопировать ссылку</button></div><div class="two-col"><article class="material"><div class="meta"><span>${esc(d.type)}</span><span>${esc(d.publisher)}</span><span>${esc(d.date)}</span></div><h1>${esc(d.title)}</h1><p class="lead">${esc(d.summary)}</p>${d.body.split('\n').filter(p=>p.trim()).map(p=>`<p>${hl?ix.highlight(p,terms):esc(p)}</p>`).join('')}${d.video?`<p><a class="btn secondary" href="${esc(safeURL(d.video[1]))}" target="_blank" rel="noopener">Видео по теме в ${esc(d.video[0])}</a></p>`:''}</article><aside><div class="card"><div class="cat">Понятия статьи</div><div class="examples">${d.tags.map(t=>conceptLink(ix.concepts.get(t.id))).join('')}</div></div><p class="muted">Материал учебной базы знаний. Ответственные строительные решения сверяйте с проектом, актуальными нормами и документацией производителя.</p></aside></div>`;
}
function conceptPage(id){
  const c=ix.concepts.get(id);if(!c)return notFound();
  const ancestors=[],seen=new Set([id]);let frontier=[id];
  while(frontier.length){const next=[];for(const cid of frontier)for(const r of ix.out.get(cid)||[])if(r.type==='является'&&!seen.has(r.to)){seen.add(r.to);ancestors.push(ix.concepts.get(r.to));next.push(r.to);}frontier=next;}
  const inherited=[];for(const parent of ancestors)for(const r of ix.out.get(parent.id)||[])if(['обладает_свойством','применяется_для'].includes(r.type))inherited.push({parent,r,c:ix.concepts.get(r.to)});
  const materials=data.documents.filter(d=>d.tags.some(t=>t.id===id));
  return pageHead(c.name,c.category)+`<div class="two-col"><section><p class="definition">${esc(c.description)}</p>${c.synonyms.length?`<p><b>Другие названия:</b> ${esc(c.synonyms.join(', '))}</p>`:''}${ancestors.length?`<p><b>Принадлежит к:</b> ${ancestors.map(c=>link('/concept/'+c.id,c.name)).join(' · ')}</p>`:''}<div class="page-actions">${link('/search','Найти статьи',{q:c.name},'btn')}${link('/graph','Показать на графе',{focus:c.id},'btn secondary')}</div><h2>Связи понятия</h2>${[...conceptGroups(id)].map(([label,cs])=>`<section class="concept-section"><h3>${esc(label)}</h3><div class="examples">${cs.map(conceptLink).join('')}</div></section>`).join('')}${inherited.length?`<h2>Наследуемые свойства и применение</h2><ul>${inherited.map(({parent,r,c})=>`<li>${esc(data.labels[r.type][0])}: ${link('/concept/'+c.id,c.name)} <small>(от понятия ${esc(parent.name)})</small></li>`).join('')}</ul>`:''}</section><aside><h2>Статьи по теме</h2>${materials.map(d=>`<div class="card"><h3>${link('/material/'+d.id,d.title)}</h3><small>${esc(d.type)}</small></div>`).join('')||'<p class="muted">Сведения об этом понятии доступны в его определении и связях.</p>'}</aside></div>`;
}
function conceptsPage(params){
  const q=params.get('q')||'';
  return pageHead('Понятия базы знаний','Определения, синонимы и связи строительных материалов, свойств и технологий.')+`<form id="concept-filter" class="filters"><label>Найти понятие<input class="text-input" name="q" value="${esc(q)}" placeholder="Например, газобетон" maxlength="100"></label><button class="btn" type="submit">Найти</button></form>`+data.categories.map(cat=>{
    const cs=data.concepts.filter(c=>c.category_id===cat.id&&normalizeText(c.name+' '+c.synonyms.join(' ')).includes(normalizeText(q)));
    return cs.length?`<section class="concept-section"><h2>${esc(cat.name)} <small>· ${cs.length}</small></h2><div class="article-list">${cs.map(c=>`<article class="article-card"><h3>${link('/concept/'+c.id,c.name)}</h3><p>${esc(c.description)}</p>${c.synonyms.length?`<p><small>${esc(c.synonyms.join(', '))}</small></p>`:''}</article>`).join('')}</div></section>`:'';
  }).join('')+(q&&!data.concepts.some(c=>normalizeText(c.name+' '+c.synonyms.join(' ')).includes(normalizeText(q)))?'<p>Такого понятия нет. Попробуйте другое название.</p>':'');
}
const normalizeText=s=>s.toLowerCase().replaceAll('ё','е');
function expertPage(params){
  const answers=Object.fromEntries(data.questions.map(q=>[q.attribute,q.options_list.includes(params.get(q.attribute))?params.get(q.attribute):'']));
  return pageHead('Подбор строительных материалов','Ответьте на вопросы. Экспертная система применит правила и объяснит рекомендации.')+`<p>${link('/rules','Посмотреть все '+data.rules.length+' правила')}</p><div class="two-col"><form id="expert-form" class="qform">${data.questions.map(q=>`<fieldset class="qrow" data-cond="${esc(q.cond_attribute||'')}" data-values="${esc(q.cond_values_list.join('|'))}"><legend>${esc(q.question_text)}</legend>${q.options_list.map((opt,i)=>`<label><input type="radio" name="${esc(q.attribute)}" value="${esc(opt)}" ${answers[q.attribute]===opt?'checked':''} ${q.attribute==='element'?'required':''}>${esc(opt)}</label>`).join('')}</fieldset>`).join('')}<div class="question-actions"><button class="btn" type="submit">Подобрать материалы</button>${link('/expert','Сбросить',{},'btn secondary')}</div></form><aside id="expert-result" class="sticky-summary" aria-live="polite"></aside></div><section id="expert-trace"></section>`;
}
function showExpertResult(answers){
  const visible=data.questions.filter(q=>!q.cond_attribute||q.cond_values_list.includes(answers[q.cond_attribute]));
  const used=Object.fromEntries(visible.filter(q=>answers[q.attribute]).map(q=>[q.attribute,answers[q.attribute]]));
  const result=infer(data.rules,used),rec=(r,bad=false)=>`<div class="rec ${bad?'bad':''}">${link('/concept/'+r.id_tag,r.name)}<span class="cf">${Math.round(r.cf*100)} %</span>${bad?'':`<div class="cfbar" style="grid-column:1/-1"><i style="width:${Math.max(0,r.cf*100)}%"></i></div>`}<div class="why">${r.rules.map(rule=>esc(rule.code+': '+rule.explanation)).join('; ')}</div></div>`;
  document.getElementById('expert-result').innerHTML=`<div class="card"><h2>Рекомендуется</h2>${result.recommended.map(r=>rec(r)).join('')||'<p>Уточните ответы — данных для уверенной рекомендации недостаточно.</p>'}<p><small>Проценты отображают коэффициент уверенности правил, а не статистическую вероятность.</small></p></div>${result.rejected.length?`<div class="card"><h2>Не рекомендуется</h2>${result.rejected.map(r=>rec(r,true)).join('')}</div>`:''}`;
  const labels=Object.fromEntries(data.questions.map(q=>[q.attribute,q.question_text]));
  document.getElementById('expert-trace').innerHTML=`<h2>Объяснение вывода</h2><div class="card"><h3>Условия и выведенные факты</h3><p>${Object.entries(result.facts).map(([k,v])=>`<span class="chip">${esc(labels[k]||k)}: <b>${esc(v)}</b>${k in result.derived?' (выведено)':''}</span>`).join(' ')}</p></div><details><summary>Шаги вывода: ${result.trace.length}</summary><div class="table-wrap"><table class="grid trace"><thead><tr><th>Шаг</th><th>Правило</th><th>Условия</th><th>Результат</th></tr></thead><tbody>${result.trace.map(t=>`<tr><td>${t.step}</td><td>${esc(t.rule.code)}</td><td>${esc(t.rule.conditions.map(([a,v])=>a+' = '+v).join(' И '))}</td><td>${esc(t.result)}</td></tr>`).join('')}</tbody></table></div></details><div class="page-actions"><button id="share-page" class="btn secondary">Скопировать ссылку на результат</button></div>`;
}
function rulesPage(){return pageHead('База экспертных правил','Продукционные правила: если выполнены все условия, система выводит факт или меняет уверенность в рекомендации.')+`<p>${link('/expert','Перейти к подбору')}</p><div class="table-wrap"><table class="grid trace"><thead><tr><th>Правило</th><th>Если</th><th>То</th><th>CF</th><th>Объяснение</th></tr></thead><tbody>${data.rules.map(r=>`<tr><td>${esc(r.code)}</td><td>${esc(r.conditions.map(([a,v])=>a+' = '+v).join(' И '))}</td><td>${r.then_kind==='fact'?esc(r.then_attribute+' = '+r.then_value):link('/concept/'+r.id_tag,r.tag_name)}</td><td>${r.cf}</td><td>${esc(r.explanation)}</td></tr>`).join('')}</tbody></table></div>`;}
function graphPage(params){return pageHead('Онтология строительных материалов','Нажмите на понятие, чтобы открыть его определение и связи. Граф можно перемещать пальцем и масштабировать кнопками.')+`<div class="graph-tools"><label for="relfilter">Отношение</label><select id="relfilter"><option value="">Все отношения</option>${Object.keys(data.labels).map(t=>`<option value="${esc(t)}">${esc(t.replaceAll('_',' '))}</option>`).join('')}</select><button id="graph-plus" class="btn secondary" aria-label="Увеличить граф">+</button><button id="graph-minus" class="btn secondary" aria-label="Уменьшить граф">−</button><button id="graph-fit" class="btn secondary">Показать целиком</button></div><div id="legend" class="legend"></div><svg id="graph" role="img" aria-label="Семантическая сеть строительных материалов"></svg><p>${link('/concepts','Текстовый список всех понятий')}</p>`;}
function catalogPage(){return pageHead('Каталог строительных материалов','Учебные данные: производители, цены и характеристики из базы проекта. Цены приведены в BYN и не являются предложением продажи.')+`<div class="table-wrap"><table class="grid catalog-table"><thead><tr><th>Материал</th><th>Производитель</th><th>Цена, BYN</th><th>Плотность, кг/м³</th><th>Теплопроводность, Вт/(м·К)</th><th>Прочность, МПа</th></tr></thead><tbody>${data.products.map(p=>`<tr><td>${link('/search',p.name,{q:p.category})}<br><small>${esc(p.category)}</small></td><td>${esc(p.manufacturer)}<br><small>${esc(p.city)}</small></td><td>${p.price??'—'} / ${esc(p.unit||'')}</td><td>${p.density??'—'}</td><td>${p.thermal_conductivity??'—'}</td><td>${p.compressive_strength??'—'}</td></tr>`).join('')}</tbody></table></div>`;}
function statsPage(){
  const recent=storage.get('recent',[]);
  return pageHead('Исследование базы знаний','Проверьте время поиска на вашем устройстве и посмотрите объяснение ранжирования.')+statsTiles()+`<h2>Скорость поиска на этом устройстве</h2><p>По 20 повторов каждого контрольного запроса. Измеряется работа поискового алгоритма в браузере после загрузки базы.</p><button id="benchmark" class="btn">Запустить измерение</button><div id="benchmark-results" aria-live="polite"></div><h2>Последние запросы на этом устройстве</h2><p class="muted">Журнал хранится только в вашем браузере. Общая статистика других посетителей не собирается.</p>${recent.length?`<div class="table-wrap"><table class="grid"><thead><tr><th>Запрос</th><th>Тип</th><th>Найдено</th><th>Время, мс</th></tr></thead><tbody>${recent.slice(0,20).map(r=>`<tr><td>${link('/search',r.q,{q:r.q})}</td><td>${esc(r.kind)}</td><td>${r.total}</td><td>${r.ms}</td></tr>`).join('')}</tbody></table></div><button class="btn secondary" id="clear-history">Очистить журнал</button>`:'<p>Выполните поиск, чтобы увидеть его результаты в журнале.</p>'}`;
}
function aboutPage(){return pageHead('О проекте dusovstroimir')+`<div class="prose"><p>Курсовой проект Дусова А.Э. «Проектирование базы знаний по строительным материалам». Система помогает искать сведения о материалах, исследовать связи между понятиями и получать объяснимые рекомендации.</p><h2>Что можно проверить</h2><ol><li>${link('/search','Поиск по синониму «минвата»',{q:'минвата'})} — распознавание понятия «Минеральная вата».</li><li>${link('/search','Исправление запроса «гипсакартон»',{q:'гипсакартон'})} — поиск с исправлением опечатки.</li><li>${link('/search','Из чего делают силикатный кирпич',{q:'из чего делают силикатный кирпич'})} — быстрый ответ и связи с сырьём.</li><li>${link('/expert','Утепление фасада бани',{element:'Утепление',building:'Баня',place:'Фасад',budget:'Эконом'})} — рекомендации с трассой вывода.</li><li>${link('/graph','Граф онтологии')} — типы отношений и связанные понятия.</li><li>${link('/stats','Измерение скорости поиска')} — замер на текущем устройстве.</li></ol><h2>Публичная версия</h2><p>Все статьи, понятия, связи, правила и каталог собраны из исходной базы проекта. Поиск BM25F, русская нормализация и прямой экспертный вывод выполняются в браузере. После первой полной загрузки сайт доступен повторно без сети в браузерах с поддержкой офлайн-кеширования.</p><p>Основная серверная версия Flask и SQL Server, редактор знаний, SQL-схема и тесты доступны в <a href="https://github.com/ilovemytea/stroy_kb" target="_blank" rel="noopener">открытом репозитории проекта</a>. Изменения знаний публикуются автором из исходного проекта.</p><h2>Учебные ограничения</h2><p>Приведённые рекомендации помогают изучить предметную область. Для строительства нужны проектные расчёты, актуальные нормативы и документация конкретного производителя. Коэффициенты уверенности правил не являются статистической вероятностью.</p></div>`;}
function notFound(){return pageHead('Страница не найдена')+`<p>Проверьте ссылку или ${link('/','перейдите на главную')}.</p>`;}

function bindSearch(){
  for(const box of main.querySelectorAll('.searchbox')){
    const form=box.querySelector('form'),input=box.querySelector('input'),suggest=box.querySelector('.suggest'),counter=box.querySelector('.counter');
    form.addEventListener('submit',e=>{e.preventDefault();const q=input.value.trim();if(q)navigate('/search',{q});});
    input.addEventListener('input',()=>{
      const count=tokenize(input.value).length;counter.textContent=count?`${count} / 15 слов${count>15?' · учтём первые 15':''}`:'До 15 слов · можно задать вопрос целиком';
      const choices=ix.suggest(input.value);suggest.replaceChildren();
      for(const text of choices){const li=document.createElement('li'),button=document.createElement('button');button.type='button';button.textContent=text;button.addEventListener('click',()=>{navigate('/search',{q:text});});li.append(button);suggest.append(li);}
      suggest.style.display=choices.length?'block':'none';
    });
    input.addEventListener('keydown',e=>{if(e.key==='Escape')suggest.style.display='none';if(e.key==='ArrowDown'&&suggest.firstElementChild){e.preventDefault();suggest.querySelector('button')?.focus();}});
    box.addEventListener('focusout',()=>setTimeout(()=>{if(!box.contains(document.activeElement))suggest.style.display='none';},100));
  }
}
function bindExpert(params){
  const form=document.getElementById('expert-form');if(!form)return;
  const current=()=>Object.fromEntries(new FormData(form));
  const update=()=>{const answers=current();for(const row of form.querySelectorAll('[data-cond]')){
    const show=!row.dataset.cond||row.dataset.values.split('|').includes(answers[row.dataset.cond]);row.hidden=!show;
    row.querySelectorAll('input').forEach(input=>input.disabled=!show);
  }};
  form.addEventListener('change',update);update();
  form.addEventListener('submit',e=>{e.preventDefault();navigate('/expert',current());});
  if(params.get('element'))showExpertResult(current());
}
async function benchmark(button){
  button.disabled=true;button.textContent='Измеряем…';const output=document.getElementById('benchmark-results'),rows=[];
  for(const q of examples){const times=[];let res;for(let i=0;i<20;i++){const start=performance.now();res=ix.search(q);times.push(performance.now()-start);}times.sort((a,b)=>a-b);rows.push({q,total:res.total,median:(times[9]+times[10])/2,max:times.at(-1)});await new Promise(requestAnimationFrame);if(!button.isConnected)return;}
  output.innerHTML=`<div class="table-wrap"><table class="grid"><thead><tr><th>Запрос</th><th>Найдено</th><th>Медиана, мс</th><th>Максимум, мс</th></tr></thead><tbody>${rows.map(r=>`<tr><td>${esc(r.q)}</td><td>${r.total}</td><td>${r.median.toFixed(2)}</td><td>${r.max.toFixed(2)}</td></tr>`).join('')}</tbody></table></div>`;button.disabled=false;button.textContent='Измерить ещё раз';
}
function render(){
  if(!ix)return;if(location.hash==='#content'){main.focus();return;}
  disposeGraph?.();disposeGraph=null;routeAbort?.abort();routeAbort=new AbortController();
  if(location.hash.startsWith('#/')) {
    const legacy=new URL(location.hash.slice(1),'https://legacy.local');
    history.replaceState(null,'',href(legacy.pathname,Object.fromEntries(legacy.searchParams)));
  }
  const url=new URL(location.href),path=routePath(url),params=url.searchParams;
  let html;
  if(path==='/')html=home();else if(path==='/search')html=searchPage(params);
  else if(/^\/material\/\d+$/.test(path))html=materialPage(Number(path.split('/')[2]),params);
  else if(/^\/concept\/\d+$/.test(path))html=conceptPage(Number(path.split('/')[2]));
  else if(path==='/concepts')html=conceptsPage(params);else if(path==='/expert')html=expertPage(params);
  else if(path==='/rules')html=rulesPage();else if(path==='/graph')html=graphPage(params);
  else if(path==='/catalog')html=catalogPage();else if(path==='/stats')html=statsPage();
  else if(path==='/about')html=aboutPage();else html=notFound();
  main.innerHTML=html;main.setAttribute('aria-busy','false');
  const canonical = document.querySelector('link[rel="canonical"]');
  if(canonical && publishedBase)canonical.href=new URL(path.replace(/^\//,'')+(path==='/'?'':'/'),publishedBase).href;
  const robots=document.querySelector('meta[name="robots"]');
  if(robots)robots.content=['/search','/stats'].includes(path)?'noindex,follow':'index,follow,max-image-preview:large';
  document.getElementById('main-nav').classList.remove('open');document.getElementById('menu-toggle').setAttribute('aria-expanded','false');
  document.querySelectorAll('.nav a').forEach(a=>{const active=routePath(new URL(a.href))===path;a.classList.toggle('active',active);if(active)a.setAttribute('aria-current','page');else a.removeAttribute('aria-current');});
  bindSearch();bindExpert(params);
  if(path==='/graph')disposeGraph=mountGraph({nodes:data.concepts,links:data.relations.map(r=>({source:r.from,target:r.to,type:r.type}))},Number(params.get('focus'))||0);
  for(const [id,key] of [['filter-type','type'],['filter-cat','cat']])document.getElementById(id)?.addEventListener('change',e=>{const p=Object.fromEntries(params);if(e.target.value)p[key]=e.target.value;else delete p[key];navigate('/search',p);});
  document.getElementById('concept-filter')?.addEventListener('submit',e=>{e.preventDefault();navigate('/concepts',{q:new FormData(e.target).get('q')});});
  document.getElementById('benchmark')?.addEventListener('click',e=>benchmark(e.currentTarget));
  document.getElementById('clear-history')?.addEventListener('click',()=>{storage.set('recent',[]);render();});
  main.addEventListener('click',async e=>{if(e.target.id==='share-page'){try{await navigator.clipboard.writeText(location.href);toast('Ссылка скопирована');}catch{toast('Скопируйте адрес из строки браузера');}}},{signal:routeAbort.signal});
  window.scrollTo({top:0,behavior:'instant'});
  if(path==='/expert'&&params.get('element'))requestAnimationFrame(()=>document.getElementById('expert-result')?.scrollIntoView({block:'start'}));
}
document.getElementById('menu-toggle').addEventListener('click',e=>{const nav=document.getElementById('main-nav');nav.classList.toggle('open');e.currentTarget.setAttribute('aria-expanded',String(nav.classList.contains('open')));});
window.addEventListener('hashchange',render);
window.addEventListener('popstate',render);
document.addEventListener('click',e=>{
  const a=e.target.closest('a[href]');
  if(!a||a.target==='_blank'||a.hasAttribute('download')||e.ctrlKey||e.metaKey||e.shiftKey||e.altKey||e.button!==0||a.getAttribute('href').startsWith('#'))return;
  const u=new URL(a.href);
  if(u.origin!==location.origin||!u.pathname.startsWith(APP_BASE.pathname))return;
  const path=routePath(u);
  if(!/^\/(?:search|concepts|expert|graph|catalog|stats|about|rules|material\/\d+|concept\/\d+)?$/.test(path))return;
  e.preventDefault(); navigate(path,Object.fromEntries(u.searchParams));
});
async function init(){
  try{
    const response=await fetch(new URL('./knowledge.json',import.meta.url));if(!response.ok)throw new Error('knowledge unavailable');
    data=await response.json();ix=new KnowledgeIndex(data);render();
    if('serviceWorker' in navigator)navigator.serviceWorker.register(new URL('./sw.js',import.meta.url)).catch(()=>{});
  }catch(error){main.setAttribute('aria-busy','false');main.innerHTML=pageHead('Не удалось загрузить базу знаний')+'<p>Проверьте интернет-соединение и попробуйте ещё раз.</p><button class="btn" id="retry-load">Повторить загрузку</button>';document.getElementById('retry-load').addEventListener('click',init);console.error(error);}
}
init();
