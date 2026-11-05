<?php
/**
 * GM&E admin screens: codes (masked), access requests, approvals, reveal, audit log.
 *
 * @package AssetCongresDemo
 */

defined( 'ABSPATH' ) || exit;

/**
 * GM&E back office.
 */
class Asset_CD_Gme_Admin {

	/**
	 * Codes revealed during this request (congres_id => code). Never persisted.
	 *
	 * @var array<int,string>
	 */
	private static $revealed = array();

	/**
	 * Reveal outcome message for this request.
	 *
	 * @var string
	 */
	private static $reveal_msg = '';

	/**
	 * Hooks.
	 */
	public static function init() {
		add_action( 'admin_menu', array( __CLASS__, 'menu' ) );
		add_action( 'admin_post_asset_gme_request', array( __CLASS__, 'handle_request' ) );
		add_action( 'admin_post_asset_gme_decide', array( __CLASS__, 'handle_decide' ) );
		add_action( 'admin_post_asset_gme_save', array( __CLASS__, 'handle_save' ) );
		add_action( 'wp_dashboard_setup', array( __CLASS__, 'dashboard' ) );
		add_action( 'admin_notices', array( __CLASS__, 'dashboard_notice' ) );
	}

	/**
	 * Decision feedback on the dashboard (decisions taken from the widget).
	 */
	public static function dashboard_notice() {
		$screen = get_current_screen();
		if ( $screen && 'dashboard' === $screen->id && current_user_can( 'asset_manage_gme' ) ) {
			if ( ! Asset_CD_Gme::key_ok() ) {
				self::notice( 'nokey' );
			}
			self::notice( self::msg_param() );
		}
	}

	/**
	 * Menus.
	 */
	public static function menu() {
		$hook = add_menu_page( __( 'Accès GM&E', 'asset-congres-demo' ), __( 'Accès GM&E', 'asset-congres-demo' ), 'asset_view_gme', 'asset-gme', array( __CLASS__, 'render_codes' ), 'dashicons-lock', 27 );
		add_submenu_page( 'asset-gme', __( 'Codes GM&E', 'asset-congres-demo' ), __( 'Codes GM&E', 'asset-congres-demo' ), 'asset_view_gme', 'asset-gme', array( __CLASS__, 'render_codes' ) );
		add_submenu_page( 'asset-gme', __( 'Demandes d’accès', 'asset-congres-demo' ), __( 'Demandes d’accès', 'asset-congres-demo' ), 'asset_manage_gme', 'asset-gme-acces', array( __CLASS__, 'render_access' ) );
		add_submenu_page( 'asset-gme', __( 'Journal GM&E', 'asset-congres-demo' ), __( 'Journal GM&E', 'asset-congres-demo' ), 'asset_manage_gme', 'asset-gme-journal', array( __CLASS__, 'render_log' ) );
		add_action( 'load-' . $hook, array( __CLASS__, 'maybe_reveal' ) );
	}

	/**
	 * Processes a reveal POST before the page renders (result shown only in this response).
	 */
	public static function maybe_reveal() {
		if ( ! isset( $_SERVER['REQUEST_METHOD'] ) || 'POST' !== $_SERVER['REQUEST_METHOD'] ) {
			return;
		}
		// phpcs:disable WordPress.Security.NonceVerification.Missing -- verified below; failures are logged.
		if ( ! isset( $_POST['asset_gme_action'] ) || 'reveal' !== $_POST['asset_gme_action'] ) {
			return;
		}
		$cid   = isset( $_POST['congres_id'] ) ? absint( $_POST['congres_id'] ) : 0;
		$nonce = isset( $_POST['asset_nonce'] ) ? sanitize_key( wp_unslash( $_POST['asset_nonce'] ) ) : '';
		// phpcs:enable
		$uid = get_current_user_id();
		nocache_headers();
		if ( ! $cid || ! $nonce || ! wp_verify_nonce( $nonce, 'asset_gme_reveal_' . $cid ) ) {
			Asset_CD_Gme::log( $uid, $cid, 'reveal_refused', __( 'Jeton de sécurité invalide', 'asset-congres-demo' ) );
			self::$reveal_msg = 'refused_nonce';
			return;
		}
		$code = Asset_CD_Gme::reveal( $uid, $cid );
		if ( null === $code ) {
			self::$reveal_msg = Asset_CD_Gme::key_ok() || ! Asset_CD_Gme::can_reveal( $uid, $cid ) ? 'refused' : 'nokey';
			return;
		}
		self::$revealed[ $cid ] = $code;
		self::$reveal_msg       = 'revealed';
	}

