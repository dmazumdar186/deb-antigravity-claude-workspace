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
