const fs=require('fs'),vm=require('vm'),assert=require('assert');
const code=fs.readFileSync('web/app.js','utf8').split('function el')[0];
const context={};vm.createContext(context);vm.runInContext(code,context);
assert.equal(context.sourceAttachmentLabel('available'),'已加载');
assert.equal(context.sourceAttachmentLabel('unreadable'),'PDF 不可读');
assert.equal(context.sourceAttachmentLabel('missing'),'PDF 缺失');
assert.equal(vm.runInContext('labels.unmatched',context),'PDF 缺失或尚未匹配');
assert.equal(vm.runInContext('labels.missing_attachment',context),'PDF 缺失');
console.log('Source attachment labels: available, unreadable and missing passed.');