	/**
	 * Notice messages (whitelisted keys only).
	 *
	 * @return array<string,array{0:string,1:string}>
	 */
	private static function messages() {
		return array(
			'requested'     => array( 'success', __( 'Demande d’accès envoyée à la Direction.', 'asset-congres-demo' ) ),
			'reason'        => array( 'error', __( 'Indiquez la raison de votre demande d’accès.', 'asset-congres-demo' ) ),
			'exists'        => array( 'warning', __( 'Une demande est déjà en cours ou un accès est déjà actif pour ce congrès.', 'asset-congres-demo' ) ),
			'approve'       => array( 'success', __( 'Accès approuvé pour 24 heures.', 'asset-congres-demo' ) ),
			'refuse'        => array( 'success', __( 'Demande refusée.', 'asset-congres-demo' ) ),
			'revoke'        => array( 'success', __( 'Accès révoqué immédiatement.', 'asset-congres-demo' ) ),
			'state'         => array( 'error', __( 'Cette action n’est pas possible dans l’état actuel de la demande.', 'asset-congres-demo' ) ),
			'saved'         => array( 'success', __( 'Code enregistré (chiffré).', 'asset-congres-demo' ) ),
			'invalid'       => array( 'error', __( 'Données invalides : vérifiez le congrès, le format du code (lettres majuscules, chiffres, tirets) et les dates.', 'asset-congres-demo' ) ),
			'revealed'      => array( 'info', __( 'Code affiché une seule fois. Cette consultation est enregistrée dans le journal GM&E.', 'asset-congres-demo' ) ),
			'refused'       => array( 'error', __( 'Accès refusé : aucune autorisation active pour ce congrès. La tentative est enregistrée.', 'asset-congres-demo' ) ),
			'nokey'         => array( 'error', __( 'Clé de chiffrement GM&E absente ou invalide : l’enregistrement et la révélation des codes sont désactivés. Définissez ASSET_GME_KEY (64 caractères hexadécimaux) dans wp-config.php.', 'asset-congres-demo' ) ),
			'refused_nonce' => array( 'error', __( 'Accès refusé : jeton de sécurité invalide ou expiré. La tentative est enregistrée.', 'asset-congres-demo' ) ),
		);
	}

	/**
	 * Prints a notice for a message key.
	 *
	 * @param string $key Key.
	 */
	private static function notice( $key ) {
		$all = self::messages();
		if ( isset( $all[ $key ] ) ) {
			printf( '<div class="notice notice-%1$s asset-notice-%3$s"><p>%2$s</p></div>', esc_attr( $all[ $key ][0] ), esc_html( $all[ $key ][1] ), esc_attr( $key ) );
		}
	}

	/**
	 * Message key from the query string.
	 *
	 * @return string
	 */
	private static function msg_param() {
		return isset( $_GET['msg'] ) ? sanitize_key( wp_unslash( $_GET['msg'] ) ) : ''; // phpcs:ignore WordPress.Security.NonceVerification.Recommended
	}

	/**
	 * Masked code markup.
	 *
	 * @return string
	 */
	private static function masked() {
		return '<span class="asset-masked" aria-label="' . esc_attr__( 'Code masqué', 'asset-congres-demo' ) . '">•••• •••• ••••</span>';
	}

	/**
	 * Formats a UTC datetime for display.
	 *
	 * @param string $utc UTC datetime.
	 * @return string
	 */
	public static function dt( $utc ) {
		return Asset_CD_Ui::datetime( (string) $utc );
	}

	/**
	 * Decision buttons for a pending request.
	 *
	 * @param object $r    Request.
	 * @param string $back Return page slug.
	 * @return string
	 */
	public static function decision_forms( $r, $back ) {
		$state = Asset_CD_Gme::effective_status( $r );
		$html  = '';
		$btns  = array();
		if ( 'pending' === $state ) {
			$btns = array(
				'approve' => array( __( 'Approuver (24 h)', 'asset-congres-demo' ), 'button button-primary' ),
				'refuse'  => array( __( 'Refuser', 'asset-congres-demo' ), 'button' ),
			);
		} elseif ( 'approved' === $state ) {
			$btns = array( 'revoke' => array( __( 'Révoquer', 'asset-congres-demo' ), 'button asset-btn-danger' ) );
		}
		foreach ( $btns as $decision => $b ) {
			$html .= '<form method="post" action="' . esc_url( admin_url( 'admin-post.php' ) ) . '" class="asset-inline-form">'
				. '<input type="hidden" name="action" value="asset_gme_decide" />'
				. '<input type="hidden" name="request_id" value="' . esc_attr( (string) $r->id ) . '" />'
				. '<input type="hidden" name="decision" value="' . esc_attr( $decision ) . '" />'
				. '<input type="hidden" name="back" value="' . esc_attr( $back ) . '" />'
				. wp_nonce_field( 'asset_gme_' . $decision . '_' . $r->id, 'asset_nonce', false, false )
				. '<button type="submit" class="' . esc_attr( $b[1] ) . '">' . esc_html( $b[0] ) . '</button></form>';
		}
		return $html;
	}

