<?php
/**
 * Roles and capabilities.
 *
 * @package AssetCongresDemo
 */

defined( 'ABSPATH' ) || exit;

/**
 * Roles: Contributeur ASSET, Équipe ASSET, Direction ASSET.
 */
class Asset_CD_Roles {

	/**
	 * Congress primitive capabilities (capability_type asset_congres / asset_congress).
	 *
	 * @return array<string,string[]> map role level => caps.
	 */
	public static function congres_caps() {
		$contrib = array( 'read', 'edit_asset_congress', 'delete_asset_congress', 'assign_asset_congres_terms' );
		$team    = array_merge(
			$contrib,
			array(
				'publish_asset_congress',
				'edit_others_asset_congress',
				'edit_published_asset_congress',
				'edit_private_asset_congress',
				'read_private_asset_congress',
				'delete_others_asset_congress',
				'delete_published_asset_congress',
				'delete_private_asset_congress',
				'manage_asset_congres_terms',
				'upload_files',
			)
		);
		return array(
			'contrib' => $contrib,
			'team'    => $team,
		);
	}

	/**
	 * Page-editing capabilities granted to Direction ASSET (edit, publish and delete pages,
	 * including other users' pages).
	 *
	 * @return string[]
	 */
	public static function page_caps() {
		return array(
			'edit_pages',
			'edit_others_pages',
			'edit_published_pages',
			'edit_private_pages',
			'read_private_pages',
			'publish_pages',
			'delete_pages',
			'delete_others_pages',
			'delete_published_pages',
			'delete_private_pages',
			// The page editor reads reusable blocks and pattern previews through REST with
			// context=edit, which needs edit_posts; without it every page edit logs 403s.
			// The « Articles » menu stays hidden (hide_posts_menu); publish_posts is not granted.
			'edit_posts',
		);
	}

	/**
	 * Hooks.
	 */
	public static function init() {
		add_action( 'admin_menu', array( __CLASS__, 'hide_posts_menu' ), 99 );
		add_action( 'admin_bar_menu', array( __CLASS__, 'hide_new_post' ), 999 );
	}

	/**
	 * True for an ASSET staff account that is not an administrator.
	 *
	 * @return bool
	 */
	private static function is_asset_staff() {
		$u = wp_get_current_user();
		return $u->exists() && ! in_array( 'administrator', (array) $u->roles, true ) && array_intersect( array( 'asset_direction', 'asset_equipe', 'asset_contributeur' ), (array) $u->roles );
	}

	/**
	 * The demo has no blog: no « Articles » menu for ASSET staff.
	 */
	public static function hide_posts_menu() {
		if ( self::is_asset_staff() ) {
			remove_menu_page( 'edit.php' );
		}
	}

	/**
	 * No « Nouveau → Article » in the admin bar for ASSET staff.
	 *
	 * @param WP_Admin_Bar $bar Admin bar.
	 */
	public static function hide_new_post( $bar ) {
		if ( self::is_asset_staff() ) {
			$bar->remove_node( 'new-post' );
		}
	}

	/**
	 * Creates roles and grants capabilities. Idempotent.
	 */
	public static function install() {
		$caps = self::congres_caps();

		$contrib_caps = array_fill_keys( $caps['contrib'], true );
		$team_caps    = array_fill_keys( $caps['team'], true );
		$team_caps   += array(
			'asset_manage_demandes' => true,
			'asset_view_gme'        => true,
		);
		// Direction also edits the site's pages (CE-D1-001). Pages only: no unfiltered_html, no
		// user, plugin, theme or option management.
		$dir_caps     = $team_caps + array( 'asset_manage_gme' => true ) + array_fill_keys( self::page_caps(), true );

		$defs = array(
			'asset_contributeur' => array( __( 'Contributeur ASSET', 'asset-congres-demo' ), $contrib_caps ),
			'asset_equipe'       => array( __( 'Équipe ASSET', 'asset-congres-demo' ), $team_caps ),
			'asset_direction'    => array( __( 'Direction ASSET', 'asset-congres-demo' ), $dir_caps ),
		);

		foreach ( $defs as $slug => $def ) {
			$role = get_role( $slug );
			if ( ! $role ) {
				add_role( $slug, $def[0], $def[1] );
				continue;
			}
			foreach ( $def[1] as $cap => $grant ) {
				$role->add_cap( $cap, $grant );
			}
		}

		$admin = get_role( 'administrator' );
		if ( $admin ) {
			foreach ( array_keys( $dir_caps ) as $cap ) {
				$admin->add_cap( $cap );
			}
		}
	}
}
