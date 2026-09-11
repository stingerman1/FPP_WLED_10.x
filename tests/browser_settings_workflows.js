async (page) => {
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 const base='http://localhost:18787';
 await page.request.post(base+'/api/login',{headers:{Authorization:'Bearer local-browser-test-token-not-for-deployment'},data:{}});
 const schedule=await(await page.request.get(base+'/api/schedules')).json();
 await page.request.post(base+'/api/schedules',{data:{revision:schedule.revision,preview:false,timers:[],location:null}});
 await page.request.post(base+'/json/state',{data:{psave:1,n:'QA warm'}});
 await page.reload();
 await page.waitForFunction(()=>document.getElementById('accessDetails').dataset.setupState==='complete');
 for(const link of await page.locator('a[href^="#"]').all()) if(await page.locator(await link.getAttribute('href')).count()!==1) throw Error('Broken section link');
 await page.locator('#applyLighting').click();
 await page.waitForFunction(()=>document.getElementById('lightingStatus').textContent==='Lighting updated.');
 if(await page.locator('.action-feedback').count() || await page.locator('#result').textContent()) throw Error('Duplicate confirmation');
 await page.locator('#lightOff').click();
 await page.waitForFunction(()=>document.getElementById('lightingStatus').textContent==='Lighting updated.');
 if((await(await page.request.get(base+'/json/state')).json()).on) throw Error('Off failed');
 await page.locator('#applyLighting').click();
 await page.locator('#startNightlight').click();
 await page.waitForFunction(()=>document.getElementById('nightStatus').textContent.includes('Running'));
 await page.locator('#startNightlight').click();
 await page.waitForFunction(()=>document.getElementById('nightStatus').textContent.includes('No nightlight'));
 // Schedule create, preview, failed save retry, save, edit, remove.
 await page.locator('#addSchedule').click();
 await page.locator('#previewSchedules').click();
 await page.waitForFunction(()=>!document.getElementById('saveSchedules').disabled);
 await page.route('**/api/schedules', async route=>{
  if(route.request().method()==='POST') await route.fulfill({status:503,json:{error:'QA temporary failure'}}); else await route.continue();
 });
 await page.locator('#saveSchedules').click();
 await page.waitForFunction(()=>document.getElementById('scheduleReport').textContent.includes('QA temporary failure'));
 if(await page.locator('#saveSchedules').isDisabled()) throw Error('Save retry disabled');
 await page.unroute('**/api/schedules');
 await page.locator('#saveSchedules').click();
 await page.waitForFunction(()=>document.getElementById('scheduleReport').textContent.includes('Saved. These schedules'));
 if((await(await page.request.get(base+'/api/schedules')).json()).timers.length!==1) throw Error('Schedule not saved');
 await page.locator('#scheduleList').getByRole('button',{name:'Edit timer 1',exact:true}).click();
 await page.locator('#scheduleClock').fill('20:15');
 await page.locator('#addSchedule').click();
 await page.locator('#previewSchedules').click();
 await page.waitForFunction(()=>!document.getElementById('saveSchedules').disabled);
 await page.locator('#saveSchedules').click();
 await page.waitForFunction(()=>document.getElementById('scheduleReport').textContent.includes('Saved. These schedules'));
 // Invalid output draft must fail without mutation, valid save has one status.
 await page.locator('#cfgCount').fill('');
 await page.locator('#saveGuided').click();
 await page.waitForFunction(()=>document.getElementById('configFeedback').textContent.includes('Check'));
 await page.locator('#reloadConfig').click();
 await page.waitForFunction(()=>document.getElementById('cfgCount').value==='1000');
 await page.locator('#saveGuided').click();
 await page.waitForFunction(()=>!document.getElementById('saveGuided').disabled);
 // Network saves keep unfinished JSON drafts and have one confirmation.
 await page.locator('#configuration > details > summary').last().click();
 await page.locator('#config').fill('{unfinished draft');
 await page.locator('#networkName').fill('QA player');
 await page.locator('#saveNetwork').click();
 await page.waitForFunction(()=>document.getElementById('networkFeedback').textContent.includes('Saved.'));
 if(await page.locator('#config').inputValue()!=='{unfinished draft') throw Error('Network overwrote draft');
 await page.locator('#discover').click();
 await page.waitForFunction(()=>document.getElementById('discoveryFeedback').textContent.includes('Checked'));
 // Palette create, read, export and delete.
 await page.locator('#savePalette').click();
 await page.waitForFunction(()=>document.getElementById('paletteStatus').textContent.includes('Saved slot'));
 await page.locator('#loadPalette').click();
 if(!(await page.request.get(base+'/palette0.json')).ok()) throw Error('Palette download failed');
 await page.locator('#deletePalette').click();
 await page.waitForFunction(()=>document.getElementById('paletteStatus').textContent.includes('Deleted slot'));
 // Preset preview and import.
 await page.locator('#presetImport').fill(JSON.stringify({'2':{n:'QA imported',bri:80}}));
 await page.locator('#previewImport').click();
 await page.waitForFunction(()=>!document.getElementById('commitImport').disabled);
 await page.locator('#commitImport').click();
 await page.waitForFunction(()=>document.getElementById('importReport').textContent.startsWith('Saved.'));
 if(!(await(await page.request.get(base+'/presets.json')).json())['2']) throw Error('Preset not imported');
 // Show lock and clear; no actual external device output.
 await page.locator('#ownershipDetails > summary').click();
 await page.locator('#ownershipDetails details > summary').first().click();
 await page.locator('#source').fill('qa:local');
 await page.locator('[data-op="show-start"]').click();
 await page.waitForFunction(()=>document.getElementById('ownershipSummary').textContent.includes('qa:local'));
 await page.waitForFunction(()=>document.getElementById('applyLighting').disabled);
 await page.locator('[data-op="show-end"]').click();
 await page.waitForFunction(()=>!document.getElementById('applyLighting').disabled);
 if(await page.locator('#result').textContent() || await page.locator('.action-feedback').count()) throw Error('Duplicate or raw result');
 if(errors.length) throw Error(errors.join('; '));
}
