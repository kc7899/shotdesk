const assert=require('assert'),vm=require('vm'),fs=require('fs');const ctx={};vm.createContext(ctx);vm.runInContext(fs.readFileSync('static/model-discovery.js','utf8'),ctx);const State=ctx.ShotdeskModelDiscovery;
let s=new State(),r=s.begin();s.accept(r,['only']);assert.equal(s.selected,'only');
s=new State();s.accept(s.begin(),['one','two']);assert.equal(s.selected,'');s.choose('two');s.accept(s.begin(),['one','two']);assert.equal(s.selected,'two');
s.reset('saved');s.accept(s.begin(),['other']);assert.equal(s.selected,'saved');assert(s.missing);
s.reset();let old=s.begin();s.invalidate();let latest=s.begin();s.accept(latest,['new']);assert.equal(s.accept(old,['old']),false);assert.equal(s.selected,'new');
s.reset();old=s.begin();s.choose('user-choice');s.accept(old,['user-choice','other']);assert.equal(s.selected,'user-choice');
s.reset('manual-id');r=s.begin();s.fail(r);assert.equal(s.selected,'manual-id');assert.equal(s.status,'unavailable');
s.reset();s.accept(s.begin(),['same','same','']);assert.equal(s.ids.length,1);assert.equal(s.selected,'same');
console.log('PASS discovery: single auto-select, multiple explicit choice, saved ID retention, stale responses ignored, manual fallback');
