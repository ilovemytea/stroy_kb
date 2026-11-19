(()=>{'use strict';const prefix='ctroimir-reader:';
const get=(key,fallback=[])=>{try{return JSON.parse(localStorage.getItem(prefix+key))??fallback;}catch{return fallback;}};
const set=(key,value)=>{try{localStorage.setItem(prefix+key,JSON.stringify(value));return true;}catch{return false;}};
const ids=key=>{const data=get(key);return Array.isArray(data)?data.filter(Number.isInteger):[];};
for(const button of document.querySelectorAll('[data-local-save]')){
const id=Number(button.dataset.localSave);const refresh=()=>{const saved=ids('saved').includes(id);button.textContent=saved?'В избранном':'Сохранить статью';button.setAttribute('aria-pressed',String(saved));};refresh();
button.addEventListener('click',()=>{const old=ids('saved'),next=old.includes(id)?old.filter(x=>x!==id):[id,...old];if(set('saved',next))refresh();else button.textContent='Сохранение недоступно: добавьте страницу в закладки';});
const read=ids('read');set('read',[id,...read.filter(x=>x!==id)].slice(0,12));
}
for(const input of document.querySelectorAll('[data-local-check]')){const key='check:'+input.dataset.localCheck,step=Number(input.dataset.step),old=get(key);input.checked=Array.isArray(old)&&old.includes(step);input.addEventListener('change',()=>{const raw=get(key),old=Array.isArray(raw)?raw:[];set(key,input.checked?[...new Set([...old,step])]:old.filter(x=>x!==step));});}
for(const button of document.querySelectorAll('[data-local-video]'))button.addEventListener('click',()=>{const id=button.dataset.localVideo;if(!/^[\w-]{11}$/.test(id))return;const frame=document.createElement('iframe');frame.src='https://www.youtube-nocookie.com/embed/'+id;frame.title='Обучающее видео';frame.allow='encrypted-media; picture-in-picture; fullscreen';frame.allowFullscreen=true;button.closest('.video-stage').replaceChildren(frame);});
const filter=mode=>{const chosen=ids(mode),cards=[...document.querySelectorAll('[data-local-card]')];for(const card of cards)card.hidden=mode!=='all'&&!chosen.includes(Number(card.dataset.localCard));const empty=document.getElementById('local-library-empty');if(empty)empty.hidden=cards.some(c=>!c.hidden);for(const b of document.querySelectorAll('[data-local-filter]'))b.setAttribute('aria-pressed',String(b.dataset.localFilter===mode));};
for(const b of document.querySelectorAll('[data-local-filter]'))b.addEventListener('click',()=>filter(b.dataset.localFilter));
if(document.querySelector('[data-local-card]'))filter(new URL(location.href).searchParams.get('saved')==='1'?'saved':'all');
})();