	/**
	 * Pending request table (Direction).
	 *
	 * @param string $back Return slug.
	 */
	private static function pending_table( $back ) {
		$pending = Asset_CD_Gme::requests( 'pending' );
		echo '<h2>' . esc_html__( 'Demandes d’accès en attente', 'asset-congres-demo' ) . '</h2>';
		if ( ! $pending ) {
			echo '<p>' . esc_html__( 'Aucune demande en attente.', 'asset-congres-demo' ) . '</p>';
			return;
		}
		echo '<table class="widefat striped asset-pending asset-stack"><thead><tr><th scope="col">' . esc_html__( 'Demandeur', 'asset-congres-demo' ) . '</th><th scope="col">' . esc_html__( 'Congrès', 'asset-congres-demo' ) . '</th><th scope="col">' . esc_html__( 'Raison', 'asset-congres-demo' ) . '</th><th scope="col">' . esc_html__( 'Demandée le', 'asset-congres-demo' ) . '</th><th scope="col">' . esc_html__( 'Décision', 'asset-congres-demo' ) . '</th></tr></thead><tbody>';
		foreach ( $pending as $r ) {
			echo '<tr><td>' . esc_html( Asset_CD_Demandes_Admin::user_label( (int) $r->user_id ) ) . '</td><td>' . esc_html( get_the_title( (int) $r->congres_id ) ) . '</td><td>' . esc_html( $r->reason ) . '</td><td>' . esc_html( self::dt( $r->requested_at ) ) . '</td><td>' . self::decision_forms( $r, $back ) . '</td></tr>'; // phpcs:ignore WordPress.Security.EscapeOutput.OutputNotEscaped -- decision_forms escapes.
		}
		echo '</tbody></table>';
	}

	/**
	 * Main screen: codes list (masked), request/reveal actions, Direction tools.
	 */
	public static function render_codes() {
		ob_start();
		self::render_codes_body();
		echo Asset_CD_Ui::stack_tables( (string) ob_get_clean() ); // phpcs:ignore WordPress.Security.EscapeOutput.OutputNotEscaped -- body is escaped; only data-label attributes (esc_attr) are added.
	}

	/**
	 * Screen body.
	 */
	private static function render_codes_body() {
		if ( ! current_user_can( 'asset_view_gme' ) ) {
			wp_die( esc_html__( 'Accès refusé.', 'asset-congres-demo' ), 403 );
		}
		$uid    = get_current_user_id();
		$manage = current_user_can( 'asset_manage_gme' );
		$codes  = Asset_CD_Gme::all_codes();
		$labels = Asset_CD_Gme::statuses();

		echo '<div class="wrap asset-admin"><h1>' . esc_html__( 'Accès GM&E', 'asset-congres-demo' ) . '</h1>';
		echo '<p class="description">' . esc_html__( 'Codes tarifaires Air France-KLM Global Meetings & Events (codes fictifs de démonstration). Ils sont chiffrés, masqués par défaut et chaque consultation est enregistrée.', 'asset-congres-demo' ) . '</p>';
		if ( ! Asset_CD_Gme::key_ok() && 'nokey' !== self::$reveal_msg ) {
			self::notice( 'nokey' );
		}
		self::notice( self::$reveal_msg ? self::$reveal_msg : self::msg_param() );

		if ( $manage ) {
			self::pending_table( 'asset-gme' );
			echo '<h2>' . esc_html__( 'Codes', 'asset-congres-demo' ) . '</h2>';
		}

		if ( ! $codes ) {
			echo '<p>' . esc_html__( 'Aucun code enregistré.', 'asset-congres-demo' ) . '</p>';
		} else {
			echo '<table class="widefat striped asset-gme-table asset-stack"><thead><tr><th scope="col">' . esc_html__( 'Congrès', 'asset-congres-demo' ) . '</th><th scope="col">' . esc_html__( 'Code', 'asset-congres-demo' ) . '</th><th scope="col">' . esc_html__( 'Statut', 'asset-congres-demo' ) . '</th><th scope="col">' . esc_html__( 'Validité', 'asset-congres-demo' ) . '</th><th scope="col">' . esc_html__( 'Preuve', 'asset-congres-demo' ) . '</th><th scope="col">' . esc_html__( 'Accès', 'asset-congres-demo' ) . '</th></tr></thead><tbody>';
			foreach ( $codes as $row ) {
				$cid = (int) $row->congres_id;
				echo '<tr data-congres="' . esc_attr( (string) $cid ) . '"><td><strong>' . esc_html( get_the_title( $cid ) ) . '</strong></td><td>';
				if ( isset( self::$revealed[ $cid ] ) ) {
					echo '<code class="asset-revealed">' . esc_html( self::$revealed[ $cid ] ) . '</code>';
				} else {
					echo self::masked(); // phpcs:ignore WordPress.Security.EscapeOutput.OutputNotEscaped
				}
				echo '</td><td>' . esc_html( $labels[ $row->status ] ?? $row->status ) . '</td>';
				echo '<td>' . esc_html( ( $row->valid_from ? Asset_CD_Congres::format_date( $row->valid_from ) : '—' ) . ' → ' . ( $row->valid_to ? Asset_CD_Congres::format_date( $row->valid_to ) : '—' ) ) . '</td>';
				echo '<td>' . esc_html( $row->evidence ) . '</td><td class="asset-gme-actions">';
				self::row_actions( $uid, $cid, $manage, (string) $row->status );
				echo '</td></tr>';
			}
			echo '</tbody></table>';
		}

		if ( $manage ) {
			self::code_form( $codes );
		}
		echo '</div>';
	}

