(() => {
  if(window.wledTheme)return;
  const root=document.documentElement;
  if(window.parent!==window&&new URLSearchParams(location.search).has('embedded')){
    root.dataset.fppEmbedded='true';
    function inherit(){
      const host=parent.document.documentElement,style=parent.getComputedStyle(host);
      root.dataset.bsTheme=host.dataset.bsTheme||'light';root.style.colorScheme=root.dataset.bsTheme;
      for(const name of ['body-bg','body-color','secondary-bg','tertiary-bg','secondary-color','border-color','primary','primary-bg-subtle','primary-text-emphasis','success-bg-subtle','success-text-emphasis','success-border-subtle','warning-bg-subtle','warning-text-emphasis','warning-border-subtle','link-color'])root.style.setProperty('--bs-'+name,style.getPropertyValue('--bs-'+name));
    }
    inherit();new MutationObserver(inherit).observe(parent.document.documentElement,{attributes:true,attributeFilter:['data-bs-theme']});
    window.wledTheme={apply:inherit,set:()=>{},toggle:()=>{},mount:()=>{}};return;
  }
  const key='fpp-wled-appearance',media=matchMedia('(prefers-color-scheme: dark)');
  const hosted=!!document.getElementById('fpp-wled-page-navigation');
  let inherited=hosted?root.dataset.bsTheme:null,choice=hosted?'auto':'dark',lastApplied;
  const normalize=value=>['light','dark'].includes(value)?value:'auto';
  try{const saved=localStorage.getItem(key);if(saved)choice=normalize(saved);}catch{}
  function apply(){
    const theme=choice==='auto'?(['light','dark'].includes(inherited)?inherited:media.matches?'dark':'light'):choice;
    lastApplied=theme;root.dataset.bsTheme=theme;root.style.colorScheme=theme;
    document.querySelectorAll('[data-wled-mode]').forEach(button=>{
      const selected=button.dataset.wledMode===choice;
      button.setAttribute('aria-pressed',String(selected));
      button.classList.toggle('btn-primary',selected);button.classList.toggle('btn-outline-secondary',!selected);
    });
  }
  function set(value){choice=normalize(value);try{localStorage.setItem(key,choice);}catch{}apply();}
  function mount(target){
    if(!target||document.getElementById('wled-theme-modes'))return;
    const group=document.createElement('div');group.id='wled-theme-modes';group.className='btn-group ms-auto';
    group.setAttribute('role','group');group.setAttribute('aria-label','Appearance');
    group.style.cssText='display:inline-flex;flex-shrink:0;gap:0;vertical-align:middle;';
    for(const mode of ['light','dark','auto']){
      const button=document.createElement('button');button.type='button';button.dataset.wledMode=mode;
      button.className='btn btn-sm btn-outline-secondary';button.textContent=mode[0].toUpperCase()+mode.slice(1);
      button.style.cssText='font:inherit;font-size:14px;line-height:1.4;min-height:40px;padding:6px 10px;margin:0;border:1px solid var(--bs-border-color,ButtonBorder);border-radius:0;cursor:pointer;';
      if(mode==='light')button.style.borderRadius='.375rem 0 0 .375rem';
      if(mode==='auto')button.style.borderRadius='0 .375rem .375rem 0';
      button.onclick=()=>set(mode);group.append(button);
    }
    target.append(group);apply();
  }
  window.wledTheme={set,apply,mount,toggle:()=>set(['light','dark','auto'][(['light','dark','auto'].indexOf(choice)+1)%3])};
  function bind(){
    document.querySelectorAll('[data-wled-theme]').forEach(select=>select.closest('p').remove());
    mount(document.getElementById('fpp-wled-page-navigation')||document.querySelector('.wled-app-nav'));apply();
  }
  bind();document.addEventListener('DOMContentLoaded',bind);
  media.addEventListener('change',apply);
  window.addEventListener('storage',event=>{if(event.key===key||event.key===null){try{choice=normalize(localStorage.getItem(key));}catch{choice='auto';}apply();}});
  if(hosted)new MutationObserver(()=>{if(root.dataset.bsTheme!==lastApplied){inherited=root.dataset.bsTheme;apply();}}).observe(root,{attributes:true,attributeFilter:['data-bs-theme']});
})();
