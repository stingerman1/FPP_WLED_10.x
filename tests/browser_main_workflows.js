async(page)=>{
 await page.setViewportSize({width:1280,height:1000});
 const base='http://localhost:18787';
 await page.request.post(base+'/api/login',{headers:{Authorization:'Bearer local-browser-test-token-not-for-deployment'},data:{}});
 // Count the upstream selected-effect timer across state notifications.
 await page.addInitScript(()=>{if(window.qaIntervalPatched)return;window.qaIntervalPatched=true;window.qaIntervals=0;const old=window.setInterval;window.setInterval=function(fn,...args){if(fn.name==='setSelectedEffectPosition')window.qaIntervals++;return old.call(this,fn,...args);};});
 await page.reload();
 await page.waitForFunction(()=>getComputedStyle(document.getElementById('cv')).opacity==='0');
 for(const [button,hash] of [['buttonNl','#ambient-lighting'],['buttonSr','#ambient-lighting'],['buttonSync','#network']]) {
  await page.locator('#'+button).click();
  if(!page.url().endsWith('/settings'+hash))throw Error('Wrong route '+button);
  await page.goto(base+'/');
  await page.waitForFunction(()=>getComputedStyle(document.getElementById('cv')).opacity==='0');
 }
 await page.locator('#fxlist .lstI[data-id="1"]').click();
 await page.waitForFunction(()=>document.querySelector('#fxlist .selected')?.dataset.id==='1');
 await page.locator('#pallist .lstI[data-id="6"]').click();
 await page.waitForFunction(()=>document.querySelector('#pallist .selected')?.dataset.id==='6');
 await page.evaluate(()=>makePUtil());
 await page.locator('#p0txt').fill('QA browser preset');
 await page.locator('#p0id').fill('3');
 await page.evaluate(()=>saveP(0,false));
 await page.waitForTimeout(1200);
 const presets=await(await page.request.get(base+'/presets.json')).json();
 if(presets['3']?.n!=='QA browser preset')throw Error('UI preset save failed');
 await page.evaluate(()=>requestJson({ps:1}));
 await page.waitForTimeout(1000);
 if((await(await page.request.get(base+'/json/state')).json()).ps!==1)throw Error('Preset recall failed');
 await page.evaluate(()=>makePlUtil());
 await page.locator('#p0txt').fill('QA browser playlist');
 await page.locator('#p0id').fill('4');
 await page.evaluate(()=>saveP(0,true));
 await page.waitForTimeout(1000);
 if(!(await(await page.request.get(base+'/presets.json')).json())['4']?.playlist)throw Error('Playlist save failed');
 if(await page.evaluate(()=>window.qaIntervals)!==1)throw Error('Timer accumulated');
 await page.setViewportSize({width:390,height:844});
 await page.evaluate(()=>window.wledTheme.set('light'));
 await page.screenshot({path:'output/playwright/qa-main-light.png'});
 await page.evaluate(()=>window.wledTheme.set('dark'));
 await page.screenshot({path:'output/playwright/qa-main-dark.png'});
}
