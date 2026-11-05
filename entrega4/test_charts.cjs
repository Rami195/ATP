/* Compila y ejecuta Vega sin navegador: valida gramática, datos y filtros. */
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const context=vm.createContext({console,setTimeout,clearTimeout,performance,structuredClone});
for(const file of ['vega.min.js','vega-lite.min.js'])vm.runInContext(fs.readFileSync('web/vendor/'+file,'utf8'),context);
const data=JSON.parse(fs.readFileSync('dist/datos.json','utf8'));
(async()=>{
  const checks=[];
  for(const name of fs.readdirSync('dist/charts').filter(x=>x.endsWith('.json'))){
    const spec=JSON.parse(fs.readFileSync('dist/charts/'+name,'utf8'));
    spec.width=800;
    const compiled=context.vegaLite.compile(spec).spec;
    const view=new context.vega.View(context.vega.parse(compiled),{renderer:'none'}).initialize();
    await view.runAsync();
    if(name==='explorar.json'){
      const transformed=compiled.data.find(d=>d.transform?.some(t=>t.type==='filter'&&JSON.stringify(t).includes('minPartidos'))).name;
      assert.equal(view.data(transformed).length,1224);
      view.signal('superficie','clay').signal('minPartidos',100);await view.runAsync();
      assert.equal(view.data(transformed).length,data.profiles.filter(x=>x.superficie==='clay'&&x.partidos>=100).length);
      view.signal('busqueda','NO_EXISTE_123');await view.runAsync();assert.equal(view.data(transformed).length,0);
    }
    const svg=await view.toSVG();assert.ok(svg.includes('<svg'));
    checks.push(name);view.finalize();
  }
  console.log(JSON.stringify({charts:checks.length,compiled:checks,filter_checks:'passed'}));
})().catch(e=>{console.error(e);process.exit(1)});
