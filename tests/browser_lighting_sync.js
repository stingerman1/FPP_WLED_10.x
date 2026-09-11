async(page)=>{
 const base='http://localhost:18787';
 await page.request.post(base+'/api/login',{headers:{Authorization:'Bearer local-browser-test-token-not-for-deployment'},data:{}});
 await page.request.post(base+'/api/command',{data:{operation:'ambient-enable'}});
 await page.goto(base+'/settings');
 await page.waitForFunction(()=>!document.getElementById('applyLighting').disabled);
 // An external WLED client changes the state while Settings remains open.
 await page.request.post(base+'/json/state',{data:{on:true,bri:90,seg:{fx:1,pal:6,col:[[0,0,255],[0,255,0],[255,0,255]]}}});
 await page.waitForFunction(()=>document.getElementById('lightEffect').value==='1'&&document.getElementById('lightPalette').value==='6'&&document.getElementById('lightPrimary').value==='#0000ff'&&document.getElementById('lightThird').value==='#ff00ff');
 if(await page.locator('#lightBrightness').inputValue()!=='90')throw Error('Brightness stale');
 // Preserve one edited field; untouched fields still follow the other client.
 await page.locator('#lightTransition').fill('2.5');
 await page.request.post(base+'/json/state',{data:{bri:120,seg:{fx:0,pal:0,col:[[255,0,0],[0,0,0],[0,255,0]]}}});
 await page.waitForFunction(()=>document.getElementById('lightEffect').value==='0'&&document.getElementById('lightPrimary').value==='#ff0000');
 if(await page.locator('#lightTransition').inputValue()!=='2.5')throw Error('External state overwrote draft');
 await page.locator('#discardLighting').click();
 await page.waitForFunction(()=>document.getElementById('discardLighting').hidden);
 await page.locator('#lightPalette').selectOption('6');
 await page.locator('#lightThird').fill('#00ffff');
 await page.locator('#applyLighting').click();
 await page.waitForFunction(()=>document.getElementById('lightingStatus').textContent==='Lighting updated.'&&document.getElementById('discardLighting').hidden);
 const state=await(await page.request.get(base+'/json/state')).json();if(state.seg[0].pal!==6||state.seg[0].col[2][1]!==255||state.seg[0].col[2][2]!==255)throw Error('Palette/third color not applied');
 await page.route('**/api/preview',route=>route.fulfill({json:{allowed:true,count:2,width:2,height:1,stride:1,pixels:[[0,0,0,255],[1,0,255,0]]}}));
 await page.waitForFunction(()=>document.getElementById('summaryLiveColors').textContent.includes('Blue')&&document.getElementById('summaryLiveColors').textContent.includes('Green'));
 if(!(await page.locator('#summaryColors').textContent()).includes('Red'))throw Error('Configured and rendered colors conflated');
 await page.unroute('**/api/preview');
 await page.screenshot({path:'build/lighting-sync.png'});
}
