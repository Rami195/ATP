/* Prueba en Chrome real sobre la app servida por HTTP. Es la que detecta lo que el DOM simulado
   no ve: gráficos con ancho 0, errores de consola, desbordes y los controles contra Vega real.
   Uso: node test_browser.cjs [url] [carpeta-para-capturas]
   Requiere Chrome y puppeteer-core (ver README). CHROME_PATH cambia la ruta del ejecutable. */
const assert=require('node:assert/strict'),fs=require('node:fs'),os=require('node:os'),path=require('node:path');
let puppeteer;try{puppeteer=require('puppeteer-core');}catch{puppeteer=require('../../.qa-entrega4/node_modules/puppeteer-core');}
const url=process.argv[2]||'http://127.0.0.1:8765/',shots=process.argv[3];
const chrome=process.env.CHROME_PATH||'C:/Program Files/Google/Chrome/Application/chrome.exe';
const sleep=ms=>new Promise(r=>setTimeout(r,ms));

async function open(browser,width,height,problems){
  const page=await browser.newPage();await page.setViewport({width,height});
  page.on('console',m=>{if(['error','warn','warning'].includes(m.type()))problems.push(m.type()+': '+m.text());});
  page.on('pageerror',e=>problems.push('pageerror: '+e.message));
  page.on('requestfailed',r=>problems.push('requestfailed: '+r.url()));
  page.on('response',r=>{if(r.status()>=400)problems.push(r.status()+': '+r.url());});
  const start=Date.now();await page.goto(url,{waitUntil:'networkidle0',timeout:60000});
  await page.waitForFunction(()=>document.getElementById('estado').textContent==='',{timeout:30000});
  return {page,loaded:Date.now()-start};
}
// Sin capturas antes de medir: una captura dispara resize y tapa justo el error que se busca.
const widths=page=>page.evaluate(()=>Object.fromEntries([...document.querySelectorAll('.chart')].map(e=>[e.id,+(e.querySelector('svg')?.getAttribute('width')||0)])));
const value=(page,id)=>page.$eval('#'+id,e=>e.textContent);
const pick=(page,id,v)=>page.evaluate((id,v)=>{const e=document.getElementById(id);e.value=v;for(const t of ['input','change'])e.dispatchEvent(new Event(t,{bubbles:true}));},id,v);
const marks=page=>page.$$eval('#explorar svg path[aria-roledescription="point"]',e=>e.length);

