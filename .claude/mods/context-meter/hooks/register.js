import { clean, text, code, row, frame, bar, pretty, bounded, entries, safePath } from './ui.js'
const ID = "context-meter"

export function register(on) {
  on('session.start', async ($, e, next) => {

    await $.command.register({name:ID, description:"See the current context window fill and remaining tokens.", immediate:true, argumentHint:""})
    return next(e)
  })
  on('command.run', {command:"context-meter"}, async ($, e) => {

    await $.ui.open({id:ID,title:"Context Meter",focus:true,closeOnEscape:true})
    return {}
  })

  on('ui.render', {component:'Pane'}, async ($, e, next) => {
    if(e.requestId !== ID) return next(e)
    const E = $.ui.resolve(e)
    try {
      const body = await draw($, E)
      return frame(E,"Context Meter","See the current context window fill and remaining tokens.",body)
    } catch(error) {
      return frame(E,"Context Meter",'Unable to inspect this data.',[text(E,error.message,{color:'yellow'}),E.Button({key:'refresh',label:'Refresh',onPress:()=>$.ui.invalidate('ui.render')})])
    }
  })
}
async function draw($, E) {
  const refresh = E.Button({key:'refresh',label:'Refresh',hotkey:'r',plain:true,onPress:()=>$.ui.invalidate('ui.render')})

const u = await $.session.usage()
const c = u.context
if(c.tokens===undefined || c.percent===undefined) return [text(E,'Context usage not reported yet.'),text(E,'Window: '+c.window+' tokens'),refresh]
return [text(E, bar(c.percent), {color:c.percent >= 80 ? 'yellow' : 'green'}),
  text(E, Number(c.tokens).toLocaleString() + ' / ' + Number(c.window).toLocaleString() + ' tokens'),
  text(E, Math.max(0,c.window-c.tokens).toLocaleString() + ' tokens remaining'), refresh]

}
