async(page)=>{
 const base='http://localhost:18787';
 await page.request.post(base+'/api/login',{headers:{Authorization:'Bearer local-browser-test-token-not-for-deployment'},data:{}});
 await page.request.post(base+'/json/state',{data:{on:true,transition:0,seg:{fx:27,pal:0,col:[[255,160,0],[8,255,0],[0,0,0]]}}});
 await page.setViewportSize({width:1280,height:1000});
 await page.goto(base+'/');
 await page.waitForFunction(()=>getComputedStyle(document.getElementById('cv')).opacity==='0');
 if(await page.locator('#linux-active-palette').count())throw Error('Unwanted preview above wheel');
 const settings=await page.context().newPage();await settings.goto(base+'/settings');
 const names=await(await page.request.get(base+'/json/palettes')).json();
 for(const id of [57,6,11]){
  await page.locator('#pallist .lstI[data-id="'+id+'"]').click();
  await page.waitForFunction(id=>document.querySelector('#pallist .selected')?.dataset.id===String(id),id);
  await settings.waitForFunction(name=>document.getElementById('summaryPalette').textContent===name,names[id]);
  await settings.waitForFunction(()=>document.querySelector('#summaryPalette .summary-palette-strip')?.style.background.includes('gradient'));
  const state=await(await page.request.get(base+'/json/state')).json();
  if(state.seg[0].pal!==id)throw Error('Palette click did not reach runtime');
  if(state.seg[0].col[0][0]===255&&state.seg[0].col[0][1]===160)throw Error('Palette selection left stale effect colors');
  const main=await page.locator('#pallist .selected .lstIprev').evaluate(el=>el.style.background);
  const summary=await settings.locator('.summary-palette-strip').first().evaluate(el=>el.style.background);
  if(!main.includes('gradient')||!summary.includes('gradient'))throw Error('Missing palette colors');
 }
 // A different client changes the palette; both open pages must follow it.
 await page.request.post(base+'/json/state',{data:{seg:{pal:57}}});
 await page.waitForFunction(()=>document.querySelector('#pallist .selected')?.dataset.id==='57');
 await settings.waitForFunction(()=>document.getElementById('summaryPalette').textContent==='Candy');
 await page.locator('#picker').scrollIntoViewIfNeeded();
 await page.screenshot({path:'build/palette-overview-desktop.png'});
 await settings.screenshot({path:'build/palette-overview-summary.png'});
 await page.setViewportSize({width:390,height:844});
 for(const theme of ['light','dark']){
  await page.evaluate(theme=>window.wledTheme.set(theme),theme);
  await page.locator('#picker').scrollIntoViewIfNeeded();
  await page.screenshot({path:'build/palette-overview-'+theme+'.png'});
 }
 // Dynamic palettes follow their source color slots; custom previews load too.
 await page.request.post(base+'/json/state',{data:{seg:{pal:2,col:[[0,0,255],[0,255,0],[0,0,0]]}}});
 await settings.waitForFunction(()=>document.querySelector('#summaryPalette .summary-palette-strip')?.style.background.includes('0, 0, 255'));
 await page.request.post(base+'/api/palettes',{data:{slot:0,palette:[0,'FF0000',255,'0000FF']}});
 await page.request.post(base+'/json/state',{data:{seg:{pal:200}}});
 await settings.waitForFunction(()=>document.getElementById('summaryPalette').textContent==='Custom palette 0'&&document.querySelector('#summaryPalette .summary-palette-strip')?.style.background.includes('gradient'));
 await page.waitForFunction(()=>document.querySelector('#pallist .selected')?.dataset.id==='200'&&document.querySelector('#pallist .selected .lstIprev').style.background.includes('gradient'));
 await page.request.post(base+'/api/palettes',{data:{slot:0,palette:[0,'00FF00',255,'00FFFF']}});
 await page.waitForFunction(()=>document.querySelector('#pallist .selected .lstIprev').style.background.includes('0, 255, 0'));
 await settings.waitForFunction(()=>document.querySelector('#summaryPalette .summary-palette-strip')?.style.background.includes('0, 255, 0'));
 await settings.close();
}
