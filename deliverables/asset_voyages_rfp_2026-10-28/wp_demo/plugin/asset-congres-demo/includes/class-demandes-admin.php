<?php
/**
 * Enquiries back office: list, detail, status workflow, history, CSV export, dashboard widget.
 *
 * @package AssetCongresDemo
 */

defined( 'ABSPATH' ) || exit;

if ( ! class_exists( 'WP_List_Table' ) ) {
	require_once ABSPATH . 'wp-admin/includes/class-wp-list-table.php';
}

/**
 * Admin screens for enquiries.
 */
class Asset_CD_Demandes_Admin {

	const CAP = 'asset_manage_demandes';

	/**
	 * Hooks.
	 */
	public static function init() {
		add_action( 'admin_menu', array( __CLASS__, 'menu' ) );
		add_action( 'admin_post_asset_demande_update', array( __CLASS__, 'handle_update' ) );
		add_action( 'admin_post_asset_demandes_export', array( __CLASS__, 'handle_export' ) );
		add_action( 'wp_dashboard_setup', array( __CLASS__, 'dashboard' ) );
		add_action( 'admin_enqueue_scripts', array( __CLASS__, 'assets' ) );
	}

	/**
	 * Admin CSS on plugin screens.
	 *
	 * @param string $hook Hook suffix.
	 */
	public static function assets( $hook ) {
		$screen = function_exists( 'get_current_screen' ) ? get_current_screen() : null;
		if ( str_contains( (string) $hook, 'asset-' ) || 'index.php' === $hook || ( $screen && Asset_CD_Congres::POST_TYPE === $screen->post_type ) ) {
			wp_enqueue_style( 'asset-cd-admin', ASSET_CD_URL . 'assets/css/admin.css', array(), ASSET_CD_VERSION );
		}
	}

	/**
	 * Menu.
	 */
	public static function menu() {
		add_menu_page( __( 'Demandes de devis', 'asset-congres-demo' ), __( 'Demandes', 'asset-congres-demo' ), self::CAP, 'asset-demandes', array( __CLASS__, 'render' ), 'dashicons-clipboard', 26 );
		add_submenu_page( 'asset-demandes', __( 'Demandes de devis', 'asset-congres-demo' ), __( 'Toutes les demandes', 'asset-congres-demo' ), self::CAP, 'asset-demandes', array( __CLASS__, 'render' ) );
	}

	/**
	 * Display name of a user (or a dash).
	 *
	 * @param int $user_id User ID.
	 * @return string
	 */
	public static function user_label( $user_id ) {
		if ( ! $user_id ) {
			return '—';
		}
		$u = get_userdata( (int) $user_id );
		return $u ? $u->display_name : '—';
	}

	/**
	 * Staff who can own an enquiry.
	 *
	 * @return WP_User[]
	 */
	public static function staff() {
		return get_users(
			array(
				'role__in' => array( 'administrator', 'asset_direction', 'asset_equipe' ),
				'orderby'  => 'display_name',
			)
		);
	}

	/**
	 * Status label.
	 *
	 * @param string $slug Slug.
	 * @return string
	 */
	public static function status_label( $slug ) {
		$s = Asset_CD_Demandes::statuses();
		return $s[ $slug ] ?? '—';
	}

	/**
	 * Reads list filters from GET.
	 *
	 * @return array{statut:string,s:string,orderby:string,order:string}
	 */
	public static function list_filters() {
		// phpcs:disable WordPress.Security.NonceVerification.Recommended -- read-only list filters.
		$statut  = isset( $_GET['statut'] ) ? sanitize_key( wp_unslash( $_GET['statut'] ) ) : '';
		$statut  = isset( Asset_CD_Demandes::statuses()[ $statut ] ) ? $statut : '';
		$s       = isset( $_GET['s'] ) ? mb_substr( sanitize_text_field( wp_unslash( $_GET['s'] ) ), 0, 100 ) : '';
		$orderby = isset( $_GET['orderby'] ) ? sanitize_key( wp_unslash( $_GET['orderby'] ) ) : 'date';
		$orderby = in_array( $orderby, array( 'date', 'reference', 'passagers', 'statut', 'depart' ), true ) ? $orderby : 'date';
		$order   = ( isset( $_GET['order'] ) && 'asc' === strtolower( sanitize_key( wp_unslash( $_GET['order'] ) ) ) ) ? 'ASC' : 'DESC';
		// phpcs:enable
		return compact( 'statut', 's', 'orderby', 'order' );
	}

