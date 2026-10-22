import { mock } from 'claude-code/testing'
export function world(on) {
  const clock=mock.clock(on,{now:Date.parse('2026-10-03T09:00:00Z')})
  const saved=new Map<string,any>()
  const state={registered:[] as any[],opened:[] as any[],argv:[] as any[],copies:[] as string[],drafts:[] as string[],toasts:[] as string[],reads:[] as string[],size:100,isLink:false,sizeError:false,processError:false,failTool:false,downstream:0,contextMissing:false,emptyAgents:false,emptyLimits:false,sourceOverride:null as string|null}
  const sources:Record<string,string>={
    'package.json':'{"name":"demo-app","version":"1.2.0","scripts":{"test":"vitest run","build":"vite build"},"dependencies":{"react":"^19.0.0"},"devDependencies":{"vitest":"^3.0.0"}}',
    'README.md':'# Demo application\n\n## Setup\n```md\n# not a heading\n```\n### Tests\n',
    'data.csv':'name,city\n"Ada, A.",London\nGrace,"New\nYork"\n',
    'app.log':'INFO server ready\nWARN retrying\nERROR connection refused\nINFO recovered\n',
    '.env.example':'API_URL=https://example.com\nAPI_KEY=\n# docs\n',
    'before.txt':'hello\nold\n', 'after.txt':'hello\nnew\n',
    'animation.txt':'[o] frame one\f[-] frame two'
  }
  on('store.keys',()=>({value:[...saved.keys()]}))
  on('store.get',($,e)=>({value:saved.get(e.key)}))
  on('store.set',($,e)=>{saved.set(e.key,e.value);return {value:undefined}})
  on('store.delete',($,e)=>{saved.delete(e.key);return {value:undefined}})
  on('session.start',($,e)=>({cwd:e.cwd}))
  on('session.cwd',()=>({value:'/work'}))
  on('session.usage',()=>({value:{context:state.contextMissing?{window:200000}:{tokens:84000,window:200000,percent:42},rateLimits:state.emptyLimits?[]:[{kind:'five_hour',percentUsed:37,resetsAt:'2026-10-03T12:00:00Z'},{kind:'seven_day',percentUsed:61,resetsAt:'2026-10-09T09:00:00Z'}],cost:{usd:1.2}}}))
  on('agent.list',()=>({value:state.emptyAgents?[]:[{id:'a-1',description:'Review accessibility',type:'Explore',status:'running'}]}))
  on('command.register',($,e)=>{state.registered.push(e);return {value:undefined}})
  on('ui.open',($,e)=>{state.opened.push(e);return {value:{isPlaced:true}}})
  on('ui.copy',($,e)=>{state.copies.push(e.text);return {value:{isCopied:true}}})
  on('prompt.fill',($,e)=>{state.drafts.push(e.text);return {isFilled:true}})
  on('ui.toast',($,e)=>{state.toasts.push(e.text);return {value:undefined}})
  on('ui.render',()=>({type:'Text',props:{},children:['Other pane untouched']}))
  on('fs.stat',()=>state.sizeError?{deny:'File does not exist'}:{value:{kind:'file',size:state.size,mtimeMs:0,isLink:state.isLink}})
  on('fs.read',($,e)=>{state.reads.push(e.path);return {value:state.sourceOverride ?? sources[e.path.split('/').pop()] ?? 'sample text'}})
  on('fs.list',()=>({value:[{name:'src',kind:'dir',size:0,isLink:false},{name:'package.json',kind:'file',size:220,isLink:false},{name:'linked',kind:'dir',size:0,isLink:true}]}))
  on('process.run',($,e)=>{
    state.argv.push(e.argv)
    if(state.processError)return {deny:'Git not available'}
    let stdout='sample Git inspection\n'
    if(e.argv.includes('status'))stdout='## feature/mod-gallery\n M src/index.ts\n?? docs/notes.md\n'
    if(e.argv.includes('branch'))stdout='* feature/mod-gallery  123abcd [origin/feature/mod-gallery] Add gallery\n  main                 456def0 [origin/main] Release\n'
    if(e.argv.includes('--cached'))stdout=e.argv.includes('--stat')?' src/index.ts | 2 +-\n 1 file changed\n':'@@ -1 +1 @@\n-old label\n+new label\n'
    if(e.argv.includes('log'))stdout='123abcd  2026-10-03  Ada\n    Add keyboard controls\n456def0  2026-10-02  Grace\n    Fix empty states\n'
    if(e.argv.includes('stash'))stdout=e.argv.includes('list')?'stash@{0}  WIP on feature/search\nstash@{1}  WIP on main\n':' src/search.ts | 8 ++++----\n'
    if(e.argv.includes('worktree'))stdout='worktree /work\nHEAD 123abcd\nbranch refs/heads/main\n\nworktree /work-review\nHEAD 456def0\nbranch refs/heads/review\n'
    if(e.argv.includes('--diff-filter=U'))stdout='src/config.ts\n'
    if(e.argv.includes('grep'))stdout=e.argv.includes('TODO|FIXME|HACK')?'src/index.ts:12:// TODO improve empty state\nsrc/api.ts:44:// FIXME retry timeout\n':'src/config.ts:4:<<<<<<< HEAD\nsrc/config.ts:8:>>>>>>> review\n'
    if(e.argv.includes('blame'))stdout='123abcd (Ada 2026-10-03 1) # Demo application\n456def0 (Grace 2026-10-02 2) ## Setup\n'
    if(e.argv.includes('check-ignore'))stdout='.gitignore:3:dist/\tdist/bundle.js\n'
    return {value:{exitCode:0,stdout,stderr:''}}
  })
  on('tool.call',()=>{state.downstream++;return state.failTool?{result:'Fixture failure',isError:true}:{result:'ok'}})
  on('turn.complete',()=>({text:''}))
  on('turn.step',async function*($,e){
    yield {kind:'text',index:0,text:'ok'}
    return {turnId:e.turnId,index:e.index,answer:'ok',toolUses:[],stopReason:'end_turn',usage:{input_tokens:20,output_tokens:10,cache_read_input_tokens:1000,cache_creation_input_tokens:80}}
  })
  return {clock,saved,state}
}
export function site(plugin, surface:'terminal'|'desktop'='terminal', width=60) {
  return {plugin,component:'Pane' as const,requestId:plugin,surface,viewport:{columns:width+40,rows:30},props:{title:plugin,isFocused:true,bodyColumns:width,placement:'inline' as const,scroll:{offset:0,bodyRows:20},view:{}}}
}
