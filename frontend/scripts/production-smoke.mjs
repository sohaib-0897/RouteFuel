import { chromium } from '@playwright/test'
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import assert from 'node:assert/strict'
const base=process.env.ROUTEFUEL_BASE_URL||'http://127.0.0.1:8003'
const output='../artifacts/routefuel-production'
mkdirSync(output,{recursive:true})
for(const path of ['/','/health/','/api/docs/','/api/schema/']){
 const response=await fetch(base+path);assert.equal(response.status,200,path)
}
const browser=await chromium.launch({headless:true,args:['--enable-unsafe-swiftshader']})
const page=await browser.newPage({viewport:{width:1440,height:900}})
const errors=[]
page.on('pageerror',e=>errors.push(e.message))
page.on('console',m=>{if(m.type()==='error')errors.push(m.text())})
await page.addInitScript(()=>{
 window.__qa={cls:0,longTasks:[],lcp:0}
 new PerformanceObserver(list=>{for(const e of list.getEntries())if(!e.hadRecentInput)window.__qa.cls+=e.value}).observe({type:'layout-shift',buffered:true})
 new PerformanceObserver(list=>{for(const e of list.getEntries())window.__qa.longTasks.push(e.duration)}).observe({type:'longtask',buffered:true})
 new PerformanceObserver(list=>{for(const e of list.getEntries())window.__qa.lcp=e.startTime}).observe({type:'largest-contentful-paint',buffered:true})
})
await page.goto(base,{waitUntil:'networkidle'})
await page.evaluate(()=>document.fonts.ready)
await page.screenshot({path:output+'/hero.png'})
const performanceResult=await page.evaluate(()=>({
 ...window.__qa,
 resources:performance.getEntriesByType('resource').filter(e=>e.name.includes('/static/routefuel/')).map(e=>({name:e.name.split('/').pop(),bytes:e.transferSize,duration:e.duration})),
 canvases:document.querySelectorAll('canvas').length,
}))
const timings=[]
for(const [name,finish] of [['dallas-la','Los Angeles, CA'],['dallas-austin','Austin, TX']]){
 if(name!=='dallas-la')await page.getByRole('button',{name:/Plan another route/}).click()
 await page.getByRole('textbox',{name:'FROM'}).fill('Dallas, TX')
 await page.getByRole('textbox',{name:'TO'}).fill(finish)
 const responsePromise=page.waitForResponse(r=>r.url().endsWith('/api/v1/route/')&&r.request().method()==='POST',{timeout:110000})
 const started=Date.now()
 await page.getByRole('button',{name:'PLAN ROUTE'}).click()
 const response=await responsePromise
 assert.equal(response.status(),200)
 const plan=await response.json()
 const seconds=(Date.now()-started)/1000
 const baseline=JSON.parse(readFileSync('../artifacts/routefuel-baseline/'+name+'.json','utf8'))
 for(const key of ['route','fuel_stops','initial_fueling','vehicle','fuel','optimization','warnings'])assert.deepEqual(plan[key],baseline[key],key)
 await page.getByTestId('route-map').waitFor({timeout:40000})
 await page.waitForFunction(()=>document.querySelector('[data-testid="route-map"]')?.dataset.drawn==='true',{timeout:30000})
 await page.waitForTimeout(1000)
 assert.equal(await page.locator('.fuel-marker').count(),plan.fuel_stops.length)
 assert.equal(await page.locator('canvas').count(),1)
 await page.screenshot({path:output+'/'+name+'.png',fullPage:true})
 const mapResponse=await fetch(base+plan.map_url);assert.equal(mapResponse.status,200)
 timings.push({route:name,seconds,cost:plan.fuel.estimated_fuel_cost_usd,stops:plan.fuel_stops.length,exactRegressionMatch:true})
}
assert.deepEqual(errors,[])
const result={endpoints:'root,health,swagger,schema and fallback map: 200',timings,consoleErrors:errors,performance:performanceResult}
writeFileSync(output+'/report.json',JSON.stringify(result,null,2))
console.log(JSON.stringify({...result,performance:{cls:performanceResult.cls,lcpMs:performanceResult.lcp,longTasks:performanceResult.longTasks.length,maxLongTaskMs:Math.max(0,...performanceResult.longTasks),canvases:performanceResult.canvases}},null,2))
await browser.close()
