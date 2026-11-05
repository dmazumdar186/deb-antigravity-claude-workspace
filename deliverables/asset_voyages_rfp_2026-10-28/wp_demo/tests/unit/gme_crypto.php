<?php
/**
 * Unit checks for Asset_CD_Gme crypto and validation (no WordPress needed).
 * Usage: php gme_crypto.php <key-or-"none">  -> prints one JSON line.
 */
define( 'ABSPATH', __DIR__ . '/' );
$arg = $argv[1] ?? 'none';
if ( 'none' !== $arg ) {
	define( 'ASSET_GME_KEY', $arg );
}
require dirname( __DIR__, 2 ) . '/plugin/asset-congres-demo/includes/class-gme.php';

$out = array( 'key_ok' => Asset_CD_Gme::key_ok() );
$enc = Asset_CD_Gme::encrypt( 'DEMO-GME-ABCD', 5 );
$out['encrypted']        = null !== $enc;
$out['roundtrip']        = $enc ? Asset_CD_Gme::decrypt( $enc, 5 ) : null;
$out['other_congres']    = $enc ? Asset_CD_Gme::decrypt( $enc, 7 ) : null;
$out['tampered']         = $enc ? Asset_CD_Gme::decrypt( substr( $enc, 0, -4 ) . 'AAAA', 5 ) : null;
$out['plaintext_in_enc'] = $enc ? str_contains( base64_decode( $enc ), 'DEMO-GME' ) : false;
$out['valid_plain']      = Asset_CD_Gme::valid_code( 'DEMO-GME-ABCD' );
$out['valid_newline']    = Asset_CD_Gme::valid_code( "DEMO-GME-ABCD\n" );
$out['valid_lower']      = Asset_CD_Gme::valid_code( 'demo-gme-abcd' );
$out['valid_array']      = Asset_CD_Gme::valid_code( array( 'x' ) );
echo json_encode( $out ), "\n";