	/**
	 * WP_Query args for the list/export.
	 *
	 * @param array $f        Filters.
	 * @param int   $per_page Per page (-1 = all).
	 * @param int   $paged    Page.
	 * @return array
	 */
	public static function query_args( $f, $per_page = 20, $paged = 1 ) {
		$args = array(
			'post_type'      => Asset_CD_Demandes::POST_TYPE,
			'post_status'    => array( 'private', 'publish', 'draft', 'pending' ),
			'posts_per_page' => $per_page,
			'paged'          => $paged,
			'meta_query'     => array( 'relation' => 'AND' ), // phpcs:ignore WordPress.DB.SlowDBQuery.slow_db_query_meta_query
		);
		if ( $f['statut'] ) {
			$args['meta_query'][] = array(
				'key'   => '_asset_statut',
				'value' => $f['statut'],
			);
		}
		if ( '' !== $f['s'] ) {
			$or = array( 'relation' => 'OR' );
			foreach ( array( '_asset_ref', '_asset_nom', '_asset_email', '_asset_societe', '_asset_ville_depart' ) as $k ) {
				$or[] = array(
					'key'     => $k,
					'value'   => $f['s'],
					'compare' => 'LIKE',
				);
			}
			$args['meta_query'][] = $or;
		}
		$map = array(
			'reference' => array( '_asset_ref', 'meta_value' ),
			'passagers' => array( '_asset_passagers', 'meta_value_num' ),
			'statut'    => array( '_asset_statut', 'meta_value' ),
			'depart'    => array( '_asset_date_aller', 'meta_value' ),
		);
		if ( isset( $map[ $f['orderby'] ] ) ) {
			$args['meta_key'] = $map[ $f['orderby'] ][0]; // phpcs:ignore WordPress.DB.SlowDBQuery.slow_db_query_meta_key
			$args['orderby']  = array(
				$map[ $f['orderby'] ][1] => $f['order'],
				'ID'                     => 'DESC',
			);
		} else {
			$args['orderby'] = array(
				'date' => $f['order'],
				'ID'   => $f['order'],
			);
		}
		return $args;
	}

	/**
	 * Count per status.
	 *
	 * @return array<string,int>
	 */
	public static function counts() {
		$out = array();
		foreach ( array_keys( Asset_CD_Demandes::statuses() ) as $slug ) {
			$q            = new WP_Query(
				self::query_args(
					array(
						'statut'  => $slug,
						's'       => '',
						'orderby' => 'date',
						'order'   => 'DESC',
					),
					1
				) + array( 'fields' => 'ids' )
			);
			$out[ $slug ] = (int) $q->found_posts;
		}
		return $out;
	}

	/**
	 * Router: list or detail.
	 */
	public static function render() {
		if ( ! current_user_can( self::CAP ) ) {
			wp_die( esc_html__( 'Accès refusé.', 'asset-congres-demo' ), 403 );
		}
		// phpcs:disable WordPress.Security.NonceVerification.Recommended
		$action = isset( $_GET['action'] ) ? sanitize_key( wp_unslash( $_GET['action'] ) ) : '';
		$id     = isset( $_GET['id'] ) ? absint( $_GET['id'] ) : 0;
		// phpcs:enable
		ob_start();
		if ( 'view' === $action && $id ) {
			self::render_detail( $id );
		} else {
			self::render_list();
		}
		echo Asset_CD_Ui::stack_tables( (string) ob_get_clean() ); // phpcs:ignore WordPress.Security.EscapeOutput.OutputNotEscaped -- body is escaped.
	}

