const uiContext=()=>{const c={};require('vm').runInNewContext(require('fs').readFileSync('static/i18n.js','utf8'),c);return c.ShotdeskI18n.text};
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync('static/asset-extraction.js','utf8'),ctx={ui:uiContext(),esc:x=>String(x).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;')};vm.createContext(ctx);
vm.runInContext(source.slice(source.indexOf('function assetCoverageSummary('),source.indexOf('function assetExtractionPanel(')),ctx);
const job={result:{candidates:Array.from({length:5},()=>({type:'角色'}))}};
let html=ctx.assetCoverageSummary(job);assert(html.includes('人物 5 · 场景 0 · 道具 0'));assert(html.includes('建议重新提取'));
job.result.candidates.push({type:'场景'});job.result.coverage={empty_reasons:{道具:'没有必要道具 <img>'}};html=ctx.assetCoverageSummary(job);assert(html.includes('场景 1'));assert(html.includes('&lt;img&gt;'));assert(!html.includes('<img>'));
console.log('PASS extraction category counts, omitted category explanation and safe escaping');

vm.runInContext(source.slice(source.indexOf('function extractionWarnings('),source.indexOf('function assetExtractionPanel(')),ctx);assert(ctx.extractionWarnings({review_warnings:['白色或灰色 <img>']}).includes('&lt;img&gt;'));assert.equal(ctx.extractionWarnings({}),'');
