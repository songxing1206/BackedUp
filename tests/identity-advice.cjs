const fs=require('fs'),vm=require('vm'),assert=require('assert');
const code=fs.readFileSync('web/automatic-review.js','utf8');
const ctx={};vm.createContext(ctx);vm.runInContext(code.slice(0,code.indexOf('function jumpToCheckLocation')),ctx);
assert.equal(ctx.checkErrorAdvice('书目信息不完整').action,'metadata');
assert(ctx.checkErrorAdvice('书目信息不完整').next.includes('（作者，年份）'));
assert(!ctx.checkErrorAdvice('唯一映射').next.includes('无需自行填写字符位置'));
assert(!code.includes('下一步：'));
console.log('Identity advice passed.');
