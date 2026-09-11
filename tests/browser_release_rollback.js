async(page)=>{
 const fs=await import('node:fs/promises'), os=await import('node:os'), path=await import('node:path'), cp=await import('node:child_process');
 const root=await fs.mkdtemp(path.join(os.tmpdir(),'wled-release-browser-'));
 let server;
 try {
  await fs.copyFile('page-loader.php',path.join(root,'page-loader.php'));
  for(const pageName of ['settings.php','lights.php'])await fs.copyFile(pageName,path.join(root,pageName));
  for(const name of ['old','new']){
   const release=path.join(root,'build/releases',name);await fs.mkdir(path.join(release,'pages'),{recursive:true});
   await fs.mkdir(path.join(release,'web'));
   await fs.writeFile(path.join(release,'release.json'),'{"format":1}');
   // The historical failure: old summary code requires a heading removed by
   // newer PHP. Both pages and assets must follow the selected snapshot.
   await fs.writeFile(path.join(release,'pages/settings.php'),`<!doctype html><body>${name==='old'?'<h1>Old title</h1>':''}<main id="summary"></main><script src="/summary.js"></script>`);
   await fs.writeFile(path.join(release,'web/summary.js'),name==='old'?`document.querySelector('h1').before(document.createElement('aside'));document.querySelector('#summary').textContent='old';`:`document.querySelector('#summary').textContent='new';`);
   await fs.writeFile(path.join(release,'pages/lights.php'),`<!doctype html><p id="lighting">${name}</p>`);
  }
  await fs.writeFile(path.join(root,'router.php'),`<?php header('Cache-Control: no-store'); if ($_SERVER['REQUEST_URI']==='/summary.js') { clearstatcache(true); header('Content-Type: text/javascript'); readfile(__DIR__.'/build/current/web/summary.js'); return; } return false;`);
  const current=path.join(root,'build/current');await fs.symlink('releases/new',current);
  server=cp.spawn('php',['-S','127.0.0.1:18890','router.php'],{cwd:root,stdio:'ignore'});
  for(let i=0;i<50;i++){try{if((await fetch('http://127.0.0.1:18890/settings.php')).ok)break;}catch{}await new Promise(r=>setTimeout(r,100));}
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  for(const selected of ['new','old','new']){
   await fs.unlink(current);await fs.symlink('releases/'+selected,current);
   await page.goto('http://127.0.0.1:18890/settings.php');
   await page.waitForFunction(name=>document.querySelector('#summary').textContent===name,selected);
   await page.goto('http://127.0.0.1:18890/lights.php');
   if(await page.locator('#lighting').textContent()!==selected)throw Error('Wrong lighting release');
  }
  if(errors.length)throw Error(errors.join('; '));
 }finally{
  if(server){server.kill();await new Promise(resolve=>server.once('exit',resolve));}
  await fs.rm(root,{recursive:true,force:true});
 }
}
