// Read-only overview: share the settings page's state poll, never edit its drafts.
(() => {
 const $ = id => document.getElementById(id);
 // Group only the heading and overview; settings.php still finds the first h1.
 const header = document.createElement('div'); header.className = 'wled-summary-header';
 const summary = $('lightingSummary'), title = summary.previousElementSibling;
 title.before(header); header.append(title, summary);
 let effects = [], presets = {}, palettes=[], customPalettes={}, nextCatalog = 0, fetching = false, latest;
 const list=summary.querySelector('dl');
 for(const [title,id] of [['Palette','summaryPalette'],['Live WLED colors','summaryLiveColors']]){const item=document.createElement('div'),term=document.createElement('dt'),value=document.createElement('dd');term.textContent=title;value.id=id;value.textContent='Checking...';item.append(term,value);list.append(item);}
 $('summaryColors').previousElementSibling.textContent='Color controls';
 const name = id => presets[String(id)]?.n || 'Preset ' + id;
 window.wledEffectLabel = id => effects[id] && !effects[id].startsWith('RSVD') ? effects[id]+' (ID '+id+')' : 'Reserved / unavailable slot '+id;
 function colorName(rgb) {
  const [r,g,b] = rgb, hi = Math.max(r,g,b), lo = Math.min(r,g,b), delta = hi-lo;
  if (hi < 12) return 'Black';
  if (delta < 22) return hi > 225 ? 'White' : hi > 100 ? 'Gray' : 'Dark gray';
  if (r > 220 && g > 155 && b > 85 && r > g && g > b) return 'Warm white';
  let hue = delta === 0 ? 0 : hi === r ? 60*((g-b)/delta%6) : hi === g ? 60*((b-r)/delta+2) : 60*((r-g)/delta+4);
  hue = (hue+360)%360;
  const label = hue < 15 || hue >= 345 ? 'Red' : hue < 45 ? 'Orange' : hue < 70 ? 'Yellow' : hue < 165 ? 'Green' : hue < 195 ? 'Cyan' : hue < 255 ? 'Blue' : hue < 290 ? 'Purple' : 'Pink';
  return hi < 90 ? 'Dark '+label.toLowerCase() : label;
 }
 function render(data) {
  const s=data.state, status=data.info.fpp, badge=$('summaryStatus');
  let state='on', label='Online · WLED ambient lighting', detail='WLED controls the background lighting between shows.';
  if(status.fault){state='error';label='Online · Needs attention';detail='Background lighting is paused: '+status.fault;}
  else if(!status.observer_healthy){state='warning';label='Online · FPP status unknown';detail='Background lighting is paused until WLED can confirm who controls the lights.';}
  else if(status.show_owned){state='show';label=status.sources.some(source=>source.startsWith('fpp:'))?'Online · FPP controls the lights':'Online · Show has control';detail='WLED ambient lighting is paused. Show ownership: '+status.sources.join(', ')+'.';}
  else if(!status.enabled){state='off';label='Online · Background lighting disabled';detail='Allow background lighting in Lights between shows to use WLED.';}
  else if(!status.quiet){state='warning';label='Online · Waiting after show';detail='WLED will resume after the quiet period.';}
  else if(!s.on||s.bri===0){state='off';label='Online · WLED lights off';detail='Background lighting is enabled, but WLED power or brightness is off.';}
  badge.dataset.state=state;if(badge.textContent!==label)badge.textContent=label;if($('summaryDetail').textContent!==detail)$('summaryDetail').textContent=detail;
  $('summaryVersion').textContent=data.info.ver;
  $('summaryPreset').textContent=s.pl>0?'Playlist: '+name(s.pl)+(s.ps>0?' · '+name(s.ps):''):s.ps>0?name(s.ps):'No preset selected';
  const segments=s.seg.filter(segment=>segment.on!==false&&segment.stop>segment.start);
  const labels=[...new Set(segments.map(segment=>effects[segment.fx]||'Effect '+segment.fx))];
  $('summaryEffect').textContent=labels.join(', ')||'No active segments';
  $('summaryPalette').textContent=[...new Set(segments.map(segment=>palettes[segment.pal]||customPalettes[segment.pal]||'Palette '+segment.pal))].join(', ')||'None';
  const colors=new Map();
  for(const segment of segments)for(const color of segment.col||[]){const rgba=[...color.slice(0,3),color[3]||0];colors.set(rgba.join(','),rgba);}
  $('summaryColors').replaceChildren();
  for(const color of colors.values()){
   const rgb=color.slice(0,3), hex='#'+rgb.map(v=>v.toString(16).padStart(2,'0')).join('');
   const chip=document.createElement('span'), swatch=document.createElement('span');
   chip.className='summary-color';swatch.className='summary-swatch';swatch.style.background=hex;swatch.setAttribute('aria-hidden','true');
   chip.title=hex.toUpperCase()+(color[3]?' · White channel '+color[3]:' · RGB');
   chip.append(swatch,document.createTextNode(colorName(rgb)+(color[3]?' + white '+Math.round(color[3]/255*100)+'%':'')));
   $('summaryColors').append(chip);
  }
  if(!colors.size)$('summaryColors').textContent='No active segments';
 }
 window.wledSummary = data => {
  if(latest&&(latest.state.ps!==data.state.ps||latest.state.pl!==data.state.pl||latest.info.palrev!==data.info.palrev))nextCatalog=0;
  latest=data; render(data);
  if(fetching||Date.now()<nextCatalog)return;
  fetching=true;nextCatalog=Date.now()+10000;
  Promise.all([wledFetch('/json/effects'),wledFetch('/presets.json'),wledFetch('/json/palettes'),wledFetch('/api/palettes')]).then(async responses=>{
   if(!responses.every(r=>r.ok))return;
   const data=await Promise.all(responses.map(r=>r.json()));[effects,presets,palettes]=data;customPalettes=Object.fromEntries(Object.entries(data[3].ids).map(([slot,id])=>[id,'Custom palette '+slot]));if(latest)render(latest);
  }).catch(()=>{}).finally(()=>fetching=false);
 };
 window.wledSummaryUnavailable = () => {
  latest=null;$('summaryStatus').dataset.state='error';$('summaryStatus').textContent='Offline · WLED unavailable';
  $('summaryDetail').textContent='Cannot read current status. Check the plugin in FPP. The last reported selection below may be out of date.';
 };
 window.wledSummaryPreview = preview => {
  const output=$('summaryLiveColors');output.replaceChildren();
  if(!preview){output.textContent='Live sample unavailable / preview off';return;}
  if(!preview.allowed){output.textContent='WLED output paused';return;}
  const groups=new Map();
  for(const [,r,g,b,w=0] of preview.pixels){const rgb=[r,g,b].map(v=>Math.min(255,v+w)),name=colorName(rgb),group=groups.get(name)||{name,count:0,sum:[0,0,0]};group.count++;rgb.forEach((value,i)=>group.sum[i]+=value);groups.set(name,group);}
  for(const group of [...groups.values()].sort((a,b)=>b.count-a.count).slice(0,8)){
   const chip=document.createElement('span'),swatch=document.createElement('span');chip.className='summary-color';swatch.className='summary-swatch';swatch.style.background='rgb('+group.sum.map(v=>Math.round(v/group.count)).join(',')+')';swatch.setAttribute('aria-hidden','true');chip.append(swatch,document.createTextNode(group.name));chip.title='Sampled from WLED rendering';output.append(chip);
  }
  if(!groups.size)output.textContent='No pixel sample';
 };
})();
