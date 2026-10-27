(() => {
'use strict';
const root=document.documentElement;
let language='en';
try{if(localStorage.getItem('jv_lang')==='fr')language='fr';}catch(_){}
root.lang=language;
root.classList.add('i18n-wait');
const en={
 pageTitle:`Jeevana — Yoga in Paris`,
 privacyTitle:`Privacy & mentions légales — Jeevana`,
 description:`Yoga in Paris with Jeevana Gogula. Explore the practice, discover twelve breaths, and register your interest in a class.`,
 ogDescription:`Steady. At ease. Twelve breaths at a time. Yoga in Paris with Jeevana Gogula.`,
 ogImageAlt:`Jeevana seated on a park lawn in Paris.`,
 skip:`Skip to content`,home:`Jeevana — home`,navigation:`Main navigation`,language:`Language`,
 navPractice:`Practice`,navBreaths:`Twelve breaths`,navClasses:`Classes`,navContact:`Contact`,register:`Register`,
 heroEyebrow:`Yoga in Paris`,heroHeadline:`Steady. At ease. Twelve breaths at a time.`,
 heroLine1:`Steady. At ease.`,heroLine2:`Twelve breaths`,heroLine3:`at a time.`,
 heroSub:`The posture is steady and at ease. A place to begin, with movement, attention, and the breath.`,
 heroRegister:`Register for a class`,seeClasses:`See the classes`,heroChip:`Jeevana Gogula · Paris`,
 portraitNote:`A little space to simply be.`,coverFoot:`Movement. Stillness. A fresh beginning.`,explore:`Explore the practice`,
 practiceEyebrow:`01 / The practice`,practiceTitle:`Less striving.\nMore listening.`,
 sutra12:`Yoga is the stilling of the movements of the mind.`,sutra12Ref:`Yoga Sūtra 1.2`,
 practiceBody:`Jeevana teaches yoga in Paris. The practice begins with attention: noticing the ground, the rhythm of breathing, and the space between movements. A posture is not an image to reproduce, but a place to explore steadiness and ease. Movement and stillness belong together; effort can sit alongside softness. From a simple seated pause to a flowing sequence, the invitation is to stay curious about what is present. There is no need to rush towards a shape. Each breath offers another moment to listen, adjust, and begin again with fresh attention.`,
 photoLift:`01 · Open`,photoRest:`02 · Rest`,photoBe:`03 · Be`,
 breathsEyebrow:`02 / Sūrya Namaskāra`,breathsTitle:`One breath.\nTwelve moments.`,
 breathsBody:`A sun salutation, unfolded. Follow the photographs, the breath, and the words that accompany each movement.`,
 stripHelp:`Swipe or drag to explore. Use the arrow keys when the sequence is focused.`,
 stripLabel:`Twelve breaths: sun salutation`,stripRole:`carousel`,previous:`Previous breath`,next:`Next breath`,
 playSequence:`Play the sequence`,pauseSequence:`Pause the sequence`,motionOff:`Autoplay off`,breathCount:`Breath {n} of 12`,
 sequenceNote:`An invitation to explore, not a substitute for individual guidance. Let comfort lead; never force a posture. If retaining the breath feels uncomfortable, breathe freely.`,
 classesEyebrow:`03 / Practise together`,classesTitle:`Make room\nfor your practice.`,
 timetable:`Timetable opens soon — register your interest.`,group:`Group`,private:`Private`,workshop:`Workshop`,
 groupBody:`Share the space, and explore movement and stillness together.`,
 privateBody:`A space to discuss your questions and your own practice.`,
 workshopBody:`Time set aside to explore a part of the practice more closely.`,
 price:`Price on request`,interest:`Register your interest`,
 registrationEyebrow:`Your next breath`,registrationTitle:`Begin with\na hello.`,
 registrationBody:`Tell Jeevana what you are looking for. This is an expression of interest, not a confirmed booking.`,
 preferEmail:`Prefer email? Write to Jeevana ↗`,registrationFormTitle:`Class registration`,yourDetails:`Your details`,
 requiredNote:`All fields are required unless marked optional.`,name:`Name`,email:`Email`,optionalPhone:`Phone (optional)`,
 phoneHint:`Include your country code, for example +33.`,format:`Format`,anyFormat:`Open to any format`,experience:`Experience`,
 levelNew:`New to yoga`,levelSome:`Some experience`,levelRegular:`Regular practice`,message:`A note for Jeevana (optional)`,
 registerConsent:`I agree that Jeevana stores these details to answer my registration. They are never shared or sold, and I can ask for their deletion at any time by email.`,
 subscribeConsent:`I agree to receive Jeevana's newsletter by email. I can unsubscribe at any time.`,
 privacyShort:`Privacy information`,sendRegistration:`Send my interest`,sending:`Sending…`,
 registrationSuccessTitle:`Your hello is on its way.`,
 registrationSuccessBody:`Thank you for your interest. Jeevana has received your details. This is not a confirmed booking.`,
 errorName:`Please enter your name. Your other details have been kept.`,
 errorEmail:`Please check your email address and try again. Your details have been kept.`,
 errorPhone:`Please check your phone number, including its country code, and try again.`,
 errorConsent:`Please tick the consent checkbox before sending.`,
 errorFields:`Please check the required fields. Your details have been kept.`,
 errorRate:`Too many attempts. Please wait 10 minutes before trying again, or contact Jeevana by email.`,
 errorServer:`Your request could not be saved. Your details are still here. Please try again or email Jeevana.`,
 errorNetwork:`The request could not be confirmed. Please check your connection and try again, or email Jeevana. Your details are still here.`,
 noscript:`Online forms need JavaScript. To register your interest, email`,
 aboutEyebrow:`04 / Jeevana, Paris`,aboutTitle:`Rooted in practice.\nHere in Paris.`,
 aboutBody:`Yoga has a place in the city, too. Jeevana Gogula teaches in Paris, where the pace of everyday life offers a reason to pause. Her practice brings attention back to movement, breath, and stillness. Whether you are looking for a group class or a private session, you can get in touch to explore a way to practise together in Paris.`,
 lineage:`Lineage`,tapovan:`Graduate of Tapovan`,lineageBody:`This training provides a foundation for sharing the practice with care.`,parisChip:`Champ-de-Mars, Paris`,
 contactEyebrow:`05 / Stay in touch`,contactTitle:`A conversation\nis a beginning.`,
 newsletterEyebrow:`A note, now and then`,newsletterTitle:`Keep a little space\nfor yoga.`,
 newsletterBody:`Receive Jeevana’s newsletter by email.`,newsletterFormTitle:`Newsletter sign-up`,yourEmail:`Your email`,subscribe:`Subscribe`,
 newsletterSuccessTitle:`A little space, kept.`,newsletterSuccessBody:`Thank you. You are subscribed to Jeevana’s newsletter. You can unsubscribe at any time.`,
 footerThought:`Steady. At ease. One breath at a time.`,backTop:`Back to top`,privacy:`Privacy & mentions légales`,designerEmail:`Email Debanjan Mazumdar`,
 heroAlt:`Jeevana seated cross-legged on a park lawn in Paris, eyes closed, a gentle smile, hands resting on her knees.`,
 practice01Alt:`Jeevana in cobra pose on a mat, chest lifted, eyes closed.`,
 practice02Alt:`Jeevana in child's pose on a grey mat, seen from above.`,
 practice03Alt:`Jeevana seated in meditation on the grass, hands in jñāna mudrā.`,
 parisAlt:`Jeevana in a full backbend, Chakrāsana, on a blue mat on the Champ-de-Mars, the Eiffel Tower behind her.`
};
const fr={
 pageTitle:`Jeevana — Yoga à Paris`,
 privacyTitle:`Confidentialité & mentions légales — Jeevana`,
 description:`Le yoga à Paris avec Jeevana Gogula. Explorez la pratique, découvrez douze souffles et manifestez votre intérêt pour un cours.`,
 ogDescription:`Stable. À l'aise. Douze souffles à la fois. Le yoga à Paris avec Jeevana Gogula.`,
 ogImageAlt:`Jeevana assise sur une pelouse à Paris.`,
 skip:`Aller au contenu`,home:`Jeevana — accueil`,navigation:`Navigation principale`,language:`Langue`,
 navPractice:`Pratique`,navBreaths:`Douze souffles`,navClasses:`Cours`,navContact:`Contact`,register:`S’inscrire`,
 heroEyebrow:`Yoga à Paris`,heroHeadline:`Stable. À l'aise. Douze souffles à la fois.`,
 heroLine1:`Stable. À l'aise.`,heroLine2:`Douze souffles`,heroLine3:`à la fois.`,
 heroSub:`La posture est stable et confortable. Un point de départ, avec le mouvement, l’attention et le souffle.`,
 heroRegister:`S’inscrire à un cours`,seeClasses:`Découvrir les cours`,heroChip:`Jeevana Gogula · Paris`,
 portraitNote:`Un peu d’espace pour simplement être.`,coverFoot:`Mouvement. Immobilité. Un nouveau départ.`,explore:`Explorer la pratique`,
 practiceEyebrow:`01 / La pratique`,practiceTitle:`Moins chercher.\nMieux écouter.`,
 sutra12:`Le yoga est l'apaisement des mouvements du mental.`,sutra12Ref:`Yoga Sūtra 1.2`,
 practiceBody:`Jeevana enseigne le yoga à Paris. La pratique commence par l’attention : sentir le sol, le rythme de la respiration et l’espace entre les mouvements. Une posture n’est pas une image à reproduire, mais un lieu où explorer la stabilité et l’aisance. Mouvement et immobilité se répondent ; l’effort peut côtoyer la douceur. D’une simple pause assise à un enchaînement fluide, l’invitation est de rester à l’écoute de ce qui est là. Inutile de se précipiter vers une forme. Chaque souffle offre un instant pour écouter, ajuster et recommencer avec une attention renouvelée.`,
 photoLift:`01 · S’ouvrir`,photoRest:`02 · Se reposer`,photoBe:`03 · Être`,
 breathsEyebrow:`02 / Sūrya Namaskāra`,breathsTitle:`Un souffle.\nDouze instants.`,
 breathsBody:`Une salutation au soleil, pas à pas. Suivez les photographies, le souffle et les mots qui accompagnent chaque mouvement.`,
 stripHelp:`Balayez ou faites glisser pour explorer. Utilisez les touches fléchées lorsque la séquence est sélectionnée.`,
 stripLabel:`Douze souffles : salutation au soleil`,stripRole:`carrousel`,previous:`Souffle précédent`,next:`Souffle suivant`,
 playSequence:`Lancer la séquence`,pauseSequence:`Mettre en pause`,motionOff:`Lecture auto désactivée`,breathCount:`Souffle {n} sur 12`,
 sequenceNote:`Une invitation à explorer, qui ne remplace pas un accompagnement individuel. Privilégiez le confort ; ne forcez jamais une posture. Si retenir le souffle vous gêne, respirez librement.`,
 classesEyebrow:`03 / Pratiquer ensemble`,classesTitle:`Faire une place\nà votre pratique.`,
 timetable:`Le planning ouvre bientôt — manifestez votre intérêt.`,group:`Collectif`,private:`Individuel`,workshop:`Atelier`,
 groupBody:`Partager un espace et explorer ensemble le mouvement et l’immobilité.`,
 privateBody:`Un espace pour échanger sur vos questions et votre propre pratique.`,
 workshopBody:`Un temps dédié pour explorer un aspect de la pratique de plus près.`,
 price:`Tarif sur demande`,interest:`Manifester mon intérêt`,
 registrationEyebrow:`Votre prochain souffle`,registrationTitle:`Commencer par\nun bonjour.`,
 registrationBody:`Dites à Jeevana ce que vous recherchez. Il s’agit d’une manifestation d’intérêt, et non d’une réservation confirmée.`,
 preferEmail:`Par e-mail ? Écrivez à Jeevana ↗`,registrationFormTitle:`Inscription à un cours`,yourDetails:`Vos coordonnées`,
 requiredNote:`Tous les champs sont requis, sauf mention « facultatif ».`,name:`Nom`,email:`E-mail`,optionalPhone:`Téléphone (facultatif)`,
 phoneHint:`Indiquez l’indicatif du pays, par exemple +33.`,format:`Format`,anyFormat:`Tous les formats m’intéressent`,experience:`Expérience`,
 levelNew:`Je découvre le yoga`,levelSome:`J’ai déjà pratiqué`,levelRegular:`Je pratique régulièrement`,message:`Un mot pour Jeevana (facultatif)`,
 registerConsent:`J'accepte que Jeevana conserve ces informations pour répondre à mon inscription. Elles ne sont jamais partagées ni vendues, et je peux demander leur suppression à tout moment par e-mail.`,
 subscribeConsent:`J'accepte de recevoir la lettre d'information de Jeevana par e-mail. Je peux me désinscrire à tout moment.`,
 privacyShort:`Protection des données`,sendRegistration:`Envoyer ma demande`,sending:`Envoi en cours…`,
 registrationSuccessTitle:`Votre bonjour est envoyé.`,
 registrationSuccessBody:`Merci pour votre intérêt. Jeevana a reçu vos coordonnées. Il ne s’agit pas d’une réservation confirmée.`,
 errorName:`Veuillez indiquer votre nom. Vos autres informations sont conservées.`,
 errorEmail:`Vérifiez votre adresse e-mail et réessayez. Vos informations sont conservées.`,
 errorPhone:`Vérifiez votre numéro de téléphone, avec l’indicatif du pays, puis réessayez.`,
 errorConsent:`Veuillez cocher la case de consentement avant l’envoi.`,
 errorFields:`Vérifiez les champs obligatoires. Vos informations sont conservées.`,
 errorRate:`Trop de tentatives. Patientez 10 minutes avant de réessayer, ou contactez Jeevana par e-mail.`,
 errorServer:`Votre demande n’a pas pu être enregistrée. Vos informations sont toujours là. Réessayez ou écrivez à Jeevana.`,
 errorNetwork:`L’envoi n’a pas pu être confirmé. Vérifiez votre connexion et réessayez, ou écrivez à Jeevana. Vos informations sont toujours là.`,
 noscript:`Les formulaires en ligne nécessitent JavaScript. Pour manifester votre intérêt, écrivez à`,
 aboutEyebrow:`04 / Jeevana, Paris`,aboutTitle:`Ancrée dans la pratique.\nIci, à Paris.`,
 aboutBody:`Le yoga a aussi sa place en ville. Jeevana Gogula enseigne à Paris, où le rythme du quotidien invite à faire une pause. Sa pratique ramène l’attention vers le mouvement, le souffle et l’immobilité. Que vous cherchiez un cours collectif ou une séance individuelle, vous pouvez la contacter pour explorer une façon de pratiquer ensemble à Paris.`,
 lineage:`Lignée`,tapovan:`Diplômée de Tapovan`,lineageBody:`Cette formation lui donne une base pour transmettre la pratique avec attention.`,parisChip:`Champ-de-Mars, Paris`,
 contactEyebrow:`05 / Garder le lien`,contactTitle:`Une conversation,\nun commencement.`,
 newsletterEyebrow:`Un mot, de temps en temps`,newsletterTitle:`Garder une petite place\npour le yoga.`,
 newsletterBody:`Recevez la lettre d’information de Jeevana par e-mail.`,newsletterFormTitle:`Inscription à la lettre d’information`,yourEmail:`Votre e-mail`,subscribe:`S’abonner`,
 newsletterSuccessTitle:`Une petite place, gardée.`,newsletterSuccessBody:`Merci. Vous êtes inscrit à la lettre d’information de Jeevana. Vous pouvez vous désinscrire à tout moment.`,
 footerThought:`Stable. À l’aise. Un souffle à la fois.`,backTop:`Retour en haut`,privacy:`Confidentialité & mentions légales`,designerEmail:`Écrire à Debanjan Mazumdar`,
 heroAlt:`Jeevana assise en tailleur sur une pelouse à Paris, les yeux fermés, un léger sourire, les mains posées sur les genoux.`,
 practice01Alt:`Jeevana en posture du cobra sur un tapis, la poitrine ouverte, les yeux fermés.`,
 practice02Alt:`Jeevana en posture de l'enfant sur un tapis gris, vue d'en haut.`,
 practice03Alt:`Jeevana assise en méditation sur l'herbe, les mains en jñāna mudrā.`,
 parisAlt:`Jeevana en pont complet, Chakrāsana, sur un tapis bleu au Champ-de-Mars, la tour Eiffel derrière elle.`
};
const positions=[
 [`Praṇāmāsana`,`Exhale`,`Expirer`,`to the friend of all`,`à l'ami de tous`],
 [`Hasta Uttānāsana`,`Inhale`,`Inspirer`,`to the shining one`,`à celui qui rayonne`],
 [`Pādahastāsana`,`Exhale`,`Expirer`,`to the one who induces activity`,`à celui qui suscite l'activité`],
 [`Aśva Sañcālanāsana`,`Inhale`,`Inspirer`,`to the one who illumines`,`à celui qui illumine`],
 [`Parvatāsana`,`Exhale`,`Expirer`,`to the one who moves through the sky`,`à celui qui traverse le ciel`],
 [`Aṣṭāṅga Namaskāra`,`Retain the breath`,`Retenir le souffle`,`to the giver of strength`,`à celui qui donne la force`],
 [`Bhujaṅgāsana`,`Inhale`,`Inspirer`,`to the golden cosmic self`,`au soi cosmique doré`],
 [`Parvatāsana`,`Exhale`,`Expirer`,`to the rays of light`,`aux rayons de lumière`],
 [`Aśva Sañcālanāsana`,`Inhale`,`Inspirer`,`to the son of Aditi`,`au fils d'Aditi`],
 [`Pādahastāsana`,`Exhale`,`Expirer`,`to the stimulating power`,`à la puissance qui stimule`],
 [`Hasta Uttānāsana`,`Inhale`,`Inspirer`,`to the one who is fit to be praised`,`à celui qui est digne de louange`],
 [`Praṇāmāsana`,`Exhale`,`Expirer`,`to the one who leads to enlightenment`,`à celui qui mène à l'éveil`]
];
positions.forEach((p,index)=>{
 const n=index+1;
 en['s'+n+'Alt']=`Step ${n}: Jeevana in ${p[0]} on a mat on a park lawn in Paris.`;
 fr['s'+n+'Alt']=`Étape ${n} : Jeevana en ${p[0]} sur un tapis, sur une pelouse à Paris.`;
 en['s'+n+'Breath']=p[1];fr['s'+n+'Breath']=p[2];
 en['s'+n+'Gloss']=p[3];fr['s'+n+'Gloss']=p[4];
});
const dictionaries={en,fr};
function t(key){return dictionaries[language][key]??en[key]??key;}
function replaceText(el,value){
 el.replaceChildren();
 value.split('\n').forEach((part,index)=>{if(index)el.append(document.createElement('br'));el.append(document.createTextNode(part));});
}
function setLanguage(value,persist=true){
 language=value==='fr'?'fr':'en';root.lang=language;
 document.querySelectorAll('[data-i18n]').forEach(el=>replaceText(el,t(el.dataset.i18n)));
 let wordIndex=0;
 document.querySelectorAll('[data-i18n-words]').forEach(el=>{
  el.replaceChildren();
  t(el.dataset.i18nWords).split(/\s+/).forEach((word,index)=>{
   if(index)el.append(document.createTextNode(' '));
   const span=document.createElement('span');span.className='word w'+wordIndex++;span.textContent=word;el.append(span);
  });
 });
 [['data-i18n-alt','alt'],['data-i18n-aria','aria-label'],['data-i18n-roledesc','aria-roledescription']].forEach(([attribute,target])=>{
  document.querySelectorAll('['+attribute+']').forEach(el=>el.setAttribute(target,t(el.getAttribute(attribute))));
 });
 document.querySelectorAll('[data-lang]').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.lang===language)));
 document.querySelectorAll('[data-lang-block]').forEach(block=>{block.hidden=block.dataset.langBlock!==language;});
 const privacy=location.pathname.startsWith('/privacy');
 document.title=t(privacy?'privacyTitle':'pageTitle');
 if(!privacy){
  [['meta[name=description]','description'],['meta[property="og:title"]','pageTitle'],['meta[property="og:description"]','ogDescription'],['meta[property="og:image:alt"]','ogImageAlt']].forEach(([selector,key])=>{const el=document.querySelector(selector);if(el)el.content=t(key);});
  const locale=document.querySelector('meta[property="og:locale"]');if(locale)locale.content=language==='fr'?'fr_FR':'en_GB';
 }
 if(persist){try{localStorage.setItem('jv_lang',language);}catch(_){}}
 root.classList.remove('i18n-wait');
 document.dispatchEvent(new CustomEvent('jeevana:language',{detail:{language}}));
}
window.JeevanaI18n={dictionaries,t,setLanguage,get language(){return language;}};
function init(){
 try{
  document.querySelectorAll('button[data-lang]').forEach(button=>button.addEventListener('click',()=>setLanguage(button.dataset.lang)));
  setLanguage(language,false);
 }finally{root.classList.remove('i18n-wait');}
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init,{once:true});else init();
})();
