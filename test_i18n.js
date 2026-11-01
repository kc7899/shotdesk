const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync('static/i18n.js','utf8');
function context(language){const store=new Map([['shotdesk.uiLanguage',language]]),c={localStorage:{getItem:k=>store.get(k),setItem:(k,v)=>store.set(k,v)},location:{reload:()=>c.reloads++},reloads:0};vm.createContext(c);vm.runInContext(source,c);return c}
(async()=>{
 const en=context('en'),zh=context('zh'),t=en.ShotdeskI18n.text;
 assert.equal(t('生成全部视频'),'Generate all videos');assert.equal(zh.ShotdeskI18n.text('生成全部视频'),'生成全部视频');assert.equal(context('unknown').ShotdeskI18n.language,'zh');
 const name='场景 · 默认 <script>人物</script>',prompt='角色在场景中说：关闭';
 assert.equal(t`<b>标题</b>${name}<textarea>${prompt}</textarea>`,`<b>Title</b>${name}<textarea>${prompt}</textarea>`,'interpolated content is never translated');
 assert.equal(t('<option value="角色" data-kind="道具">角色</option>'),'<option value="角色" data-kind="道具">Character</option>','API enum values stay unchanged');
 const app=fs.readFileSync('static/app.js','utf8'),c={ShotdeskI18n:en.ShotdeskI18n,p:{assets:[{id:'actor',type:'角色',name:'场景',default_look_id:'look',looks:[{id:'look',name:'关闭',image:'/media/角色.png'}]}]},esc:s=>String(s),ui:t};vm.createContext(c);
 vm.runInContext(app.split('\n').find(x=>x.startsWith('function shotAssetPicker(')),c);
 const markup=c.shotAssetPicker({asset_ids:['actor'],character_looks:{actor:'look'}});
 assert.match(markup,/Character/);assert.match(markup,/>场景<\/span>/);assert.match(markup,/>关闭 · Default<\/option>/);assert.match(markup,/data-asset-toggle="actor"/);assert.match(markup,/value="" selected/);assert.match(markup,/\/media\/角色.png/);
 const rendered=JSON.stringify(c.p);assert(rendered.includes('"type":"角色"'));assert(rendered.includes('"name":"关闭"'));
 let saveDone=false;en.ShotdeskBeforeLocaleChange=async()=>{saveDone=true};await en.ShotdeskI18n.setLanguage('zh');assert(saveDone);assert.equal(en.reloads,1);assert.equal(en.localStorage.getItem('shotdesk.uiLanguage'),'zh');
 en.alert=()=>{};en.document={querySelector:()=>({})};en.ShotdeskBeforeLocaleChange=async()=>{throw Error('save failed')};await en.ShotdeskI18n.setLanguage('en');assert.equal(en.reloads,1,'failed save prevents reload');assert.equal(en.ShotdeskI18n.language,'zh');
 console.log('PASS zh/en labels, persistence, save-before-switch, unchanged user content, asset enums and bindings');
})().catch(e=>{console.error(e);process.exitCode=1});
