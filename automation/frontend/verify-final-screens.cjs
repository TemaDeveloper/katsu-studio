const {chromium}=require(process.env.KATSU_PLAYWRIGHT_PATH || 'playwright');
const fs=require('node:fs');
const path=require('node:path');
const assert=require('node:assert/strict');
(async()=>{
 const out=path.resolve(__dirname,'../evidence');
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{
  const page=await browser.newPage();
  const base='http://127.0.0.1:8850';
  const projects=await page.request.get(base+'/api/projects').then(r=>r.json());
  const episode=projects.find(p=>p.imported);
  const samples=[];
  for(const [name,size] of [['desktop',{width:1360,height:960}],['mobile',{width:390,height:844}]]){
   await page.setViewportSize(size);
   for(const [screen,url,heading] of [['studio','/','My videos.'],['create','/new','An idea goes in.'],['episode','/projects/'+episode.id,episode.title],['settings','/settings','Make it yours.']]){
    await page.goto(base+url);
    await page.locator('main h1').waitFor();
    await page.evaluate(()=>document.fonts.ready);
    await page.waitForFunction(()=>Array.from(document.images).filter(i=>i.loading!=='lazy').every(i=>i.complete));
    assert(!(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth)));
    await page.screenshot({path:path.join(out,`final-${screen}-${name}.png`)});
    if(screen==='studio')samples.push(await page.locator('h1').evaluate(el=>({viewport:innerWidth,font:getComputedStyle(el).fontFamily,loaded:document.fonts.check('650 32px "Fredoka Variable"')})));
    if(screen==='episode'){
     await page.getByRole('tab',{name:'Images (120)'}).click();
     await page.locator('.scene-gallery').scrollIntoViewIfNeeded();
     await page.waitForFunction(()=>Array.from(document.querySelectorAll('.scene-card img')).slice(0,innerWidth<650?1:3).every(i=>i.complete&&i.naturalWidth>0));
     await page.screenshot({path:path.join(out,`final-gallery-${name}.png`)});
    }
    if(screen==='settings'){
     await page.getByLabel('Narrator',{exact:true}).scrollIntoViewIfNeeded();
     await page.screenshot({path:path.join(out,`final-settings-voice-${name}.png`)});
    }
   }
  }
  assert(samples.every(s=>s.font.includes('Fredoka')&&s.loaded));
  fs.writeFileSync(path.join(out,'final-screens.json'),JSON.stringify({viewports:[[1360,960],[390,844]],overflow:false,displayFont:samples,projects:projects.length},null,2));
  console.log('Final desktop/mobile screenshots captured with loaded display font, decoded gallery images and no horizontal overflow.');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
