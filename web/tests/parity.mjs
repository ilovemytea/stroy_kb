import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {KnowledgeIndex, infer, stem, distance, combineCF} from '../src/engine.js';

const data=JSON.parse(await readFile(new URL('../dist/knowledge.json',import.meta.url),'utf8'));
const fixtures=JSON.parse(await readFile(new URL('./parity.json',import.meta.url),'utf8'));
const ix=new KnowledgeIndex(data);
let failed=0;
for(const [word,expected] of Object.entries(fixtures.stems)){
  try{assert.equal(stem(word),expected,`stem ${word}`);}catch(e){console.error(e.message);failed++;}
}
for(const expected of fixtures.queries){
  const result=ix.search(expected.q);
  try{
    assert.deepEqual(result.results.map(r=>r.doc.id),expected.ids,`ranking: ${expected.q}`);
    assert.equal(result.query.corrected,expected.corrected,`correction: ${expected.q}`);
    assert.deepEqual(result.query.concepts,expected.concepts,`concepts: ${expected.q}`);
    assert.equal(result.answer?.text_html??null,expected.answer,`answer: ${expected.q}`);
  }catch(e){console.error(e.message);failed++;}
}
for(const expected of fixtures.expert){
  const r=infer(data.rules,expected.answers);
  try{
    for(const key of ['recommended','rejected']){
      assert.deepEqual(r[key].map(x=>x.id_tag),expected[key].map(x=>x[0]),`${key} IDs: ${JSON.stringify(expected.answers)}`);
      r[key].forEach((x,i)=>assert.ok(Math.abs(x.cf-expected[key][i][1])<=.00101,`${key} CF`));
    }
    assert.deepEqual(r.facts,expected.facts);
    assert.deepEqual(r.trace.map(x=>x.rule.code),expected.trace);
  }catch(e){console.error(e.message);failed++;}
}
assert.equal(ix.highlight('<b>бетон</b>',new Set([stem('бетон')])),'&lt;b&gt;<mark>бетон</mark>&lt;/b&gt;');
assert.equal(distance('бетон','бтеон'),1);
assert.equal(distance('','бетон'),4); // limit + 1, same early cutoff as Python
assert.ok(Math.abs(combineCF(.6,.5)-.8)<1e-10);
assert.ok(ix.suggest('газоб').includes('Газобетон'));
assert.ok(ix.search('бетон',{limit:-1}).results.length<=1);
assert.ok(ix.search('минвата',{type_id:1}).results.every(r=>r.doc.type_id===1));
assert.ok(ix.search('кирпич',{category_id:1}).results.every(r=>r.doc.tags.some(t=>ix.concepts.get(t.id).category_id===1)));
if(failed)throw new Error(`${failed} parity checks failed`);
console.log(`PASS: ${Object.keys(fixtures.stems).length} word forms, ${fixtures.queries.length} searches and ${fixtures.expert.length} expert scenarios match Python; safety and filter checks passed.`);
