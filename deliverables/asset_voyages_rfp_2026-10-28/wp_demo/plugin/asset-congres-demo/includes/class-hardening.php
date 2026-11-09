<?php
/**
 * Hardening and editor comfort: login throttle, generic login errors, REST user list hidden from
 * visitors, security headers, calmer heartbeat, plain-text congress editor with a label.
 *
 * @package AssetCongresDemo
 */

defined( 'ABSPATH' ) || exit;

/**
 * Hardening.
 */
class Asset_CD_Hardening {

	const LOGIN_MAX    = 10;
	const LOGIN_WINDOW = 900; // 15 minutes.

	/**
	 * Hooks.
	 */
	public static function init() {
		add_filter( 'authenticate', array( __CLASS__, 'throttle_and_generic' ), 100, 2 );
		add_action( 'wp_login_failed', array( __CLASS__, 'login_failed' ) );
		add_action( 'wp_login', array( __CLASS__, 'login_ok' ) );
		add_action( 'wp_login', array( __CLASS__, 'cancel_playground_auto_login' ), 1 );
		add_filter( 'rest_endpoints', array( __CLASS__, 'hide_users_endpoint' ) );
		add_action( 'template_redirect', array( __CLASS__, 'no_author_archives' ), 1 );
		add_action( 'send_headers', array( __CLASS__, 'headers' ) );
		add_filter( 'heartbeat_settings', array( __CLASS__, 'heartbeat' ) );
		add_filter( 'user_can_richedit', array( __CLASS__, 'plain_editor' ) );
		add_action( 'edit_form_after_title', array( __CLASS__, 'editor_label' ) );
		add_action( 'admin_enqueue_scripts', array( __CLASS__, 'no_autosave' ), 100 );
		// WordPress 7 opts wp-admin into cross-document view transitions (@view-transition). Moving from an
		// opted-in admin page to the front end, or interrupting a navigation, throws an uncaught
		// "Transition was aborted … ViewTransition opt-in disabled" page error; it also ghosted screenshots.
		remove_action( 'admin_enqueue_scripts', 'wp_enqueue_view_transitions_admin_css' );
		add_action( 'admin_bar_menu', array( __CLASS__, 'guard_command_palette' ), 999 );
		add_action( 'admin_bar_menu', array( __CLASS__, 'back_to_site' ), 35 );
		add_action( 'wp_dashboard_setup', array( __CLASS__, 'trim_dashboard' ), 99 );
		add_filter( 'login_message', array( __CLASS__, 'session_expired_message' ) );
		add_action( 'admin_init', array( __CLASS__, 'skip_compression_test' ), 1 );
	}

	/**
	 * Core runs an admin-ajax « wp-compression-test » until can_compress_scripts is set; under
	 * Playground it answers 400 and logs console errors on admin pages (CE-C1-001). Record the
	 * answer once (no compression), so the test never runs.
	 */
	public static function skip_compression_test() {
		if ( false === get_site_option( 'can_compress_scripts' ) ) {
			update_site_option( 'can_compress_scripts', 0 );
		}
	}

	/**
	 * WordPress sends a reader whose session ended to wp-login.php?reauth=1 with no explanation
	 * (CE-C7-003). Say so in plain French above the form.
	 *
	 * @param string $message Existing login message markup.
	 * @return string
	 */
	public static function session_expired_message( $message ) {
		// phpcs:ignore WordPress.Security.NonceVerification.Recommended -- read-only display flag.
		if ( empty( $_GET['reauth'] ) || is_user_logged_in() ) {
			return $message;
		}
		return '<p class="message asset-session-expired" role="status">' . esc_html__( 'Votre session a expiré. Reconnectez-vous.', 'asset-congres-demo' ) . '</p>' . $message;
	}

	/**
	 * The admin bar « Ctrl + K » item calls wp.data inline; clicked before the page's scripts have
	 * loaded it threw "wp is not defined". Same action, guarded.
	 *
	 * @param WP_Admin_Bar $bar Admin bar.
	 */
	public static function guard_command_palette( $bar ) {
		$node = $bar->get_node( 'command-palette' );
		if ( ! $node ) {
			return;
		}
		$args                    = (array) $node;
		$args['meta']            = (array) ( $args['meta'] ?? array() );
		$args['meta']['onclick'] = 'if ( window.wp && wp.data ) { wp.data.dispatch( "core/commands" ).open(); } return false;';
		$bar->add_node( $args );
	}