(async()=>{
  const browser=await puppeteer.launch({executablePath:chrome,headless:true,userDataDir:fs.mkdtempSync(path.join(os.tmpdir(),'atp-qa-')),args:['--no-first-run']});
  const problems=[],report={};
  try{
    const {page,loaded}=await open(browser,1366,900,problems);report.load_ms=loaded;
    // Los dos gráficos del simulador nacen dentro de un bloque oculto.
    await sleep(300);const first=await widths(page);
    for(const id of ['calidad','victorias','rendimiento','enfrentamiento','explorar','distancias'])assert.ok(first[id]>300,id+' ancho '+first[id]);
    // Abrir cada desplegable y volver a medir, sin redimensionar la ventana.
    await page.evaluate(()=>document.querySelectorAll('details').forEach(d=>{d.open=true;}));await sleep(600);
    const opened=await widths(page);for(const [id,w] of Object.entries(opened))assert.ok(w>200,id+' abierto, ancho '+w);
    report.charts=Object.keys(opened).length;
    await page.evaluate(()=>document.querySelectorAll('details').forEach(d=>{d.open=false;}));

    // Filtros contra Vega real: los puntos dibujados coinciden con el contador.
    const total=await marks(page);assert.equal(total,1224);
    await pick(page,'surface','grass');await sleep(250);
    assert.equal(await marks(page),259);assert.match(await value(page,'filtered-count'),/^259 de 1\.224/);
    await pick(page,'search','federer');await sleep(250);assert.equal(await marks(page),1);
    assert.match(await value(page,'detail'),/El modelo lo asigna a:/);
    await page.click('#reset');await sleep(250);assert.equal(await marks(page),1224);

    // El clic en un punto fija el detalle.
    await page.evaluate(()=>document.getElementById('explorar').scrollIntoView());await sleep(150);
    const before=await page.$eval('#profile-select',e=>e.value);
    const point=await page.$$eval('#explorar svg path[aria-roledescription="point"]',e=>{const b=e[e.length-1].getBoundingClientRect();return {x:b.x+b.width/2,y:b.y+b.height/2};});
    await page.mouse.click(point.x,point.y);await sleep(200);
    assert.notEqual(await page.$eval('#profile-select',e=>e.value),before,'el clic no cambió el perfil');

    // El ejemplo donde los estilos cambian al favorito.
    await page.evaluate(()=>document.querySelectorAll('#duel-examples button')[1].click());await sleep(350);
    assert.equal(await value(page,'duel-title'),'Daniil Medvedev vs. Rafael Nadal');
    assert.equal(await value(page,'duel-favorite-ranking'),'Daniil Medvedev');
    assert.equal(await value(page,'duel-favorite-combined'),'Rafael Nadal');
    assert.equal(await value(page,'duel-favorite-styles'),'Restadores sólidos');
    assert.match(await value(page,'duel-comparison-reading'),/El favorito cambia/);
    const bars=await page.$$eval('#enfrentamiento svg path[aria-roledescription="bar"]',e=>e.length);assert.equal(bars,6);
    const after=await widths(page);assert.ok(after.enfrentamiento>300);

    // Buscador de jugadores con teclado y mouse reales.
    await pick(page,'duel-season','2023');await pick(page,'duel-surface','cemento');await sleep(300);
    await page.click('#duel-search-a');await page.keyboard.type('alcar');await sleep(120);
    const dropdown=await page.$eval('#duel-list-a',e=>({height:e.getBoundingClientRect().height,hidden:e.hidden,first:e.querySelector('[role=option]')?.firstChild.textContent}));
    assert.ok(dropdown.height>30&&!dropdown.hidden);assert.equal(dropdown.first,'Carlos Alcaraz');
    await page.keyboard.press('Enter');await sleep(300);assert.equal(await value(page,'duel-name-a'),'Carlos Alcaraz');
    await page.click('#duel-search-b');await page.keyboard.type('sinn');await sleep(120);
    await page.click('#duel-list-b [role=option]');await sleep(300);assert.equal(await value(page,'duel-name-b'),'Jannik Sinner');
    // Después de elegir, escribir reemplaza el nombre en vez de agregarse al final.
    await page.keyboard.type('med');await sleep(120);
    assert.equal(await page.$eval('#duel-search-b',e=>e.value),'med');
    await page.keyboard.press('Escape');await sleep(120);assert.equal(await page.$eval('#duel-search-b',e=>e.value),'Jannik Sinner');
    if(shots){fs.mkdirSync(shots,{recursive:true});await page.screenshot({path:path.join(shots,'desktop.png'),fullPage:true});}

    // Sin desborde horizontal, en un teléfono y en una pantalla chica.
    report.overflow={};
    for(const [width,height] of [[390,844],[768,1024]]){
      const {page:small}=await open(browser,width,height,problems);await sleep(300);
      const size=await small.evaluate(()=>({scroll:document.documentElement.scrollWidth,client:document.documentElement.clientWidth}));
      assert.ok(size.scroll<=size.client,'desborde a '+width+'px: '+JSON.stringify(size));
      const w=await widths(small);assert.ok(w.enfrentamiento>150&&w.enfrentamiento<=width,'enfrentamiento a '+width+': '+w.enfrentamiento);
      report.overflow[width]=size.scroll;
      if(shots)await small.screenshot({path:path.join(shots,'w'+width+'.png'),fullPage:true});
      await small.close();
    }
    assert.deepEqual(problems,[]);
    console.log(JSON.stringify({browser:'passed',...report}));
  }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
