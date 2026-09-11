async(page)=>{
 const base='http://localhost:18787';
 await page.request.post(base+'/api/login',{headers:{Authorization:'Bearer local-browser-test-token-not-for-deployment'},data:{}});
 await page.request.post(base+'/api/command',{data:{operation:'ambient-enable',source:'qa:buttons'}});
 await page.request.post(base+'/json/state',{data:{on:true,nl:{on:false}}});
 await page.goto(base+'/settings');
 await page.waitForFunction(()=>document.getElementById('lightOff').textContent==='Turn lights off'&&!document.getElementById('lightOff').disabled);
 await page.locator('#lightOff').click();
 await page.waitForFunction(()=>document.getElementById('lightOff').textContent==='Turn lights on');
 await page.route('**/json/state',async route=>route.request().method()==='POST'?route.fulfill({status:409,json:{error:'QA rejected'}}):route.continue());
 await page.locator('#lightOff').click();
 await page.waitForFunction(()=>document.getElementById('lightingStatus').textContent.includes('QA rejected'));
 if(await page.locator('#lightOff').textContent()!=='Turn lights on')throw Error('Rejected change flipped button');
 await page.unroute('**/json/state');
 await page.locator('#lightOff').click();
 await page.waitForFunction(()=>document.getElementById('lightOff').textContent==='Turn lights off');
 await page.locator('#startNightlight').click();
 await page.waitForFunction(()=>document.getElementById('startNightlight').textContent==='Stop nightlight');
 // Stopping must not validate an unfinished draft of the next nightlight.
 await page.locator('#nightMinutes').fill('');
 await page.locator('#startNightlight').click();
 await page.waitForFunction(()=>document.getElementById('startNightlight').textContent==='Start nightlight');
 if(await page.locator('#stopNightlight').count())throw Error('Duplicate nightlight button');
 await page.locator('#ownershipDetails > summary').click();
 await page.locator('#ambientToggle').click();
 await page.waitForFunction(()=>document.getElementById('ambientToggle').textContent==='Allow background lighting');
 if(await page.locator('[data-op^="ambient-"]').count()!==1)throw Error('Duplicate background controls');
 await page.locator('#ambientToggle').click();
 await page.waitForFunction(()=>document.getElementById('ambientToggle').textContent==='Stop background lighting');
 for(const theme of ['light','dark']){
  await page.evaluate(theme=>window.wledTheme.set(theme),theme);
  const colors=await page.locator('#lightOff').evaluate(button=>{
   const s=getComputedStyle(button);return {fg:s.color,bg:s.backgroundColor,radius:s.borderRadius,border:s.borderWidth};
  });
  const luminance=color=>color.match(/[\d.]+/g).slice(0,3).map(Number).map(v=>v/255).map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4).reduce((n,v,i)=>n+v*[.2126,.7152,.0722][i],0);
  const values=[luminance(colors.fg),luminance(colors.bg)].sort((a,b)=>b-a);
  if((values[0]+.05)/(values[1]+.05)<4.5||parseFloat(colors.radius)===0||parseFloat(colors.border)===0)throw Error('Unreadable or missing button outline: '+theme);
  await page.locator('#ambient-lighting').screenshot({path:'build/buttons-'+theme+'.png'});
 }
 await page.goto(base+'/');
 await page.waitForFunction(()=>document.querySelector('#buttonPower .tab-label')?.textContent==='Turn off');
 await page.locator('#buttonPower').click();
 await page.waitForFunction(()=>document.querySelector('#buttonPower .tab-label')?.textContent==='Turn on');
 await page.locator('#buttonPower').click();
 await page.waitForFunction(()=>document.querySelector('#buttonPower .tab-label')?.textContent==='Turn off');
}
