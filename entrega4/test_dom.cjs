/* Integración de controles HTML en jsdom; no es una inspección visual.
   Los gráficos usan un adaptador de vista de pruebas. Su compilación real
   y los cálculos reales se verifican en test_charts.cjs y test_app.cjs. */
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
let JSDOM;try{({JSDOM}=require('jsdom'));}catch{({JSDOM}=require('../../.qa-entrega4/node_modules/jsdom'));}
const dom=new JSDOM(fs.readFileSync('dist/index.html','utf8'),{runScripts:'outside-only',pretendToBeVisual:true,url:'https://example.test/'});
const w=dom.window,errors=[],datasets=new Map();
w.console.error=(e)=>errors.push(String(e));
w.fetch=async url=>({ok:true,json:async()=>JSON.parse(fs.readFileSync(path.join('dist',url),'utf8'))});
w.vega={changeset:()=>({remove(){return this},insert(rows){this.rows=rows;return this}})};
w.vegaEmbed=async selector=>({view:{signal(){return this},change(name,changes){datasets.set(selector+'|'+name,changes.rows);return this},resize(){return this},addEventListener(){},runAsync:async()=>{}}});
w.eval(fs.readFileSync('web/modelo.js','utf8'));w.eval(fs.readFileSync('web/app.js','utf8'));
const el=id=>w.document.getElementById(id);
const settle=async()=>{for(let i=0;i<5;i++)await new Promise(resolve=>setImmediate(resolve));};
const change=async(id,value,event='change')=>{el(id).value=value;el(id).dispatchEvent(new w.Event(event,{bubbles:true}));await settle();};
(async()=>{
  await settle();assert.deepEqual(errors,[]);assert.equal(el('estado').textContent,'');
  assert.equal(el('duel-season').value,'2019');assert.equal(el('duel-surface').value,'clay');
  assert.equal(el('duel-name-a').textContent,'Rafael Nadal');assert.equal(el('duel-name-b').textContent,'Roger Federer');
  assert.equal(el('duel-style-a').textContent,'Restadores sólidos');assert.equal(el('duel-style-b').textContent,'Restadores sólidos');
  assert.equal(el('duel-favorite-styles').textContent,'Sin favorito claro');assert.equal(el('duel-output').hidden,false);
  // Portada, sección 2 y sección 3 toman sus números del informe, no del HTML.
  assert.equal(el('hero-fav').textContent,'66 %');assert.equal(el('hero-fav-power').textContent,'61,6 %');assert.equal(el('hero-fav-fragile').textContent,'56,4 %');assert.equal(el('flip-count').textContent,'112');assert.equal(el('flip-rank').textContent,'63');assert.equal(el('flip-style').textContent,'49');
  for(const id of ['funnel-body','validation-body','test-body','mistakes-body'])assert.ok(el(id).children.length>=3,id);
  assert.match(el('funnel-body').textContent,/77\.954 partidos/);assert.match(el('funnel-body').textContent,/1\.224 perfiles/);
  assert.match(el('hyp-h5').textContent,/r = −0,58/);
  assert.match(el('validation-body').textContent,/0,6289 ± 0,0126/);assert.match(el('rely-no-rank').textContent,/0,692/);
  assert.match(el('best-return').textContent,/53,8/);assert.match(el('best-fragile').textContent,/33,4/);assert.match(el('duel-conclusion').textContent,/112/);
  // Buscador: encuentra por cualquier parte del nombre, sin importar tildes ni mayúsculas.
  const search=el('duel-search-a'),list=el('duel-list-a'),found=()=>Array.from(list.querySelectorAll('[role=option]')).map(li=>li.firstChild.textContent);
  const fire=async(type,Event=w.Event,init={})=>{search.dispatchEvent(new Event(type,{bubbles:true,cancelable:true,...init}));await settle();};
  const type=async query=>{search.value=query;await fire('input');};
  assert.equal(search.value,'Rafael Nadal');assert.equal(el('duel-search-b').value,'Roger Federer');
  await fire('focus');assert.equal(search.value,'');assert.equal(list.hidden,false);assert.equal(search.getAttribute('aria-expanded'),'true');
  assert.ok(found().length>100);assert.ok(!found().includes('Roger Federer'),'el rival no se ofrece');
  await type('carreño busta');assert.deepEqual(found(),['Pablo Carreno Busta']);
  await type('BUSTA pab');assert.deepEqual(found(),['Pablo Carreno Busta']);
  await type('zzz');assert.deepEqual(found(),[]);assert.match(list.textContent,/Nadie coincide en polvo de ladrillo al cierre de 2019/);
  await fire('blur');assert.equal(search.value,'Rafael Nadal');assert.equal(list.hidden,true);
  await fire('focus');await type('carreno');await fire('keydown',w.KeyboardEvent,{key:'Enter'});
  assert.equal(el('duel-name-a').textContent,'Pablo Carreno Busta');assert.equal(search.value,'Pablo Carreno Busta');assert.equal(list.hidden,true);
  await fire('focus');await type('nad');await fire('keydown',w.KeyboardEvent,{key:'Escape'});
  assert.equal(search.value,'Pablo Carreno Busta');assert.equal(list.hidden,true);
  await fire('focus');await type('nad');list.querySelector('[role=option]').click();await settle();assert.equal(el('duel-name-a').textContent,'Rafael Nadal');
  await fire('focus');await fire('keydown',w.KeyboardEvent,{key:'ArrowUp'});assert.equal(list.lastChild.getAttribute('aria-selected'),'true');await fire('blur');
  // Los tres ejemplos llevan su etiqueta y cargan superficie, temporada y jugadores.
  const examples=Array.from(el('duel-examples').querySelectorAll('button'));
  assert.deepEqual(examples.map(b=>b.querySelector('small').textContent),['mismo estilo','los estilos cambian al favorito','estilos distintos, mismo favorito']);
  examples[1].click();await settle();
  assert.equal(el('duel-surface').value,'clay');assert.equal(el('duel-season').value,'2021');
  assert.equal(el('duel-favorite-ranking').textContent,'Daniil Medvedev');assert.equal(el('duel-favorite-combined').textContent,'Rafael Nadal');
  assert.equal(el('duel-favorite-styles').textContent,'Restadores sólidos');assert.match(el('duel-note-styles').textContent,/Rafael Nadal/);
  examples[0].click();await settle();
  assert.match(el('duel-meta-a').textContent,/475 partidos/);
  const rows=datasets.get('#enfrentamiento|enfrentamiento');assert.equal(rows.length,6);
  for(let i=0;i<6;i+=2)assert.ok(Math.abs(rows[i].probabilidad+rows[i+1].probabilidad-1)<1e-12);
  await change('duel-surface','grass');assert.match(el('duel-meta-a').textContent,/91 partidos/);
  assert.equal(el('duel-name-b').textContent,'Roger Federer');
  el('duel-swap').click();await settle();assert.equal(el('duel-name-a').textContent,'Roger Federer');
  await change('duel-player-b',el('duel-player-a').value);assert.equal(el('duel-output').hidden,true);assert.match(el('duel-error').textContent,/distintos/);
  await change('duel-player-b','N409');assert.equal(el('duel-output').hidden,false);assert.equal(el('duel-error').textContent,'');
  await change('duel-season','2025');assert.ok(!Array.from(el('duel-player-a').options).some(o=>o.textContent==='Roger Federer'));
  assert.equal(el('duel-output').hidden,false);assert.equal(el('duel-error').textContent,'');
  assert.notEqual(el('duel-player-a').value,el('duel-player-b').value);
  await change('duel-player-a',Array.from(el('duel-player-a').options).find(o=>o.value!==el('duel-player-b').value).value);
  await change('duel-format','5');assert.equal(el('duel-error').textContent,'');
  el('duel-form').dispatchEvent(new w.Event('submit',{bubbles:true,cancelable:true}));await settle();assert.equal(el('duel-output').hidden,false);
  await change('search','SIN_COINCIDENCIAS_123','input');assert.match(el('filtered-count').textContent,/No hay coincidencias/);assert.equal(el('profile-select').disabled,true);
  el('reset').click();await settle();assert.equal(el('profile-select').disabled,false);
  assert.deepEqual(errors,[]);
  console.log(JSON.stringify({dom:'passed',nadal_federer_default:true,surface_updates_rates:true,swap:true,same_player_rejected:true,season_filters_inactive:true,model_form_submit:true,exploration_reset:true,examples:true,player_search:true,report_numbers:true,graphics:'adapter mocked; real Vega checked in test_browser.cjs'}));
  dom.window.close();
})().catch(e=>{console.error(e);dom.window.close();process.exit(1)});
