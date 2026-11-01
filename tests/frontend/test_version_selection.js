const uiContext=()=>{const c={};require('vm').runInNewContext(require('fs').readFileSync('static/i18n.js','utf8'),c);return c.ShotdeskI18n.text};
// Execute the real frontend save/refresh guard with delayed mocked HTTP.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync(__dirname+'/../../static/app.js','utf8');
const resources=source.slice(source.indexOf('function frontendResources('),source.indexOf('function audioAssets('));
const code=source.slice(source.indexOf('async function save(){'),source.indexOf('async function list()'));
const context=vm.createContext({ui:uiContext(),structuredClone,clearTimeout,console});
vm.runInContext(`
let p={id:'project',updated:1,assets:[],shots:[{id:'s',image:'V1'}]},mediaBase={s:{image:'V1'}},dirty=false,saving=Promise.resolve(),savePending=0,editRevision=0,deletingProjectId=null,projectOpening=false;
const indicator={},$=()=>indicator,document={activeElement:null,querySelectorAll:()=>[]};function change(){};
let server=structuredClone(p),calls=[];
async function api(path,body){
 calls.push(structuredClone(body));
 await Promise.resolve();
 const incoming=body.shots[0].image,base=body._media_base.s.image;
 if(incoming!==base)server.shots[0].image=incoming;
 return structuredClone(server);
}
${resources}
${code}
async function choose(image){p.shots[0].image=image;dirty=true;editRevision++;return save()}
globalThis.run=async()=>{
 const a=choose('V2'),b=choose('V1');await Promise.all([a,b]);
 if(server.shots[0].image!=='V1')throw Error('queued selection reverted');
 if(calls[1]._media_base.s.image!=='V2')throw Error('save used stale baseline');
 await choose('V2');if(server.shots[0].image!=='V2')throw Error('V2 not saved');
 const revision=editRevision;await choose('V1');
 if(canApplyProject('project',revision,{updated:10}))throw Error('late refresh overwrites newer edit');
 if(canApplyProject('project',editRevision,{updated:0}))throw Error('older server response accepted');
 if(!canApplyProject('project',editRevision,{updated:10}))throw Error('fresh refresh rejected');
 dirty=true;if(canApplyProject('project',editRevision,{updated:10}))throw Error('dirty state overwritten');dirty=false;
 savePending=1;if(canApplyProject('project',editRevision,{updated:10}))throw Error('in-flight save overwritten');
};`,context);
context.run().then(()=>console.log('PASS rapid V2→V1→V2, queued save baselines, delayed refresh, dirty and pending guards')).catch(e=>{console.error(e);process.exitCode=1});