	/**
	 * Actions cell for a code row.
	 *
	 * @param int  $uid    User.
	 * @param int  $cid    Congress.
	 * @param bool $manage Direction.
	 */
	private static function row_actions( $uid, $cid, $manage, $status = '' ) {
		$reveal_form = static function () use ( $cid ) {
			echo '<form method="post" action="' . esc_url( admin_url( 'admin.php?page=asset-gme' ) ) . '" class="asset-inline-form">';
			echo '<input type="hidden" name="asset_gme_action" value="reveal" /><input type="hidden" name="congres_id" value="' . esc_attr( (string) $cid ) . '" />';
			wp_nonce_field( 'asset_gme_reveal_' . $cid, 'asset_nonce' );
			echo '<button type="submit" class="button button-primary">' . esc_html__( 'Révéler le code', 'asset-congres-demo' ) . '</button></form>';
		};
		if ( 'expire' === $status ) {
			echo '<p class="description asset-no-action">' . esc_html__( 'Code expiré : consultation fermée.', 'asset-congres-demo' ) . '</p>';
			if ( $manage ) {
				echo ' <a class="button" href="' . esc_url( admin_url( 'admin.php?page=asset-gme&edit=' . $cid . '#asset-gme-form' ) ) . '">' . esc_html__( 'Modifier', 'asset-congres-demo' ) . '</a>';
			}
			return;
		}
		if ( $manage ) {
			$reveal_form();
			echo ' <a class="button" href="' . esc_url( admin_url( 'admin.php?page=asset-gme&edit=' . $cid . '#asset-gme-form' ) ) . '">' . esc_html__( 'Modifier', 'asset-congres-demo' ) . '</a>';
			return;
		}
		$grant = Asset_CD_Gme::active_grant( $uid, $cid );
		if ( $grant ) {
			/* translators: %s: expiry date. */
			echo '<p class="asset-grant">' . esc_html( sprintf( __( 'Accès autorisé jusqu’au %s', 'asset-congres-demo' ), self::dt( $grant->expires_at ) ) ) . '</p>';
			$reveal_form();
			return;
		}
		if ( ! Asset_CD_Gme::requestable_status( $status ) ) {
			echo '<p class="description asset-no-action">' . esc_html__( 'Code en cours de vérification : pas encore de demande possible.', 'asset-congres-demo' ) . '</p>';
			return;
		}
		$latest = Asset_CD_Gme::latest_request( $uid, $cid );
		$state  = $latest ? Asset_CD_Gme::effective_status( $latest ) : '';
		if ( 'pending' === $state ) {
			echo '<p class="asset-pending-label">' . esc_html__( 'Demande en attente de la Direction', 'asset-congres-demo' ) . '</p>';
			return;
		}
		if ( $state ) {
			$labels = Asset_CD_Gme::request_labels();
			/* translators: %s: request status. */
			echo '<p class="description">' . esc_html( sprintf( __( 'Dernière demande : %s', 'asset-congres-demo' ), $labels[ $state ] ?? $state ) ) . '</p>';
		}
		$fid = 'asset-reason-' . $cid;
		echo '<form method="post" action="' . esc_url( admin_url( 'admin-post.php' ) ) . '" class="asset-request-form">';
		echo '<input type="hidden" name="action" value="asset_gme_request" /><input type="hidden" name="congres_id" value="' . esc_attr( (string) $cid ) . '" />';
		wp_nonce_field( 'asset_gme_request_' . $cid, 'asset_nonce' );
		echo '<label for="' . esc_attr( $fid ) . '">' . esc_html__( 'Raison de la demande (obligatoire)', 'asset-congres-demo' ) . '</label>';
		echo '<textarea id="' . esc_attr( $fid ) . '" name="reason" rows="2" maxlength="500" required></textarea>';
		echo '<button type="submit" class="button">' . esc_html__( 'Demander l’accès', 'asset-congres-demo' ) . '</button></form>';
	}

