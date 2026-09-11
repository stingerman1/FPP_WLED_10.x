async(page)=>{
 const base='http://localhost:18787';
 await page.request.post(base+'/api/login',{headers:{Authorization:'Bearer local-browser-test-token-not-for-deployment'},data:{}});
 await page.goto(base+'/?view=lights');
 await page.waitForFunction(()=>getComputedStyle(document.getElementById('cv')).opacity==='0');
 for(const width of [1280,390,320]){
  await page.setViewportSize({width,height:900});await page.waitForTimeout(300);
  const geometry=await page.evaluate(()=>{
   const rect=s=>document.querySelector(s).getBoundingClientRect();
   return {content:rect('.container').bottom,footer:rect('#linux-footer').top,notice:rect('#linux-status-notice').bottom,bar:rect('#bot').top,barHeight:rect('#bot').height,mode:rect('#wled-theme-modes').right};
  });
  if(geometry.content>geometry.footer+1)throw Error('Content under footer '+JSON.stringify(geometry));
  if(geometry.barHeight&&Math.abs(geometry.notice-geometry.bar)>1)throw Error('Detached status '+JSON.stringify(geometry));
  if(geometry.mode>width)throw Error('Theme overflow');
  await page.evaluate(()=>document.querySelectorAll('.tabcontent').forEach(e=>e.scrollTop=e.scrollHeight));
  await page.screenshot({path:'build/footer-'+width+'.png'});
 }
}
