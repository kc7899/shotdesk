const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const {webcrypto}=require('node:crypto');
// LAN HTTP exposes getRandomValues but no randomUUID. Execute the production helper.
const source=fs.readFileSync('static/app.js','utf8').split('\n')[0];
const context=vm.createContext({crypto:{getRandomValues:array=>webcrypto.getRandomValues(array)}});
vm.runInContext(source,context);
const ids=Array.from({length:1000},()=>vm.runInContext('newResourceId()',context));
assert.equal(new Set(ids).size,ids.length);
for(const id of ids)assert.match(id,/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
console.log('PASS resource IDs on LAN HTTP without crypto.randomUUID');
