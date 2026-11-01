const assert=require('assert'),fs=require('fs'),vm=require('vm');
const source=fs.readFileSync('static/app.js','utf8');
const code=source.split('\n').filter(line=>line.startsWith('function videoModelsFor(')||line.startsWith('async function loadModelCatalog(')).join('\n');
const catalog={images:[],videos:[{id:'local',modes:['reference'],max_references:4},{id:'cloud-seedance',modes:['reference','first_frame'],max_references:30}],strategies:{reference:{models:['local','cloud-seedance']},first_frame:{models:['cloud-seedance']}}};
const context=vm.createContext({api:async()=>catalog,refreshModelSelectors(){},p:null,ui:x=>x,toast:message=>{throw Error(message)}});
vm.runInContext(`let modelCatalog={},models=[],videoCapabilities={strategies:{reference:{models:['local']}}};function strategy(mode){return videoCapabilities.strategies[mode]}\n${code}\nglobalThis.check=async()=>{await loadModelCatalog();return {refs:videoModelsFor('reference'),first:videoModelsFor('first_frame')}};function canonicalVideoModel(x){return x}`,context);
context.check().then(result=>{assert.deepEqual(Array.from(result.refs),['local','cloud-seedance']);assert.deepEqual(Array.from(result.first),['cloud-seedance']);console.log('PASS saved cloud models immediately refresh compatible model choices; local models retained')}).catch(error=>{console.error(error);process.exitCode=1});
