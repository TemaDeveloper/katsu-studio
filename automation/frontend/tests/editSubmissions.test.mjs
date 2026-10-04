import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import ts from 'typescript';

const source = await readFile(new URL('../src/editSubmissions.ts', import.meta.url), 'utf8');
const compiled = ts.transpileModule(source, {compilerOptions:{module:ts.ModuleKind.ES2022}}).outputText;
const {getEditSubmission,clearEditSubmission,readProjectSubmission,getProjectSubmission} = await import('data:text/javascript;base64,'+Buffer.from(compiled).toString('base64'));
const storage = () => {const data = new Map(); return {getItem:key=>data.get(key)??null,setItem:(key,value)=>data.set(key,value),removeItem:key=>data.delete(key)}};

test('a lost response and page reload reuse the same paid edit identity', () => {
 const saved=storage(),body=JSON.stringify({instructions:'Larger headline',base_fingerprint:'original'});
 const sent=getEditSubmission(saved,'episode-thumbnail',body);
 assert.equal(getEditSubmission(saved,'episode-thumbnail',body).key,sent.key);
 assert.equal(getEditSubmission(saved,'episode-thumbnail',body).body,body);
});
test('a changed instruction or source image starts a new edit',()=>{
 const saved=storage();
 const first=getEditSubmission(saved,'episode-thumbnail','{"instructions":"Bigger","base_fingerprint":"one"}');
 const changed=getEditSubmission(saved,'episode-thumbnail','{"instructions":"Smaller","base_fingerprint":"one"}');
 const newImage=getEditSubmission(saved,'episode-thumbnail','{"instructions":"Smaller","base_fingerprint":"two"}');
 assert.notEqual(changed.key,first.key);assert.notEqual(newImage.key,changed.key);
});
test('explicit discard allows a fresh preview while other editors retain their keys',()=>{
 const saved=storage(),first=getEditSubmission(saved,'scene-one','body'),other=getEditSubmission(saved,'scene-two','body');
 clearEditSubmission(saved,'scene-one');
 assert.notEqual(getEditSubmission(saved,'scene-one','body').key,first.key);
 assert.equal(getEditSubmission(saved,'scene-two','body').key,other.key);
});

test('new video submissions send a duration without a requested illustration count',()=>{
 const saved=storage(),request={topic:'Why do we want more?',target_seconds:180,budget_usd:20};
 const first=getProjectSubmission(saved,'project',request);
 assert.deepEqual(JSON.parse(first.body),request);
 assert.equal(readProjectSubmission(saved,'project').key,first.key);
 assert.equal(getProjectSubmission(saved,'project',request).key,first.key);
});
test('a pre-upgrade lost creation response preserves its original body and identity',()=>{
 const saved=storage(),body=JSON.stringify({topic:'Why do we want more?',target_seconds:480,scene_count:72,budget_usd:20});
 saved.setItem('project',JSON.stringify({key:'old-click',body}));
 const retry=getProjectSubmission(saved,'project',{topic:'Why do we want more?',target_seconds:480,budget_usd:20});
 assert.equal(retry.key,'old-click');assert.equal(retry.body,body);
});
test('changing the target minutes creates one fresh submission and drops the obsolete count',()=>{
 const saved=storage();
 saved.setItem('project',JSON.stringify({key:'old-click',body:JSON.stringify({topic:'Why do we want more?',target_seconds:480,scene_count:72,budget_usd:20})}));
 const request={topic:'Why do we want more?',target_seconds:300,budget_usd:20};
 const changed=getProjectSubmission(saved,'project',request);
 assert.notEqual(changed.key,'old-click');assert.deepEqual(JSON.parse(changed.body),request);
 assert.equal(getProjectSubmission(saved,'project',request).key,changed.key);
});
