async(page)=>{
 const base='http://localhost:18787';
 await page.goto(base+'/');await page.evaluate(()=>localStorage.removeItem('fpp-wled-appearance'));
 await page.emulateMedia({colorScheme:'light'});await page.reload();
 await page.waitForFunction(()=>window.wledTheme&&document.documentElement.dataset.bsTheme==='dark');
 await page.locator('#wled-theme-toggle').click();
 await page.waitForFunction(()=>document.documentElement.dataset.bsTheme==='light');
 await page.reload();await page.waitForFunction(()=>window.wledTheme);
 if(await page.evaluate(()=>document.documentElement.dataset.bsTheme)!=='light')throw Error('Explicit light mode not preserved');
 await page.locator('#wled-theme-toggle').click();
 await page.goto(base+'/settings');
 await page.waitForFunction(()=>document.documentElement.dataset.bsTheme==='dark');
 await page.locator('[data-wled-theme]').selectOption('fpp');
 await page.waitForFunction(()=>document.documentElement.dataset.bsTheme==='light');
 await page.emulateMedia({colorScheme:'dark'});
 await page.waitForFunction(()=>document.documentElement.dataset.bsTheme==='dark');
 await page.locator('[data-wled-theme]').selectOption('dark');
 await page.emulateMedia({colorScheme:'light'});
 if(await page.evaluate(()=>document.documentElement.dataset.bsTheme)!=='dark')throw Error('System overrode explicit dark mode');
}
