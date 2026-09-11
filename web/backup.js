(() => {
 const section=document.createElement('section');section.id='backup-restore';
 section.innerHTML=`<h2>Back up or restore this player</h2><p>Download a backup before changing your layout. It includes the active WLED setup, current lighting selection, presets, palettes, timers and explicit show locks. Unapplied setup edits and FPP output settings are not included.</p>
 <p>Browser access tokens and MQTT passwords are never included. Restore keeps this player's credentials, combines existing and backed-up show locks, clears native-device recovery snapshots, and leaves background lighting disabled until you enable it.</p>
 <button id="downloadSetup">Download setup backup</button><button id="downloadPreviousSetup">Download setup from before last restore</button>
 <label>Restore file <input id="restoreFile" type="file" accept=".json,application/json"></label><button id="previewRestore" disabled>Preview restore</button><button id="stageRestore" disabled>Save restore for next restart</button><button id="cancelRestore" hidden>Cancel pending restore</button><pre id="restoreFeedback" role="status">Choose a backup to preview its contents. Maximum size: 8 MiB.</pre><a href="#configuration">Apply saved setup and restart WLED</a>`;
 document.getElementById('compatibility').before(section);
 const $=id=>document.getElementById(id);let bundle=null,revision=null,busy=false;
 const nav=document.querySelector('nav[aria-label="Setup sections"]'),link=document.createElement('a');link.href='#backup-restore';link.textContent='Backup';nav.append(document.createTextNode(' · '),link);
 async function download(previous){
  try{const response=await wledFetch(previous?'/api/backup/previous':'/api/backup');const data=await response.json();if(!response.ok)throw Error(data.error||'Cannot download backup.');
   const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'})),a=document.createElement('a');a.href=url;a.download=previous?'wled-before-restore.json':'wled-setup-backup.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);$('restoreFeedback').textContent='Backup downloaded. Keep it somewhere safe.';
  }catch(error){$('restoreFeedback').textContent=error.message;}
 }
 $('downloadSetup').onclick=()=>download(false);$('downloadPreviousSetup').onclick=()=>download(true);
 $('restoreFile').onchange=async()=>{
  bundle=null;revision=null;$('stageRestore').disabled=$('previewRestore').disabled=true;
  try{const file=$('restoreFile').files[0];if(!file)return;if(file.size>8*1024*1024-2048)throw Error('Backup exceeds the 8 MiB limit.');bundle=JSON.parse(await file.text());$('previewRestore').disabled=false;$('restoreFeedback').textContent='File loaded. Preview it before saving.';}
  catch(error){$('restoreFeedback').textContent=error.message;}
 };
 async function restore(preview){
  if(busy||!bundle)return;busy=true;$('restoreFile').disabled=$('previewRestore').disabled=$('stageRestore').disabled=true;
  try{const response=await wledFetch('/api/restore',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({backup:bundle,preview,revision}),signal:AbortSignal.timeout(30000)}),data=await response.json();if(!response.ok)throw Error(data.error||'Restore not accepted.');
   if(preview){revision=data.revision;$('restoreFeedback').textContent=data.pixels+' pixels · '+data.presets+' preset entries\nBackup show locks: '+(data.locks.join(', ')||'none')+'\n\n'+data.warnings.join('\n');}
   else{revision=null;$('cancelRestore').hidden=false;$('restoreFeedback').textContent='Restore saved. Apply saved setup to restart WLED and finish restoring. A backup of the previous setup is available above.';}
  }catch(error){$('restoreFeedback').textContent=error.name==='TimeoutError'?'No reply. Check saved setup before retrying.':error.message;}
  finally{busy=false;$('restoreFile').disabled=false;$('previewRestore').disabled=false;$('stageRestore').disabled=!revision;}
 }
 $('previewRestore').onclick=()=>restore(true);$('stageRestore').onclick=()=>restore(false);
 $('cancelRestore').onclick=async()=>{try{const response=await wledFetch('/api/restore/cancel',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});if(!response.ok)throw Error('Could not cancel restore.');$('cancelRestore').hidden=true;$('restoreFeedback').textContent='Restore cancelled. Your current setup is unchanged.';}catch(error){$('restoreFeedback').textContent=error.message;}};
 wledFetch('/api/config/status').then(r=>r.json()).then(status=>{$('cancelRestore').hidden=!status.restore_pending;}).catch(()=>{});
 wledStyleControls(section);
})();