	/**
	 * List screen.
	 */
	private static function render_list() {
		$f      = self::list_filters();
		$table  = new Asset_CD_Demandes_List_Table( $f );
		$counts = self::counts();
		$table->prepare_items();
		$base = admin_url( 'admin.php?page=asset-demandes' );
		echo '<div class="wrap asset-admin"><h1 class="wp-heading-inline">' . esc_html__( 'Demandes de devis', 'asset-congres-demo' ) . '</h1>';
		$export = wp_nonce_url(
			add_query_arg(
				array_filter(
					array(
						'action' => 'asset_demandes_export',
						'statut' => $f['statut'],
						's'      => $f['s'],
					)
				),
				admin_url( 'admin-post.php' )
			),
			'asset_demandes_export'
		);
		echo ' <a class="page-title-action" href="' . esc_url( $export ) . '">' . esc_html__( 'Exporter en CSV', 'asset-congres-demo' ) . '</a><hr class="wp-header-end" />';

		echo '<ul class="subsubsub">';
		$links   = array();
		$all     = array_sum( $counts );
		$links[] = sprintf( '<a href="%1$s"%2$s>%3$s <span class="count">(%4$d)</span></a>', esc_url( $base ), '' === $f['statut'] ? ' class="current" aria-current="page"' : '', esc_html__( 'Toutes', 'asset-congres-demo' ), (int) $all );
		foreach ( Asset_CD_Demandes::statuses() as $slug => $label ) {
			$links[] = sprintf( '<a href="%1$s"%2$s>%3$s <span class="count">(%4$d)</span></a>', esc_url( add_query_arg( 'statut', $slug, $base ) ), $slug === $f['statut'] ? ' class="current" aria-current="page"' : '', esc_html( $label ), (int) $counts[ $slug ] );
		}
		echo '<li>' . implode( ' |</li><li>', $links ) . '</li></ul>'; // phpcs:ignore WordPress.Security.EscapeOutput.OutputNotEscaped -- built from escaped parts.

		echo '<form method="get"><input type="hidden" name="page" value="asset-demandes" />';
		if ( $f['statut'] ) {
			echo '<input type="hidden" name="statut" value="' . esc_attr( $f['statut'] ) . '" />';
		}
		// Visible label and hint (the core search box hides its label on small screens).
		echo '<p class="asset-search"><label for="asset-demandes-search-input">' . esc_html__( 'Rechercher une demande', 'asset-congres-demo' ) . '</label> <input type="search" id="asset-demandes-search-input" name="s" value="' . esc_attr( $f['s'] ) . '" placeholder="' . esc_attr__( 'Nom, e-mail, société, ville ou référence', 'asset-congres-demo' ) . '" /> <input type="submit" id="search-submit" class="button" value="' . esc_attr__( 'Rechercher', 'asset-congres-demo' ) . '" /></p>';
		$table->display();
		echo '</form></div>';
	}

