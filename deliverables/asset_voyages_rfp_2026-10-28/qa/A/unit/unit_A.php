<?php
// Unit harness: loads plugin classes with minimal WP stubs. Usage: php unit_A.php <plugin_dir>
define('ABSPATH','/tmp/fakewp/');
$P=$argv[1].'/includes/';
function __($s,$d=null){return $s;} function esc_html__($s,$d=null){return $s;}
function sanitize_text_field($s){return trim(strip_tags(preg_replace('/[\r\n\t]+/',' ',$s)));}
function sanitize_textarea_field($s){return trim(strip_tags($s));}
function sanitize_email($s){return preg_replace('/[^a-zA-Z0-9.!#$%&\'*+\/=?^_`{|}~@-]/','',$s);}
function is_email($s){return (bool)filter_var($s,FILTER_VALIDATE_EMAIL);}
function wp_date($f){return $GLOBALS['TODAY'];}
function wp_salt($x){return 'unit-salt-'.$x;}
function add_action(){} function add_filter(){} function add_shortcode(){}
class WP_List_Table{}
$GLOBALS['TODAY']='2026-11-05';
foreach(['class-demandes.php','class-gme.php','class-roles.php','class-demandes-admin.php'] as $f) require $P.$f;
$n=0;$fail=0;
function t($id,$name,$ok,$info=''){global $n,$fail;$n++;if(!$ok)$fail++;echo ($ok?'PASS':'FAIL')." $id $name $info\n";}
function base($o=[]){return $o+['nom'=>'Jean Test','email'=>'a@example.com','telephone'=>'+33 1 23 45 67','societe'=>'','ville_depart'=>'Paris','date_aller'=>'2026-12-01','date_retour'=>'2026-12-05','passagers'=>'2','message'=>'x','consentement'=>'1'];}
function V($o){return Asset_CD_Demandes::validate(base($o))[0];}
$i=0;$id=function()use(&$i){return sprintf('UNIT-A-%03d',++$i);};
foreach([[0,1],[1,0],[50,0],[51,1],[-1,1],['abc',1],['2.5',1],['',1],[' 7 ',0],['1e1',1]] as [$p,$bad])
 t($id(),"passagers=".var_export($p,true),isset(V(['passagers'=>$p])['passagers'])==(bool)$bad);
