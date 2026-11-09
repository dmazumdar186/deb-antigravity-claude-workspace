<?php
/**
 * Plugin Name:       ASSET Congrès — démonstration
 * Description:       Démonstration : catalogue de congrès, demandes de devis vol, suivi des demandes et codes GM&E protégés. Données fictives uniquement.
 * Version:           0.2.1
 * Requires at least: 6.5
 * Requires PHP:      8.1
 * Author:            ProdCraft
 * License:           GPL-2.0-or-later
 * Text Domain:       asset-congres-demo
 * Domain Path:       /languages
 *
 * @package AssetCongresDemo
 */

defined( 'ABSPATH' ) || exit;

define( 'ASSET_CD_VERSION', '0.2.1' );
define( 'ASSET_CD_FILE', __FILE__ );
define( 'ASSET_CD_DIR', plugin_dir_path( __FILE__ ) );
define( 'ASSET_CD_URL', plugin_dir_url( __FILE__ ) );

require_once ASSET_CD_DIR . 'includes/class-ui.php';
require_once ASSET_CD_DIR . 'includes/class-hardening.php';
require_once ASSET_CD_DIR . 'includes/class-roles.php';
require_once ASSET_CD_DIR . 'includes/class-congres.php';
require_once ASSET_CD_DIR . 'includes/class-catalogue.php';
require_once ASSET_CD_DIR . 'includes/class-notifications.php';
require_once ASSET_CD_DIR . 'includes/class-demandes.php';
require_once ASSET_CD_DIR . 'includes/class-demandes-admin.php';
require_once ASSET_CD_DIR . 'includes/class-gme.php';
require_once ASSET_CD_DIR . 'includes/class-gme-admin.php';
require_once ASSET_CD_DIR . 'includes/class-seed.php';

/**
 * Installs tables, roles and rewrite rules.
 */
function asset_cd_activate() {
	Asset_CD_Roles::install();
	Asset_CD_Gme::install_tables();
	Asset_CD_Notifications::install_table();
	Asset_CD_Congres::register();
	Asset_CD_Demandes::register_post_type();
	flush_rewrite_rules();
}
register_activation_hook( __FILE__, 'asset_cd_activate' );

/**
 * Removes rewrite rules on deactivation (data is kept).
 */
function asset_cd_deactivate() {
	flush_rewrite_rules();
}
register_deactivation_hook( __FILE__, 'asset_cd_deactivate' );

add_action(
	'init',
	static function () {
		load_plugin_textdomain( 'asset-congres-demo', false, dirname( plugin_basename( __FILE__ ) ) . '/languages' );
		// Upgrade path: make sure tables exist even if activation hook did not run.
		if ( get_option( 'asset_cd_db_version' ) !== ASSET_CD_VERSION ) {
			Asset_CD_Roles::install();
			Asset_CD_Gme::install_tables();
			Asset_CD_Notifications::install_table();
			update_option( 'asset_cd_db_version', ASSET_CD_VERSION, false );
		}
	},
	1
);

/**
 * Staff land on the dashboard after login (WordPress sends users without edit_posts to their profile).
 *
 * @param string           $redirect_to Destination.
 * @param string           $requested   Requested destination.
 * @param WP_User|WP_Error $user        User.
 * @return string
 */
function asset_cd_login_redirect( $redirect_to, $requested, $user ) {
	if ( $user instanceof WP_User && array_intersect( array( 'asset_direction', 'asset_equipe', 'asset_contributeur' ), (array) $user->roles ) ) {
		if ( '' === $requested || str_contains( (string) $redirect_to, 'profile.php' ) || admin_url() === $requested ) {
			return admin_url( 'index.php' ); // Not admin_url(): core would re-route that to profile.php.
		}
	}
	return $redirect_to;
}
add_filter( 'login_redirect', 'asset_cd_login_redirect', 10, 3 );

Asset_CD_Ui::init();
Asset_CD_Roles::init();
Asset_CD_Hardening::init();
Asset_CD_Congres::init();
Asset_CD_Catalogue::init();
Asset_CD_Demandes::init();
Asset_CD_Demandes_Admin::init();
Asset_CD_Gme_Admin::init();
Asset_CD_Notifications::init();
Asset_CD_Seed::init();

/**
 * Seeds the demo content (idempotent). Called from the blueprint.
 *
 * @return array Summary counts.
 */
function asset_congres_demo_seed() {
	return Asset_CD_Seed::run();
}
