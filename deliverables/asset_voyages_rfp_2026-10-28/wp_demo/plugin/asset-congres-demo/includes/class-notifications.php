<?php
/**
 * Team notifications (wp_mail) + "Journal des notifications" admin screen.
 *
 * @package AssetCongresDemo
 */

defined( 'ABSPATH' ) || exit;

/**
 * Notifications.
 */
class Asset_CD_Notifications {

	/**
	 * Table name.
	 *
	 * @return string
	 */
	public static function table() {
		global $wpdb;
		return $wpdb->prefix . 'asset_notif_log';
	}

	/**
	 * Hooks.
	 */
	public static function init() {
		add_action( 'admin_menu', array( __CLASS__, 'menu' ), 20 );
	}

	/**
	 * Creates the log table.
	 */
	public static function install_table() {
		global $wpdb;
		$table   = self::table();
		$charset = $wpdb->get_charset_collate();
		// phpcs:ignore WordPress.DB.DirectDatabaseQuery,WordPress.DB.PreparedSQL.InterpolatedNotPrepared -- schema, no user input.
		$wpdb->query( "CREATE TABLE IF NOT EXISTS {$table} ( id bigint(20) unsigned NOT NULL AUTO_INCREMENT, created_at datetime NOT NULL, recipient varchar(190) NOT NULL DEFAULT '', subject varchar(255) NOT NULL DEFAULT '', body text NOT NULL, ref varchar(40) NOT NULL DEFAULT '', delivered tinyint(1) NOT NULL DEFAULT 0, PRIMARY KEY  (id) ) {$charset}" );
	}

	/**
	 * Sends a team notification and records it in the journal.
	 *
	 * @param string $subject Subject.
	 * @param string $body    Plain-text body.
	 * @param string $ref     Related reference.
	 * @return bool Delivered by wp_mail.
	 */
	public static function notify_team( $subject, $body, $ref = '' ) {
		global $wpdb;
		$to = (string) get_option( 'asset_cd_notify_email', get_option( 'admin_email' ) );
		$to = is_email( $to ) ? $to : (string) get_option( 'admin_email' );

		$ok = false;
		try {
			$ok = (bool) wp_mail( $to, $subject, $body, array( 'Content-Type: text/plain; charset=UTF-8' ) );
		} catch ( \Throwable $e ) {
			$ok = false; // Delivery is best effort; the journal below is the fallback record.
		}

		// phpcs:ignore WordPress.DB.DirectDatabaseQuery.DirectQuery
		$wpdb->insert(
			self::table(),
			array(
				'created_at' => current_time( 'mysql', true ),
				'recipient'  => $to,
				'subject'    => mb_substr( $subject, 0, 250 ),
				'body'       => $body,
				'ref'        => mb_substr( $ref, 0, 40 ),
				'delivered'  => $ok ? 1 : 0,
			),
			array( '%s', '%s', '%s', '%s', '%s', '%d' )
		);
		return $ok;
	}

	/**
	 * Submenu under "Demandes".
	 */
	public static function menu() {
		add_submenu_page( 'asset-demandes', __( 'Journal des notifications', 'asset-congres-demo' ), __( 'Journal des notifications', 'asset-congres-demo' ), 'asset_manage_demandes', 'asset-notifications', array( __CLASS__, 'render' ) );
	}

	/**
	 * Journal screen.
	 */
	public static function render() {
		if ( ! current_user_can( 'asset_manage_demandes' ) ) {
			wp_die( esc_html__( 'Accès refusé.', 'asset-congres-demo' ), 403 );
		}
		global $wpdb;
		$table = self::table();
		// phpcs:ignore WordPress.DB.DirectDatabaseQuery,WordPress.DB.PreparedSQL.InterpolatedNotPrepared -- table name is internal.
		$rows = $wpdb->get_results( "SELECT * FROM {$table} ORDER BY id DESC LIMIT 200" );
		echo '<div class="wrap asset-admin"><h1>' . esc_html__( 'Journal des notifications', 'asset-congres-demo' ) . '</h1>';
		echo '<p class="description">' . esc_html__( 'Chaque notification envoyée à l’équipe est aussi enregistrée ici. Dans la démonstration (WordPress Playground), aucun serveur SMTP n’est configuré : l’envoi réel apparaît comme « non distribué ».', 'asset-congres-demo' ) . '</p>';
		if ( ! $rows ) {
			echo '<p>' . esc_html__( 'Aucune notification pour le moment.', 'asset-congres-demo' ) . '</p></div>';
			return;
		}
		echo '<table class="widefat striped"><thead><tr><th scope="col">' . esc_html__( 'Date (UTC)', 'asset-congres-demo' ) . '</th><th scope="col">' . esc_html__( 'Destinataire', 'asset-congres-demo' ) . '</th><th scope="col">' . esc_html__( 'Objet', 'asset-congres-demo' ) . '</th><th scope="col">' . esc_html__( 'Contenu', 'asset-congres-demo' ) . '</th><th scope="col">' . esc_html__( 'Distribution', 'asset-congres-demo' ) . '</th></tr></thead><tbody>';
		foreach ( $rows as $r ) {
			printf(
				'<tr><td>%1$s</td><td>%2$s</td><td>%3$s</td><td><pre class="asset-pre">%4$s</pre></td><td>%5$s</td></tr>',
				esc_html( $r->created_at ),
				esc_html( $r->recipient ),
				esc_html( $r->subject ),
				esc_html( $r->body ),
				$r->delivered ? esc_html__( 'Distribué', 'asset-congres-demo' ) : esc_html__( 'Non distribué (pas de SMTP)', 'asset-congres-demo' )
			);
		}
		echo '</tbody></table></div>';
	}
}
