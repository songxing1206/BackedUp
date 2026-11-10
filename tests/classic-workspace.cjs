const assert=require('assert'),fs=require('fs');
const h=fs.readFileSync('web/index.html','utf8'),css=fs.readFileSync('web/workspace-classic.css','utf8');
assert(h.includes('class="brand"')&&h.includes('id="history-open"')&&h.includes('id="open-data"'));
assert(!h.includes('class="app-sidebar"'));assert(h.includes('/workspace-classic.css'));
for(const id of ['folder-files','model-open','run','review-intent','token-budget','request-budget']) { if(id!=='review-intent') assert(h.includes('id="'+id+'"')); }
assert(css.includes('.check-summary-line')&&css.includes('.history-panel'));console.log('Classic workspace contracts passed');

for(const color of ['green','yellow','red','gray'])assert(css.includes('.citation-nav-item.'+color+'{'));
assert(!h.includes('class="intent-field"'));assert(!h.includes('<i>3</i> 选择检查方式'));
