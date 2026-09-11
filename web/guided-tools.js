(() => {
 const $=id=>document.getElementById(id), section=document.createElement('section');section.id='mqtt-setup';
 section.innerHTML=`<h2>Home Assistant and MQTT</h2><p>Use an MQTT broker to connect this player to Home Assistant or other automation tools. Home Assistant's MQTT integration will discover the light after connection. Shows still take priority over lighting commands.</p>
 <fieldset id="mqttFields"><label><input id="mqttEnabled" type="checkbox"> Enable MQTT and Home Assistant discovery</label><label>Broker address <input id="mqttHost" placeholder="192.168.1.10"></label><label>Broker port <input id="mqttPort" type="number" min="1" max="65535" value="1883" required></label><label><input id="mqttTls" type="checkbox"> Use TLS (requires a trusted broker certificate)</label><label>Topic <input id="mqttTopic" value="wled/fpp" required></label><label>Unique player ID <input id="mqttId" value="fpp_wled" required></label><p>Give each player a different topic and ID. Your broker administrator supplies its address and login.</p>
 <label>Broker login <select id="mqttCredentials"><option value="keep">Keep saved login</option><option value="replace">Set a new login</option><option value="clear">Remove saved login</option></select></label><div id="mqttLogin" hidden><label>Username <input id="mqttUser" autocomplete="off" maxlength="1024"></label><label>Password <input id="mqttPassword" type="password" autocomplete="new-password" maxlength="1024"></label></div><button id="saveMqtt">Save MQTT setup</button><button id="reloadMqtt">Discard edits and reload</button></fieldset><p id="mqttFeedback" role="status"></p><p id="mqttConnection" role="status">Checking connection...</p><a href="#configuration">Apply saved setup and restart WLED</a>`;
 $('network').after(section);
 const nav=document.querySelector('nav[aria-label="Setup sections"]'),link=document.createElement('a');link.href='#mqtt-setup';link.textContent='Home Assistant';nav.append(document.createTextNode(' · '),link);
 $('mqttCredentials').onchange=()=>{$('mqttLogin').hidden=$('mqttCredentials').value!=='replace';};
 async function load(fill){
  try{const response=await wledFetch('/api/mqtt');if(!response.ok)throw Error('Cannot check MQTT.');const data=await response.json(),c=data.config;
   $('mqttConnection').textContent=(data.connected?'Connected to the broker.':c.enabled?'Not connected. Apply saved setup, then check broker address and login.':'MQTT is disabled.')+(data.credentials_saved?' A broker login is saved.':' No broker login is saved.');
   if(fill){$('mqttEnabled').checked=!!c.enabled;$('mqttTls').checked=!!c.tls;for(const [id,key,value] of [['mqttHost','host',''],['mqttPort','port',1883],['mqttTopic','topic','wled/fpp'],['mqttId','id','fpp_wled']])$(id).value=c[key]??value;$('mqttUser').value=$('mqttPassword').value='';$('mqttCredentials').value='keep';$('mqttCredentials').onchange();}
  }catch(error){$('mqttConnection').textContent=error.message;}
 }
 $('reloadMqtt').onclick=()=>load(true);
 $('saveMqtt').onclick=async()=>{
  if(![...$('mqttFields').querySelectorAll('input')].every(input=>input.reportValidity()))return;
  $('mqttFields').disabled=true;
  try{const body={config:{enabled:$('mqttEnabled').checked,host:$('mqttHost').value.trim(),port:Number($('mqttPort').value),topic:$('mqttTopic').value.trim(),id:$('mqttId').value.trim(),tls:$('mqttTls').checked},credentials:$('mqttCredentials').value};if(body.credentials==='replace'){body.username=$('mqttUser').value;body.password=$('mqttPassword').value;}
   const response=await wledFetch('/api/mqtt',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body),signal:AbortSignal.timeout(15000)}),data=await response.json();if(!response.ok)throw Error(data.error||'MQTT setup not saved.');
   $('mqttPassword').value='';await load(true);$('mqttFeedback').textContent='Saved. Apply saved setup to connect with these settings.';
  }catch(error){$('mqttFeedback').textContent=error.message;}finally{$('mqttFields').disabled=false;}
 };
 load(true);setInterval(()=>{if(!document.hidden)load(false);},5000);

 const editor=document.createElement('details');editor.id='paletteDesigner';
 editor.innerHTML=`<summary>Design a palette with color stops</summary><p>Choose colors along the gradient. Positions run from 0 (start) to 255 (end). Keep stops in order. Save colors uses the palette slot selected above.</p><div id="paletteStops"></div><button id="addColorStop">Add color stop</button><button id="readColorStops">Load colors from the JSON below</button><button id="saveColorStops">Save colors to selected slot</button><div id="draftGradient" role="img" aria-label="Draft palette preview" style="height:2rem"></div><p id="colorStopFeedback" role="status"></p>`;
 $('paletteJson').parentElement.before(editor);
 let stops=[[0,'#ff0000'],[255,'#0000ff']];
 function gradient(){ $('draftGradient').style.background='linear-gradient(to right,'+stops.map(([position,color])=>color+' '+position/255*100+'%').join(',')+')'; }
 function render(){
  $('paletteStops').replaceChildren();stops.forEach((stop,index)=>{
   const row=document.createElement('div');row.className='setup-row';const label=document.createElement('label');label.textContent='Position ';const position=document.createElement('input');position.type='number';position.min=0;position.max=255;position.required=true;position.value=stop[0];position.oninput=()=>{stop[0]=position.value===''?null:Number(position.value);gradient();};label.append(position);
   const colorLabel=document.createElement('label');colorLabel.textContent='Color ';const color=document.createElement('input');color.type='color';color.value=stop[1];color.oninput=()=>{stop[1]=color.value;gradient();};colorLabel.append(color);
   const remove=document.createElement('button');remove.textContent='Remove stop';remove.onclick=()=>{stops.splice(index,1);render();};row.append(label,colorLabel,remove);$('paletteStops').append(row);
  });gradient();$('addColorStop').disabled=stops.length>=18;wledStyleControls(editor);
 }
 $('addColorStop').onclick=()=>{let index=0,gap=-1;for(let i=1;i<stops.length;i++)if(stops[i][0]-stops[i-1][0]>gap){gap=stops[i][0]-stops[i-1][0];index=i;}stops.splice(index,0,[gap>0?Math.round((stops[index][0]+stops[index-1][0])/2):0,'#ffffff']);render();};
 $('readColorStops').onclick=()=>{
  try{const values=JSON.parse($('paletteJson').value).palette;if(!Array.isArray(values))throw Error('No palette array found.');const hex=typeof values[1]==='string',stride=hex?2:4;if(values.length%stride||values.length/stride<2||values.length/stride>18)throw Error('Choose 2 to 18 complete stops.');
   const candidate=[];for(let i=0;i<values.length;i+=stride){const color=hex?'#'+values[i+1].slice(-6):'#'+values.slice(i+1,i+4).map(v=>v.toString(16).padStart(2,'0')).join('');if(!/^#[0-9a-f]{6}$/i.test(color))throw Error('Invalid color.');candidate.push([values[i],color]);}stops=candidate;render();$('colorStopFeedback').textContent='Colors loaded into the editor.';
  }catch(error){$('colorStopFeedback').textContent=error.message;}
 };
 $('saveColorStops').onclick=async()=>{
  if(![...$('paletteStops').querySelectorAll('input')].every(input=>input.reportValidity()))return;
  if(stops.length<2||stops[0][0]!==0||stops.at(-1)[0]!==255||stops.some((stop,index)=>index&&stop[0]<stops[index-1][0])){$('colorStopFeedback').textContent='Use 2 to 18 ordered stops, starting at 0 and ending at 255.';return;}
  $('paletteJson').value=JSON.stringify({palette:stops.flatMap(([position,color])=>[position,color.slice(1).toUpperCase()])});$('colorStopFeedback').textContent='';$('saveColorStops').disabled=true;try{await savePalette(false);}finally{$('saveColorStops').disabled=false;}
 };
 render();
 wledStyleControls(section);
})();
