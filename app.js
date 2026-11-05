'use strict';
const $=id=>document.getElementById(id);
const fmt=(n,d=0)=>Number(n).toLocaleString('es-AR',{minimumFractionDigits:d,maximumFractionDigits:d});
const pct=(n,d=1)=>fmt(n*100,d)+' %';
const views={};let data,predictive,matchupCatalog,filtered=[];
async function json(path){const r=await fetch(path);if(!r.ok)throw new Error('No se pudo cargar '+path);return r.json();}
const LOCALE={decimal:',',thousands:'.',grouping:[3],currency:['$','']};
// En pantallas angostas la leyenda va en columna y el título del eje se alinea para no cortarse.
function fitNarrow(spec){if(window.innerWidth<600){spec.config.legend.columns=1;spec.config.axisX={titleAnchor:'end'};}return spec;}
async function embed(name){const spec=fitNarrow(await json('charts/'+name+'.json'));const result=await vegaEmbed('#'+name,spec,{actions:false,renderer:'svg',formatLocale:LOCALE,logLevel:vega.Error});views[name]=result.view;return result.view;}
// Vega mide el contenedor al cargar y en cada resize: un gráfico oculto arranca con ancho 0.
const refit=()=>window.dispatchEvent(new Event('resize'));
function text(id,value){if($(id))$(id).textContent=value;}
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
    await updateDataset('comparacion','comparacion',data.model.columns.flatMap((c,j)=>[{rasgo:data.model.labels[c],z:r.z[j],serie:'Tu perfil'},{rasgo:data.model.labels[c],z:data.model.centers[r.index][j],serie:'Centro asignado'}]));
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
async function main(){
  [data,predictive,matchupCatalog]=await Promise.all([json('datos.json'),json('prediccion.json'),json('enfrentamientos.json')]);
  document.querySelectorAll('[data-stat]').forEach(e=>e.textContent=fmt(data.stats[e.dataset.stat],e.dataset.stat==='silhouette'?3:0));
  text('corr',fmt(data.stats.correlation,2));text('low-sil',fmt(data.stats.below025*100));text('pca-total',fmt((data.stats.pca[0]+data.stats.pca[1])*100,1));
  text('count-power',fmt(data.stats.counts['Sacadores de potencia']));text('count-return',fmt(data.stats.counts['Restadores sólidos']));text('count-fragile',fmt(data.stats.counts['Saque frágil']));
  text('surface-counts',Object.entries(data.stats.surface_counts).map(([s,n])=>fmt(n)+' en '+data.model.surfaces[s].toLocaleLowerCase()).join(', '));
  text('audit-note',data.stats.source_differences+' tasas de '+data.stats.profiles_source_differences+' perfiles difieren del Silver local. Los gráficos de estilos conservan la instantánea guardada en E3 (Z y escalador exacto). El análisis predictivo se reconstruye desde partidos.');
  const r=predictive.report;text('test-count',fmt(r.counts.test));text('test-coverage',pct(r.counts.test/r.counts.test_candidates));
  text('rank-acc',pct(r.metrics['Ranking + contexto'].accuracy,2));text('style-acc',pct(r.metrics['Ranking + contexto + estilos'].accuracy,2));
  text('hero-rank',pct(r.metrics['Ranking + contexto'].accuracy,2));text('hero-style',pct(r.metrics['Ranking + contexto + estilos'].accuracy,2));text('hero-matches',fmt(r.counts.test));
  const flips=r.favorite_changes;text('hero-net',fmt(Math.abs(flips.net_matches)));text('flip-count',fmt(flips.changed));text('flip-rank',fmt(flips.ranking_right));text('flip-style',fmt(flips.styles_right));
  text('win-return',pct(r.association.find(x=>x.surface==='Todas'&&x.estilo==='Restadores sólidos').winrate));text('best-return',pct(r.best_ranked_share['Restadores sólidos']));text('best-fragile',pct(r.best_ranked_share['Saque frágil']));
  text('delta-accuracy',fmt(r.comparison.delta_accuracy*100,2)+' puntos porcentuales');text('delta-ci',r.comparison.accuracy_ci95.map(x=>fmt(x*100,2)).join(' a ')+' puntos porcentuales');
  const all=r.association.filter(x=>x.surface==='Todas');text('win-summary',all.map(x=>x.estilo+': '+pct(x.winrate)+' ('+fmt(x.n)+' participaciones)').join(' · '));
  await Promise.all(['calidad','relacion','grupos','explorar','centros','distancias','comparacion','victorias','rendimiento','calibracion','ganador','enfrentamiento','rasgos-enfrentamiento'].map(embed));
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
