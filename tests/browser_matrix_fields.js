async (page) => {
 await page.request.post('http://localhost:18788/api/login',{headers:{Authorization:'Bearer local-browser-test-token-not-for-deployment'},data:{}});
 await page.reload();
 await page.waitForFunction(()=>getComputedStyle(document.getElementById('cv')).opacity==='0');
 await page.locator('#sege0').click();
 for(const [suffix,value] of [['s','2'],['e','30'],['sY','3'],['eY','20']]) {
  await page.locator('#seg0'+suffix).fill('');
  await page.waitForTimeout(700);
  if(await page.locator('#seg0'+suffix).inputValue()!=='') throw Error('Empty reset '+suffix);
  await page.locator('#seg0'+suffix).fill(value);
 }
 await page.waitForTimeout(1500);
 await page.locator('#seg0eY').press('Enter');
 await page.waitForTimeout(1000);
 let s=await(await page.request.get('http://localhost:18788/json/state')).json();
 if(s.seg[0].start!==2||s.seg[0].stop!==30||s.seg[0].startY!==3||s.seg[0].stopY!==20) throw Error('Matrix bounds not saved');
 await page.locator('#seg0eY').fill('26');
 await page.locator('#seg0eY').press('Enter');
 s=await(await page.request.get('http://localhost:18788/json/state')).json();
 if(s.seg[0].stopY!==20) throw Error('Out of bounds accepted');
 await page.locator('#seg0eY').fill('25');
 await page.locator('#seg0e').fill('40');
 await page.locator('#seg0eY').press('Enter');
 await page.waitForTimeout(1000);
 s=await(await page.request.get('http://localhost:18788/json/state')).json();
 if(s.seg[0].stop!==40||s.seg[0].stopY!==25) throw Error('Matrix maximum rejected');
}
