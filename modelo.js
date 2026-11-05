/* Misma matemática en Node (pruebas) y en el navegador (app). */
(function(root){
  'use strict';
  function assign(model,surface,values){
    if(!model.means[surface]) throw new Error('Elegí una superficie conocida.');
    const z=model.columns.map(c=>{
      const v=values[c];
      if(typeof v!=='number'||!Number.isFinite(v)||v<0||v>1) throw new Error('Cada tasa debe ser un número entre 0 y 100 %.');
      return (v-model.means[surface][c])/model.stds[surface][c];
    });
    const distances=model.centers.map(center=>Math.sqrt(center.reduce((sum,v,j)=>sum+(v-z[j])**2,0)));
    const order=distances.map((v,i)=>({v,i})).sort((a,b)=>a.v-b.v||a.i-b.i);
    const index=order[0].i;
    const outside=model.ranges?model.columns.filter(c=>values[c]<model.ranges[surface][c][0]-1e-10||values[c]>model.ranges[surface][c][1]+1e-10):[];
    return {index,name:model.names[index],z,distances,outside,far:model.distance95?order[0].v>model.distance95:false,
      boundary:(order[1].v-order[0].v)/Math.max(order[1].v,1e-12)<.1};
  }
  function featureVector(rankA,rankB,surface,bestOf,clusterA,clusterB,expanded){
    if(!Number.isInteger(rankA)||!Number.isInteger(rankB)||rankA<1||rankB<1) throw new Error('Los rankings deben ser enteros positivos.');
    if(!['cemento','clay','grass'].includes(surface)||![3,5].includes(bestOf)) throw new Error('Superficie o formato desconocidos.');
    const d=Math.log(rankB/rankA), x=[d,d*(surface==='clay'),d*(surface==='grass'),d*(bestOf===5)];
    if(expanded){
      if(![0,1,2].includes(clusterA)||![0,1,2].includes(clusterB)) throw new Error('Estilos desconocidos.');
      for(const s of ['cemento','clay','grass'])for(const [i,j] of [[0,1],[0,2],[1,2]])x.push((s===surface)*((clusterA===i&&clusterB===j)-(clusterA===j&&clusterB===i)));
    }
    return x;
  }
  function predict(model,rankA,rankB,surface,bestOf,clusterA,clusterB){
    const x=featureVector(rankA,rankB,surface,bestOf,clusterA,clusterB,model.expanded);
    const score=x.reduce((sum,v,i)=>sum+v*model.coef[i],model.intercept);
    return 1/(1+Math.exp(-score));
  }
  function matchupProfiles(catalog,season,surface){
    return catalog.profiles.filter(p=>p.season===season&&p.surface===surface).slice().sort((a,b)=>a.nombre.localeCompare(b.nombre,'es'));
  }
  function compareMatchup(model,a,b,surface,bestOf,rankA=a.ranking,rankB=b.ranking){
    if(a.id===b.id)throw new Error('Elegí dos jugadores distintos.');
    if(a.surface!==surface||b.surface!==surface||a.season!==b.season)throw new Error('Los perfiles deben corresponder a la misma superficie y temporada.');
    const assignments=[assign(model.styles,surface,a),assign(model.styles,surface,b)];
    const clusters=assignments.map(r=>r.index);
    const base=model.models['Ranking + contexto'],expanded=model.models['Ranking + contexto + estilos'];
    const ranking=predict(base,rankA,rankB,surface,bestOf,...clusters);
    const combined=predict(expanded,rankA,rankB,surface,bestOf,...clusters);
    // Diagnóstico del mismo modelo ampliado: anulamos sólo la diferencia de ranking.
    // No es otro modelo entrenado ni la exactitud de un modelo de "sólo estilos".
    const equalRanking=predict(expanded,100,100,surface,bestOf,...clusters);
    const favorite=p=>Math.abs(p-.5)<1e-10?null:p>.5?0:1;
    return {assignments,ranking,combined,equalRanking,delta:combined-ranking,
      rankingFavorite:favorite(ranking),combinedFavorite:favorite(combined),styleFavorite:favorite(equalRanking)};
  }
  root.ATPModel={assign,predict,featureVector,matchupProfiles,compareMatchup};
  if(typeof module!=='undefined'&&module.exports)module.exports=root.ATPModel;
})(typeof globalThis!=='undefined'?globalThis:this);
