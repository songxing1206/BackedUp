const fs=require('fs'),assert=require('assert');
const html=fs.readFileSync('web/index.html','utf8'),code=fs.readFileSync('web/automatic-review.js','utf8'),app=fs.readFileSync('web/app.js','utf8');
assert.doesNotMatch(html,/id="scope"|先检查前 3 处引用/);assert.match(html,/id="review-mode"/);assert.match(html,/默认检查全部引用/);assert.match(html,/id="token-budget"/);assert.match(html,/id="request-budget"/);
assert.doesNotMatch(code,/location_limit:|\$\('scope'\)/);assert.match(html,/id="token-budget"><option value="" selected>不限制/);assert.match(html,/id="request-budget"><option value="" selected>不限制/);
assert.match(code,/max_requests:.*request-budget.*:null/);assert.match(code,/token_budget:.*token-budget.*:null/);
assert.match(app,/processing_seconds/);assert.match(code,/处理耗时/);
console.log('Full-run default, explicit deep mode and per-run budget controls are wired.');
