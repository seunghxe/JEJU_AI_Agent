// Run with node tests/check_garage_ui.cjs (no npm modules required).
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const code=fs.readFileSync(__dirname+'/../static/app.js','utf8').replace(/init\(\);\s*$/,'');
const handlers={},sent=[];
const box={style:{},scrollHeight:40,value:'',addEventListener:(k,fn)=>handlers[k]=fn,setCustomValidity(s){this.message=s;},reportValidity(){}};
const form={addEventListener:(k,fn)=>handlers[k]=fn,requestSubmit:()=>handlers.submit({preventDefault(){}})};
const run=vm.createContext({document:{querySelector:()=>box},window:{addEventListener(){}},box,form,send:s=>sent.push(s)});
vm.runInContext(code+';wireComposer(box,form,send);',run);
const message='협재에서 충전하고 싶어.\n'+'이 조건도 고려해 줘. '.repeat(40);
box.value=message;handlers.keydown({key:'Enter',shiftKey:true});
handlers.keydown({key:'Enter',isComposing:true});
assert.equal(sent.length,0);form.requestSubmit();assert.equal(sent[0],message);assert.equal(box.value,'');
box.value='새 질문';assert.equal(sent[0],message);box.value='가'.repeat(2001);form.requestSubmit();assert.equal(sent.length,1);assert.equal(box.value.length,2001);
box.value=' ';form.requestSubmit();assert.equal(sent.length,1);
assert.equal(vm.runInContext('new Set(Object.values(carPhotos).map(x=>x[0])).size',run),6);
run.response={ok:false,query:message+'<script>',clarify:true,battery:24,summary:'어느 지역인가요?'};
const detail=vm.runInContext('resultHtml(response)',run);assert.ok(detail.includes(message+'&lt;script&gt;'));assert.ok(detail.includes('내 요청 보기'));
console.log('OK: multiline submit, clear, IME, empty/length validation, original text, six model photos');
