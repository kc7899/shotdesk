const fs=require('fs'),vm=require('vm'),assert=require('assert');
const ctx={};vm.createContext(ctx);vm.runInContext(fs.readFileSync('static/segment-timing.js','utf8')+';globalThis.helper=ShotdeskSegmentTiming',ctx);
const script='🙂早晨\n甲等待。\n晚上\n甲等待。\n灯灭。',start=script.lastIndexOf('甲等待。'),row=ctx.helper.anchor(script,start,start+4,'b');
assert.equal(row.start,Array.from(script.slice(0,start)).length);assert.equal(row.end-row.start,4);assert.equal(ctx.helper.locate(script,row).start,row.start);assert.equal(ctx.helper.locate('引言\n'+script,row).start,row.start+3);assert.equal(ctx.helper.locate(script.replaceAll('甲等待。','甲离开。'),row),null);
assert.equal(ctx.helper.total({shots:[{timing_constraint_id:'b',timing_constraint_quote:row.quote,duration:15},{timing_constraint_id:'other',duration:120}]},row),15);
console.log('PASS segment timing selection: Unicode anchors, repeated text, re-location, stale source and scoped duration');
