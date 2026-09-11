async(page)=>{
 const base='http://localhost:18787';
 const denied=await page.request.post(base+'/api/layout',{data:{}});
 if(denied.status()!==401)throw Error('Layout changes accepted without browser access');
 await page.request.post(base+'/api/login',{headers:{Authorization:'Bearer local-browser-test-token-not-for-deployment'},data:{}});
 await page.goto(base+'/settings');
 await page.locator('#configuration > details > summary').first().click();
 await page.locator('#readFppLayout').click();
 await page.locator('#fppLayoutItems input').first().waitFor();
 if(!(await page.locator('#fppLayoutItems').textContent()).includes('Porch'))throw Error('FPP API model missing');
 await page.locator('#fppLayoutItems input').first().check();
 const before=await(await page.request.get(base+'/api/config')).text();
 await page.locator('#previewFppLayout').click();
 await page.waitForFunction(()=>!document.getElementById('saveFppLayout').disabled);
 if(await(await page.request.get(base+'/api/config')).text()!==before)throw Error('Preview changed saved configuration');
}
