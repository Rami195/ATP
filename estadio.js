/* Estadio: efectos visuales al scrollear. No lee ni cambia datos de la app. */
(function(){
  'use strict';
  const root=document.documentElement;
  const reduce=window.matchMedia&&matchMedia('(prefers-reduced-motion: reduce)').matches;
  if(!reduce)root.classList.add('anim');

  function start(){
    const sections=[...document.querySelectorAll('main>section[data-surface]')];
    const ball=document.querySelector('.bg-ball'),shadow=document.querySelector('.bg-ball-shadow');
    let current=null,ticking=false;

    function surfaceInView(){
      const line=innerHeight*.45;let surface=sections.length?sections[0].dataset.surface:'grass';
      for(const s of sections){if(s.getBoundingClientRect().top<=line)surface=s.dataset.surface;}
      return surface;
    }
    function update(){
      ticking=false;
      const y=scrollY,max=Math.max(1,document.documentElement.scrollHeight-innerHeight);
      root.style.setProperty('--progress',Math.min(1,y/max).toFixed(4));
      root.style.setProperty('--spin',(y*.02).toFixed(2));
      const surface=surfaceInView();
      if(surface!==current){current=surface;root.dataset.surface=surface;}
      if(ball&&!reduce){
        // Un peloteo de lado a lado: cada 900 px de scroll la pelota cruza la cancha.
        const period=900,t=(y%period)/period,dir=Math.floor(y/period)%2;
        const w=innerWidth,h=innerHeight,x=(dir?1-t:t)*(w-80)+20;
        const floor=h*.78,lift=Math.sin(Math.PI*t)*h*.42;
        ball.style.transform='translate('+x.toFixed(1)+'px,'+(floor-lift).toFixed(1)+'px) rotate('+(y*.8).toFixed(0)+'deg)';
        const scale=(1-.5*Math.sin(Math.PI*t)).toFixed(2);
        shadow.style.transform='translate('+x.toFixed(1)+'px,'+(floor+30).toFixed(1)+'px) scale('+scale+')';
        shadow.style.opacity=(.35+.65*(1-Math.sin(Math.PI*t))).toFixed(2);
      }
    }
    function onScroll(){if(!ticking){ticking=true;requestAnimationFrame(update);}}
    addEventListener('scroll',onScroll,{passive:true});addEventListener('resize',onScroll);
    update();

    // Aparición suave de bloques al entrar en pantalla.
    const blocks=document.querySelectorAll('.section-heading,.chart-box,.style-notes article,main>section>details,.decide-card,.metrics>div,.controls,.detail-panel,.duel-examples,#duel-form,.model-layout,.read-box,.table-wrap,footer>*');
    if(reduce||!('IntersectionObserver' in window))return;
    // Al terminar la entrada se quitan las clases, para que los efectos de hover vuelvan a funcionar.
    const settle=el=>{el.classList.remove('rv','in');el.style.transitionDelay='';};
    const io=new IntersectionObserver(entries=>{for(const e of entries)if(e.isIntersecting){const el=e.target;el.classList.add('in');io.unobserve(el);el.addEventListener('transitionend',ev=>{if(ev.target===el&&ev.propertyName==='opacity')settle(el);});setTimeout(()=>settle(el),1600);}},{rootMargin:'0px 0px -8% 0px',threshold:0});
    blocks.forEach((b,i)=>{b.classList.add('rv');b.style.transitionDelay=((i%3)*.06)+'s';io.observe(b);});
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start);else start();
})();
