async(page)=>{
 const base='http://localhost:18787';
 // Serve the installed FPP logo for the direct-runtime fixture's FPP origin.
 await page.route('http://localhost/images/redesign/fpp-logo.svg',async route=>route.fulfill({contentType:'image/svg+xml',body:'<svg xmlns="http://www.w3.org/2000/svg" width="32" height="28"><text x="0" y="20" fill="white">FPP</text></svg>'}));
 for(const path of ['/','/settings','/login']){
  await page.goto(base+path);
  await page.waitForFunction(()=>document.getElementById('fpp-navigation')?.querySelector('img').naturalWidth>0);
  if(await page.locator('#fpp-navigation').getAttribute('href')!=='http://localhost/index.php')throw Error('FPP link retained runtime port');
  for(const width of [1280,390,320]){
   await page.setViewportSize({width,height:900});
   const link=await page.locator('#fpp-navigation').boundingBox();
   if(!link||link.x<0||link.x+link.width>width)throw Error('Menu link off screen');
  }
 }
 await page.goto(base+'/');
 await page.waitForFunction(()=>getComputedStyle(document.getElementById('cv')).opacity==='0');
 await page.screenshot({path:'build/fpp-navigation-mobile.png'});
 // FPP wrapper must retain only its own navigation.
 await page.evaluate(()=>{
  document.getElementById('fpp-navigation').remove();
  const wrapper=document.createElement('div');wrapper.id='fpp-wled-settings';document.body.append(wrapper);
  wledAddFPPNavigation();
 });
 if(await page.locator('#fpp-navigation').count())throw Error('Duplicate navigation in FPP wrapper');
}
