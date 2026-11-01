const uiContext=()=>{const c={};require('vm').runInNewContext(require('fs').readFileSync('static/i18n.js','utf8'),c);return c.ShotdeskI18n.text};
const assert=require('assert'),fs=require('fs'),vm=require('vm');
const code=fs.readFileSync('static/app.js','utf8').split('\n').find(l=>l.startsWith('function renderLLMSettings()'));
function render(project){const el={};const context={ui:uiContext(),p:project,llmCatalog:{default:'Qwen3.8-27B',models:[{id:'Qwen3.8-27B',status:'online'},{id:'Qwen3.6-35B-A3B-Uncensored',status:'offline'}]},$:()=>el,esc:s=>String(s)};vm.runInNewContext(code+';renderLLMSettings()',context);return el;}
let el=render({});assert.equal(el.value,'Qwen3.8-27B');assert(el.innerHTML.includes('Qwen3.8-27B · 在线'));assert(el.innerHTML.includes('Qwen3.6-35B-A3B-Uncensored · 未启动/加载中'));assert(!el.innerHTML.includes('disabled'));
el=render({llm_model:'Qwen3.6-35B-A3B-Uncensored'});assert.equal(el.value,'Qwen3.6-35B-A3B-Uncensored');
console.log('PASS all configured LLMs visible, offline selection retained, default Qwen3.8');
