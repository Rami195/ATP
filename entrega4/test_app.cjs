const fs=require('node:fs'),assert=require('node:assert/strict');
const {assign,predict,matchupProfiles,compareMatchup}=require('./web/modelo.js');
const data=JSON.parse(fs.readFileSync('dist/datos.json','utf8'));
const pred=JSON.parse(fs.readFileSync('dist/prediccion.json','utf8'));
for(const row of data.profiles){
  const r=assign(data.model,row.superficie,row);
  assert.equal(r.name,row.estilo);
  assert.ok(Math.abs(Math.min(...r.distances)-row.distancia)<1e-10);
}
let maxError=0;
for(const m of pred.matches){
  const values=side=>Object.fromEntries(data.model.columns.map(c=>[c,m[c+'_'+side]]));
  const a=assign(pred.model.styles,m.surface,values('a')),b=assign(pred.model.styles,m.surface,values('b'));
  assert.equal(a.index,m.cluster_a);assert.equal(b.index,m.cluster_b);
  for(const [name,reference] of [['Ranking + contexto','p_ranking'],['Ranking + contexto + estilos','p_estilos']]){
    const p=predict(pred.model.models[name],m.rank_a,m.rank_b,m.surface,m.best_of,a.index,b.index);
    const inv=predict(pred.model.models[name],m.rank_b,m.rank_a,m.surface,m.best_of,b.index,a.index);
    maxError=Math.max(maxError,Math.abs(p-m[reference]));
    assert.ok(Math.abs(p-m[reference])<1e-12);assert.ok(Math.abs(p+inv-1)<1e-12);
  }
}
assert.throws(()=>assign(data.model,'Carpet',data.profiles[0]));
assert.throws(()=>assign(data.model,'cemento',{...data.profiles[0],tasa_aces:NaN}));
assert.throws(()=>assign(data.model,'cemento',{...data.profiles[0],tasa_aces:1.01}));
assert.throws(()=>predict(pred.model.models[pred.model.selected],0,20,'cemento',3,0,1));
const rare=assign(data.model,'cemento',Object.fromEntries(data.model.columns.map(c=>[c,1])));
assert.ok(rare.outside.length&&rare.far);
// Los cambios de favorito explican toda la diferencia de accuracy: se recuentan desde los partidos.
const report=pred.report,flip=report.favorite_changes,right=(p,m)=>(p>=.5)===(m.gana_a===1);
const flips=pred.matches.filter(m=>(m.p_ranking>=.5)!==(m.p_estilos>=.5));
assert.equal(flips.length,flip.changed);
assert.equal(flips.filter(m=>right(m.p_ranking,m)).length,flip.ranking_right);
assert.equal(flips.filter(m=>right(m.p_estilos,m)).length,flip.styles_right);
assert.ok(Math.abs(flip.net_matches/pred.matches.length-report.comparison.delta_accuracy)<1e-12);
assert.equal(report.association_rank.length,9);
// La evidencia del modelo: lo que exige el «Cómo lo sabemos», recalculado desde los partidos.
assert.ok(report.candidates.every(c=>c.anios===4&&c.log_loss_desvio>0&&c.accuracy_desvio>0));
assert.ok(report.reliance.sin_ranking>report.reliance.completo);
const upsets=pred.matches.filter(m=>(m.rank_a<m.rank_b)!==(m.gana_a===1));
const upsetRow=report.mistakes.find(m=>m.categoria==='Ganó el peor rankeado');
assert.equal(upsets.length,upsetRow.n);
assert.ok(Math.abs(upsets.filter(m=>right(m.p_estilos,m)).length/upsets.length-upsetRow.accuracy)<1e-12);
// El embudo sólo baja, y termina en el universo del mapa.
const counts=data.stats.funnel.filter(f=>f.unidad==='perfiles').map(f=>f.filas);
assert.ok(counts.every((n,i)=>!i||n<=counts[i-1]));assert.equal(counts.at(-1),data.profiles.length);
assert.equal(data.stats.hypotheses.length,6);assert.ok(data.stats.hypotheses.some(h=>h.estado==='Se sostuvo')&&data.stats.hypotheses.some(h=>h.estado==='No se sostuvo'));
const catalog=JSON.parse(fs.readFileSync('dist/enfrentamientos.json','utf8'));
assert.equal(new Set(catalog.profiles.map(p=>p.season+'|'+p.surface+'|'+p.id)).size,catalog.profiles.length);
for(const p of catalog.profiles){
  assert.equal(assign(pred.model.styles,p.surface,p).name,p.estilo);
  assert.ok(p.n>=20&&p.cobertura_saque>=.8&&p.cobertura_resto>=.8);
  assert.ok(p.ranking_fecha<(p.season+1)+'-01-01');assert.ok(p.ultima_superficie<(p.season+1)+'-01-01');
}
for(const f of catalog.fixtures){
  const pool=matchupProfiles(catalog,f.season,f.surface),a=pool.find(p=>p.id===f.a),b=pool.find(p=>p.id===f.b);
  const r=compareMatchup(pred.model,a,b,f.surface,f.best_of),inv=compareMatchup(pred.model,b,a,f.surface,f.best_of);
  for(const [key,expected] of [['ranking','ranking'],['combined','combined'],['equalRanking','equal_ranking']]){
    assert.ok(Math.abs(r[key]-f[expected])<1e-12);assert.ok(Math.abs(r[key]+inv[key]-1)<1e-12);
  }
  if(a.cluster===b.cluster)assert.equal(r.equalRanking,.5);
}
// Los ejemplos del simulador muestran cada uno un caso distinto.
const tags=catalog.ejemplos.map(e=>{const pool=matchupProfiles(catalog,e.season,e.surface),r=compareMatchup(pred.model,pool.find(p=>p.id===e.a),pool.find(p=>p.id===e.b),e.surface,e.best_of);
  return [r.assignments[0].index===r.assignments[1].index,r.rankingFavorite!==r.combinedFavorite];});
assert.deepEqual(tags,[[true,false],[false,true],[false,false]]);
const clay=matchupProfiles(catalog,2019,'clay');
const nadal=clay.find(p=>p.nombre==='Rafael Nadal'),federer=clay.find(p=>p.nombre==='Roger Federer');
assert.ok(nadal&&federer);
const example=compareMatchup(pred.model,nadal,federer,'clay',3);
assert.equal(example.styleFavorite,null);assert.equal(example.rankingFavorite,0);
assert.throws(()=>compareMatchup(pred.model,nadal,nadal,'clay',3));
assert.throws(()=>compareMatchup(pred.model,nadal,federer,'grass',3));
const html=fs.readFileSync('dist/index.html','utf8');
assert.equal((html.match(/class="story"/g)||[]).length,3);
assert.ok(!/<details[^>]*\bopen\b/.test(html));
for(const file of ['app.js','modelo.js','style.css','prediccion.css','vendor/vega.min.js','vendor/vega-lite.min.js','vendor/vega-embed.min.js'])assert.ok(fs.statSync('dist/'+file).size>0);
console.log(JSON.stringify({descriptive_assignments:data.profiles.length,test_matches:pred.matches.length,max_probability_error:maxError,catalog_profiles:catalog.profiles.length,matchup_fixtures:catalog.fixtures.length,nadal_federer_2019:example,favorite_changes:flip,invalid_inputs:'rejected',swap_symmetry:'passed',rare_profile:'warning',story_sections:3}));
