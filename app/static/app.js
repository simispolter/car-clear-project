'use strict';
(() => {
 document.documentElement.classList.remove('no-js');
 const $=(s,r=document)=>r.querySelector(s), $$=(s,r=document)=>[...r.querySelectorAll(s)];
 const key='car-clear:comparison:v1';let selected=[];
 try {const saved=JSON.parse(localStorage.getItem(key)||'[]');if(Array.isArray(saved))selected=saved.filter(x=>x&&typeof x.id==='string'&&/^[a-f0-9]{16}(-[a-f0-9]{8})?$/.test(x.id)&&typeof x.name==='string').slice(0,3);}catch{}
 const compared=$$('[data-selected-id]');
 if(compared.length) selected=compared.map(el=>({id:el.dataset.selectedId,name:el.dataset.selectedName}));
 let toastTimer;
 function toast(message){const t=$('.toast');if(!t)return;t.textContent=message;t.hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>{t.hidden=true;},3500);}
 function sync(){
  try{localStorage.setItem(key,JSON.stringify(selected));}catch{}
  const href='/compare'+(selected.length?'?ids='+selected.map(c=>encodeURIComponent(c.id)).join(','):'');
  $$('[data-compare-link]').forEach(el=>el.href=href);$$('[data-compare-count]').forEach(el=>el.textContent=selected.length);
  const names=$('[data-selected-names]'),dock=$('[data-dock]');if(names)names.textContent=selected.map(c=>c.name).join(' / ');if(dock)dock.hidden=!selected.length;
  $$('[data-add]').forEach(b=>{const exists=selected.some(x=>x.id===b.dataset.add);b.setAttribute('aria-pressed',String(exists));if(b.classList.contains('compare-icon')){b.textContent=exists?'✓':'＋';b.setAttribute('aria-label',(exists?'הסרת ':'הוספת ')+b.dataset.name+(exists?' מההשוואה':' להשוואה'));}else b.textContent=exists?'✓ נוסף להשוואה':'＋ הוספה להשוואה';});
 }
 document.addEventListener('click',event=>{const b=event.target.closest('[data-add]');if(!b)return;const id=b.dataset.add,i=selected.findIndex(c=>c.id===id);if(i>=0)selected.splice(i,1);else{if(selected.length>=3){toast('אפשר להשוות עד שלושה רכבים. הסירו רכב כדי להוסיף אחר.');return;}selected.push({id,name:b.dataset.name});}sync();});
 $$('[data-remove]').forEach(b=>b.addEventListener('click',()=>{selected=selected.filter(c=>c.id!==b.dataset.remove);sync();location.assign('/compare'+(selected.length?'?ids='+selected.map(c=>c.id).join(','):''));}));
 $('[data-clear]')?.addEventListener('click',()=>{selected=[];sync();toast('הבחירה נוקתה');});
 $('[data-share]')?.addEventListener('click',async()=>{try{await navigator.clipboard.writeText(location.href);toast('הקישור הועתק');}catch{toast('אפשר להעתיק את כתובת העמוד משורת הכתובת');}});
 $('[data-print]')?.addEventListener('click',()=>window.print());
 $('[data-differences]')?.addEventListener('change',e=>{$$('[data-row]').forEach(r=>{const cells=$$('td',r).map(c=>c.textContent.trim().replace(/\s+/g,' '));r.hidden=e.target.checked&&cells.length>1&&new Set(cells).size===1;});});
 const filters=$('#filter-modal'),form=$('#filter-form'),filterHome=$('[data-filter-home]');
 $('[data-open-filters]')?.addEventListener('click',()=>{if(!filters||!form)return;$('[data-filter-slot]',filters).append(form);filters.showModal();});
 $('[data-close-filters]')?.addEventListener('click',()=>filters.close());
 filters?.addEventListener('close',()=>filterHome?.append(form));
 filters?.addEventListener('click',e=>{if(e.target===filters){const r=filters.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)filters.close();}});
 matchMedia('(min-width:821px)').addEventListener('change',e=>{if(e.matches&&filters?.open)filters.close();});
 const photo=$('#photo-modal');$('[data-open-photo]')?.addEventListener('click',()=>photo?.showModal());$('[data-close-photo]')?.addEventListener('click',()=>photo?.close());
 if('IntersectionObserver' in window){const links=$$('.product-tabs a'),observer=new IntersectionObserver(entries=>{entries.forEach(entry=>{if(entry.isIntersecting){links.forEach(a=>a.classList.toggle('active',a.hash==='#'+entry.target.id));}});},{rootMargin:'-140px 0px -55% 0px',threshold:0});links.forEach(a=>{const section=$(a.hash);if(section)observer.observe(section);});}
 const currency=n=>Math.round(n).toLocaleString('he-IL')+' ₪';
 function value(el,min,max){if(!el||el.value.trim()==='')return null;const n=Number(el.value);return Number.isFinite(n)&&n>=min&&n<=max?n:null;}
 $$('[data-ownership]').forEach(root=>{
  function calculate(){
   const mode=$('[data-energy-mode]',root).value,km=value($('[data-annual]',root),0,200000),liters=value($('[data-consumption]',root),.1,50),fuel=value($('[data-fuel-tariff]',root),.1,50),kwh=value($('[data-electric-consumption]',root),.1,100),tariff=value($('[data-electric-tariff]',root),.01,20),share=value($('[data-electric-share]',root),0,100);
   $('[data-fuel-fields]',root).hidden=mode==='electric';$('[data-electric-fields]',root).hidden=mode==='fuel';$('[data-plugin-fields]',root).hidden=mode!=='plugin';
   const fraction=mode==='electric'?1:mode==='fuel'?0:share===null?null:share/100;
   let energy=null;
   if(km!==null&&fraction!==null){if(km===0)energy=0;else if((fraction===1||liters!==null&&fuel!==null)&&(fraction===0||kwh!==null&&tariff!==null))energy=km/100/12*((1-fraction)*(liters||0)*(fuel||0)+fraction*(kwh||0)*(tariff||0));}
   let extras=0,invalidExtra=false;
   $$('[data-extra]',root).forEach(input=>{const limit=input.dataset.extra==='depreciation'?1000000:200000,n=value(input,0,limit),out=$('[data-'+input.dataset.extra+'-result]',root);if(input.value.trim()!==''&&n===null)invalidExtra=true;if(n!==null)extras+=n/12;out.textContent=n===null?'לא הוזן':currency(n/12);});
   $('[data-energy-result]',root).textContent=energy===null?'—':currency(energy);
   $('[data-ownership-total]',root).textContent=energy===null||invalidExtra?'—':currency(energy+extras);
   $('[data-calculation-message]',root).textContent=invalidExtra?'בדקו את ערכי ההוצאות השנתיות.':energy===null?'הזינו מרחק, צריכה ותעריף תקינים.':'לחודש, לפי ההוצאות שהזנתם בלבד.';
  }
  $$('input,select',root).forEach(i=>i.addEventListener('input',calculate));calculate();
 });
 sync();
})();
