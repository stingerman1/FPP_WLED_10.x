// Use tests/ui_fixture.py with MEDIADIR pointing to two named ten-pixel strings.
async(page)=>{
 const base='http://localhost:18787',errors=[];page.on('pageerror',error=>errors.push(error.message));
 await page.request.post(base+'/api/login',{headers:{Authorization:'Bearer local-browser-test-token-not-for-deployment'},data:{}});
 await page.goto(base+'/settings');
 await page.locator('#readVirtualSources').click();
 await page.waitForFunction(()=>!document.getElementById('addVirtualGroup').disabled);
 while(await page.locator('#virtualGroups').getByRole('button',{name:'Remove segment',exact:true}).count())await page.locator('#virtualGroups').getByRole('button',{name:'Remove segment',exact:true}).first().click();
 await page.locator('#addVirtualGroup').click();
 const groups=page.locator('#virtualGroups');
 await groups.getByLabel('Segment name',{exact:true}).fill('Porch and roof');
 await groups.getByLabel('How many pixels',{exact:true}).fill('3');
 await groups.getByRole('button',{name:'Add pixel range',exact:true}).click();
 await groups.locator('select').nth(1).selectOption('1');
 await groups.getByLabel('How many pixels',{exact:true}).nth(1).fill('2');
 await groups.getByLabel('Reverse order',{exact:true}).nth(1).check();
 await page.locator('#previewVirtual').click();
 await page.waitForFunction(()=>!document.getElementById('saveVirtual').disabled);
 if(!(await page.locator('#virtualFeedback').textContent()).includes('5 × 1'))throw Error('Wrong virtual preview');
 // Invalid draft must invalidate preview and retain the typed value.
 await groups.getByLabel('First pixel',{exact:true}).nth(1).fill('99');
 if(!await page.locator('#saveVirtual').isDisabled())throw Error('Stale preview can save');
 await page.locator('#previewVirtual').click();
 await page.waitForFunction(()=>document.getElementById('virtualFeedback').textContent.includes('first source pixel'));
 if(await groups.getByLabel('First pixel',{exact:true}).nth(1).inputValue()!=='99')throw Error('Draft reset');
 await groups.getByLabel('First pixel',{exact:true}).nth(1).fill('1');
 await page.locator('#previewVirtual').click();await page.waitForFunction(()=>!document.getElementById('saveVirtual').disabled);
 await page.locator('#saveVirtual').click();await page.waitForFunction(()=>document.getElementById('virtualFeedback').textContent.startsWith('Layout saved'));
 const config=(await(await page.request.get(base+'/api/config/status')).json()).saved;
 if(config.imported_layout.segments[0].n!=='Porch and roof'||JSON.stringify(config.ledmap)!=='[0,1,2,4,3]')throw Error('Wrong mapping');
 await page.locator('#readVirtualSources').click();await page.waitForFunction(()=>document.getElementById('virtualFeedback').textContent==='Saved virtual layout loaded.');
 await page.locator('#mqttHost').fill('localhost');await page.locator('#mqttCredentials').selectOption('replace');
 await page.locator('#mqttUser').fill('qa');await page.locator('#mqttPassword').fill('fixture-only-secret');
 await page.locator('#saveMqtt').click();await page.waitForFunction(()=>document.getElementById('mqttFeedback').textContent.startsWith('Saved.'));
 if(await page.locator('#mqttPassword').inputValue())throw Error('Password left visible in form');
 const mqtt=await(await page.request.get(base+'/api/mqtt')).text();if(mqtt.includes('fixture-only-secret'))throw Error('Secret exposed');
 await page.locator('#paletteDesigner > summary').click();await page.locator('#addColorStop').click();await page.locator('#saveColorStops').click();
 await page.waitForFunction(()=>document.getElementById('paletteStatus').textContent.includes('Saved slot'));
 const palette=await(await page.request.get(base+'/palette0.json')).json();if(palette.palette.length!==12)throw Error('Palette designer not saved');
 const bundle=await(await page.request.get(base+'/api/backup')).json();if(JSON.stringify(bundle).includes('fixture-only-secret'))throw Error('Backup contains secret');
 const downloadEvent=page.waitForEvent('download');await page.locator('#downloadSetup').click();const download=await downloadEvent;await download.saveAs('build/browser-backup.json');
 await page.locator('#restoreFile').setInputFiles('build/browser-backup.json');
 await page.locator('#previewRestore').click();await page.waitForFunction(()=>!document.getElementById('stageRestore').disabled);
 await page.locator('#stageRestore').click();await page.waitForFunction(()=>document.getElementById('restoreFeedback').textContent.startsWith('Restore saved.'));
 if(!(await page.request.get(base+'/api/backup/previous')).ok())throw Error('Previous backup missing');
 await page.locator('#cancelRestore').click();await page.waitForFunction(()=>document.getElementById('restoreFeedback').textContent.startsWith('Restore cancelled.'));
 if((await(await page.request.get(base+'/api/config/status')).json()).restore_pending)throw Error('Restore not cancelled');
 if(errors.length)throw Error(errors.join('; '));
}
