async(page)=>{
 const base='http://localhost:18787';
 await page.setViewportSize({width:1280,height:1000});
 await page.request.post(base+'/api/login',{headers:{Authorization:'Bearer local-browser-test-token-not-for-deployment'},data:{}});
 await page.request.post(base+'/api/command',{data:{operation:'ambient-enable'}});
 await page.goto(base+'/');
 await page.waitForFunction(async()=>{const r=await fetch('/api/status');return (await r.json()).allowed;});
 const initial=await page.request.post(base+'/json/state',{data:{on:true,transition:0,seg:{fx:27,pal:0}}});
 if(!initial.ok())throw Error('Seed state rejected');
 await page.waitForFunction(()=>getComputedStyle(document.getElementById('cv')).opacity==='0');
 const state=async()=>await(await page.request.get(base+'/json/state')).json();
 const choose=async id=>{
  await page.locator('#pallist .lstI[data-id="'+id+'"]').click();
  await page.waitForFunction(id=>selectedPal===id,id);
  return (await state()).seg[0].col;
 };
 const candy=await choose(57);
 if(JSON.stringify(candy)!==JSON.stringify([[0,0,117,0],[125,37,139,0],[243,242,23,0]]))throw Error('Candy colors were not loaded: '+JSON.stringify(candy));
 // Selecting a circle selects the editing target without changing lights.
 await page.locator('#csl1').click();
 if(JSON.stringify((await state()).seg[0].col)!==JSON.stringify(candy))throw Error('Selecting a slot changed its color');
 // Exercise the native quick-color -> wheel -> setColor path for that slot.
 await page.evaluate(()=>pC('#00ff00'));
 await page.waitForFunction(()=>selectedPal===4&&document.getElementById('csl1').dataset.g==='255');
 let edited=(await state()).seg[0];
 if(JSON.stringify(edited.col[1])!=='[0,255,0,0]'||edited.pal!==4)throw Error('Edited color not used by editable palette');
 if(JSON.stringify(edited.col[0])!==JSON.stringify(candy[0]))throw Error('Editing Bg changed Fx');
 await page.request.post(base+'/json/state',{data:{psave:20,n:'Profile QA'}});
 const ocean=await choose(9);
 if(JSON.stringify(ocean)===JSON.stringify(edited.col))throw Error('New palette retained edited colors');
 await choose(57);
 if(JSON.stringify((await state()).seg[0].col)!==JSON.stringify(candy))throw Error('Reselecting profile did not restore colors');
 await page.request.post(base+'/json/state',{data:{ps:20}});
 await page.waitForFunction(()=>selectedPal===4);
 if(JSON.stringify((await state()).seg[0].col)!==JSON.stringify(edited.col))throw Error('Preset lost edited colors');
 await page.reload();await page.waitForFunction(()=>getComputedStyle(document.getElementById('cv')).opacity==='0');
 if(await page.locator('#linux-active-palette').count())throw Error('Above-wheel view remains');
 await page.locator('#picker').scrollIntoViewIfNeeded();
 await page.screenshot({path:'build/profile-colors.png'});
}
