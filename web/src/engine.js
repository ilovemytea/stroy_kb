// Browser implementation of search/engine.py and expert.py.
// The inverted index and all knowledge are generated from the Python sources.
export const normalize = text => String(text).toLowerCase().replaceAll('ё', 'е');
const tokenRE = /[0-9a-zа-яё]+(?:[-.,x×][0-9a-zа-яё]+)*/gi;
export const tokenize = text => normalize(text).match(tokenRE) || [];
export const escapeHTML = text => String(text ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#x27;'}[c]));
const vowels = new Set('аеиоуыэюя');
let suffixes = {}, stemCache = new Map();

export function stem(input) {
  const word = normalize(input);
  if (stemCache.has(word)) return stemCache.get(word);
  if (/\d/.test(word) || word.length <= 2 || ![...word].some(c => vowels.has(c))) return word;
  let rv = [...word].findIndex(c => vowels.has(c)) + 1;
  function nextRegion(start) {
    for (let i = start + 1; i < word.length; i++) if (!vowels.has(word[i]) && vowels.has(word[i-1])) return i+1;
    return word.length;
  }
  const r2 = nextRegion(nextRegion(0));
  function strip(w, start, group) {
    const s = (suffixes[group] || []).find(s => w.endsWith(s) && w.length-s.length >= start);
    return s ? [w.slice(0, -s.length), true] : [w, false];
  }
  function pair(w, start, first, second) {
    let best = (suffixes[first] || []).find(s => w.endsWith(s) && w.length-s.length >= start &&
      w.length-s.length-1 >= start && 'ая'.includes(w[w.length-s.length-1]));
    const b = (suffixes[second] || []).find(s => w.endsWith(s) && w.length-s.length >= start);
    if (b && (!best || b.length > best.length)) best = b;
    return best ? [w.slice(0, -best.length), true] : [w, false];
  }
  let [w, ok] = pair(word, rv, 'PERFECTIVE_GERUND_1', 'PERFECTIVE_GERUND_2');
  if (!ok) {
    [w] = strip(w, rv, 'REFLEXIVE');
    let [w2, found] = strip(w, rv, 'ADJECTIVE');
    if (found) [w] = pair(w2, rv, 'PARTICIPLE_1', 'PARTICIPLE_2');
    else {
      [w2, found] = pair(w, rv, 'VERB_1', 'VERB_2');
      w = found ? w2 : strip(w, rv, 'NOUN')[0];
    }
  }
  if (w.endsWith('и') && w.length-1 >= rv) w = w.slice(0, -1);
  [w] = strip(w, r2, 'DERIVATIONAL');
  if (w.endsWith('нн') && w.length-2 >= rv) w = w.slice(0, -1);
  else {
    let [w2, found] = strip(w, rv, 'SUPERLATIVE');
    if (found) { w = w2; if (w.endsWith('нн')) w = w.slice(0,-1); }
    else if (w.endsWith('ь') && w.length-1 >= rv) w = w.slice(0,-1);
  }
  if (stemCache.size > 20000) stemCache.clear();
  stemCache.set(word, w);
  return w;
}

export function distance(a, b, limit = 3) {
  if (Math.abs(a.length-b.length) > limit) return limit+1;
  let prev2 = null, prev = Array.from({length:b.length+1}, (_,i) => i);
  for (let i=1; i<=a.length; i++) {
    const cur = [i]; let min = i;
    for (let j=1; j<=b.length; j++) {
      cur[j] = Math.min(prev[j]+1, cur[j-1]+1, prev[j-1]+Number(a[i-1] !== b[j-1]));
      if (prev2 && i>1 && j>1 && a[i-1]===b[j-2] && a[i-2]===b[j-1]) cur[j]=Math.min(cur[j], prev2[j-2]+1);
      min = Math.min(min, cur[j]);
    }
    if (min>limit) return limit+1;
    prev2=prev; prev=cur;
  }
  return prev.at(-1);
}
const bigrams = word => {const w=`^${word}$`; return new Set(Array.from({length:w.length-1},(_,i)=>w.slice(i,i+2)));};
const sentences = text => text.split(/\n/).flatMap(p=>p.trim().split(/(?<=[.!?])\s+(?=[А-ЯЁA-Z0-9«])/)).filter(Boolean);
const round = (v, digits=3) => Number(v.toFixed(digits));

export class KnowledgeIndex {
  constructor(data) {
    this.data=data; suffixes=data.suffixes; stemCache=new Map();
    this.docs=new Map(data.documents.map(d=>[d.id,d]));
    this.concepts=new Map(data.concepts.map(c=>[c.id,c]));
    this.stop=new Set(data.stopwords); this.questions=new Set(data.question_words);
    this.intentStems=new Set(data.intent_stems);
    this.intents=data.intents.map(([name,rx,rel,title])=>[name,new RegExp(rx.replace('сто\\b','сто(?=$|[^0-9a-zа-яё_])')),rel,title]);
    this.phrases=new Map(data.phrases.map(([words,cid])=>[words.join('\u0001'),cid]));
    this.maxPhrase=Math.max(...data.phrases.map(([words])=>words.length));
    this.out=new Map(); this.in=new Map(); this.grams=new Map();
    for(const r of data.relations) {
      for(const [map,key] of [[this.out,r.from],[this.in,r.to]]) {if(!map.has(key))map.set(key,[]);map.get(key).push(r);}
    }
    for(const word of Object.keys(data.vocabulary)) for(const bg of bigrams(word)) {
      if(!this.grams.has(bg))this.grams.set(bg,new Set()); this.grams.get(bg).add(word);
    }
  }
  content(text) { return tokenize(text).filter(w=>!this.stop.has(w)).map(stem); }
  correct(word) {
    const freq=this.data.vocabulary;
    if(word.length<4 || word in freq || /\d/.test(word)) return null;
    const limit=word.length<=6 ? 1:2, grams=bigrams(word), counts=new Map();
    for(const bg of grams) for(const cand of this.grams.get(bg)||[]) counts.set(cand,(counts.get(cand)||0)+1);
    let best=null, bestDistance=Infinity, bestFrequency=-1;
    for(const [cand,common] of counts) {
      if(common<Math.max(1,grams.size-2*limit-2))continue;
      const d=distance(word,cand,limit);
      if(d<=limit && (d<bestDistance || (d===bestDistance && freq[cand]>bestFrequency))) {
        best=cand;bestDistance=d;bestFrequency=freq[cand];
      }
    }
    return best;
  }
  parse(raw) {
    const all=tokenize(raw), words=all.slice(0,15);
    const q={raw,words,truncated:all.length>15,kind:words.length<=1?'слово':words.length<=4?'словосочетание':'предложение',
      corrected:null,terms:[],n_groups:0,concepts:[],intent:null,orig_stems:[]};
    let changed=false;
    const fixed=words.map(w=>{
      const c=this.stop.has(w)||this.questions.has(w)?null:this.correct(w);
      if(c && stem(c)!==stem(w)){changed=true;return c;}return w;
    });
    if(changed)q.corrected=fixed.join(' ');
    const intent=this.intents.find(([,rx])=>rx.test(fixed.join(' ')));
    if(intent)q.intent=[intent[0],intent[2],intent[3]];
    let content=fixed.filter(w=>!this.stop.has(w)&&!this.questions.has(w));
    if(!content.length)content=fixed.filter(w=>!this.stop.has(w));
    if(!content.length)content=fixed;
    const stems=content.map(stem),groups=[];
    stems.forEach((s,i)=>{
      const special=this.intentStems.has(s)&&q.intent&&stems.length>1;
      if(!special)groups.push(i);
      q.terms.push({stem:s,weight:special?.3:1,origin:special?'intent':'query',groups:special?[]:[i],label:content[i]});
    });
    q.n_groups=groups.length;q.orig_stems=groups.map(i=>stems[i]);
    for(let i=0;i<stems.length;) {
      let found=false;
      for(let len=Math.min(this.maxPhrase,stems.length-i);len>0;len--) {
        const cid=this.phrases.get(stems.slice(i,i+len).join('\u0001'));
        if(cid!==undefined) {
          if(!q.concepts.includes(cid)) {
            q.concepts.push(cid);
            const span=Array.from({length:len},(_,j)=>i+j), covered=span.filter(j=>groups.includes(j));
            this.expand(q,cid,covered.length?covered:span);
          }
          i+=len;found=true;break;
        }
      }
      if(!found)i++;
    }
    return q;
  }
  expand(q,cid,groups) {
    const c=this.concepts.get(cid),have=new Set(q.terms.map(t=>t.stem));
    const add=(name,weight,origin)=>{for(const s of this.content(name))if(!have.has(s)){
      q.terms.push({stem:s,weight,origin,groups,label:name});have.add(s);
    }};
    for(const name of [c.name,...c.synonyms])add(name,.7,'synonym');
    for(const r of this.in.get(cid)||[])if(r.type==='является'&&this.concepts.has(r.from))add(this.concepts.get(r.from).name,.35,'child');
  }
  bm25(term,id) {
    const fields=this.data.postings[term.stem]?.[id];if(!fields)return 0;
    let tf=0;const weights={title:3,tags:2,summary:1.5,body:1};
    for(const [f,cnt] of Object.entries(fields))tf+=weights[f]*cnt/(.25+.75*this.data.field_len[id][f]/this.data.avg_len[f]);
    return (this.data.idf[term.stem]||0)*tf/(1.2+tf);
  }
  proximity(id,stems) {
    const pos=this.data.positions[id]||{},events=[...new Set(stems)].flatMap(s=>(pos[s]||[]).map(p=>[p,s])).sort((a,b)=>a[0]-b[0]);
    const need=new Set(events.map(e=>e[1])).size;
    if(need<2)return 0;
    let best=Infinity,left=0,have=0;const counts=new Map();
    for(const [p,s]of events){counts.set(s,(counts.get(s)||0)+1);if(counts.get(s)===1)have++;
      while(have===need){best=Math.min(best,p-events[left][0]+1);const ls=events[left++][1];counts.set(ls,counts.get(ls)-1);if(!counts.get(ls))have--;}}
    return need/best;
  }
  search(raw,{type_id=null,category_id=null,limit=20}={}) {
    const start=performance.now(),q=this.parse(raw),candidates=new Set(),conceptWeights=new Map();
    for(const t of q.terms)for(const id of Object.keys(this.data.postings[t.stem]||{}))candidates.add(Number(id));
    for(const cid of q.concepts){for(const r of this.in.get(cid)||[])if(r.type==='является'&&!conceptWeights.has(r.from))conceptWeights.set(r.from,.5);conceptWeights.set(cid,1);}
    let scored=[];
    for(const id of candidates){const d=this.docs.get(id);
      if(type_id&&d.type_id!==type_id)continue;
      if(category_id&&!d.tags.some(t=>this.concepts.get(t.id)?.category_id===category_id))continue;
      let bm25=0;const covered=new Set(),matched=[];
      for(const t of q.terms){const s=this.bm25(t,id);if(s>0){bm25+=t.weight*s;t.groups.forEach(g=>covered.add(g));matched.push(t.label);}}
      if(bm25<=0)continue;
      const coverage=q.n_groups?covered.size/q.n_groups:1,prox=q.n_groups>1?this.proximity(id,q.orig_stems):0;
      const tag=Math.max(0,...d.tags.filter(t=>conceptWeights.has(t.id)).map(t=>t.relevance*conceptWeights.get(t.id)));
      const score=bm25*(.3+.7*coverage**2)*(1+.6*prox)*(1+.5*tag);
      scored.push({doc:d,score,explain:{bm25:round(bm25),coverage:round(coverage,2),proximity:round(prox,2),tag:round(tag,2),matched:[...new Set(matched)].sort()}});
    }
    scored.sort((a,b)=>b.score-a.score||a.doc.id-b.doc.id);
    if(scored.length)scored=scored.filter(s=>s.score>=scored[0].score*.08);
    const hl=new Set(q.terms.filter(t=>t.origin!=='intent').map(t=>t.stem));
    const answer=this.answer(q,scored,hl);
    const results=scored.slice(0,Math.max(1,Math.min(100,limit))).map(r=>({...r,score:round(r.score),title_html:this.highlight(r.doc.title,hl),snippet_html:this.snippet(r.doc,hl)}));
    return {query:q,results,total:scored.length,answer,took_ms:round(performance.now()-start,2)};
  }
  highlight(text,stems) {
    let result='',last=0;
    for(const match of normalize(text).matchAll(tokenRE))if(stems.has(stem(match[0]))&&!this.stop.has(match[0])){
      result+=escapeHTML(text.slice(last,match.index))+`<mark>${escapeHTML(text.slice(match.index,match.index+match[0].length))}</mark>`;last=match.index+match[0].length;
    }
    return result+escapeHTML(text.slice(last));
  }
  snippet(d,stems,max=260) {
    const parts=sentences((d.summary||'')+'\n'+(d.body||''));if(!parts.length)return '';
    const score=s=>new Set(tokenize(s).map(stem).filter(s=>stems.has(s))).size;
    let best=0;for(let i=1;i<parts.length;i++)if(score(parts[i])>score(parts[best]))best=i;
    let text=parts[best];if(text.length<max/2&&best+1<parts.length)text+=' '+parts[best+1];
    if(text.length>max){text=text.slice(0,max);text=text.slice(0,text.lastIndexOf(' ')>=0?text.lastIndexOf(' '):max)+'…';}
    return this.highlight(text,stems);
  }
  answer(q,scored,hl) {
    if(!scored.length||!q.n_groups)return null;
    const orig=new Set(q.orig_stems),want=new Set([...orig,...q.terms.filter(t=>t.origin==='synonym').map(t=>t.stem)]);let best=null;
    for(const r of scored.slice(0,3))for(const s of sentences(r.doc.body||'')){
      const ss=new Set(tokenize(s).map(stem)),cov=[...orig].filter(x=>ss.has(x)).length/orig.size;
      const syn=[...want].filter(x=>ss.has(x)).length,intent=q.intent&&[...ss].some(x=>this.intentStems.has(x))?1:0;
      const key=(cov+.15*syn+.3*intent)*(1+r.score/(scored[0].score*4));
      if(s.length>=40&&s.length<=400&&(!best||key>best.key))best={key,text:s,doc:r.doc};
    }
    return best&&best.key>=.6&&(q.kind!=='слово'||q.intent)?{text_html:this.highlight(best.text,hl),doc:best.doc}:null;
  }
  suggest(prefix,limit=8) {
    const words=tokenize(prefix);if(!words.length)return [];
    const head=words.slice(0,-1).map(stem),last=words.at(-1),seen=new Set(),out=[];
    const names=[...this.concepts.values()].flatMap(c=>[c.name,...c.synonyms]).sort();
    for(const text of [...names,...[...this.docs.values()].map(d=>d.title).sort()]){
      const toks=tokenize(text),ts=new Set(toks.map(stem));
      if(head.every(h=>ts.has(h))&&toks.some(t=>t.startsWith(last))&&!seen.has(normalize(text))){seen.add(normalize(text));out.push(text);if(out.length>=limit)break;}
    }return out;
  }
}

export function combineCF(a,b) {
  if(a>=0&&b>=0)return a+b*(1-a);
  if(a<0&&b<0)return a+b*(1+a);
  const denominator=1-Math.min(Math.abs(a),Math.abs(b));
  return denominator?(a+b)/denominator:0;
}
export function infer(rules,answers,threshold=.2) {
  const facts=Object.fromEntries(Object.entries(answers).filter(([,v])=>v)),fired=new Set(),derived={},trace=[],items=new Map();
  let changed=true;
  while(changed){changed=false;for(const r of rules){
    if(fired.has(r.code)||!r.conditions.every(([a,v])=>facts[a]===v))continue;
    fired.add(r.code);let result;
    if(r.then_kind==='fact'){
      if(facts[r.then_attribute]!==r.then_value){facts[r.then_attribute]=r.then_value;derived[r.then_attribute]=r.then_value;changed=true;}
      result=`${r.then_attribute} = ${r.then_value}`;
    } else {
      const prev=items.get(r.id_tag),cf=prev?combineCF(prev.cf,r.cf):r.cf;
      items.set(r.id_tag,{id_tag:r.id_tag,name:r.tag_name,cf,rules:[...(prev?.rules||[]),r]});result=`${r.tag_name}: CF ${cf.toFixed(3)}`;
    }
    trace.push({step:trace.length+1,rule:r,result});
  }}
  const values=[...items.values()].map(r=>({...r,cf:round(r.cf)}));
  return {facts,derived,trace,recommended:values.filter(r=>r.cf>=threshold).sort((a,b)=>b.cf-a.cf),rejected:values.filter(r=>r.cf<0).sort((a,b)=>a.cf-b.cf)};
}
