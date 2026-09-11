async(page)=>{
 const base='http://localhost:18787';
 await page.setViewportSize({width:1280,height:1000});
 await page.request.post(base+'/api/login',{headers:{Authorization:'Bearer local-browser-test-token-not-for-deployment'},data:{}});
 await page.goto(base+'/');
 await page.waitForFunction(()=>getComputedStyle(document.getElementById('cv')).opacity==='0');
 await page.evaluate(()=>makePUtil());
 await page.locator('#p0txt').fill('Draft kept');
 await page.locator('#p0id').fill('10');
 await page.route('**/json/state',async route=>{
  if(route.request().method()==='POST') await route.fulfill({status:422,json:{error:'QA rejected preset'}}); else await route.continue();
 });
 await page.evaluate(()=>saveP(0,false));
 await page.waitForFunction(()=>document.getElementById('linux-preset-feedback')?.textContent.includes('QA rejected preset'));
 if(await page.locator('#p0txt').inputValue()!=='Draft kept')throw Error('Draft lost');
 if(await page.evaluate(()=>!!pJson[10]))throw Error('Rejected save added phantom preset');
 await page.unroute('**/json/state');
 await page.evaluate(()=>saveP(0,false));
 await page.waitForFunction(()=>pJson[10]?.n==='Draft kept');
 if(!(await(await page.request.get(base+'/presets.json')).json())['10'])throw Error('Retry not saved');
 // Rejected delete must keep authoritative catalog entry.
 await page.route('**/json/state',route=>route.fulfill({status:409,json:{error:'QA cannot delete'}}));
 await page.evaluate(()=>window.wledSavePreset({pdel:10}));
 if(!await page.evaluate(()=>!!pJson[10]))throw Error('Rejected delete removed preset');
 await page.unroute('**/json/state');
 await page.evaluate(()=>window.wledSavePreset({pdel:10}));
 if(await page.evaluate(()=>!!pJson[10]))throw Error('Delete did not update catalog');
}