	/**
	 * Detail screen.
	 *
	 * @param int $id Enquiry ID.
	 */
	private static function render_detail( $id ) {
		$post = get_post( $id );
		if ( ! $post || Asset_CD_Demandes::POST_TYPE !== $post->post_type ) {
			wp_die( esc_html__( 'Demande introuvable.', 'asset-congres-demo' ), 404 );
		}
		$m       = static function ( $k ) use ( $id ) {
			return (string) get_post_meta( $id, '_asset_' . $k, true );
		};
		$congres = (int) $m( 'congres_id' );
		$statut  = $m( 'statut' );
		$owner   = (int) $m( 'owner' );
		echo '<div class="wrap asset-admin">';
		/* translators: %s: reference. */
		echo '<h1>' . esc_html( sprintf( __( 'Demande %s', 'asset-congres-demo' ), $m( 'ref' ) ) ) . '</h1>';
		echo '<p><a href="' . esc_url( admin_url( 'admin.php?page=asset-demandes' ) ) . '">' . esc_html__( 'Retour à la liste', 'asset-congres-demo' ) . '</a></p>';
		// phpcs:ignore WordPress.Security.NonceVerification.Recommended
		if ( isset( $_GET['updated'] ) ) {
			echo '<div class="notice inline notice-success"><p>' . esc_html__( 'Demande mise à jour.', 'asset-congres-demo' ) . '</p></div>';
		}

		$rows = array(
			__( 'Référence', 'asset-congres-demo' )         => $m( 'ref' ),
			__( 'Reçue le', 'asset-congres-demo' )          => Asset_CD_Ui::datetime( $post->post_date_gmt ),
			__( 'Congrès', 'asset-congres-demo' )           => $congres ? get_the_title( $congres ) : '—',
			__( 'Nom', 'asset-congres-demo' )               => $m( 'nom' ),
			__( 'E-mail', 'asset-congres-demo' )            => $m( 'email' ),
			__( 'Téléphone', 'asset-congres-demo' )         => $m( 'telephone' ),
			__( 'Société', 'asset-congres-demo' )           => $m( 'societe' ),
			__( 'Ville de départ', 'asset-congres-demo' )   => $m( 'ville_depart' ),
			__( 'Date aller', 'asset-congres-demo' )        => Asset_CD_Ui::date( $m( 'date_aller' ) ),
			__( 'Date retour', 'asset-congres-demo' )       => Asset_CD_Ui::date( $m( 'date_retour' ) ),
			__( 'Passagers', 'asset-congres-demo' )         => $m( 'passagers' ),
			__( 'Message', 'asset-congres-demo' )           => $m( 'message' ),
			__( 'Consentement RGPD', 'asset-congres-demo' ) => Asset_CD_Ui::datetime( $m( 'consent_at' ) ),
		);
		echo '<div class="asset-cols"><div class="asset-panel"><h2>' . esc_html__( 'Détails', 'asset-congres-demo' ) . '</h2><table class="widefat striped asset-kv"><tbody>';
		foreach ( $rows as $label => $value ) {
			echo '<tr><th scope="row">' . esc_html( $label ) . '</th><td>' . Asset_CD_Ui::nowrap_suffix( nl2br( esc_html( '' === $value ? '—' : $value ) ) ) . '</td></tr>'; // phpcs:ignore WordPress.Security.EscapeOutput.OutputNotEscaped -- escaped, then a span added.
		}
		echo '</tbody></table></div>';

		echo '<div class="asset-panel"><h2>' . esc_html__( 'Suivi', 'asset-congres-demo' ) . '</h2>';
		echo '<form method="post" action="' . esc_url( admin_url( 'admin-post.php' ) ) . '">';
		echo '<input type="hidden" name="action" value="asset_demande_update" /><input type="hidden" name="id" value="' . esc_attr( (string) $id ) . '" />';
		wp_nonce_field( 'asset_demande_update_' . $id, 'asset_nonce' );
		echo '<p><label for="asset-statut">' . esc_html__( 'Statut', 'asset-congres-demo' ) . '</label><br /><select id="asset-statut" name="statut">';
		foreach ( Asset_CD_Demandes::statuses() as $slug => $label ) {
			echo '<option value="' . esc_attr( $slug ) . '"' . selected( $statut, $slug, false ) . '>' . esc_html( $label ) . '</option>';
		}
		echo '</select></p>';
		echo '<p><label for="asset-owner">' . esc_html__( 'Responsable', 'asset-congres-demo' ) . '</label><br /><select id="asset-owner" name="owner"><option value="0">' . esc_html__( 'Non attribuée', 'asset-congres-demo' ) . '</option>';
		foreach ( self::staff() as $u ) {
			echo '<option value="' . esc_attr( (string) $u->ID ) . '"' . selected( $owner, $u->ID, false ) . '>' . esc_html( $u->display_name ) . '</option>';
		}
		echo '</select></p>';
		echo '<p><label for="asset-note">' . esc_html__( 'Ajouter une note interne', 'asset-congres-demo' ) . '</label><br /><textarea id="asset-note" name="note" rows="4" class="large-text" maxlength="2000"></textarea></p>';
		submit_button( __( 'Enregistrer', 'asset-congres-demo' ), 'primary', 'submit', false );
		echo '</form></div></div>';

		echo '<h2>' . esc_html__( 'Historique', 'asset-congres-demo' ) . '</h2>';
		echo '<p class="description">' . esc_html__( 'Journal en ajout seul : les entrées ne sont jamais modifiées ni supprimées.', 'asset-congres-demo' ) . '</p>';
		echo '<table class="widefat striped asset-history asset-stack"><thead><tr><th scope="col">' . esc_html__( 'Date', 'asset-congres-demo' ) . '</th><th scope="col">' . esc_html__( 'Par', 'asset-congres-demo' ) . '</th><th scope="col">' . esc_html__( 'Action', 'asset-congres-demo' ) . '</th><th scope="col">' . esc_html__( 'Détail', 'asset-congres-demo' ) . '</th></tr></thead><tbody>';
		foreach ( array_reverse( Asset_CD_Demandes::history( $id ) ) as $h ) {
			$type = (string) ( $h['type'] ?? '' );
			$by   = empty( $h['user'] ) ? __( 'Formulaire public', 'asset-congres-demo' ) : self::user_label( (int) $h['user'] );
			switch ( $type ) {
				case 'created':
					$action = __( 'Demande reçue', 'asset-congres-demo' );
					$detail = self::status_label( (string) ( $h['to'] ?? '' ) );
					break;
				case 'status':
					$action = __( 'Statut', 'asset-congres-demo' );
					$detail = self::status_label( (string) ( $h['from'] ?? '' ) ) . ' → ' . self::status_label( (string) ( $h['to'] ?? '' ) );
					break;
				case 'owner':
					$action = __( 'Responsable', 'asset-congres-demo' );
					$detail = self::user_label( (int) ( $h['from'] ?? 0 ) ) . ' → ' . self::user_label( (int) ( $h['to'] ?? 0 ) );
					break;
				default:
					$action = __( 'Note interne', 'asset-congres-demo' );
					$detail = (string) ( $h['note'] ?? '' );
			}
			echo '<tr><td>' . esc_html( Asset_CD_Ui::datetime( (string) ( $h['at'] ?? '' ) ) ) . '</td><td>' . esc_html( $by ) . '</td><td>' . esc_html( $action ) . '</td><td>' . nl2br( esc_html( $detail ) ) . '</td></tr>';
		}
		echo '</tbody></table></div>';
	}

