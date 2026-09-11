async(page)=>{
 const base='http://localhost:18787';
 const sample=await(await page.request.get(base+'/json/si')).json();
 sample.state.on=true;sample.state.ps=7;sample.state.pl=-1;
 sample.state.seg[0].fx=0;sample.state.seg[0].col=[[255,0,0],[0,255,0],[0,0,255]];
 Object.assign(sample.info.fpp,{allowed:true,enabled:true,quiet:true,observer_healthy:true,show_owned:false,sources:[],fault:null});
 await page.route('**/presets.json',route=>route.fulfill({json:{'7':{n:'Evening glow'}}}));
 let offline=false;
 await page.route('**/json/si',route=>offline?route.fulfill({status:503,json:{error:'Test outage'}}):route.fulfill({json:sample}));
 await page.goto(base+'/settings');
 await page.waitForFunction(()=>document.getElementById('summaryPreset').textContent==='Evening glow');
 if(await page.locator('#summaryEffect').textContent()!=='Solid')throw Error('Effect name missing');
 for(const name of ['Red','Green','Blue'])if(!(await page.locator('#summaryColors').textContent()).includes(name))throw Error('Color missing '+name);
 await page.locator('#nightlight > summary').click();
 await page.locator('#nightMinutes').fill('123');
 sample.info.fpp.show_owned=true;sample.info.fpp.allowed=false;sample.info.fpp.sources=['fpp:playlist'];
 await page.waitForFunction(()=>document.getElementById('summaryStatus').textContent.includes('FPP controls'));
 if(await page.locator('#nightMinutes').inputValue()!=='123')throw Error('Summary changed draft');
 sample.info.fpp.observer_healthy=false;
 await page.waitForFunction(()=>document.getElementById('summaryStatus').textContent.includes('FPP status unknown'));
 Object.assign(sample.info.fpp,{observer_healthy:true,show_owned:false,sources:[],enabled:false});
 await page.waitForFunction(()=>document.getElementById('summaryStatus').textContent.includes('disabled'));
 Object.assign(sample.info.fpp,{enabled:true,allowed:true});sample.state.on=false;
 await page.waitForFunction(()=>document.getElementById('summaryStatus').textContent.includes('lights off'));
 offline=true;
 await page.waitForFunction(()=>document.getElementById('summaryStatus').textContent.includes('Offline'));
 offline=false;sample.state.on=true;
 await page.waitForFunction(()=>document.getElementById('summaryStatus').textContent.includes('WLED ambient'));
 for(const theme of ['light','dark']){
  await page.evaluate(theme=>window.wledTheme.set(theme),theme);
  for(const width of [1280,390]){
   await page.setViewportSize({width,height:900});
   const box=await page.locator('#lightingSummary').boundingBox();
   if(box.x<0||box.x+box.width>width)throw Error('Summary overflow');
   await page.locator('.wled-summary-header').screenshot({path:`build/summary-${theme}-${width}.png`});
  }
 }
}