	/**
	 * « Retour au site » in the admin bar (the reverse of the theme's « Espace équipe » link).
	 *
	 * @param WP_Admin_Bar $bar Admin bar.
	 */
	public static function back_to_site( $bar ) {
		if ( is_admin() ) {
			$bar->add_node(
				array(
					'id'    => 'asset-back-to-site',
					'title' => esc_html__( 'Retour au site', 'asset-congres-demo' ),
					'href'  => home_url( '/' ),
				)
			);
		}
	}

	/**
	 * ASSET roles get a short dashboard: no empty core widgets.
	 */
	public static function trim_dashboard() {
		$user = wp_get_current_user();
		if ( ! array_intersect( array( 'asset_direction', 'asset_equipe', 'asset_contributeur' ), (array) $user->roles ) ) {
			return;
		}
		foreach ( array( 'dashboard_activity', 'dashboard_right_now', 'dashboard_quick_press', 'dashboard_primary', 'dashboard_site_health' ) as $id ) {
			remove_meta_box( $id, 'dashboard', 'normal' );
			remove_meta_box( $id, 'dashboard', 'side' );
		}
		remove_action( 'welcome_panel', 'wp_welcome_panel' );
		if ( ! current_user_can( 'asset_manage_demandes' ) ) {
			wp_add_dashboard_widget( 'asset_cd_contrib', __( 'Congrès', 'asset-congres-demo' ), array( __CLASS__, 'contrib_widget' ) );
		}
	}

	/**
	 * Contributor widget: the two things a contributor does.
	 */
	public static function contrib_widget() {
		echo '<p><a class="button button-primary" href="' . esc_url( admin_url( 'post-new.php?post_type=' . Asset_CD_Congres::POST_TYPE ) ) . '">' . esc_html__( 'Ajouter un congrès', 'asset-congres-demo' ) . '</a> <a class="button" href="' . esc_url( admin_url( 'edit.php?post_type=' . Asset_CD_Congres::POST_TYPE ) ) . '">' . esc_html__( 'Mes congrès', 'asset-congres-demo' ) . '</a></p>';
		echo '<p class="description">' . esc_html__( 'Rédigez un congrès puis cliquez sur « Soumettre pour relecture » : la Direction le publie.', 'asset-congres-demo' ) . '</p>';
	}

	/**
	 * Throttle key per hashed IP + username (no global account lockout: demo logins are public).
	 *
	 * @param string $username Username.
	 * @return string
	 */
	private static function key( $username ) {
		$ip = isset( $_SERVER['REMOTE_ADDR'] ) ? sanitize_text_field( wp_unslash( $_SERVER['REMOTE_ADDR'] ) ) : '0.0.0.0';
		return 'asset_cd_lt_' . substr( hash_hmac( 'sha256', $ip . '|' . strtolower( trim( (string) $username ) ), wp_salt( 'nonce' ) ), 0, 32 );
	}

	/**
	 * Blocks after too many failures and replaces "unknown user" / "wrong password" with one message.
	 *
	 * @param WP_User|WP_Error|null $user     Result so far.
	 * @param string                $username Username.
	 * @return WP_User|WP_Error|null
	 */
	public static function throttle_and_generic( $user, $username ) {
		if ( '' !== (string) $username && (int) get_transient( self::key( $username ) ) >= self::LOGIN_MAX ) {
			return new WP_Error( 'asset_too_many', __( '<strong>Erreur :</strong> trop de tentatives de connexion. Réessayez dans 15 minutes.', 'asset-congres-demo' ) );
		}
		if ( is_wp_error( $user ) && array_intersect( $user->get_error_codes(), array( 'invalid_username', 'invalid_email', 'incorrect_password' ) ) ) {
			return new WP_Error( 'asset_invalid_login', __( '<strong>Erreur :</strong> identifiant ou mot de passe incorrect.', 'asset-congres-demo' ) );
		}
		return $user;
	}

	/**
	 * Counts a failure.
	 *
	 * @param string $username Username.
	 */
	public static function login_failed( $username ) {
		$k = self::key( $username );
		set_transient( $k, (int) get_transient( $k ) + 1, self::LOGIN_WINDOW );
	}

