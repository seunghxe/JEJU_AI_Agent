const fs = require('node:fs'), vm = require('node:vm'), assert = require('node:assert/strict');
const source = fs.readFileSync(__dirname+'/../static/app.js', 'utf8').replace(/init\(\);\s*$/, '');
function el() { return {children:[],style:{},className:'',textContent:'',appendChild(x){this.children.push(x);},querySelector(){return this;}}; }
const nodes = Object.fromEntries(['#liveDot','#liveLabel','#heroChip','#connList'].map(k=>[k,el()]));
Object.defineProperty(nodes['#connList'],'innerHTML',{set(value){this.html=value;this.children=Array.from({length:5},el);}});
const ctx=vm.createContext({window:{addEventListener(){}},document:{querySelector:q=>nodes[q],createElement:el}});
vm.runInContext(source,ctx);
const hub={state:'on',loaded:{weekly:346,wait:16,daily:340,floating:43},configured_datasets:['weekly','wait','daily','floating'],details:{weekly:{rows:8464,raw_unique:476,matched:346,cached:true}},errors:{}};
ctx.hub=hub;
assert.equal(vm.runInContext('hubStatusSummary(hub)',ctx),'연동됨 · 데이터 4종');
assert.equal(vm.runInContext('hubStatusSummary({...hub,mode:"snapshot"})',ctx),'저장 자료 사용 · 데이터 4종');
assert.equal(vm.runInContext('hubStatusSummary({state:"ready"})',ctx),'데이터 준비 중');
assert.equal(vm.runInContext('hubStatusSummary({state:"error"})',ctx),'연결 확인 필요 · 과거 기록 사용');
assert.match(vm.runInContext('hubStatusSummary({loaded:{weekly:2},errors:{daily:"failed"}})',ctx),/^일부 연동/);
vm.runInContext('renderStatus({live:{state:"off",text:"미연결"},gemini:{state:"off",text:"미설정"},kakao:{state:"off",text:"미설정"},datahub:hub})',ctx);
assert.ok(nodes['#connList'].html.includes('연동됨 · 데이터 4종'));
assert.ok(!nodes['#connList'].html.includes('8464'));
const detail=nodes['#connList'].children[2].children[0];
assert.equal(detail.open,undefined); // Native details stays collapsed by default.
assert.equal(detail.children.length,5);
assert.ok(detail.children[1].textContent.includes('8464'));
console.log('OK: compact hub status; details collapsed; counts retained; loading/error/partial states');