	/**
	 * Add / edit form (Direction). The current code is never prefilled.
	 *
	 * @param array $codes Existing rows.
	 */
	private static function code_form( $codes ) {
		$edit = isset( $_GET['edit'] ) ? absint( $_GET['edit'] ) : 0; // phpcs:ignore WordPress.Security.NonceVerification.Recommended
		$row  = $edit ? Asset_CD_Gme::get_by_congres( $edit ) : null;
		$all  = get_posts(
			array(
				'post_type'      => Asset_CD_Congres::POST_TYPE,
				'post_status'    => array( 'publish', 'draft', 'pending', 'future', 'private' ),
				'posts_per_page' => 500,
				'orderby'        => 'title',
				'order'          => 'ASC',
			)
		);
		echo '<h2 id="asset-gme-form">' . ( $row ? esc_html__( 'Modifier un code', 'asset-congres-demo' ) : esc_html__( 'Ajouter un code', 'asset-congres-demo' ) ) . '</h2>';
		echo '<form method="post" action="' . esc_url( admin_url( 'admin-post.php' ) ) . '" class="asset-gme-edit"><input type="hidden" name="action" value="asset_gme_save" />';
		wp_nonce_field( 'asset_gme_save', 'asset_nonce' );
		echo '<table class="form-table" role="presentation"><tbody>';
		echo '<tr><th scope="row"><label for="asset-gme-congres">' . esc_html__( 'Congrès', 'asset-congres-demo' ) . '</label></th><td><select id="asset-gme-congres" name="congres_id" required>';
		foreach ( $all as $p ) {
			echo '<option value="' . esc_attr( (string) $p->ID ) . '"' . ( (int) $p->ID === $edit ? ' selected' : '' ) . '>' . esc_html( get_the_title( $p ) ) . '</option>';
		}
		echo '</select></td></tr>';
		$ph = $row ? __( 'Laisser vide pour conserver le code actuel', 'asset-congres-demo' ) : 'DEMO-GME-XXXX';
		echo '<tr><th scope="row"><label for="asset-gme-code">' . esc_html__( 'Code', 'asset-congres-demo' ) . '</label></th><td><input type="text" id="asset-gme-code" name="code" value="" autocomplete="off" class="regular-text" placeholder="' . esc_attr( $ph ) . '" maxlength="40" /></td></tr>';
		echo '<tr><th scope="row"><label for="asset-gme-status">' . esc_html__( 'Statut', 'asset-congres-demo' ) . '</label></th><td><select id="asset-gme-status" name="status">';
		$current_status = $row ? (string) $row->status : 'detecte';
		foreach ( Asset_CD_Gme::statuses() as $k => $l ) {
			echo '<option value="' . esc_attr( $k ) . '"' . ( $k === $current_status ? ' selected' : '' ) . '>' . esc_html( $l ) . '</option>';
		}
		echo '</select></td></tr>';
		echo '<tr><th scope="row"><label for="asset-gme-from">' . esc_html__( 'Valide du', 'asset-congres-demo' ) . '</label></th><td><input type="date" id="asset-gme-from" name="valid_from" value="' . esc_attr( $row ? $row->valid_from : '' ) . '" /></td></tr>';
		echo '<tr><th scope="row"><label for="asset-gme-to">' . esc_html__( 'Valide jusqu’au', 'asset-congres-demo' ) . '</label></th><td><input type="date" id="asset-gme-to" name="valid_to" value="' . esc_attr( $row ? $row->valid_to : '' ) . '" /></td></tr>';
		echo '<tr><th scope="row"><label for="asset-gme-evidence">' . esc_html__( 'Note de preuve', 'asset-congres-demo' ) . '</label></th><td><textarea id="asset-gme-evidence" name="evidence" rows="3" class="large-text" maxlength="500">' . esc_textarea( $row ? $row->evidence : '' ) . '</textarea></td></tr>';
		echo '</tbody></table>';
		submit_button( __( 'Enregistrer le code', 'asset-congres-demo' ) );
		echo '</form>';
	}