	/**
	 * Saves status / owner / note.
	 */
	public static function handle_update() {
		$id = isset( $_POST['id'] ) ? absint( $_POST['id'] ) : 0; // phpcs:ignore WordPress.Security.NonceVerification.Missing -- verified next line.
		if ( ! $id || ! isset( $_POST['asset_nonce'] ) || ! wp_verify_nonce( sanitize_key( wp_unslash( $_POST['asset_nonce'] ) ), 'asset_demande_update_' . $id ) ) {
			wp_die( esc_html__( 'Lien expiré ou invalide.', 'asset-congres-demo' ), 403 );
		}
		if ( ! current_user_can( self::CAP ) ) {
			wp_die( esc_html__( 'Accès refusé.', 'asset-congres-demo' ), 403 );
		}
		$post = get_post( $id );
		if ( ! $post || Asset_CD_Demandes::POST_TYPE !== $post->post_type ) {
			wp_die( esc_html__( 'Demande introuvable.', 'asset-congres-demo' ), 404 );
		}
		$statut = isset( $_POST['statut'] ) ? sanitize_key( wp_unslash( $_POST['statut'] ) ) : '';
		$owner  = isset( $_POST['owner'] ) ? absint( $_POST['owner'] ) : 0;
		$note   = isset( $_POST['note'] ) ? mb_substr( sanitize_textarea_field( wp_unslash( $_POST['note'] ) ), 0, 2000 ) : '';

		$old_statut = (string) get_post_meta( $id, '_asset_statut', true );
		if ( $statut && $statut !== $old_statut && isset( Asset_CD_Demandes::statuses()[ $statut ] ) ) {
			update_post_meta( $id, '_asset_statut', $statut );
			Asset_CD_Demandes::add_history( $id, 'status', $old_statut, $statut );
		}
		$old_owner = (int) get_post_meta( $id, '_asset_owner', true );
		if ( $owner !== $old_owner ) {
			$valid = 0 === $owner || in_array( $owner, wp_list_pluck( self::staff(), 'ID' ), true );
			if ( $valid ) {
				update_post_meta( $id, '_asset_owner', $owner );
				Asset_CD_Demandes::add_history( $id, 'owner', (string) $old_owner, (string) $owner );
			}
		}
		if ( '' !== trim( $note ) ) {
			Asset_CD_Demandes::add_history( $id, 'note', '', '', $note );
		}
		wp_safe_redirect( admin_url( 'admin.php?page=asset-demandes&action=view&updated=1&id=' . $id ), 303 );
		exit;
	}

	/**
	 * Neutralises spreadsheet formula injection.
	 *
	 * @param mixed $value Cell.
	 * @return string
	 */
	public static function csv_cell( $value ) {
		$value = (string) $value;
		if ( '' !== $value && in_array( $value[0], array( '=', '+', '-', '@', "\t", "\r" ), true ) ) {
			$value = "'" . $value;
		}
		return $value;
	}

