async(page)=>{
 const base='http://localhost:18787';
 await page.unroute('**/api/status');
 await page.setViewportSize({width:1280,height:900});
 const firstRun=await(await page.request.get(base+'/api/status')).json();firstRun.setup_complete=false;
 await page.route('**/api/status',route=>route.fulfill({json:firstRun}));
 await page.goto(base+'/');await page.waitForURL('**/settings');
 await page.locator('#wled-navigation').click();await page.waitForURL('**/?view=lights*');
 await page.waitForFunction(()=>getComputedStyle(document.getElementById('cv')).opacity==='0');
 await page.locator('#wled-config-navigation').click();await page.waitForURL('**/settings');
 await page.unroute('**/api/status');
 await page.goto(base+'/');
 await page.waitForFunction(()=>getComputedStyle(document.getElementById('cv')).opacity==='0');
 if(!page.url().includes('/#Colors'))throw Error('Configured device redirected to setup');
 for(const width of [1280,390]){
  await page.setViewportSize({width,height:900});
  await page.locator('#wled-theme-toggle').hover();
  const tip=page.locator('.tooltip.visible').last();await tip.waitFor({state:'visible'});
  const box=await tip.boundingBox();if(!box||box.x<0||box.y<0||box.x+box.width>width||box.y+box.height>900)throw Error('Tooltip outside viewport');
  if(!(await tip.textContent()).includes('mode'))throw Error('Missing theme tooltip text');
  await page.waitForTimeout(300);
  await page.screenshot({path:'build/navigation-'+width+'.png'});
  await page.mouse.move(width-1,899);
 }
 await page.locator('#wled-config-navigation').click();await page.waitForURL('**/settings');
 if(await page.locator('#wled-navigation svg').count()!==1)throw Error('Missing WLED navigation icon');
 await page.screenshot({path:'build/navigation-settings.png'});
}