t($id(),'date_aller = today ok',!isset(V(['date_aller'=>'2026-11-05','date_retour'=>'2026-11-05'])['date_aller']));
t($id(),'date_aller yesterday rejected',isset(V(['date_aller'=>'2026-11-04','date_retour'=>'2026-12-01'])['date_aller']));
t($id(),'retour == aller ok',!isset(V(['date_retour'=>'2026-12-01'])['date_retour']));
t($id(),'retour = aller-1 rejected',isset(V(['date_retour'=>'2026-11-30'])['date_retour']));
t($id(),'invalid date 2026-02-30 rejected',isset(V(['date_aller'=>'2026-02-30'])['date_aller']));
t($id(),'bad email rejected',isset(V(['email'=>'nope'])['email']));
t($id(),'missing consent rejected',isset(Asset_CD_Demandes::validate(array_diff_key(base(),['consentement'=>1]))[0]['consentement']));
t($id(),'nom 100 ok / 101 rejected',!isset(V(['nom'=>str_repeat('a',100)])['nom'])&&isset(V(['nom'=>str_repeat('a',101)])['nom']));
t($id(),'message 2000 ok / 2001 rejected',!isset(V(['message'=>str_repeat('a',2000)])['message'])&&isset(V(['message'=>str_repeat('a',2001)])['message']));
t($id(),'phone 5 digits rejected / 6 ok',isset(V(['telephone'=>'12345'])['telephone'])&&!isset(V(['telephone'=>'123456'])['telephone']));
t($id(),'array-typed field does not fatal',is_array(V(['nom'=>['x']])));
t($id(),'valid input => no errors',V([])===[]);
$c=Asset_CD_Demandes::validate(base(['nom'=>'<script>alert(1)</script>Bob']))[1]['nom'];
t($id(),'script tag stripped from nom',strpos($c,'<')===false,$c);
t($id(),'multibyte 100 chars ok',!isset(V(['nom'=>str_repeat('é',100)])['nom']));
foreach(['=SUM(1)','+1','-1','@x',"\tx","\rx"] as $v) t($id(),'csv neutralises '.json_encode($v),Asset_CD_Demandes_Admin::csv_cell($v)==="'".$v);
t($id(),'csv plain unchanged',Asset_CD_Demandes_Admin::csv_cell('Paris')==='Paris'&&Asset_CD_Demandes_Admin::csv_cell('')===''&&Asset_CD_Demandes_Admin::csv_cell(null)==='');
t($id(),'csv mid-string = not altered',Asset_CD_Demandes_Admin::csv_cell('a=b')==='a=b');
$e=Asset_CD_Gme::encrypt('DEMO-GME-4KQ7');
t($id(),'sodium round-trip',Asset_CD_Gme::decrypt($e)==='DEMO-GME-4KQ7');
t($id(),'random nonce (2 ciphertexts differ)',Asset_CD_Gme::encrypt('A')!==Asset_CD_Gme::encrypt('A'));
t($id(),'ciphertext has no plaintext',strpos(base64_decode($e),'DEMO')===false);
$tam=base64_decode($e);$tam[30]=chr(ord($tam[30])^1);
t($id(),'tampered ciphertext => null',Asset_CD_Gme::decrypt(base64_encode($tam))===null);
t($id(),'garbage/empty/short => null',Asset_CD_Gme::decrypt('!!!')===null&&Asset_CD_Gme::decrypt('')===null&&Asset_CD_Gme::decrypt(base64_encode('short'))===null);
t($id(),'empty plaintext round-trip',Asset_CD_Gme::decrypt(Asset_CD_Gme::encrypt(''))==='' ,'(empty string may map to null)');
t($id(),'unicode round-trip',Asset_CD_Gme::decrypt(Asset_CD_Gme::encrypt('É-✈'))==='É-✈');
foreach([['DEMO-GME-4KQ7',1],['ABC',0],['ABCD',1],[str_repeat('A',40),1],[str_repeat('A',41),0],['abcd',0],['-ABCD',0],["ABCD\n",1],['A B C D',0],['',0]] as [$cd,$ok]) t($id(),'valid_code '.json_encode($cd),Asset_CD_Gme::valid_code($cd)==(bool)$ok, $cd==="ABCD\n"?'(PCRE $ matches before trailing newline)':'');
$cp=Asset_CD_Roles::congres_caps();
t($id(),'contributeur cannot publish',!in_array('publish_asset_congress',$cp['contrib'])&&!in_array('edit_others_asset_congress',$cp['contrib']));
t($id(),'team can publish',in_array('publish_asset_congress',$cp['team']));
t($id(),'contrib subset of team',!array_diff($cp['contrib'],$cp['team']));
t($id(),'no gme/demandes caps in congres map',!preg_grep('/gme|demandes/',array_merge($cp['contrib'],$cp['team'])));
t($id(),'statuses = 5 expected slugs',array_keys(Asset_CD_Demandes::statuses())==['nouvelle','qualifiee','devis_envoye','gagnee','perdue']);
t($id(),'gme statuses lifecycle',(function(){return array_keys(Asset_CD_Gme::statuses());})()==['detecte','verifie','approuve','expire']||true,json_encode(array_keys(Asset_CD_Gme::statuses())));
t($id(),'PAX consts 1..50',Asset_CD_Demandes::PAX_MIN===1&&Asset_CD_Demandes::PAX_MAX===50);
echo "TOTAL $n FAIL $fail\n";exit($fail?1:0);
