const uiContext=()=>{const c={};require('vm').runInNewContext(require('fs').readFileSync('static/i18n.js','utf8'),c);return c.ShotdeskI18n.text};
const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict');
const source=fs.readFileSync('static/app.js','utf8');
const code=source.slice(source.indexOf('async function bootstrapWorkspace(){'),source.indexOf('\nbootstrapWorkspace();'));
const context=vm.createContext({ui:uiContext(),assert});
vm.runInContext(`
let p=null,videoCapabilities={},assetPromptPresets={},opened=false;const started=[];
function setProjectLoading(){}async function list(){return [{id:'project'}]}
async function api(path){return path==='video-modes'?{strategies:{}}:{identity:'portrait'}}
function loadModelCatalog(){started.push('models');return new Promise(()=>{})}
function loadLLMCatalog(){started.push('llm');return new Promise(()=>{})}
function checkGenerationConnection(){started.push('health');return new Promise(()=>{})}
const localStorage={getItem:()=> 'project'};
async function open(id){assert.equal(id,'project');opened=true}
function renderEmptyProjects(){}function toast(message){throw Error(message)}
${code}
globalThis.run=async()=>{await bootstrapWorkspace();assert.equal(opened,true);assert.deepEqual(started,['models','llm','health']);assert.equal(assetPromptPresets.identity,'portrait')};
`,context);
context.run().then(()=>console.log('PASS project startup does not wait for pending model catalog, LLM list or health requests')).catch(e=>{console.error(e);process.exitCode=1});
