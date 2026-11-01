var ui=globalThis.ShotdeskI18n?.text||((s,...v)=>Array.isArray(s)?s.reduce((out,x,i)=>out+x+(i<v.length?v[i]:''),''):String(s));
/* Stage-specific actions and explicit bulk clearing. */
const projectTextPending=new Map();let workspaceClearBusy=false;
function projectTextTask(operation){return jobs.find(j=>j.target==='project'&&j.operation===operation&&activeTask(j))}
function projectTextBusy(){return projectTextPending.has(p.id)||!!running('project','text')}
function projectTaskLabel(operation,ready,busy){return projectTextPending.get(p.id)===operation||projectTextTask(operation)?busy:ready}
async function submitProjectText(operation,path,body,message){
if(projectTextBusy())return false;const pid=p.id;projectTextPending.set(pid,operation);render();
try{await save();const job=await api('projects/'+pid+'/'+path,body);if(p?.id===pid){jobs.push(job);render()}await refreshQueue();toggleQueue(true);toast(message);return true}
catch(e){toast(e.message);return false}
finally{projectTextPending.delete(pid);if(p?.id===pid)render()}
}
function assetsWorkflow(){return ui`<section class="asset-workflow"><div class="stage-toolbar"><div><b>准备参考资产</b><p class="sub">从已审核剧本提取，确认人物、造型、场景与道具后再生成分镜。</p></div><div class="stage-buttons"><button class="primary" id="extractAssets" ${projectTextBusy()||!p.script?.trim()?'disabled':''}>${projectTaskLabel('extract_assets',ui('从剧本提取资产'),ui('正在提取资产…'))}</button><button id="toStoryboard">下一步：分镜 →</button><button class="quiet-danger" id="clearAssets" title="有未结束任务时不可清空；清空前会确认并保留备份" ${!p.assets.length||projectTextBusy()||jobs.some(activeTask)?'disabled':''}>清空全部资产</button></div></div>${assetExtractionPanel()}</section>`}
let storyboardCheckReport=null;
function storyboardReportMarkup(){if(!storyboardCheckReport||storyboardCheckReport.pid!==p.id)return '';const r=storyboardCheckReport.result;return ui`<div class="storyboard-report" role="status"><b>${r.ok?ui('规划检查通过'):ui('发现待处理问题')} · ${r.checked} 镜</b>${r.missing_prompts?ui`<p>${r.missing_prompts} 镜待编写提示词</p>`:''}${r.issues.map(x=>`<button class="storyboard-issue" data-check-shot="${esc(x.shot_id)}">${x.index}. ${esc(x.title)}：${esc([...x.errors,...x.warnings].join('；'))}</button>`).join('')}<small>基于检查时内容；不检查实际图片或视频质量。</small></div>`}
function storyboardButton(){const busy=projectTextBusy(),empty=!p.shots.length,missing=p.shots.some(s=>!(s.video_prompt||'').replace(/^Duration:.*$/gm,'').trim());return ui`<div class="storyboard-actions oneclick-storyboard"><button class="primary" id="generateStoryboard" title="自动规划、关联资源、编写提示词并检查；可恢复的写作问题在内部处理" ${busy||!p.script?.trim()?'disabled':''}>${projectTaskLabel('generate_video_prompts',projectTaskLabel('generate_storyboard',missing?ui('✧ 继续完成分镜'):ui('✧ 生成分镜'),ui('正在生成分镜…')),ui('正在生成分镜…'))}</button><details class="storyboard-advanced"><summary>更多操作</summary><div><button id="generateStoryboardPlan" ${busy||!p.script?.trim()?'disabled':''}>仅重新规划</button><button id="writeVideoPrompts" ${busy||empty?'disabled':''}>仅编写提示词</button><button id="checkStoryboard" ${busy||empty?'disabled':''}>检查分镜</button><label class="sub"><input type="checkbox" id="rewriteAllPrompts"> 重写已有提示词</label></div></details><a class="sub" href="/api/storyboard-skill?project_id=${encodeURIComponent(p.id)}" target="_blank" rel="noopener">分镜规范 ↗</a></div>${storyboardReportMarkup()}`}
async function clearWorkspace(kind){
if(workspaceClearBusy)return;const pid=p.id;workspaceClearBusy=true;let locked=false;
try{
 await save();const latest=await api('projects/'+pid);if(p?.id!==pid)return;
 const count=latest[kind].length;if(!count){toast(ui('当前没有可清空的')+(kind==='assets'?ui('资产'):ui('分镜')));return}
 const explanation=kind==='assets'?ui`清空“${latest.name}”的全部 ${count} 项参考资产（含人物造型、声线与音频资产）？\n\n保留剧本、分镜及已生成的镜头媒体，解除资产关联；提示词中的 @引用转为普通文字。旧提取候选失效。`:ui`清空“${latest.name}”的全部 ${count} 个分镜及镜头历史关联？\n\n保留剧本和参考资产，取消当前合片入口。`;
 if(!confirm(explanation+ui('\n\n会保留清空前的数据备份，原媒体文件不删除。')))return;
 for(const el of document.querySelectorAll('#main,header,#tabs'))el.inert=true;locked=true;
 const result=await api('projects/'+pid+'/clear-'+kind,{confirm_name:latest.name,expected_updated:latest.updated});
 if(p?.id===pid){p=result.project;if(kind==='shots')selected=null;else assetSelected=null;captureBase();render()}
 toast(ui`已清空 ${result.count} ${kind==='assets'?ui('项资产'):ui('个分镜')}，清空前数据已备份`)
}catch(e){toast(ui('未清空：')+e.message)}
finally{if(locked)for(const el of document.querySelectorAll('#main,header,#tabs'))el.inert=false;workspaceClearBusy=false}
}
