async(page)=>{
 const base='http://localhost:18789';const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(base+'/plugin.php?plugin=FPP_WLED_10.x&page=lights.php');
 for(const mode of ['light','dark','auto']){
  await page.locator('[data-wled-mode="'+mode+'"]').click();
  const expected=mode==='auto'?'light':mode;
  await page.waitForFunction(t=>document.documentElement.dataset.bsTheme===t&&document.getElementById('fpp-wled-frame')?.contentDocument?.documentElement.dataset.bsTheme===t,expected);
  if(await page.locator('#wled-theme-modes [aria-pressed="true"]').count()!==1)throw Error('Multiple selected modes');
 }
 await page.locator('[data-wled-mode="dark"]').click();
 await page.locator('#wled-config-navigation').click();
 await page.waitForFunction(()=>document.documentElement.dataset.bsTheme==='dark');
 if(await page.locator('[data-wled-theme]').count())throw Error('Duplicate appearance selector');
 await page.reload();await page.waitForFunction(()=>document.documentElement.dataset.bsTheme==='dark');
 await page.locator('[data-wled-mode="auto"]').click();
 await page.waitForFunction(()=>document.documentElement.dataset.bsTheme==='light');
 for(const width of [1280,390,320]){
  await page.setViewportSize({width,height:900});
  const box=await page.locator('#wled-theme-modes').boundingBox();if(box.x<0||box.x+box.width>width)throw Error('Appearance overflow');
 }
 await page.goto('http://localhost:18787/?view=lights');
 await page.locator('[data-wled-mode="auto"]').click();
 await page.emulateMedia({colorScheme:'light'});await page.waitForFunction(()=>document.documentElement.dataset.bsTheme==='light');
 await page.emulateMedia({colorScheme:'dark'});await page.waitForFunction(()=>document.documentElement.dataset.bsTheme==='dark');
 await page.locator('[data-wled-mode="light"]').click();
 await page.emulateMedia({colorScheme:'dark'});await page.waitForFunction(()=>document.documentElement.dataset.bsTheme==='light');
 await page.setViewportSize({width:1280,height:900});
 await page.screenshot({path:'build/theme-three-modes.png'});
 if(errors.length)throw Error(errors.join('; '));
}