	/**
	 * Redirects to a whitelisted admin page with a message.
	 *
	 * @param string $back Slug.
	 * @param string $msg  Message key.
	 */
	private static function back( $back, $msg ) {
		$url = 'dashboard' === $back ? admin_url( 'index.php' ) : admin_url( 'admin.php?page=' . ( in_array( $back, array( 'asset-gme', 'asset-gme-acces' ), true ) ? $back : 'asset-gme' ) );
		wp_safe_redirect( add_query_arg( 'msg', $msg, $url ), 303 );
		exit;
	}

	/**
	 * Access request (Équipe).
	 */
	public static function handle_request() {
		$cid = isset( $_POST['congres_id'] ) ? absint( $_POST['congres_id'] ) : 0; // phpcs:ignore WordPress.Security.NonceVerification.Missing -- verified next.
		if ( ! $cid || ! isset( $_POST['asset_nonce'] ) || ! wp_verify_nonce( sanitize_key( wp_unslash( $_POST['asset_nonce'] ) ), 'asset_gme_request_' . $cid ) ) {
			wp_die( esc_html__( 'Lien expiré ou invalide.', 'asset-congres-demo' ), 403 );
		}
		if ( ! current_user_can( 'asset_view_gme' ) ) {
			wp_die( esc_html__( 'Accès refusé.', 'asset-congres-demo' ), 403 );
		}
		$code_row = Asset_CD_Gme::get_by_congres( $cid );
		if ( ! $code_row || ! Asset_CD_Gme::requestable_status( (string) $code_row->status ) ) {
			self::back( 'asset-gme', 'invalid' );
		}
		$reason = isset( $_POST['reason'] ) ? trim( mb_substr( sanitize_textarea_field( wp_unslash( $_POST['reason'] ) ), 0, 500 ) ) : '';
		if ( mb_strlen( $reason ) < 3 ) {
			self::back( 'asset-gme', 'reason' );
		}
		$res = Asset_CD_Gme::create_request( get_current_user_id(), $cid, $reason );
		self::back( 'asset-gme', is_wp_error( $res ) ? 'exists' : 'requested' );
	}

	/**
	 * Approve / refuse / revoke (Direction).
	 */
	public static function handle_decide() {
		$rid = isset( $_POST['request_id'] ) ? absint( $_POST['request_id'] ) : 0; // phpcs:ignore WordPress.Security.NonceVerification.Missing -- verified next.
		$decision = isset( $_POST['decision'] ) ? sanitize_key( wp_unslash( $_POST['decision'] ) ) : ''; // phpcs:ignore WordPress.Security.NonceVerification.Missing -- the decision is part of the nonce action, verified next.
		// One nonce per decision and request: an approve token cannot be replayed as revoke or refuse.
		if ( ! $rid || ! in_array( $decision, array( 'approve', 'refuse', 'revoke' ), true ) || ! isset( $_POST['asset_nonce'] ) || ! wp_verify_nonce( sanitize_key( wp_unslash( $_POST['asset_nonce'] ) ), 'asset_gme_' . $decision . '_' . $rid ) ) {
			wp_die( esc_html__( 'Lien expiré ou invalide.', 'asset-congres-demo' ), 403 );
		}
		if ( ! current_user_can( 'asset_manage_gme' ) ) {
			wp_die( esc_html__( 'Accès refusé.', 'asset-congres-demo' ), 403 );
		}
		$back     = isset( $_POST['back'] ) ? sanitize_key( wp_unslash( $_POST['back'] ) ) : 'asset-gme';
		if ( ! in_array( $decision, array( 'approve', 'refuse', 'revoke' ), true ) ) {
			self::back( $back, 'state' );
		}
		$res = Asset_CD_Gme::decide( $rid, $decision, get_current_user_id() );
		self::back( $back, is_wp_error( $res ) ? 'state' : $decision );
	}

