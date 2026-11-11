'use strict';
const $=id=>document.getElementById(id);
const fmt=(n,d=0)=>Number(n).toLocaleString('es-AR',{minimumFractionDigits:d,maximumFractionDigits:d}).replace('-','−');
const pct=(n,d=1)=>fmt(n*100,d)+' %';
const views={};let data,predictive,matchupCatalog,filtered=[];
async function json(path){const r=await fetch(path,{cache:'no-cache'});if(!r.ok)throw new Error('No se pudo cargar '+path);return r.json();}
const LOCALE={decimal:',',thousands:'.',grouping:[3],currency:['$','']};
// En pantallas angostas la leyenda va en columna y el título del eje se alinea para no cortarse.
function fitNarrow(spec){if(window.innerWidth<600){spec.config.legend.columns=1;spec.config.axis.labelLimit=150;spec.config.axisX={titleAnchor:'end'};}return spec;}
async function embed(name){const spec=fitNarrow(await json('charts/'+name+'.json'));const result=await vegaEmbed('#'+name,spec,{actions:false,renderer:'svg',formatLocale:LOCALE,logLevel:vega.Error});views[name]=result.view;return result.view;}
// Vega mide el contenedor al cargar y en cada resize: un gráfico oculto arranca con ancho 0.
const refit=()=>window.dispatchEvent(new Event('resize'));
function explainModel(){
  const m=predictive.model,chosen=m.models[m.selected],idx=name=>m.styles.names.indexOf(name);
  const R=idx('Restadores sólidos'),F=idx('Saque frágil'),S=idx('Sacadores de potencia');
  const p=(surface,bestOf,a,b,rankA=10,rankB=20)=>pct(ATPModel.predict(chosen,rankA,rankB,surface,bestOf,a,b),0);
  const raw=(surface,bestOf)=>ATPModel.predict(chosen,10,20,surface,bestOf,R,R);
  text('ex-rank',p('cemento',3,R,R));text('ex-base',p('cemento',3,R,R));text('ex-bo5',p('cemento',5,R,R));text('ex-grass-rank',p('grass',3,R,R));
  for(const [id,v] of [['bar-base',raw('cemento',3)],['bar-bo5',raw('cemento',5)],['bar-grass',raw('grass',3)]])if($(id))$(id).style.width=Math.max(4,Math.min(100,(v-.5)/.2*100))+'%';
  text('ex-clay-rf',p('clay',3,R,F,20,20));text('ex-clay-rs',p('clay',3,R,S,20,20));text('ex-grass-sr',p('grass',3,S,R,20,20));
  const all=(cls,v)=>document.querySelectorAll('.'+cls).forEach(e=>e.textContent=v),logit=q=>Math.log(q/(1-q)),L=Math.log(2),c=chosen.coef;
  const sc=(surface,bestOf,a,b,rA,rB)=>logit(ATPModel.predict(chosen,rA,rB,surface,bestOf,a,b));
  all('ex-rank-v',p('cemento',3,R,R));all('ex-grass-v',p('grass',3,R,R));all('ex-bo5-v',p('cemento',5,R,R));
  text('ex-coef',fmt(c[0],3));all('ex-coef-v',fmt(c[0],3));text('ex-score',fmt(sc('cemento',3,R,R,10,20),3));all('ex-score-v',fmt(sc('cemento',3,R,R,10,20),3));
  text('w-base',fmt(sc('cemento',3,R,R,10,20)/L,3));text('w-clay',fmt(sc('clay',3,R,R,10,20)/L,3));text('w-grass',fmt(sc('grass',3,R,R,10,20)/L,3));text('w-bo5',fmt(sc('cemento',5,R,R,10,20)/L,3));
  text('p-clay',p('clay',3,R,R));text('bo5-more',pct(sc('cemento',5,R,R,10,20)/sc('cemento',3,R,R,10,20)-1,0));
  const sign=v=>(v>=0?'+':'')+fmt(v,3);
  text('s-clay-rf',sign(sc('clay',3,R,F,20,20)));text('s-clay-rs',sign(sc('clay',3,R,S,20,20)));text('s-grass-sr',sign(sc('grass',3,S,R,20,20)));
  try{workedExample(m,chosen,R,S);}catch(e){console.error(e);const d=document.querySelector('.decide-example');if(d)d.hidden=true;}text('tr-c',fmt(chosen.C,chosen.C<1?2:0));
  all('ex-clay-rf-v',p('clay',3,R,F,20,20));all('ex-clay-rs-v',p('clay',3,R,S,20,20));all('ex-grass-sr-v',p('grass',3,S,R,20,20));
}
// Un partido completo, con las mismas cuentas que modelo.js: variables, pesos, suma y función logística.
function workedExample(m,chosen,a,b){
  const ex={rankA:5,rankB:30,surface:'clay',bestOf:5};
  const x=ATPModel.featureVector(ex.rankA,ex.rankB,ex.surface,ex.bestOf,a,b,true),c=chosen.coef;
  const SURF={cemento:'Cemento',clay:'Polvo de ladrillo',grass:'Césped'};
  const short={'Restadores sólidos':'Restador','Saque frágil':'Saque frágil','Sacadores de potencia':'Sacador'};
  const label=name=>{
    if(name==='log(rank_b/rank_a)')return 'Distancia de ranking';
    if(name==='log_ratio × clay')return 'Ranking × polvo de ladrillo';
    if(name==='log_ratio × grass')return 'Ranking × césped';
    if(name==='log_ratio × best_of5')return 'Ranking × 5 sets';
    const [s,i,j]=name.match(/^(\w+): estilo (\d) vs (\d)$/).slice(1);
    return SURF[s]+' · '+short[m.styles.names[+i]]+' vs '+short[m.styles.names[+j]];
  };
  const rows=x.map((v,i)=>({v,w:c[i],name:chosen.features[i]})).filter(r=>r.v!==0);
  const z=x.reduce((sum,v,i)=>sum+v*c[i],0),prob=ATPModel.predict(chosen,ex.rankA,ex.rankB,ex.surface,ex.bestOf,a,b);
  if(Math.abs(prob-1/(1+Math.exp(-z)))>1e-12)throw new Error('El ejemplo no coincide con el modelo.');
  const sign=v=>(v>=0?'+':'')+fmt(v,3);
  fillTable('wx-body',rows.map(r=>[label(r.name),fmt(r.v,3),sign(r.w),sign(r.v*r.w)]));
  const styleZ=rows.filter(r=>!r.name.startsWith('log')).reduce((s,r)=>s+r.v*r.w,0),noStyle=1/(1+Math.exp(-(z-styleZ)));
  const one={'Restadores sólidos':'restador sólido','Saque frágil':'de saque frágil','Sacadores de potencia':'sacador de potencia'};
  text('wx-match',SURF[ex.surface].toLocaleLowerCase()+', a '+ex.bestOf+' sets. Jugador A: n.º '+ex.rankA+', '+one[m.styles.names[a]]+'. Jugador B: n.º '+ex.rankB+', '+one[m.styles.names[b]]+'.');
  document.querySelectorAll('.wx-ra').forEach(e=>e.textContent=ex.rankA);document.querySelectorAll('.wx-rb').forEach(e=>e.textContent=ex.rankB);
  text('wx-d',fmt(Math.log(ex.rankB/ex.rankA),3));text('wx-z',sign(z));text('wx-zero',fmt(x.length-rows.length));
  document.querySelectorAll('.wx-z-v').forEach(e=>e.textContent=fmt(z,3));text('wx-exp',fmt(Math.exp(-z),3));
  text('wx-p',pct(prob,0));document.querySelectorAll('.wx-p-v').forEach(e=>e.textContent=pct(prob,0));text('wx-q',pct(1-prob,0));
  text('wx-style','Sin el aporte del cruce de estilos ('+sign(styleZ)+' puntos), A tendría '+pct(noStyle,0)+': el estilo le suma '+fmt((prob-noStyle)*100,0)+' puntos porcentuales. Casi todo el trabajo lo hace el ranking.');
}
function text(id,value){if($(id))$(id).textContent=value;}
function fillTable(id,rows){if(!$(id))return;$(id).replaceChildren(...rows.map(cells=>{const row=document.createElement('tr');for(const cell of cells){const td=document.createElement('td');td.textContent=cell;row.append(td);}return row;}));}
function option(value,label){const o=document.createElement('option');o.value=value;o.textContent=label;return o;}
function updateDataset(name,dataset,rows){return views[name].change(dataset,vega.changeset().remove(()=>true).insert(rows)).runAsync();}
function filterProfiles(){
  const surface=$('surface').value,style=$('style').value,min=+$('minimum').value,search=$('search').value.toLocaleLowerCase();
  text('minimum-output',min);
  filtered=data.profiles.filter(p=>(surface==='Todas'||p.superficie===surface)&&(style==='Todos'||p.estilo===style)&&p.partidos>=min&&p.nombre.toLocaleLowerCase().includes(search));
  views.explorar.signal('superficie',surface).signal('estiloFiltro',style).signal('minPartidos',min).signal('busqueda',$('search').value).runAsync();
  text('filtered-count',fmt(filtered.length)+' de '+fmt(data.profiles.length)+' perfiles'+(!filtered.length?' · No hay coincidencias. Probá reducir los filtros.':''));
  const select=$('profile-select'),old=select.value;select.replaceChildren();
  filtered.slice().sort((a,b)=>a.nombre.localeCompare(b.nombre)).forEach(p=>select.add(option(p.clave,p.nombre+' · '+p.superficie_nombre)));
  if(filtered.some(p=>p.clave===old))select.value=old;
  select.disabled=!filtered.length;$('use-profile').disabled=!filtered.length;showDetail();
}
function showDetail(){
  const p=data.profiles.find(p=>p.clave===$('profile-select').value),target=$('detail');target.replaceChildren();if(!p){target.textContent='No hay un perfil seleccionado.';return;}
  const title=document.createElement('strong');title.textContent='El modelo lo asigna a: '+p.estilo;target.append(title);
  for(const t of [fmt(p.partidos)+' partidos · '+pct(p.winrate)+' de victorias históricas','Silhouette individual: '+fmt(p.silhouette,3)+' · Distancia al centro: '+fmt(p.distancia,2)]){const e=document.createElement('p');e.textContent=t;target.append(e);}
}
function fillModel(values){for(const c of data.model.columns)$('rate-'+c).value=(values[c]*100).toFixed(6);}
function defaults(){fillModel(data.model.means[$('model-surface').value]);updateRangeHints();runModel();}
function updateRangeHints(){const s=$('model-surface').value;for(const c of data.model.columns){const [lo,hi]=data.model.ranges[s][c];text('range-'+c,'Observado: '+pct(lo)+'–'+pct(hi));}}
async function runModel(event){
  if(event)event.preventDefault();
  try{
    const values={};for(const c of data.model.columns){const input=$('rate-'+c);if(!input.value.trim())throw new Error('Completá todas las tasas.');values[c]=Number(input.value)/100;}
    const r=ATPModel.assign(data.model,$('model-surface').value,values);text('prediction',r.name);
    const nearest=r.z.map((z,j)=>({j,d:Math.abs(z-data.model.centers[r.index][j])})).sort((a,b)=>a.d-b.d).slice(0,2);
    text('explanation','Los rasgos más cercanos al centro asignado son '+nearest.map(v=>data.model.labels[data.model.columns[v.j]].toLocaleLowerCase()).join(' y ')+'. La decisión usa los siete rasgos.');
    const warnings=[];if(r.outside.length)warnings.push('Fuera del rango observado: '+r.outside.map(c=>data.model.labels[c]).join(', ')+'.');if(r.far)warnings.push('Combinación poco habitual: supera el percentil 95 de distancia al centro.');if(r.boundary)warnings.push('Perfil de frontera: dos centros están a distancias parecidas.');
    $('warning').hidden=!warnings.length;text('warning',warnings.join(' '));
    await updateDataset('distancias','distancias',r.distances.map((d,i)=>({estilo:data.model.names[i],distancia:d})));
    await updateDataset('comparacion','comparacion',data.model.columns.flatMap((c,j)=>[{rasgo:data.model.labels[c],z:r.z[j],serie:'Tu perfil',marca:'Tu perfil'},{rasgo:data.model.labels[c],z:data.model.centers[r.index][j],serie:'Centro asignado',marca:r.name}]));
  }catch(e){text('prediction','Revisá los valores');text('explanation','');text('warning',e.message);$('warning').hidden=false;await updateDataset('distancias','distancias',[]);await updateDataset('comparacion','comparacion',[]);}
}
function setupPredictor(){
  const select=$('match-select');
  predictive.matches.slice().sort((a,b)=>b.fecha.localeCompare(a.fecha)).forEach(m=>select.add(option(m.id_partido,m.fecha.slice(0,10)+' · '+m.nombre_a+' / '+m.nombre_b+' · '+data.model.surfaces[m.surface])));
  for(const side of ['a','b']){
    const holder=$('match-rates-'+side);
    for(const c of data.model.columns){const label=document.createElement('label');label.textContent=data.model.labels[c]+' (%)';const input=document.createElement('input');input.id='match-'+side+'-'+c;input.type='number';input.min=0;input.max=100;input.step='any';input.required=true;label.append(input);holder.append(label);}
  }
  select.addEventListener('change',loadMatch);$('match-form').addEventListener('submit',runMatch);loadMatch();
}
function loadMatch(){
  const m=predictive.matches.find(m=>m.id_partido===$('match-select').value);if(!m)return;
  $('match-surface').value=m.surface;$('best-of').value=m.best_of;
  for(const side of ['a','b']){text('name-'+side,m['nombre_'+side]);$('rank-'+side).value=m['rank_'+side];for(const c of data.model.columns)$('match-'+side+'-'+c).value=(m[c+'_'+side]*100).toFixed(10);}
  text('match-observed','Caso histórico: ganó '+(m.gana_a?m.nombre_a:m.nombre_b)+'. Los porcentajes cargados usan sólo fechas anteriores al torneo. Si editás los campos, el resultado pasa a ser un escenario hipotético.');
  runMatch();
}
async function runMatch(event){
  if(event)event.preventDefault();
  try{
    const surface=$('match-surface').value,best=+$('best-of').value,rankA=+$('rank-a').value,rankB=+$('rank-b').value,assignments=[];
    for(const side of ['a','b']){const values={};for(const c of data.model.columns){const v=$('match-'+side+'-'+c).value;if(!v.trim())throw new Error('Completá las siete tasas de cada jugador.');values[c]=Number(v)/100;}assignments.push(ATPModel.assign(predictive.model.styles,surface,values));}
    const name=predictive.model.selected,chosen=predictive.model.models[name],p=ATPModel.predict(chosen,rankA,rankB,surface,best,assignments[0].index,assignments[1].index);
    const baseline=ATPModel.predict(predictive.model.models['Ranking + contexto'],rankA,rankB,surface,best,assignments[0].index,assignments[1].index);
    text('winner-result',p===.5?'A y B tienen la misma probabilidad':(p>.5?'Jugador A':'Jugador B')+' es el favorito · '+pct(Math.max(p,1-p)));
    text('winner-description','A: '+assignments[0].name+' · B: '+assignments[1].name+'. Sólo ranking + contexto asignaría '+pct(baseline)+' a A. Modelo elegido en validación: '+name+'.');
    let warnings=[];assignments.forEach((r,i)=>{if(r.outside.length)warnings.push('Jugador '+(i?'B':'A')+': tasas fuera de los rangos de los perfiles usados para ajustar el clustering.');if(r.boundary)warnings.push('Jugador '+(i?'B':'A')+': estilo de frontera.');});
    const [lo,hi]=predictive.model.rank_range;if(rankA<lo||rankA>hi||rankB<lo||rankB>hi)warnings.push('Ranking fuera del rango observado en entrenamiento: '+lo+'–'+hi+'.');
    text('winner-warning',warnings.join(' '));$('winner-warning').hidden=!warnings.length;
    await updateDataset('ganador','ganador',[{jugador:'Jugador A',probabilidad:p},{jugador:'Jugador B',probabilidad:1-p}]);
  }catch(e){text('winner-result','Revisá los valores');text('winner-description',e.message);await updateDataset('ganador','ganador',[]);}
}
function setupMatchups(){
  const year=$('duel-season');
  matchupCatalog.years.forEach(y=>year.add(option(y,'Al cierre de '+y)));
  matchupCatalog.ejemplos.forEach(e=>{
    const button=document.createElement('button'),detail=document.createElement('small');
    button.type='button';button.textContent=lastName(e.nombre_a)+' vs. '+lastName(e.nombre_b)+' · '+data.model.surfaces[e.surface].toLocaleLowerCase()+' '+e.season;
    detail.textContent=exampleTag(e);button.append(detail);button.addEventListener('click',()=>loadExample(e));$('duel-examples').append(button);
  });
  year.value='2019';$('duel-surface').value='clay';
  year.addEventListener('change',refreshMatchups);$('duel-surface').addEventListener('change',refreshMatchups);
  for(const side of ['a','b']){$('duel-player-'+side).addEventListener('change',()=>runMatchup());setupPlayerSearch(side);}
  $('duel-format').addEventListener('change',()=>runMatchup());
  $('duel-swap').addEventListener('click',()=>{const a=$('duel-player-a').value;$('duel-player-a').value=$('duel-player-b').value;$('duel-player-b').value=a;runMatchup();});
  $('duel-form').addEventListener('submit',runMatchup);
  refreshMatchups(true);
}
function lastName(nombre){
  const w=nombre.split(' ');let i=w.length-1;
  while(i>1&&/^(de|del|van|von|da|di)$/i.test(w[i-1]))i--;
  return w.slice(i).join(' ');
}
// Busca por cualquier parte del nombre, sin importar tildes ni mayúsculas. Primero van
// los que empiezan como lo escrito y, entre ellos, los de mejor ranking.
const normalize=text=>text.normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase();
function searchPlayers(pool,query,rival){
  const tokens=normalize(query).split(/\s+/).filter(Boolean);
  return pool.filter(p=>p.id!==rival).map(p=>{
    const name=normalize(p.nombre),words=name.split(' ');
    return {p,found:tokens.every(t=>name.includes(t)),start:tokens.every(t=>words.some(w=>w.startsWith(t)))};
  }).filter(r=>r.found).sort((a,b)=>b.start-a.start||a.p.ranking-b.p.ranking).map(r=>r.p);
}
const whereLabel=()=>data.model.surfaces[$('duel-surface').value].toLocaleLowerCase()+' al cierre de '+$('duel-season').value;
// El <select> oculto guarda la elección; el campo de texto sólo ayuda a encontrarla.
function syncPlayerSearch(){
  for(const side of ['a','b']){const select=$('duel-player-'+side),input=$('duel-search-'+side);input.disabled=select.disabled;input.value=select.selectedOptions[0]?.textContent||'';}
}
function setupPlayerSearch(side){
  const input=$('duel-search-'+side),list=$('duel-list-'+side),select=$('duel-player-'+side),rival=$('duel-player-'+(side==='a'?'b':'a'));
  let results=[],active=-1;
  const close=()=>{list.hidden=true;input.setAttribute('aria-expanded','false');input.removeAttribute('aria-activedescendant');};
  const mark=index=>{
    active=index;Array.from(list.children).forEach((item,i)=>item.setAttribute('aria-selected',String(i===index)));
    const item=list.children[index];if(item){input.setAttribute('aria-activedescendant',item.id);item.scrollIntoView?.({block:'nearest'});}
  };
  const choose=p=>{select.value=p.id;close();runMatchup();input.select();};
  function show(query){
    results=searchPlayers(ATPModel.matchupProfiles(matchupCatalog,+$('duel-season').value,$('duel-surface').value),query,rival.value);
    list.replaceChildren(...results.map((p,i)=>{
      const item=document.createElement('li'),rank=document.createElement('small');
      item.id=list.id+'-'+i;item.setAttribute('role','option');item.textContent=p.nombre;rank.textContent='#'+fmt(p.ranking);item.append(rank);
      item.addEventListener('click',()=>choose(p));return item;
    }));
    if(!results.length){const empty=document.createElement('li');empty.className='duel-combo-empty';empty.textContent='Nadie coincide en '+whereLabel()+'. Probá otra superficie o año.';list.append(empty);}
    list.hidden=false;list.scrollTop=0;input.setAttribute('aria-expanded','true');mark(query.trim()&&results.length?0:-1);
  }
  const open=()=>{input.value='';show('');};
  list.addEventListener('mousedown',event=>event.preventDefault());
  input.addEventListener('focus',open);
  input.addEventListener('click',()=>{if(list.hidden)open();});
  input.addEventListener('input',()=>show(input.value));
  input.addEventListener('blur',()=>{close();syncPlayerSearch();});
  input.addEventListener('keydown',event=>{
    if(event.key==='ArrowDown'||event.key==='ArrowUp'){
      event.preventDefault();
      if(list.hidden)show('');
      else if(results.length){const step=event.key==='ArrowDown'?1:-1;mark((Math.max(active,step>0?-1:0)+step+results.length)%results.length);}
    }else if(event.key==='Enter'&&!list.hidden){event.preventDefault();if(results[active])choose(results[active]);}
    else if(event.key==='Tab'&&!list.hidden&&results[active])choose(results[active]);
    else if(event.key==='Escape'){event.preventDefault();close();syncPlayerSearch();input.select();}
  });
}
function exampleProfiles(e){const pool=ATPModel.matchupProfiles(matchupCatalog,e.season,e.surface);return [e.a,e.b].map(id=>pool.find(p=>p.id===id));}
function exampleTag(e){
  const [a,b]=exampleProfiles(e),r=ATPModel.compareMatchup(predictive.model,a,b,e.surface,e.best_of);
  return r.assignments[0].index===r.assignments[1].index?'mismo estilo':r.rankingFavorite!==r.combinedFavorite?'los estilos cambian al favorito':'estilos distintos, mismo favorito';
}
function loadExample(e){
  $('duel-season').value=e.season;$('duel-surface').value=e.surface;$('duel-format').value=e.best_of;
  refreshMatchups(false,[e.a,e.b]);
}
function refreshMatchups(initial=false,chosen=null){
  const pool=ATPModel.matchupProfiles(matchupCatalog,+$('duel-season').value,$('duel-surface').value);
  const selects=['a','b'].map(s=>$('duel-player-'+s)),previous=selects.map(s=>s.value);
  for(let i=0;i<2;i++){
    selects[i].replaceChildren();pool.forEach(p=>selects[i].add(option(p.id,p.nombre)));
    const preferred=initial===true?(i?'Roger Federer':'Rafael Nadal'):null,other=i?selects[0].value:previous[1];
    const candidate=pool.find(p=>chosen&&p.id===chosen[i])||pool.find(p=>p.nombre===preferred)||pool.find(p=>p.id===previous[i]&&p.id!==other)||pool.find(p=>p.id!==other);
    if(candidate)selects[i].value=candidate.id;
    selects[i].disabled=pool.length<2;
  }
  $('duel-submit').disabled=pool.length<2;$('duel-swap').disabled=pool.length<2;
  text('duel-available',fmt(pool.length)+' jugadores con historial suficiente en '+whereLabel()+'. Escribí cualquier parte del nombre.');
  runMatchup();
}
function matchupPlayerCard(side,p,r){
  text('duel-name-'+side,p.nombre);text('duel-style-'+side,r.name);
  const badge=$('duel-style-'+side);badge.className='duel-style '+({'Sacadores de potencia':'power','Restadores sólidos':'return','Saque frágil':'fragile'}[r.name]);
  text('duel-rank-'+side,'#'+fmt(p.ranking));
  text('duel-meta-'+side,fmt(p.n)+' partidos acumulados · cobertura saque '+pct(p.cobertura_saque)+', resto '+pct(p.cobertura_resto));
  text('duel-dates-'+side,'Ranking registrado: '+p.ranking_fecha+' · último torneo en la superficie: '+p.ultima_superficie);
}
async function runMatchup(event){
  if(event)event.preventDefault();
  syncPlayerSearch();
  try{
    const season=+$('duel-season').value,surface=$('duel-surface').value,bestOf=+$('duel-format').value;
    const pool=ATPModel.matchupProfiles(matchupCatalog,season,surface);
    const players=['a','b'].map(s=>pool.find(p=>p.id===$('duel-player-'+s).value));
    if(players.some(p=>!p))throw new Error('No hay dos perfiles disponibles con estos filtros.');
    const [a,b]=players;
    // Mostrar los perfiles aun si se seleccionó accidentalmente el mismo jugador.
    for(let i=0;i<2;i++)matchupPlayerCard(i?'b':'a',players[i],ATPModel.assign(predictive.model.styles,surface,players[i]));
    const r=ATPModel.compareMatchup(predictive.model,a,b,surface,bestOf);
    const names=players.map(p=>p.nombre),short=players.map(p=>lastName(p.nombre));
    text('duel-title',a.nombre+' vs. '+b.nombre);
    text('duel-reference','Escenario hipotético con perfiles acumulados hasta el 31/12/'+season+'. Los rankings corresponden a sus últimas apariciones registradas de ese año.');
    for(const [key,p,fav] of [['ranking',r.ranking,r.rankingFavorite],['styles',r.equalRanking,r.styleFavorite],['combined',r.combined,r.combinedFavorite]]){
      text('duel-favorite-'+key,fav===null?'Sin favorito claro':key==='styles'?r.assignments[fav].name:names[fav]);
      text('duel-prob-'+key,fav===null?'50 % / 50 %':pct(fav===0?p:1-p));
    }
    text('duel-note-styles',r.styleFavorite===null?'Con los rankings igualados.':'A favor de '+names[r.styleFavorite]+', con los rankings igualados.');
    if(r.styleFavorite===null){
      text('duel-style-reading',r.assignments[0].index===r.assignments[1].index?'Los dos perfiles pertenecen a «'+r.assignments[0].name+'». Con ranking igualado, el estilo no distingue a un favorito, aunque sus tasas sean diferentes.':'Con ranking igualado, este emparejamiento queda equilibrado.');
    }else{
      const favorite=r.styleFavorite; text('duel-style-reading','A igualdad de ranking, el emparejamiento se inclina por «'+r.assignments[favorite].name+'», el estilo de '+names[favorite]+'. Es una preferencia para este cruce y esta superficie; no una superioridad general.');
    }
    const delta=r.delta*100;
    const shift='Para '+short[0]+', sumar estilos cambia la probabilidad de '+pct(r.ranking)+' a '+pct(r.combined)+' ('+(delta>=0?'+':'')+fmt(delta,2)+' puntos porcentuales).';
    const change=r.rankingFavorite===r.combinedFavorite?'El favorito se mantiene.':'El favorito cambia al sumar estilos.';
    text('duel-comparison-reading',shift+' '+change);
    const flips=predictive.report.favorite_changes;
    text('duel-conclusion','¿El estilo aporta sobre el ranking? Este cruce muestra cómo cambia una estimación. La respuesta general sale de los '+fmt(predictive.report.counts.test)+' partidos del test: sumar estilos cambió al favorito del ranking en '+fmt(flips.changed)+' ('+pct(flips.share)+'), y en ésos acertó el ranking '+fmt(flips.ranking_right)+' veces y los estilos '+fmt(flips.styles_right)+'. No hubo una mejora clara: '+pct(predictive.report.metrics['Ranking + contexto'].accuracy,2)+' con ranking y '+pct(predictive.report.metrics['Ranking + contexto + estilos'].accuracy,2)+' al agregar estilos.');
    const warnings=[];
    r.assignments.forEach((assignment,i)=>{if(assignment.outside.length)warnings.push(short[i]+': algunos rasgos quedan fuera de los rangos usados para ajustar los estilos.');if(assignment.boundary)warnings.push(short[i]+': perfil cerca de la frontera de dos estilos.');if(+players[i].ultima_superficie.slice(0,4)<season)warnings.push(short[i]+': sin partidos registrados en esta superficie durante '+season+'; se usa el historial anterior.');});
    text('duel-warning',warnings.join(' '));$('duel-warning').hidden=!warnings.length;
    text('duel-error','');$('duel-output').hidden=false;
    const methods=[['Ranking + contexto',r.ranking],['Estilos · ranking igualado',r.equalRanking],['Ranking + estilos',r.combined]];
    await updateDataset('enfrentamiento','enfrentamiento',methods.flatMap(([metodo,p])=>[{metodo,jugador:a.nombre,lado:'A',probabilidad:p},{metodo,jugador:b.nombre,lado:'B',probabilidad:1-p}]));
    await updateDataset('rasgos-enfrentamiento','rasgos_enfrentamiento',players.flatMap((p,i)=>data.model.columns.map((c,j)=>({jugador:p.nombre,lado:i?'B':'A',rasgo:data.model.labels[c],z:r.assignments[i].z[j],tasa:p[c]}))));
    refit();
  }catch(error){text('duel-error',error.message);$('duel-output').hidden=true;}
}
function showEvidence(r){
  const hypothesis=id=>data.stats.hypotheses.find(h=>h.id===id),number=h=>h.medida+' = '+fmt(h.valor,2);
  fillTable('funnel-body',data.stats.funnel.map(f=>[f.paso,fmt(f.filas)+' '+f.unidad,f.motivo]));
  fillTable('hyp-body',data.stats.hypotheses.map(h=>[h.id,h.hipotesis,number(h),fmt(h.n),h.estado]));
  for(const id of ['h2','h5','h6'])text('hyp-'+id,number(hypothesis(id.toUpperCase())));
  const best=name=>r.candidates.filter(c=>c.modelo===name).sort((a,b)=>a.log_loss_validacion-b.log_loss_validacion)[0];
  const spread=(c,key,d,scale=1,unit='')=>fmt(c[key+'_media']*scale,d)+' ± '+fmt(c[key+'_desvio']*scale,d)+unit;
  const models=['Ranking + contexto','Ranking + contexto + estilos'].map(best),[base,styles]=models;
  fillTable('validation-body',[['Piso: gana el mejor rankeado','—',spread(r.validation_floor,'accuracy',2,100,' %')],...models.map(c=>[c.modelo,spread(c,'log_loss',4),spread(c,'accuracy',2,100,' %')])]);
  text('validation-note','Con estilos, el log-loss mejora apenas '+fmt(base.log_loss_media-styles.log_loss_media,4)+', pero eso es mucho menos de lo que varía de un año a otro ('+fmt(base.log_loss_desvio,4)+'): es ruido. Por eso no esperábamos una mejora en el test, y no la hubo.');
  explainModel();
  text('chosen-c',String(best(r.selected_by_validation).C).replace('.',','));
  fillTable('tuning-body',r.candidates.filter(c=>c.modelo===r.selected_by_validation).map(c=>[fmt(c.C,2)+(c.C===best(c.modelo).C?' · elegido':''),fmt(c.log_loss_validacion,5),spread(c,'log_loss',4)]));
  const metric=(label,m)=>[label,pct(m.accuracy,2),m.log_loss===null?'—':fmt(m.log_loss,4)];
  fillTable('test-body',[metric('Ranking + contexto',r.metrics['Ranking + contexto']),metric('Ranking + contexto + estilos',r.metrics['Ranking + contexto + estilos']),metric('Piso: gana el mejor rankeado',r.metrics['Gana el mejor rankeado']),metric('Probabilidad constante 50 %',r.metrics['Azar 50/50'])]);
  fillTable('mistakes-body',r.mistakes.map(m=>[m.grupo,m.categoria,fmt(m.n),pct(m.accuracy)]));
  text('balance',pct(r.counts.target_balance_test));text('floor-acc',pct(r.metrics['Gana el mejor rankeado'].accuracy,2));
  for(const [id,value] of [['tr-train',r.counts.train],['tr-val',r.counts.validation],['n-train',r.counts.train],['n-val',r.counts.validation],['n-test',r.counts.test],['n-valid',r.counts.valid_surface_non_walkover],['n-eligible',r.counts.eligible],['n-tournaments',r.comparison.tournaments],['n-resamples',r.comparison.resamples]])text(id,fmt(value));
  text('delta-loss',fmt(r.comparison.delta_log_loss,5));text('delta-loss-ci',r.comparison.log_loss_ci95.map(x=>fmt(x,5)).join(' a '));
  text('rely-full',fmt(r.reliance.completo,4));text('rely-no-rank',fmt(r.reliance.sin_ranking,4));text('rely-no-style',fmt(r.reliance.sin_estilos,4));
}
async function main(){
  [data,predictive,matchupCatalog]=await Promise.all([json('datos.json'),json('prediccion.json'),json('enfrentamientos.json')]);
  document.querySelectorAll('[data-stat]').forEach(e=>e.textContent=fmt(data.stats[e.dataset.stat],e.dataset.stat==='silhouette'?3:0));
  document.querySelectorAll('.corr').forEach(e=>e.textContent=fmt(data.stats.correlation,2));text('corr-raw',fmt(data.stats.correlation_raw,2));text('low-sil',fmt(data.stats.below025*100));text('pca-total',fmt((data.stats.pca[0]+data.stats.pca[1])*100,1));
  text('hero-sil',fmt(data.stats.silhouette,2));
  for(const [id,name] of [['hero-power','Sacadores de potencia'],['hero-return','Restadores sólidos'],['hero-fragile','Saque frágil']])text(id,fmt(data.stats.counts[name]));
  text('count-power',fmt(data.stats.counts['Sacadores de potencia']));text('count-return',fmt(data.stats.counts['Restadores sólidos']));text('count-fragile',fmt(data.stats.counts['Saque frágil']));
  text('surface-counts',Object.entries(data.stats.surface_counts).map(([s,n])=>fmt(n)+' en '+data.model.surfaces[s].toLocaleLowerCase()).join(', '));
  text('audit-note',data.stats.source_differences+' tasas de '+data.stats.profiles_source_differences+' perfiles difieren del Silver local. Los gráficos de estilos conservan la instantánea guardada en E3 (Z y escalador exacto). El análisis predictivo se reconstruye desde partidos.');
  const r=predictive.report;showEvidence(r);text('test-count',fmt(r.counts.test));text('test-coverage',pct(r.counts.test/r.counts.test_candidates));
  text('rank-acc',pct(r.metrics['Ranking + contexto'].accuracy,2));text('style-acc',pct(r.metrics['Ranking + contexto + estilos'].accuracy,2));
  text('hero-rank',pct(r.metrics['Ranking + contexto'].accuracy,1));text('hero-style',pct(r.metrics['Ranking + contexto + estilos'].accuracy,1));text('hero-matches',fmt(r.counts.test));
  const heroRate=c=>r.association_rank.find(x=>x.condicion===c&&x.estilo==='Restadores sólidos').winrate;text('hero-fav',pct(heroRate('Llega como mejor rankeado'),0));
  const favRate=e=>r.association_rank.find(x=>x.condicion==='Llega como mejor rankeado'&&x.estilo===e).winrate;text('hero-fav-power',pct(favRate('Sacadores de potencia'),1));text('hero-fav-fragile',pct(favRate('Saque frágil'),1));
  const flips=r.favorite_changes;text('flip-count',fmt(flips.changed));text('flip-rank',fmt(flips.ranking_right));text('flip-style',fmt(flips.styles_right));
  text('win-return',pct(r.association.find(x=>x.surface==='Todas'&&x.estilo==='Restadores sólidos').winrate));text('best-return',pct(r.best_ranked_share['Restadores sólidos']));text('best-fragile',pct(r.best_ranked_share['Saque frágil']));
  text('delta-accuracy',fmt(r.comparison.delta_accuracy*100,2)+' puntos porcentuales');text('delta-ci',r.comparison.accuracy_ci95.map(x=>fmt(x*100,2)).join(' a ')+' puntos porcentuales');
  const all=r.association.filter(x=>x.surface==='Todas');text('win-summary',all.map(x=>x.estilo+': '+pct(x.winrate)+' ('+fmt(x.n)+' participaciones)').join(' · '));
  await Promise.all(['calidad','relacion','grupos','explorar','centros','distancias','comparacion','victorias','rendimiento','calibracion','coeficientes','ganador','enfrentamiento','rasgos-enfrentamiento'].map(embed));
  // Los gráficos en detalles cerrados se redimensionan al abrirse.
  document.querySelectorAll('details').forEach(d=>d.addEventListener('toggle',()=>{if(d.open)requestAnimationFrame(refit);}));
  views.explorar.addEventListener('click',(_,item)=>{const clave=item&&item.datum&&item.datum.clave;if(clave&&filtered.some(p=>p.clave===clave)){$('profile-select').value=clave;showDetail();}});
  for(const id of ['surface','style','minimum','search'])$(id).addEventListener('input',filterProfiles);
  $('reset').addEventListener('click',()=>{$('surface').value='Todas';$('style').value='Todos';$('minimum').value=20;$('search').value='';filterProfiles();});
  $('profile-select').addEventListener('change',showDetail);
  for(const c of data.model.columns){const label=document.createElement('label');label.textContent=data.model.labels[c]+' (%)';const input=document.createElement('input');input.id='rate-'+c;input.type='number';input.min=0;input.max=100;input.step='any';input.required=true;const hint=document.createElement('small');hint.id='range-'+c;label.append(input,hint);$('model-inputs').append(label);}
  $('model-form').addEventListener('submit',runModel);$('model-surface').addEventListener('change',defaults);$('model-reset').addEventListener('click',defaults);
  $('use-profile').addEventListener('click',()=>{const p=data.profiles.find(p=>p.clave===$('profile-select').value);if(p){$('model-surface').value=p.superficie;fillModel(p);updateRangeHints();runModel();$('modelo').scrollIntoView({behavior:'smooth'});}});
  filterProfiles();defaults();setupPredictor();setupMatchups();text('estado','');
}
main().catch(error=>{text('estado','No se pudo iniciar la aplicación: '+error.message+'. Recargá la página o ejecutala mediante un servidor HTTP.');console.error(error);});
