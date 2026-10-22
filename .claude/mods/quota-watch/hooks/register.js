import { clean, text, code, row, frame, bar, pretty, bounded, entries, safePath } from './ui.js'
const ID = "quota-watch"

export function register(on) {
  on('session.start', async ($, e, next) => {

    await $.command.register({name:ID, description:"Inspect reported plan windows and their reset times.", immediate:true, argumentHint:""})
    return next(e)
  })
  on('command.run', {command:"quota-watch"}, async ($, e) => {

    await $.ui.open({id:ID,title:"Quota Watch",focus:true,closeOnEscape:true})
    return {}
  })

  on('ui.render', {component:'Pane'}, async ($, e, next) => {
    if(e.requestId !== ID) return next(e)
    const E = $.ui.resolve(e)
    try {
      const body = await draw($, E)
      return frame(E,"Quota Watch","Inspect reported plan windows and their reset times.",body)
    } catch(error) {
      return frame(E,"Quota Watch",'Unable to inspect this data.',[text(E,error.message,{color:'yellow'}),E.Button({key:'refresh',label:'Refresh',onPress:()=>$.ui.invalidate('ui.render')})])
    }
  })
}
async function draw($, E) {
  const refresh = E.Button({key:'refresh',label:'Refresh',hotkey:'r',plain:true,onPress:()=>$.ui.invalidate('ui.render')})

const u = await $.session.usage()
return [text(E,'Reported plan windows',{bold:true}), ...u.rateLimits.map((r) => text(E,
  r.kind + '  ' + bar(r.percentUsed) + '\nResets: ' + (r.resetsAt ? new Date(r.resetsAt).toISOString() : 'not reported'))),
  ...(u.rateLimits.length ? [] : [text(E,'No plan limits reported for this account.')]),refresh]

}