	/**
	 * Add / edit a code (Direction).
	 */
	public static function handle_save() {
		if ( ! isset( $_POST['asset_nonce'] ) || ! wp_verify_nonce( sanitize_key( wp_unslash( $_POST['asset_nonce'] ) ), 'asset_gme_save' ) ) {
			wp_die( esc_html__( 'Lien expiré ou invalide.', 'asset-congres-demo' ), 403 );
		}
		if ( ! current_user_can( 'asset_manage_gme' ) ) {
			wp_die( esc_html__( 'Accès refusé.', 'asset-congres-demo' ), 403 );
		}
		if ( ! Asset_CD_Gme::key_ok() ) {
			self::back( 'asset-gme', 'nokey' );
		}
		$cid      = isset( $_POST['congres_id'] ) ? absint( $_POST['congres_id'] ) : 0;
		$code     = isset( $_POST['code'] ) ? strtoupper( trim( sanitize_text_field( wp_unslash( $_POST['code'] ) ) ) ) : '';
		$status   = isset( $_POST['status'] ) ? sanitize_key( wp_unslash( $_POST['status'] ) ) : '';
		$from     = isset( $_POST['valid_from'] ) ? Asset_CD_Congres::sanitize_field( 'date', sanitize_text_field( wp_unslash( $_POST['valid_from'] ) ) ) : '';
		$to       = isset( $_POST['valid_to'] ) ? Asset_CD_Congres::sanitize_field( 'date', sanitize_text_field( wp_unslash( $_POST['valid_to'] ) ) ) : '';
		$evidence = isset( $_POST['evidence'] ) ? mb_substr( sanitize_textarea_field( wp_unslash( $_POST['evidence'] ) ), 0, 500 ) : '';
		$post     = $cid ? get_post( $cid ) : null;
		$exists   = $cid ? Asset_CD_Gme::get_by_congres( $cid ) : null;
		if ( ! $post || Asset_CD_Congres::POST_TYPE !== $post->post_type || ! isset( Asset_CD_Gme::statuses()[ $status ] )
			|| ( '' !== $code && ! Asset_CD_Gme::valid_code( $code ) ) || ( '' === $code && ! $exists )
			|| ( $from && $to && $to < $from ) ) {
			self::back( 'asset-gme', 'invalid' );
		}
		Asset_CD_Gme::save_code( $cid, '' === $code ? null : $code, $status, $from, $to, $evidence, get_current_user_id() );
		Asset_CD_Gme::log( get_current_user_id(), $cid, $exists ? 'code_update' : 'code_create', '' === $code ? __( 'Métadonnées', 'asset-congres-demo' ) : __( 'Code remplacé', 'asset-congres-demo' ) );
		self::back( 'asset-gme', 'saved' );
	}

	/**
	 * "Demandes d'accès" screen (Direction).
	 */
	public static function render_access() {
		ob_start();
		self::render_access_body();
		echo Asset_CD_Ui::stack_tables( (string) ob_get_clean() ); // phpcs:ignore WordPress.Security.EscapeOutput.OutputNotEscaped -- body is escaped; only data-label attributes (esc_attr) are added.
	}

	/**
	 * Screen body.
	 */
	private static function render_access_body() {
		if ( ! current_user_can( 'asset_manage_gme' ) ) {
			wp_die( esc_html__( 'Accès refusé.', 'asset-congres-demo' ), 403 );
		}
		echo '<div class="wrap asset-admin"><h1>' . esc_html__( 'Demandes d’accès GM&E', 'asset-congres-demo' ) . '</h1>';
		self::notice( self::msg_param() );
		self::pending_table( 'asset-gme-acces' );
		$labels = Asset_CD_Gme::request_labels();
		echo '<h2>' . esc_html__( 'Historique des demandes', 'asset-congres-demo' ) . '</h2>';
		echo '<table class="widefat striped asset-access-history asset-stack"><thead><tr><th scope="col">#</th><th scope="col">' . esc_html__( 'Demandeur', 'asset-congres-demo' ) . '</th><th scope="col">' . esc_html__( 'Congrès', 'asset-congres-demo' ) . '</th><th scope="col">' . esc_html__( 'Raison', 'asset-congres-demo' ) . '</th><th scope="col">' . esc_html__( 'État', 'asset-congres-demo' ) . '</th><th scope="col">' . esc_html__( 'Décidé par', 'asset-congres-demo' ) . '</th><th scope="col">' . esc_html__( 'Expire le', 'asset-congres-demo' ) . '</th><th scope="col">' . esc_html__( 'Action', 'asset-congres-demo' ) . '</th></tr></thead><tbody>';
		foreach ( Asset_CD_Gme::requests() as $r ) {
			$state = Asset_CD_Gme::effective_status( $r );
			echo '<tr><td>' . esc_html( (string) $r->id ) . '</td><td>' . esc_html( Asset_CD_Demandes_Admin::user_label( (int) $r->user_id ) ) . '</td><td>' . esc_html( get_the_title( (int) $r->congres_id ) ) . '</td><td>' . esc_html( $r->reason ) . '</td><td>' . esc_html( $labels[ $state ] ?? $state ) . '</td><td>' . esc_html( $r->decided_by ? Asset_CD_Demandes_Admin::user_label( (int) $r->decided_by ) : '—' ) . '</td><td>' . esc_html( 'approved' === $state || 'expired' === $state ? self::dt( $r->expires_at ) : '—' ) . '</td><td>' . self::decision_forms( $r, 'asset-gme-acces' ) . '</td></tr>'; // phpcs:ignore WordPress.Security.EscapeOutput.OutputNotEscaped -- decision_forms escapes.
		}
		echo '</tbody></table></div>';
	}