	/**
	 * Clears the counter on success.
	 *
	 * @param string $username Username.
	 */
	public static function login_ok( $username ) {
		delete_transient( self::key( $username ) );
	}

	/**
	 * Visitor demo: playground.wordpress.net logs every visitor in as "admin" unless the URL carries
	 * login=no. When the visitor blueprint defines ASSET_DEMO_VISITOR, that automatic login (which never
	 * goes through wp-login.php) is cancelled at once, so the visitor sees the public site logged out.
	 * A real login through wp-login.php is not affected.
	 */
	public static function cancel_playground_auto_login() {
		$uri = isset( $_SERVER['REQUEST_URI'] ) ? sanitize_text_field( wp_unslash( $_SERVER['REQUEST_URI'] ) ) : '';
		if ( defined( 'ASSET_DEMO_VISITOR' ) && ASSET_DEMO_VISITOR && function_exists( 'playground_auto_login' ) && ! str_contains( $uri, 'wp-login.php' ) ) {
			wp_clear_auth_cookie();
			wp_set_current_user( 0 );
		}
	}

	/**
	 * Removes /wp/v2/users for visitors (no account enumeration).
	 *
	 * @param array $endpoints Endpoints.
	 * @return array
	 */
	public static function hide_users_endpoint( $endpoints ) {
		if ( ! is_user_logged_in() ) {
			foreach ( array_keys( $endpoints ) as $route ) {
				if ( str_starts_with( $route, '/wp/v2/users' ) ) {
					unset( $endpoints[ $route ] );
				}
			}
		}
		return $endpoints;
	}

	/**
	 * Author archives (?author=1, /author/x/) answer 404 to visitors.
	 */
	public static function no_author_archives() {
		// phpcs:ignore WordPress.Security.NonceVerification.Recommended -- read-only routing check.
		if ( ! is_user_logged_in() && ( is_author() || isset( $_GET['author'] ) ) ) {
			global $wp_query;
			$wp_query->set_404();
			status_header( 404 );
			nocache_headers();
		}
	}

	/**
	 * Security headers on front-end responses.
	 */
	public static function headers() {
		if ( headers_sent() ) {
			return;
		}
		header( 'X-Content-Type-Options: nosniff' );
		header( 'X-Frame-Options: SAMEORIGIN' );
		header( "Content-Security-Policy: frame-ancestors 'self'" );
		header( 'Referrer-Policy: strict-origin-when-cross-origin' );
	}

	/**
	 * Calmer heartbeat (fewer background requests in the in-browser Playground).
	 *
	 * @param array $settings Settings.
	 * @return array
	 */
	public static function heartbeat( $settings ) {
		$settings['interval']        = 60;
		$settings['minimalInterval'] = 60; // Caps the editor's 10 s post-lock polling as well.
		return $settings;
	}

	/**
	 * True on the congress editor screen.
	 *
	 * @return bool
	 */
	private static function on_congres_editor() {
		$screen = function_exists( 'get_current_screen' ) ? get_current_screen() : null;
		return $screen && 'post' === $screen->base && Asset_CD_Congres::POST_TYPE === $screen->post_type;
	}

	/**
	 * Plain-text description field for congresses (no TinyMCE: shorter keyboard path, labelled field).
	 *
	 * @param bool $can Current value.
	 * @return bool
	 */
	public static function plain_editor( $can ) {
		return self::on_congres_editor() ? false : $can;
	}

	/**
	 * Visible label for the description field.
	 *
	 * @param WP_Post $post Post.
	 */
	public static function editor_label( $post ) {
		if ( Asset_CD_Congres::POST_TYPE === $post->post_type ) {
			echo '<p class="asset-editor-label"><label for="content">' . esc_html__( 'Description du congrès', 'asset-congres-demo' ) . '</label></p>';
		}
	}

	/**
	 * No autosave on the congress editor. Autosave locks « Publier » (class "disabled") while its
	 * heartbeat round-trip is pending, and shows « Connexion perdue » when that round-trip is slow;
	 * in the in-browser Playground this blocked keyboard publishing. The form is short, so a normal
	 * save is enough.
	 */
	public static function no_autosave() {
		if ( self::on_congres_editor() ) {
			wp_dequeue_script( 'autosave' );
		}
	}
}
