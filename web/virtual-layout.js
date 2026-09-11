(() => {
 const section=document.createElement('section');section.id='virtual-layout';
 section.innerHTML=`<h2>Build virtual segments</h2><p>Join parts of different strings or models into one lighting pattern. Read your FPP lights, add a segment, then choose its pixel ranges in order. Pixel 1 means the first pixel of that source. Matrix sources count left to right, then top to bottom.</p>
 <p>This creates a replacement layout. Include every pixel you want WLED to light. Each physical pixel can appear only once. FPP show outputs stay unchanged.</p>
 <fieldset id="virtualFields"><button id="readVirtualSources">Read FPP lights</button><div id="virtualGroups"></div><button id="addVirtualGroup" disabled>Add a virtual segment</button><button id="previewVirtual" disabled>Preview layout</button><button id="saveVirtual" disabled>Save this layout</button></fieldset><pre id="virtualFeedback" role="status">Read FPP lights to begin.</pre><a href="#configuration">Apply saved setup and restart WLED</a>`;
 document.getElementById('configuration').after(section);
 const nav=document.querySelector('nav[aria-label="Setup sections"]'),link=document.createElement('a');link.href='#virtual-layout';link.textContent='Virtual segments';nav.append(document.createTextNode(' · '),link);
 const $=id=>document.getElementById(id);let sources=[],revision='',groups=[],preview=null;
 function dirty(){preview=null;$('saveVirtual').disabled=true;}
 function number(label,value,min,max,change){const wrap=document.createElement('label'),input=document.createElement('input');wrap.textContent=label+' ';input.type='number';input.min=min;input.max=max;input.step=1;input.required=true;input.value=value;input.oninput=()=>{change(input.value===''?null:Number(input.value));dirty();};wrap.append(input);return wrap;}
 function button(label,action){const item=document.createElement('button');item.textContent=label;item.onclick=()=>{action();dirty();render();};return item;}
 function size(source){return source.kind==='string'?source.source.pixelCount:source.source.ChannelCount/(source.source.ChannelCountPerNode||3);}
 function render(){
  $('virtualGroups').replaceChildren();
  groups.forEach((group,index)=>{
   const box=document.createElement('fieldset');box.className='setup-row';box.style.display='block';
   const legend=document.createElement('legend');legend.textContent='Segment '+(index+1);box.append(legend);
   const label=document.createElement('label'),input=document.createElement('input');label.textContent='Segment name ';input.value=group.name;input.maxLength=128;input.required=true;input.oninput=()=>{group.name=input.value;dirty();};label.append(input);box.append(label);
   box.append(number('Matrix columns (0 = strip)',group.columns,0,16000,value=>group.columns=value));
   group.pieces.forEach((piece,pieceIndex)=>{
    const row=document.createElement('div');row.className='setup-row';
    const sourceLabel=document.createElement('label'),select=document.createElement('select');sourceLabel.textContent='Source ';
    sources.forEach(source=>select.add(new Option(source.name+' · '+size(source)+' pixels',source.id)));select.value=piece.source;
    select.onchange=()=>{piece.source=Number(select.value);dirty();};sourceLabel.append(select);row.append(sourceLabel);
    row.append(number('First pixel',piece.start===null?'':piece.start+1,1,16000,value=>piece.start=value===null?null:value-1),number('How many pixels',piece.count,1,16000,value=>piece.count=value));
    const reverse=document.createElement('label'),check=document.createElement('input');check.type='checkbox';check.checked=piece.reverse;check.onchange=()=>{piece.reverse=check.checked;dirty();};reverse.append(check,document.createTextNode(' Reverse order'));row.append(reverse);
    if(pieceIndex)row.append(button('Move range up',()=>{[group.pieces[pieceIndex-1],group.pieces[pieceIndex]]=[piece,group.pieces[pieceIndex-1]];}));
    row.append(button('Remove range',()=>group.pieces.splice(pieceIndex,1)));box.append(row);
   });
   box.append(button('Add pixel range',()=>group.pieces.push({source:sources[0].id,start:0,count:size(sources[0]),reverse:false})),button('Remove segment',()=>groups.splice(index,1)));$('virtualGroups').append(box);
  });
  $('previewVirtual').disabled=!groups.length;
  wledStyleControls(section);
 }
 $('readVirtualSources').onclick=async()=>{
  $('virtualFields').disabled=true;dirty();
  try{
   const response=await wledFetch('/api/layout');if(!response.ok)throw Error('Cannot read FPP lights.');
   const data=await response.json();sources=data.items;revision=data.revision;groups=[];
   // Restore the saved editor draft only while the source definitions still match.
   const configResponse=await wledFetch('/api/config/status');
   if(configResponse.ok){const saved=(await configResponse.json()).saved.virtual_layout;if(saved&&JSON.stringify(saved.sources)===JSON.stringify(sources))groups=saved.groups;}
   render();$('readVirtualSources').textContent='Discard edits and reload FPP lights';$('addVirtualGroup').disabled=!sources.length;$('virtualFeedback').textContent=data.warnings.join('\n')||(groups.length?'Saved virtual layout loaded.':'Ready. Add a virtual segment.');
  }catch(error){$('virtualFeedback').textContent=error.message;}
  finally{$('virtualFields').disabled=false;}
 };
 $('addVirtualGroup').onclick=()=>{if(groups.length>=32)return;groups.push({name:'Segment '+(groups.length+1),columns:0,pieces:[{source:sources[0].id,start:0,count:size(sources[0]),reverse:false}]});dirty();render();};
 async function submit(save){
  if(![...$('virtualGroups').querySelectorAll('input')].every(input=>input.reportValidity()))return;
  $('virtualFields').disabled=true;$('virtualFeedback').textContent=save?'Saving layout...':'Checking pixel ranges...';
  try{
   const response=await wledFetch('/api/layout',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({groups,source_revision:revision,preview:!save,revision:preview}),signal:AbortSignal.timeout(15000)});
   const data=await response.json();if(!response.ok)throw Error(data.error||'Layout not accepted.');
   if(save){dirty();$('virtualFeedback').textContent='Layout saved. Use Apply saved setup below to restart WLED with these segments.';}
   else{preview=data.config.imported_layout.revision;$('saveVirtual').disabled=false;$('virtualFeedback').textContent=data.segments.map(segment=>segment.n+': '+(segment.stop-segment.start)+' × '+(segment.stopY-segment.startY)+' pixels').join('\n')+'\n\n'+data.warnings.join('\n');}
  }catch(error){$('virtualFeedback').textContent=error.name==='TimeoutError'?'No reply. Check saved setup before retrying.':error.message;}
  finally{$('virtualFields').disabled=false;}
 }
 $('previewVirtual').onclick=()=>submit(false);$('saveVirtual').onclick=()=>submit(true);
 wledStyleControls(section);
})();
