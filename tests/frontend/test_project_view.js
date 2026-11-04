const uiContext=()=>{const c={};require('vm').runInNewContext(require('fs').readFileSync('static/i18n.js','utf8'),c);return c.ShotdeskI18n.text};
const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict');
const source=fs.readFileSync('static/app.js','utf8');
const code=source.slice(source.indexOf('function rememberProjectView('),source.indexOf('function target('));
const context=vm.createContext({ui:uiContext(),console,assert});
vm.runInContext(`
let p,tab='story',selected=null,jobs=[],assetCategory='角色',assetSelected=null,projectOpening=false,projectOpenRevision=0,dirty=false;
const entries=new Map([['shotdesk:view:project',JSON.stringify({tab:'assets',assetCategory:'角色',assetSelected:'actor'})]]);
const localStorage={getItem:k=>entries.get(k),setItem:(k,v)=>entries.set(k,v)};
const requests=new Map();function api(path){return new Promise(resolve=>requests.set(path,resolve))}
async function save(){}function captureBase(){}const loadingLabel={};const elements={'#pageLoading':{hidden:false,querySelector:()=>loadingLabel},'#main':{setAttribute(){}},'#projects':{options:[]}};const $=key=>elements[key];const esc=x=>String(x);const document={activeElement:null};function toast(){}let renders=[];
function render(){renders.push({id:p.id,tab});rememberProjectView()}
${code}
globalThis.run=async()=>{
 const opening=open('project');await Promise.resolve();
 requests.get('projects/project')({id:'project',shots:[],assets:[{id:'actor',type:'角色'}]});await Promise.resolve();await Promise.resolve();
 assert.equal(p.id,'project','ready project should render before jobs');assert.equal(tab,'assets');
 assert.equal(projectOpening,true);
 // A queue response arriving here must not render or persist default tab.
 if(p&&!projectOpening){tab='story';render()}
 assert.equal(JSON.parse(entries.get('shotdesk:view:project')).tab,'assets');
 requests.get('projects/project/jobs?view=summary')([]);await opening;
 assert.equal(tab,'assets');assert.equal(assetSelected,'actor');assert.equal(renders.length,2);
 // Competing project opens cannot restore an older late response.
 const older=open('older');await Promise.resolve();const newer=open('newer');await Promise.resolve();
 requests.get('projects/newer')({id:'newer',assets:[],shots:[]});requests.get('projects/newer/jobs?view=summary')([]);await newer;
 requests.get('projects/older')({id:'older',assets:[],shots:[]});requests.get('projects/older/jobs?view=summary')([]);await older;
 assert.equal(p.id,'newer');assert.equal(projectOpening,false);
};`,context);
context.run().then(()=>console.log('PASS project renders before delayed jobs without losing asset tab; latest project open wins')).catch(e=>{console.error(e);process.exitCode=1});
