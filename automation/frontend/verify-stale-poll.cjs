const {chromium}=require(process.env.KATSU_PLAYWRIGHT_PATH || 'playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
(async()=>{
 const evidence=path.resolve(__dirname,'../evidence');
 const {id}=JSON.parse(fs.readFileSync(path.join(evidence,'stale-poll-fixture.json')));
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{
  const page=await browser.newPage({viewport:{width:1360,height:960}});
  const base='http://127.0.0.1:8850';
  await page.goto(base+'/projects/'+id);
  await page.getByRole('link',{name:'Download video',exact:true}).waitFor();
  await page.getByRole('tab',{name:'Images (4)'}).click();
  let release,holdOnce=true,signal;
  const held=new Promise(r=>signal=r);
  await page.route('**/api/projects/'+id,async route=>{
   if(!holdOnce){await route.continue();return}
   holdOnce=false;
   const oldResponse=await route.fetch();
   await new Promise(r=>{release=r;signal()});
   await route.fulfill({response:oldResponse});
  });
  await held;
  await page.getByRole('button',{name:'Edit scene',exact:true}).first().click();
  await page.getByLabel('What should this image show?').fill('Regression fixture: a newly edited illustration. '+Date.now());
  await page.getByRole('button',{name:'Save changes',exact:true}).click();
  await page.getByRole('button',{name:'Continue production',exact:false}).waitFor();
  assert.equal(await page.getByRole('link',{name:'Download video',exact:true}).count(),0);
  release();
  await page.waitForTimeout(600);
  assert.equal(await page.getByRole('link',{name:'Download video',exact:true}).count(),0,'An older poll must not restore the invalidated video after a scene edit');
  fs.writeFileSync(path.join(evidence,'stale-poll-browser.json'),JSON.stringify({passed:true,project:id,oldCompletedResponseHeld:true,realSceneEdit:true,staleExportExcluded:true},null,2));
  console.log('Stale poll regression passed: a real scene edit remains current after an older completed-project response arrives.');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
