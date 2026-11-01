const fs=require('fs'),vm=require('vm'),assert=require('assert');
(async()=>{
 let release;const saving=new Promise(r=>release=r),calls=[];
 const ctx={p:{id:'p',script:'script',assets:[]},jobs:[],activeTask:j=>['queued','running','cancelling'].includes(j.status),render:()=>{},save:()=>saving,api:async(path)=>{calls.push(path);return {id:'j',kind:'text',target:'project',target_id:'project',operation:'extract_assets',status:'queued'}},refreshQueue:async()=>{},toggleQueue:()=>{},toast:()=>{},console};
 ctx.running=(id,kind)=>ctx.jobs.find(j=>j.target_id===id&&j.kind===kind&&ctx.activeTask(j));vm.createContext(ctx);vm.runInContext(fs.readFileSync('static/stage-actions.js','utf8'),ctx);
 for(const operation of ['generate_script','extract_assets','generate_storyboard']){
  ctx.jobs=[{kind:'text',target:'project',target_id:'project',operation,status:'running'}];assert(ctx.projectTextBusy());
  for(const op of ['generate_script','extract_assets','generate_storyboard'])assert.equal(ctx.projectTaskLabel(op,'ready','busy'),op===operation?'busy':'ready');
 }
 ctx.jobs=[];const first=ctx.submitProjectText('extract_assets','extract-assets',{},'queued');assert(ctx.projectTextBusy());assert.equal(ctx.projectTaskLabel('extract_assets','ready','busy'),'busy');assert.equal(ctx.projectTaskLabel('generate_storyboard','ready','busy'),'ready');
 assert.equal(await ctx.submitProjectText('generate_storyboard','storyboard',{},'queued'),false);release();await first;assert.equal(calls.length,1);assert.equal(ctx.projectTaskLabel('extract_assets','ready','busy'),'busy');
 ctx.jobs[0].status='completed';assert.equal(ctx.projectTextBusy(),false);assert.equal(ctx.projectTaskLabel('extract_assets','ready','busy'),'ready');
 console.log('PASS operation-specific labels, pending feedback and duplicate submission guard');
})().catch(e=>{console.error(e);process.exit(1)});
