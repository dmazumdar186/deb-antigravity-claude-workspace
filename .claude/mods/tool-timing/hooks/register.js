import { clean, text, code, row, frame, bar, pretty, bounded, entries, safePath } from './ui.js'
const ID = "tool-timing"
let stats = {}
export function register(on) {
  on('session.start', async ($, e, next) => {

    await $.command.register({name:ID, description:"Measure observed tool latency, call counts, and failures.", immediate:true, argumentHint:""})
    return next(e)
  })
  on('command.run', {command:"tool-timing"}, async ($, e) => {

    await $.ui.open({id:ID,title:"Tool Timing",focus:true,closeOnEscape:true})
    return {}
  })

on('tool.call', async ($, e, next) => {
  const t = await $.clock.now()
  try {
    const r = await next(e)
    const ms = Math.max(0, (await $.clock.now()) - t)
    const s = stats[e.tool] || {calls:0,ms:0,failed:0}
    stats[e.tool] = {calls:s.calls+1,ms:s.ms+ms,failed:s.failed+(r.deny||r.isError ? 1:0)}
    $.ui.invalidate('ui.render')
    return r
  } catch(error) { throw error }
})

  on('ui.render', {component:'Pane'}, async ($, e, next) => {
    if(e.requestId !== ID) return next(e)
    const E = $.ui.resolve(e)
    try {
      const body = await draw($, E)
      return frame(E,"Tool Timing","Measure observed tool latency, call counts, and failures.",body)
    } catch(error) {
      return frame(E,"Tool Timing",'Unable to inspect this data.',[text(E,error.message,{color:'yellow'}),E.Button({key:'refresh',label:'Refresh',onPress:()=>$.ui.invalidate('ui.render')})])
    }
  })
}
async function draw($, E) {
  const refresh = E.Button({key:'refresh',label:'Refresh',hotkey:'r',plain:true,onPress:()=>$.ui.invalidate('ui.render')})

return [text(E,'Tool                         calls   avg ms   failed',{bold:true}),
 ...Object.entries(stats).sort((a,b)=>b[1].ms-a[1].ms).map(([name,s])=>text(E,name.padEnd(28)+String(s.calls).padEnd(8)+Math.round(s.ms/s.calls).toString().padEnd(9)+s.failed)),
 ...(Object.keys(stats).length ? [] : [text(E,'No tool calls observed yet.')]),refresh]

}