	/**
	 * Audit log (Direction).
	 */
	public static function render_log() {
		ob_start();
		self::render_log_body();
		echo Asset_CD_Ui::stack_tables( (string) ob_get_clean() ); // phpcs:ignore WordPress.Security.EscapeOutput.OutputNotEscaped -- body is escaped; only data-label attributes (esc_attr) are added.
	}

	/**
	 * Screen body.
	 */
	private static function render_log_body() {
		if ( ! current_user_can( 'asset_manage_gme' ) ) {
			wp_die( esc_html__( 'Accès refusé.', 'asset-congres-demo' ), 403 );
		}
		$actions = array(
			'reveal'         => __( 'Code révélé', 'asset-congres-demo' ),
			'reveal_refused' => __( 'Révélation refusée', 'asset-congres-demo' ),
			'reveal_failed'  => __( 'Révélation impossible', 'asset-congres-demo' ),
			'request'        => __( 'Demande d’accès', 'asset-congres-demo' ),
			'approve'        => __( 'Accès approuvé', 'asset-congres-demo' ),
			'refuse'         => __( 'Accès refusé', 'asset-congres-demo' ),
			'revoke'         => __( 'Accès révoqué', 'asset-congres-demo' ),
			'code_create'    => __( 'Code ajouté', 'asset-congres-demo' ),
			'code_update'    => __( 'Code modifié', 'asset-congres-demo' ),
		);
		echo '<div class="wrap asset-admin"><h1>' . esc_html__( 'Journal GM&E', 'asset-congres-demo' ) . '</h1>';
		echo '<p class="description">' . esc_html__( 'Journal d’audit en ajout seul : qui, quel congrès, quand. Les codes eux-mêmes n’y figurent jamais.', 'asset-congres-demo' ) . '</p>';
		echo '<table class="widefat striped asset-log asset-stack"><thead><tr><th scope="col">' . esc_html__( 'Date', 'asset-congres-demo' ) . '</th><th scope="col">' . esc_html__( 'Utilisateur', 'asset-congres-demo' ) . '</th><th scope="col">' . esc_html__( 'Congrès', 'asset-congres-demo' ) . '</th><th scope="col">' . esc_html__( 'Action', 'asset-congres-demo' ) . '</th><th scope="col">' . esc_html__( 'Détail', 'asset-congres-demo' ) . '</th></tr></thead><tbody>';
		$rows = Asset_CD_Gme::log_rows();
		if ( ! $rows ) {
			echo '<tr><td colspan="5">' . esc_html__( 'Aucune entrée.', 'asset-congres-demo' ) . '</td></tr>';
		}
		foreach ( $rows as $r ) {
			echo '<tr data-action="' . esc_attr( $r->action ) . '"><td>' . esc_html( self::dt( $r->created_at ) ) . '</td><td>' . esc_html( Asset_CD_Demandes_Admin::user_label( (int) $r->user_id ) ) . '</td><td>' . esc_html( $r->congres_id ? get_the_title( (int) $r->congres_id ) : '—' ) . '</td><td>' . esc_html( $actions[ $r->action ] ?? $r->action ) . '</td><td>' . esc_html( $r->detail ) . '</td></tr>';
		}
		echo '</tbody></table></div>';
	}

	/**
	 * Dashboard widget for Direction: pending requests with one-click decisions.
	 */
	public static function dashboard() {
		if ( current_user_can( 'asset_manage_gme' ) ) {
			wp_add_dashboard_widget( 'asset_cd_gme', __( 'Accès GM&E en attente', 'asset-congres-demo' ), array( __CLASS__, 'render_widget' ) );
		}
	}

	/**
	 * Widget body.
	 */
	public static function render_widget() {
		$pending = Asset_CD_Gme::requests( 'pending', 10 );
		if ( ! $pending ) {
			echo '<p>' . esc_html__( 'Aucune demande en attente.', 'asset-congres-demo' ) . '</p>';
		}
		foreach ( $pending as $r ) {
			echo '<div class="asset-widget-req"><p><strong>' . esc_html( Asset_CD_Demandes_Admin::user_label( (int) $r->user_id ) ) . '</strong> · ' . esc_html( get_the_title( (int) $r->congres_id ) ) . '<br /><span class="description">' . esc_html( $r->reason ) . '</span></p>' . self::decision_forms( $r, 'dashboard' ) . '</div>'; // phpcs:ignore WordPress.Security.EscapeOutput.OutputNotEscaped -- decision_forms escapes.
		}
		echo '<p><a href="' . esc_url( admin_url( 'admin.php?page=asset-gme-acces' ) ) . '">' . esc_html__( 'Toutes les demandes d’accès', 'asset-congres-demo' ) . '</a></p>';
	}
}
