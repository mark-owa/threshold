const fs=require('fs'),crypto=require('crypto'),assert=require('assert');
const dir=require('path').join(__dirname, '../integrations/n8n/');
const files=['01_submit_refund.json','02_sync_outcome_to_hubspot.json'];
const workflows=files.map(f=>JSON.parse(fs.readFileSync(dir+f,'utf8')));
const AsyncFunction=Object.getPrototypeOf(async function(){}).constructor;
let count=0;
for(const w of workflows){
 const names=new Set(w.nodes.map(n=>n.name));
 for(const n of w.nodes) if(n.type.endsWith('.code')) new AsyncFunction('$json','$input','$',n.parameters.jsCode);
 for(const [from,conn] of Object.entries(w.connections)){
  assert(names.has(from));for(const branch of conn.main)for(const dest of branch)assert(names.has(dest.node));
 }
 assert(w.active===false);count++;
}
const nodes=Object.fromEntries(workflows.flatMap(w=>w.nodes).map(n=>[n.name,n]));
function run(name,json={},input={},lookup={}){
 let code=nodes[name].parameters.jsCode.replaceAll('REPLACE_WITH_THRESHOLD_ORG_UUID','org-123').replaceAll('REPLACE_WITH_HUBSPOT_PORTAL_ID','123').replaceAll('REPLACE_WITH_RESOLVED_STAGE_ID','4').replaceAll('REPLACE_WITH_REJECTED_STAGE_ID','5').replaceAll('REPLACE_WITH_THRESHOLD_WEBHOOK_URL','https://threshold.example.com/api/v1/webhooks/test').replaceAll('REPLACE_WITH_EXISTING_TEST_TICKET_ID','456');
 return new AsyncFunction('$json','$input','$',code).call({helpers:{getBinaryDataBuffer:async()=>Buffer.from(input.raw||'')}},json,{first:()=>input.item||{}},name=>({first:()=>({json:lookup[name]})}));
}
(async()=>{
 const intake=(await run('Demo Request'))[0].json;
 assert(intake.event_id==='hubspot:123:ticket:456');assert(JSON.parse(intake.raw_body).external_id===intake.event_id);assert(intake.signed_text===intake.timestamp+'.'+intake.raw_body);count++;
 await assert.rejects(()=>run('Check Acceptance',{statusCode:200,body:{accepted:true}}));count++;
 assert((await run('Check Acceptance',{statusCode:202,body:{accepted:true,duplicate:false,event_id:'e'}}))[0].json.accepted);count++;
 const payload={schema_version:1,type:'threshold.refund.final',delivery_id:'delivery-1',organization_id:'org-123',execution_id:'ex-1',event_id:'e-1',status:'completed',verified:true,crm:{provider:'hubspot',portal_id:'123',ticket_id:'456'}};
 const raw=JSON.stringify(payload),timestamp=String(Math.floor(Date.now()/1000));
 const signature=crypto.createHmac('sha256','s'.repeat(40)).update(timestamp+'.'+raw).digest('hex');
 const input={raw,item:{json:{headers:{'x-threshold-timestamp':timestamp,'x-threshold-signature':'sha256='+signature,'x-threshold-delivery-id':'delivery-1'}}}};
 const prepared=(await run('Read Signed Outcome',{},input))[0].json;
 prepared.expected_signature=signature;
 assert(prepared.signed_text===timestamp+'.'+raw);count++;
 const mapped=(await run('Validate and Map Outcome',prepared))[0].json;
 assert(mapped.ticket_id==='456'&&mapped.properties.hs_pipeline_stage==='4');count++;
 for(const bad of [{...prepared,supplied_signature:'0'.repeat(64)}, {...prepared,payload:{...payload,organization_id:'other'}},{...prepared,payload:{...payload,verified:false}},{...prepared,payload:{...payload,status:'failed'}}]){
 await assert.rejects(()=>run('Validate and Map Outcome',bad));count++;
 }
 const cancelled=structuredClone(prepared);cancelled.payload.status='cancelled';cancelled.payload.verified=false;
 assert((await run('Validate and Map Outcome',cancelled))[0].json.properties.hs_pipeline_stage==='5');count++;
 const expired=structuredClone(input);expired.item.json.headers['x-threshold-timestamp']='1';await assert.rejects(()=>run('Read Signed Outcome',{},expired));count++;
 const lookup={'Validate and Map Outcome':mapped};
 const ack=(await run('Build Delivery Acknowledgment',{statusCode:200,body:{id:'456'}},{},lookup))[0].json;
 assert(ack.response.ok&&ack.response.delivery_id==='delivery-1');count++;
 assert((await run('Build Delivery Acknowledgment',{statusCode:200,body:{id:'999'}},{},lookup))[0].json.response_code===502);count++;
 assert((await run('Build Delivery Acknowledgment',{statusCode:429,headers:{'retry-after':'30'}},{},lookup))[0].json.retry_after==='30');count++;
 console.log(count+' workflow structure and JavaScript checks passed (Node harness, not an n8n execution).');
})().catch(e=>{console.error(e);process.exit(1)});
