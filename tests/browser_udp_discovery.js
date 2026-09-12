async(page)=>{
 const base='http://localhost:18787';
 await page.request.post(base+'/api/login',{headers:{Authorization:'Bearer local-browser-test-token-not-for-deployment'},data:{}});
 await page.goto(base+'/settings#network');
 await page.waitForFunction(()=>document.getElementById('networkStatus').textContent.includes('Discovery:'));
 const option=page.locator('#networkUdpDiscovery');
 if(await option.isChecked())throw Error('UDP discovery must default off');
 await option.check();
 await page.locator('#saveNetwork').click();
 await page.waitForFunction(()=>document.getElementById('networkFeedback').textContent.startsWith('Saved.'));
 let network=await(await page.request.get(base+'/api/network')).json();
 if(!network.config.udp_discovery||network.udp_discovery_active)throw Error('Opt-in should persist without bypassing the discovery master switch');
 await page.reload();
 await page.waitForFunction(()=>document.getElementById('networkUdpDiscovery').checked);
 await option.uncheck();
 await page.locator('#saveNetwork').click();
 await page.waitForFunction(()=>document.getElementById('networkFeedback').textContent.startsWith('Saved.'));
 network=await(await page.request.get(base+'/api/network')).json();
 if(network.config.udp_discovery||network.udp_discovery_active)throw Error('UDP opt-out not saved');
}
