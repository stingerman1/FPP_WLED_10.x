async(page)=>{
 const base='http://localhost:18789';
 await page.goto(base+'/plugin.php?plugin=FPP_WLED_10.x&page=lights.php');
 await page.waitForFunction(()=>document.getElementById('fpp-wled-frame')?.contentDocument?.documentElement.dataset.fppEmbedded==='true');
 const frame=page.frameLocator('#fpp-wled-frame');
 await frame.locator('#picker').waitFor();
 await page.evaluate(()=>localStorage.setItem('fpp-wled-appearance','dark'));
 for(const theme of ['light','dark']){
  await page.evaluate(theme=>document.documentElement.dataset.bsTheme=theme,theme);
  await page.waitForFunction(theme=>document.getElementById('fpp-wled-frame').contentDocument.documentElement.dataset.bsTheme===theme,theme);
 }
 if(await frame.locator('#wled-theme-toggle').isVisible())throw Error('Embedded controls can override host theme');
 await frame.locator('#buttonSync').click();
 await page.waitForURL('**/plugin.php?plugin=FPP_WLED_10.x&page=settings.php#network');
 if(await page.locator('iframe').count())throw Error('Config nested inside WLED');
 if(await page.evaluate(()=>document.documentElement.dataset.bsTheme)!=='light')throw Error('Plugin preference overrode host theme');
 if(await page.locator('#fpp-wled-page-navigation img').getAttribute('alt')!=='Pixel Monkey')throw Error('Missing logo');
 await page.locator('#wled-navigation').click();await page.waitForURL('**/plugin.php?plugin=FPP_WLED_10.x&page=lights.php');
 for(const width of [1280,390,320]){
  await page.setViewportSize({width,height:900});
  if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1))throw Error('Host horizontal overflow');
 }
}
