async (page) => {
 await page.request.post('http://localhost:18787/api/login', {headers:{Authorization:'Bearer local-browser-test-token-not-for-deployment'},data:{}});
 await page.reload();
 await page.waitForFunction(()=>getComputedStyle(document.getElementById('cv')).opacity==='0');
 await page.locator('#sege0').click();
 await page.locator('#seg0nedit').click();
 // A paused user can leave any numeric field empty, then finish typing.
 for (const [suffix,value] of [['t','Porch'],['s','10'],['e','200'],['grp','2'],['spc','1'],['of','3']]) {
   const field=page.locator('#seg0'+suffix);
   if (!(await field.isVisible())) await page.evaluate(()=>document.querySelector('#seg0').classList.add('expanded'));
   await field.fill('');
   await page.waitForTimeout(1100);
   if(await field.inputValue()!=='') throw Error(suffix+' empty field reset');
   await field.fill(value);
   await page.waitForTimeout(1100);
   if(await field.inputValue()!==value) throw Error(suffix+' value reset');
 }
 // Unrelated updates must not discard the whole unsaved range/name.
 await page.request.post('http://localhost:18787/json/state',{data:{seg:{id:0,col:[[0,100,0]]}}});
 await page.waitForTimeout(1200);
 if(await page.locator('#seg0e').inputValue()!=='200') throw Error('Color update erased edit');
 await page.evaluate(()=>setSeg(0));
 await page.waitForTimeout(1000);
 const saved=await(await page.request.get('http://localhost:18787/json/state')).json();
 for (const [key,value] of Object.entries({n:'Porch',start:10,stop:200,grp:2,spc:1,of:3})) if(saved.seg[0][key]!==value) throw Error('Save failed '+key);
 for (const bad of ['', '0', '5', '1001', '20.5']) {
  await page.locator('#seg0e').fill(bad);
  await page.evaluate(()=>setSeg(0));
  const state=await(await page.request.get('http://localhost:18787/json/state')).json();
  if(state.seg[0].stop!==200 || state.seg.length!==1) throw Error('Invalid end changed lights');
  if(await page.locator('#seg0e').inputValue()!==bad) throw Error('Invalid draft was replaced');
 }
 await page.locator('#seg0e').fill('1000');
 await page.evaluate(()=>setSeg(0));
 await page.waitForTimeout(1000);
 if((await(await page.request.get('http://localhost:18787/json/state')).json()).seg[0].stop!==1000) throw Error('Maximum end rejected');
}
