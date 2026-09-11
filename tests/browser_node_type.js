async(page)=>{
 await page.goto('http://localhost:18787/?view=lights');
 await page.waitForFunction(()=>getComputedStyle(document.getElementById('cv')).opacity==='0');
 await page.evaluate(()=>{
  populateNodes({ndc:2,name:'Test receiver'},{nodes:[{name:'FPP04',ip:'192.0.2.4',type:255,vid:2609110},{name:'Native',ip:'192.0.2.5',type:32,vid:2609110}]});
 });
 const nodes=await page.locator('#kn').textContent();
 if(!nodes.includes('FPP04')||!nodes.includes('FPP')||!nodes.includes('ESP32'))throw Error('Incorrect node labels');
 if(await page.evaluate(()=>btype(127))!=='FPP'||await page.evaluate(()=>btype(0))!=='?')throw Error('Unknown type misclassified');
}