	/**
	 * CSV export of the current filter.
	 */
	public static function handle_export() {
		if ( ! isset( $_GET['_wpnonce'] ) || ! wp_verify_nonce( sanitize_key( wp_unslash( $_GET['_wpnonce'] ) ), 'asset_demandes_export' ) ) {
			wp_die( esc_html__( 'Lien expiré ou invalide.', 'asset-congres-demo' ), 403 );
		}
		if ( ! current_user_can( self::CAP ) ) {
			wp_die( esc_html__( 'Accès refusé.', 'asset-congres-demo' ), 403 );
		}
		$f     = self::list_filters();
		$posts = get_posts( self::query_args( $f, 5000 ) + array( 'no_found_rows' => true ) );

		nocache_headers();
		header( 'Content-Type: text/csv; charset=UTF-8' );
		header( 'Content-Disposition: attachment; filename="demandes-asset-' . wp_date( 'Ymd' ) . '.csv"' ); // Paris date, not UTC (CE-B2-001).
		header( 'X-Content-Type-Options: nosniff' );
		$out = fopen( 'php://output', 'w' ); // phpcs:ignore WordPress.WP.AlternativeFunctions.file_system_operations_fopen
		fwrite( $out, "\xEF\xBB\xBF" ); // phpcs:ignore WordPress.WP.AlternativeFunctions.file_system_operations_fwrite -- UTF-8 BOM for Excel.
		$head = array( 'Référence', 'Reçue le', 'Congrès', 'Nom', 'E-mail', 'Téléphone', 'Société', 'Ville de départ', 'Date aller', 'Date retour', 'Passagers', 'Statut', 'Responsable', 'Message' );
		fputcsv( $out, $head, ';', '"', '' );
		foreach ( $posts as $p ) {
			$m   = static function ( $k ) use ( $p ) {
				return (string) get_post_meta( $p->ID, '_asset_' . $k, true );
			};
			$cid = (int) $m( 'congres_id' );
			$row = array( $m( 'ref' ), Asset_CD_Ui::datetime( $p->post_date_gmt ), $cid ? get_the_title( $cid ) : '', $m( 'nom' ), $m( 'email' ), $m( 'telephone' ), $m( 'societe' ), $m( 'ville_depart' ), Asset_CD_Ui::date( $m( 'date_aller' ) ), Asset_CD_Ui::date( $m( 'date_retour' ) ), $m( 'passagers' ), self::status_label( $m( 'statut' ) ), (int) $m( 'owner' ) ? self::user_label( (int) $m( 'owner' ) ) : '', $m( 'message' ) );
			fputcsv( $out, array_map( array( __CLASS__, 'csv_cell' ), $row ), ';', '"', '' );
		}
		fclose( $out ); // phpcs:ignore WordPress.WP.AlternativeFunctions.file_system_operations_fclose
		exit;
	}

	/**
	 * Dashboard widget registration.
	 */
	public static function dashboard() {
		if ( current_user_can( self::CAP ) ) {
			wp_add_dashboard_widget( 'asset_cd_demandes', __( 'Demandes de devis par statut', 'asset-congres-demo' ), array( __CLASS__, 'render_widget' ) );
		}
	}

	/**
	 * Dashboard widget.
	 */
	public static function render_widget() {
		$counts = self::counts();
		$latest = get_posts( self::query_args( array( 'statut' => '', 's' => '', 'orderby' => 'date', 'order' => 'DESC' ), 1 ) + array( 'no_found_rows' => true ) );
		if ( $latest ) {
			$l   = $latest[0];
			$cid = (int) get_post_meta( $l->ID, '_asset_congres_id', true );
			echo '<p class="asset-widget-latest">' . esc_html__( 'Dernière demande :', 'asset-congres-demo' ) . ' <a class="asset-latest-link" href="' . esc_url( admin_url( 'admin.php?page=asset-demandes&action=view&id=' . $l->ID ) ) . '">' . Asset_CD_Ui::nowrap_suffix( esc_html( (string) get_post_meta( $l->ID, '_asset_ref', true ) . ' · ' . get_post_meta( $l->ID, '_asset_nom', true ) . ( $cid ? ' · ' . get_the_title( $cid ) : '' ) ) ) . '</a></p>'; // phpcs:ignore WordPress.Security.EscapeOutput.OutputNotEscaped -- escaped, then a span added.
		}
		echo '<ul class="asset-widget">';
		foreach ( Asset_CD_Demandes::statuses() as $slug => $label ) {
			printf( '<li><a href="%1$s"><span class="asset-widget__n">%2$d</span> %3$s</a></li>', esc_url( admin_url( 'admin.php?page=asset-demandes&statut=' . $slug ) ), (int) $counts[ $slug ], esc_html( $label ) );
		}
		echo '</ul><p><a href="' . esc_url( admin_url( 'admin.php?page=asset-demandes' ) ) . '">' . esc_html__( 'Voir toutes les demandes', 'asset-congres-demo' ) . '</a></p>';
	}
}

