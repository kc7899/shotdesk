const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync('static/app.js','utf8'),nodes={image_model:{}};
const ctx={modelCatalog:{images:[{id:'Qwen-Image-2.1-Turbo',display_name:'Qwen Image 2.1 · Viggle 六步 · 1K'},{id:'Qwen-Image-2.1-Official-Turbo-8step-2K',display_name:'Qwen Image 2.1 · 官方八步 Turbo · 2K'}]},p:{image_model:'Qwen-Image-2.1-Turbo'},$:s=>nodes[s.slice(1)],esc:String,renderVideoSettings:()=>{}};
vm.createContext(ctx);vm.runInContext(source.slice(source.indexOf('function imageModelLabel('),source.indexOf('async function loadModelCatalog(')),ctx);
ctx.refreshModelSelectors();assert.equal(nodes.image_model.value,'Qwen-Image-2.1-Turbo');assert(nodes.image_model.innerHTML.includes('Viggle 六步'));assert(nodes.image_model.innerHTML.includes('官方八步'));assert(nodes.image_model.innerHTML.includes('value="Qwen-Image-2.1-Official-Turbo-8step-2K"'));
assert.equal(ctx.imageModelLabel('unknown'),'unknown');console.log('PASS model display names preserve API IDs and current selection');
