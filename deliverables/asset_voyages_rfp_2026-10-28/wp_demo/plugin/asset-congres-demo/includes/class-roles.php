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
		$dir_caps     = $team_caps + array( 'asset_manage_gme' => true );

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