/**
 * List table for enquiries.
 */
class Asset_CD_Demandes_List_Table extends WP_List_Table {

	/**
	 * Filters.
	 *
	 * @var array
	 */
	private $filters;

	/**
	 * Constructor.
	 *
	 * @param array $filters Filters.
	 */
	public function __construct( $filters ) {
		$this->filters = $filters;
		parent::__construct(
			array(
				'singular' => 'demande',
				'plural'   => 'demandes',
				'ajax'     => false,
			)
		);
	}

	/**
	 * Columns.
	 *
	 * @return array
	 */
	public function get_columns() {
		return array(
			'reference'   => __( 'Référence', 'asset-congres-demo' ),
			'date'        => __( 'Date', 'asset-congres-demo' ),
			'congres'     => __( 'Congrès', 'asset-congres-demo' ),
			'contact'     => __( 'Contact', 'asset-congres-demo' ),
			'depart'      => __( 'Départ', 'asset-congres-demo' ),
			'dates'       => __( 'Dates', 'asset-congres-demo' ),
			'passagers'   => __( 'Passagers', 'asset-congres-demo' ),
			'statut'      => __( 'Statut', 'asset-congres-demo' ),
			'responsable' => __( 'Responsable', 'asset-congres-demo' ),
		);
	}

	/**
	 * Sortable columns.
	 *
	 * @return array
	 */
	protected function get_sortable_columns() {
		return array(
			'reference' => array( 'reference', false ),
			'date'      => array( 'date', true ),
			'dates'     => array( 'depart', false ),
			'passagers' => array( 'passagers', false ),
			'statut'    => array( 'statut', false ),
		);
	}

	/**
	 * Loads items.
	 */
	public function prepare_items() {
		$per   = 20;
		$paged = $this->get_pagenum();
		$q     = new WP_Query( Asset_CD_Demandes_Admin::query_args( $this->filters, $per, $paged ) );
		$this->items = $q->posts;
		$this->_column_headers = array( $this->get_columns(), array(), $this->get_sortable_columns(), 'reference' );
		$this->set_pagination_args(
			array(
				'total_items' => (int) $q->found_posts,
				'per_page'    => $per,
			)
		);
	}

	/**
	 * Empty state.
	 */
	public function no_items() {
		esc_html_e( 'Aucune demande ne correspond.', 'asset-congres-demo' );
	}

	/**
	 * Cell renderer.
	 *
	 * @param WP_Post $item Post.
	 * @param string  $col  Column.
	 * @return string
	 */
	protected function column_default( $item, $col ) {
		$m = static function ( $k ) use ( $item ) {
			return (string) get_post_meta( $item->ID, '_asset_' . $k, true );
		};
		switch ( $col ) {
			case 'reference':
				$url = admin_url( 'admin.php?page=asset-demandes&action=view&id=' . $item->ID );
				return '<strong><a class="row-title" href="' . esc_url( $url ) . '">' . esc_html( $m( 'ref' ) ) . '</a></strong>';
			case 'date':
				return esc_html( Asset_CD_Ui::datetime( $item->post_date_gmt ) );
			case 'congres':
				$cid = (int) $m( 'congres_id' );
				return Asset_CD_Ui::nowrap_suffix( esc_html( $cid ? get_the_title( $cid ) : '—' ) );
			case 'contact':
				$soc = $m( 'societe' );
				return esc_html( $m( 'nom' ) ) . '<br /><span class="description asset-email">' . str_replace( '@', '<wbr>@', esc_html( $m( 'email' ) ) ) . '</span>' . ( $soc ? '<br /><span class="description">' . esc_html( $soc ) . '</span>' : '' );
			case 'depart':
				return esc_html( $m( 'ville_depart' ) );
			case 'dates':
				$a = $m( 'date_aller' );
				$r = $m( 'date_retour' );
				return esc_html( Asset_CD_Ui::date( $a ) . ' → ' . Asset_CD_Ui::date( $r ) );
			case 'passagers':
				return esc_html( $m( 'passagers' ) );
			case 'statut':
				$s = $m( 'statut' );
				return '<span class="asset-status asset-status--' . esc_attr( $s ) . '">' . esc_html( Asset_CD_Demandes_Admin::status_label( $s ) ) . '</span>';
			case 'responsable':
				return esc_html( Asset_CD_Demandes_Admin::user_label( (int) $m( 'owner' ) ) );
		}
		return '';
	}
}
