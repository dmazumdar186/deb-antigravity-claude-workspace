<?php
/**
 * GM&E codes: encrypted storage (custom table), access grants and audit log.
 *
 * Codes are never stored in post meta, options or exposed through REST.
 * Encryption: libsodium XChaCha20-Poly1305 (AEAD), the congress id bound as additional data.
 * Key: constant ASSET_GME_KEY only (64 hex chars or base64 of 32 bytes). Without a valid key the
 * plugin fails closed: no code is saved or revealed.
 *
 * @package AssetCongresDemo
 */

defined( 'ABSPATH' ) || exit;

/**
 * Data layer for GM&E.
 */
class Asset_CD_Gme {

	const GRANT_HOURS = 24;

	/**
	 * Request-level cache of public offers.
	 *
	 * @var array<int,bool>
	 */
	private static $offer_cache = array();

	/**
	 * Table names.
	 *
	 * @param string $which codes|access|log.
	 * @return string
	 */
	public static function table( $which ) {
		global $wpdb;
		return $wpdb->prefix . 'asset_gme_' . $which;
	}

	/**
	 * Code statuses.
	 *
	 * @return array<string,string>
	 */
	public static function statuses() {
		return array(
			'detecte'  => __( 'Détecté', 'asset-congres-demo' ),
			'verifie'  => __( 'Vérifié', 'asset-congres-demo' ),
			'approuve' => __( 'Approuvé pour la vente', 'asset-congres-demo' ),
			'expire'   => __( 'Expiré', 'asset-congres-demo' ),
		);
	}

	/**
	 * Creates tables (idempotent).
	 */
	public static function install_tables() {
		global $wpdb;
		$c = $wpdb->get_charset_collate();
		$t = array(
			'codes'  => "id bigint(20) unsigned NOT NULL AUTO_INCREMENT, congres_id bigint(20) unsigned NOT NULL, code_enc text NOT NULL, status varchar(20) NOT NULL DEFAULT 'detecte', valid_from varchar(10) NOT NULL DEFAULT '', valid_to varchar(10) NOT NULL DEFAULT '', evidence text NOT NULL, updated_by bigint(20) unsigned NOT NULL DEFAULT 0, updated_at varchar(19) NOT NULL DEFAULT '', PRIMARY KEY  (id), UNIQUE KEY congres_id (congres_id)",
			'access' => "id bigint(20) unsigned NOT NULL AUTO_INCREMENT, user_id bigint(20) unsigned NOT NULL, congres_id bigint(20) unsigned NOT NULL, reason text NOT NULL, status varchar(20) NOT NULL DEFAULT 'pending', requested_at varchar(19) NOT NULL DEFAULT '', decided_by bigint(20) unsigned NOT NULL DEFAULT 0, decided_at varchar(19) NOT NULL DEFAULT '', expires_at varchar(19) NOT NULL DEFAULT '', PRIMARY KEY  (id), KEY user_congres (user_id,congres_id)",
			'log'    => "id bigint(20) unsigned NOT NULL AUTO_INCREMENT, created_at varchar(19) NOT NULL DEFAULT '', user_id bigint(20) unsigned NOT NULL DEFAULT 0, congres_id bigint(20) unsigned NOT NULL DEFAULT 0, action varchar(30) NOT NULL DEFAULT '', detail varchar(255) NOT NULL DEFAULT '', PRIMARY KEY  (id)",
		);
		foreach ( $t as $name => $cols ) {
			$table = self::table( $name );
			// phpcs:ignore WordPress.DB.DirectDatabaseQuery,WordPress.DB.PreparedSQL.InterpolatedNotPrepared -- schema, no user input.
			$wpdb->query( "CREATE TABLE IF NOT EXISTS {$table} ( {$cols} ) {$c}" );
		}
	}

	/**
	 * Encryption key (32 bytes) from ASSET_GME_KEY, or null when the constant is missing or malformed.
	 * There is deliberately no fallback: a key derived from data stored in the database would let a
	 * database copy alone decrypt every code (fail closed instead).
	 *
	 * @return string|null
	 */
	public static function key() {
		if ( ! defined( 'ASSET_GME_KEY' ) || ! is_string( ASSET_GME_KEY ) ) {
			return null;
		}
		$k = trim( ASSET_GME_KEY );
		if ( 64 === strlen( $k ) && ctype_xdigit( $k ) ) {
			return sodium_hex2bin( $k );
		}
		$b = base64_decode( $k, true ); // phpcs:ignore WordPress.PHP.DiscouragedPHPFunctions.obfuscation_base64_decode
		if ( false !== $b && SODIUM_CRYPTO_AEAD_XCHACHA20POLY1305_IETF_KEYBYTES === strlen( $b ) ) {
			return $b;
		}
		return null;
	}

	/**
	 * True when a valid key is configured.
	 *
	 * @return bool
	 */
	public static function key_ok() {
		return null !== self::key();
	}

	/**
	 * Additional authenticated data: binds a ciphertext to its congress.
	 *
	 * @param int $congres_id Congress.
	 * @return string
	 */
	private static function aad( $congres_id ) {
		return 'asset-gme|v2|congres:' . (int) $congres_id;
	}

	/**
	 * Encrypts a code for a congress (XChaCha20-Poly1305, congress id as AAD).
	 *
	 * @param string $plain      Plaintext.
	 * @param int    $congres_id Congress.
	 * @return string|null base64(nonce|ciphertext+tag), null without a valid key.
	 */
	public static function encrypt( $plain, $congres_id ) {
		$key = self::key();
		if ( null === $key ) {
			return null;
		}
		$nonce = random_bytes( SODIUM_CRYPTO_AEAD_XCHACHA20POLY1305_IETF_NPUBBYTES );
		return base64_encode( $nonce . sodium_crypto_aead_xchacha20poly1305_ietf_encrypt( $plain, self::aad( $congres_id ), $nonce, $key ) ); // phpcs:ignore WordPress.PHP.DiscouragedPHPFunctions.obfuscation_base64_encode
	}

	/**
	 * Decrypts a code; fails if the key is missing/wrong or the row was moved to another congress.
	 *
	 * @param string $enc        Stored value.
	 * @param int    $congres_id Congress the row belongs to.
	 * @return string|null
	 */
	public static function decrypt( $enc, $congres_id ) {
		$key = self::key();
		$raw = base64_decode( (string) $enc, true ); // phpcs:ignore WordPress.PHP.DiscouragedPHPFunctions.obfuscation_base64_decode
		$nb  = SODIUM_CRYPTO_AEAD_XCHACHA20POLY1305_IETF_NPUBBYTES;
		if ( null === $key || false === $raw || strlen( $raw ) <= $nb ) {
			return null;
		}
		$plain = sodium_crypto_aead_xchacha20poly1305_ietf_decrypt( substr( $raw, $nb ), self::aad( $congres_id ), substr( $raw, 0, $nb ), $key );
		return false === $plain ? null : $plain;
	}

	/**
	 * Validates a dummy/real code format.
	 *
	 * @param string $code Code.
	 * @return bool
	 */
	public static function valid_code( $code ) {
		return (bool) is_string( $code ) && preg_match( '/^[A-Z0-9][A-Z0-9-]{3,39}\z/', $code );
	}

	/**
	 * All code rows (without decrypting).
	 *
	 * @return array<int,object>
	 */
	public static function all_codes() {
		global $wpdb;
		$t = self::table( 'codes' );
		// phpcs:ignore WordPress.DB.DirectDatabaseQuery,WordPress.DB.PreparedSQL.InterpolatedNotPrepared
		return (array) $wpdb->get_results( "SELECT id, congres_id, status, valid_from, valid_to, evidence, updated_by, updated_at FROM {$t} ORDER BY id ASC" );
	}

	/**
	 * Code row for a congress (without the ciphertext).
	 *
	 * @param int $congres_id Congress ID.
	 * @return object|null
	 */
	public static function get_by_congres( $congres_id ) {
		global $wpdb;
		$t = self::table( 'codes' );
		// phpcs:ignore WordPress.DB.DirectDatabaseQuery,WordPress.DB.PreparedSQL.InterpolatedNotPrepared
		return $wpdb->get_row( $wpdb->prepare( "SELECT id, congres_id, status, valid_from, valid_to, evidence, updated_by, updated_at FROM {$t} WHERE congres_id = %d", $congres_id ) );
	}

	/**
	 * Inserts or updates the code for a congress. Caller checks capabilities.
	 *
	 * @param int         $congres_id Congress.
	 * @param string|null $code       Plain code (null = keep current).
	 * @param string      $status     Status.
	 * @param string      $from       Valid from.
	 * @param string      $to         Valid to.
	 * @param string      $evidence   Evidence note.
	 * @param int         $user_id    Acting user.
	 * @return bool
	 */
	public static function save_code( $congres_id, $code, $status, $from, $to, $evidence, $user_id ) {
		global $wpdb;
		$t    = self::table( 'codes' );
		$data = array(
			'status'     => $status,
			'valid_from' => $from,
			'valid_to'   => $to,
			'evidence'   => $evidence,
			'updated_by' => $user_id,
			'updated_at' => current_time( 'mysql', true ),
		);
		if ( ! self::key_ok() ) {
			return false; // Fail closed: never store a code without the configured key.
		}
		if ( null !== $code ) {
			$data['code_enc'] = self::encrypt( $code, (int) $congres_id );
		}
		$existing = self::get_by_congres( $congres_id );
		if ( $existing ) {
			// phpcs:ignore WordPress.DB.DirectDatabaseQuery
			$ok = false !== $wpdb->update( $t, $data, array( 'id' => (int) $existing->id ) );
		} else {
			if ( null === $code ) {
				return false;
			}
			$data['congres_id'] = $congres_id;
			// phpcs:ignore WordPress.DB.DirectDatabaseQuery
			$ok = (bool) $wpdb->insert( $t, $data );
		}
		self::$offer_cache = array();
		return $ok;
	}

	/**
	 * Decrypted code for a congress. Only call after can_reveal().
	 *
	 * @param int $congres_id Congress.
	 * @return string|null
	 */
	private static function plain_code( $congres_id ) {
		global $wpdb;
		$t = self::table( 'codes' );
		// phpcs:ignore WordPress.DB.DirectDatabaseQuery,WordPress.DB.PreparedSQL.InterpolatedNotPrepared
		$enc = $wpdb->get_var( $wpdb->prepare( "SELECT code_enc FROM {$t} WHERE congres_id = %d", $congres_id ) );
		return $enc ? self::decrypt( $enc, (int) $congres_id ) : null;
	}

	/**
	 * True when the congress has an approved, non-expired negotiated fare (no code exposed).
	 *
	 * @param int $congres_id Congress.
	 * @return bool
	 */
	public static function has_public_offer( $congres_id ) {
		$congres_id = (int) $congres_id;
		if ( ! isset( self::$offer_cache[ $congres_id ] ) ) {
			$row                              = self::get_by_congres( $congres_id );
			self::$offer_cache[ $congres_id ] = $row && 'approuve' === $row->status && ( '' === $row->valid_to || $row->valid_to >= wp_date( 'Y-m-d' ) );
		}
		return self::$offer_cache[ $congres_id ];
	}

	/**
	 * UTC now (Y-m-d H:i:s).
	 *
	 * @return string
	 */
	public static function now() {
		return gmdate( 'Y-m-d H:i:s' );
	}

	/**
	 * Appends an audit log entry.
	 *
	 * @param int    $user_id    User.
	 * @param int    $congres_id Congress.
	 * @param string $action     Action key.
	 * @param string $detail     Detail (never a code).
	 */
	public static function log( $user_id, $congres_id, $action, $detail = '' ) {
		global $wpdb;
		// phpcs:ignore WordPress.DB.DirectDatabaseQuery
		$wpdb->insert(
			self::table( 'log' ),
			array(
				'created_at' => self::now(),
				'user_id'    => (int) $user_id,
				'congres_id' => (int) $congres_id,
				'action'     => sanitize_key( $action ),
				'detail'     => mb_substr( (string) $detail, 0, 250 ),
			),
			array( '%s', '%d', '%d', '%s', '%s' )
		);
	}

	/**
	 * Access request by ID.
	 *
	 * @param int $id ID.
	 * @return object|null
	 */
	public static function get_request( $id ) {
		global $wpdb;
		$t = self::table( 'access' );
		// phpcs:ignore WordPress.DB.DirectDatabaseQuery,WordPress.DB.PreparedSQL.InterpolatedNotPrepared
		return $wpdb->get_row( $wpdb->prepare( "SELECT * FROM {$t} WHERE id = %d", $id ) );
	}

	/**
	 * Latest request of a user for a congress.
	 *
	 * @param int $user_id    User.
	 * @param int $congres_id Congress.
	 * @return object|null
	 */
	public static function latest_request( $user_id, $congres_id ) {
		global $wpdb;
		$t = self::table( 'access' );
		// phpcs:ignore WordPress.DB.DirectDatabaseQuery,WordPress.DB.PreparedSQL.InterpolatedNotPrepared
		return $wpdb->get_row( $wpdb->prepare( "SELECT * FROM {$t} WHERE user_id = %d AND congres_id = %d ORDER BY id DESC LIMIT 1", $user_id, $congres_id ) );
	}

	/**
	 * Requests by status (pending|approved|...), newest first.
	 *
	 * @param string|null $status Status or null for all.
	 * @param int         $limit  Limit.
	 * @return array<int,object>
	 */
	public static function requests( $status = null, $limit = 200 ) {
		global $wpdb;
		$t = self::table( 'access' );
		if ( null === $status ) {
			// phpcs:ignore WordPress.DB.DirectDatabaseQuery,WordPress.DB.PreparedSQL.InterpolatedNotPrepared
			return (array) $wpdb->get_results( $wpdb->prepare( "SELECT * FROM {$t} ORDER BY id DESC LIMIT %d", $limit ) );
		}
		// phpcs:ignore WordPress.DB.DirectDatabaseQuery,WordPress.DB.PreparedSQL.InterpolatedNotPrepared
		return (array) $wpdb->get_results( $wpdb->prepare( "SELECT * FROM {$t} WHERE status = %s ORDER BY id DESC LIMIT %d", $status, $limit ) );
	}

	/**
	 * Effective state of a request, accounting for expiry.
	 *
	 * @param object $r Request row.
	 * @return string pending|approved|refused|revoked|expired
	 */
	public static function effective_status( $r ) {
		if ( 'approved' === $r->status && ( '' === $r->expires_at || $r->expires_at <= self::now() ) ) {
			return 'expired';
		}
		return (string) $r->status;
	}

	/**
	 * Request status labels.
	 *
	 * @return array<string,string>
	 */
	public static function request_labels() {
		return array(
			'pending'  => __( 'En attente', 'asset-congres-demo' ),
			'approved' => __( 'Approuvée', 'asset-congres-demo' ),
			'refused'  => __( 'Refusée', 'asset-congres-demo' ),
			'revoked'  => __( 'Accès retiré', 'asset-congres-demo' ),
			'expired'  => __( 'Expirée', 'asset-congres-demo' ),
		);
	}

	/**
	 * Creates an access request (one open request per user and congress).
	 *
	 * @param int    $user_id    User.
	 * @param int    $congres_id Congress.
	 * @param string $reason     Reason.
	 * @return int|WP_Error Request ID.
	 */
	public static function create_request( $user_id, $congres_id, $reason ) {
		global $wpdb;
		$latest = self::latest_request( $user_id, $congres_id );
		if ( $latest && in_array( self::effective_status( $latest ), array( 'pending', 'approved' ), true ) ) {
			return new WP_Error( 'exists', __( 'Une demande est déjà en cours ou un accès est déjà actif pour ce congrès.', 'asset-congres-demo' ) );
		}
		// phpcs:ignore WordPress.DB.DirectDatabaseQuery
		$wpdb->insert(
			self::table( 'access' ),
			array(
				'user_id'      => $user_id,
				'congres_id'   => $congres_id,
				'reason'       => $reason,
				'status'       => 'pending',
				'requested_at' => self::now(),
			),
			array( '%d', '%d', '%s', '%s', '%s' )
		);
		$id = (int) $wpdb->insert_id;
		self::log( $user_id, $congres_id, 'request', $reason );
		return $id;
	}

	/**
	 * Applies a decision to a request. Caller checks capability asset_manage_gme.
	 *
	 * @param int    $id       Request ID.
	 * @param string $decision approve|refuse|revoke.
	 * @param int    $by       Acting user.
	 * @return true|WP_Error
	 */
	public static function decide( $id, $decision, $by ) {
		global $wpdb;
		$r = self::get_request( $id );
		if ( ! $r ) {
			return new WP_Error( 'missing', __( 'Demande introuvable.', 'asset-congres-demo' ) );
		}
		$state = self::effective_status( $r );
		$data  = array(
			'decided_by' => $by,
			'decided_at' => self::now(),
		);
		if ( 'approve' === $decision && 'pending' === $state ) {
			$data['status']     = 'approved';
			$data['expires_at'] = gmdate( 'Y-m-d H:i:s', time() + self::GRANT_HOURS * HOUR_IN_SECONDS );
		} elseif ( 'refuse' === $decision && 'pending' === $state ) {
			$data['status'] = 'refused';
		} elseif ( 'revoke' === $decision && 'approved' === $state ) {
			$data['status']     = 'revoked';
			$data['expires_at'] = self::now();
		} else {
			return new WP_Error( 'state', __( 'Cette action n’est pas possible dans l’état actuel de la demande.', 'asset-congres-demo' ) );
		}
		// phpcs:ignore WordPress.DB.DirectDatabaseQuery
		$wpdb->update( self::table( 'access' ), $data, array( 'id' => $id ) );
		/* translators: %s: user display name. */
		self::log( $by, (int) $r->congres_id, $decision, sprintf( __( 'Demande #%1$d de %2$s', 'asset-congres-demo' ), $id, Asset_CD_Demandes_Admin::user_label( (int) $r->user_id ) ) );
		return true;
	}

	/**
	 * Active grant for a user and congress.
	 *
	 * @param int $user_id    User.
	 * @param int $congres_id Congress.
	 * @return object|null
	 */
	public static function active_grant( $user_id, $congres_id ) {
		$r = self::latest_request( $user_id, $congres_id );
		return ( $r && 'approved' === self::effective_status( $r ) ) ? $r : null;
	}

	/**
	 * Code statuses for which the team may ask for access (verified or approved for sale).
	 *
	 * @param string $status Code status.
	 * @return bool
	 */
	public static function requestable_status( $status ) {
		return in_array( $status, array( 'verifie', 'approuve' ), true );
	}

	/**
	 * Server-side reveal permission.
	 *
	 * @param int $user_id    User.
	 * @param int $congres_id Congress.
	 * @return bool
	 */
	public static function can_reveal( $user_id, $congres_id ) {
		if ( ! $user_id ) {
			return false;
		}
		$row = self::get_by_congres( $congres_id );
		if ( ! $row || 'expire' === $row->status ) {
			return false; // Expired codes are closed to everyone.
		}
		if ( user_can( $user_id, 'asset_manage_gme' ) ) {
			return true;
		}
		return user_can( $user_id, 'asset_view_gme' ) && null !== self::active_grant( $user_id, $congres_id );
	}

	/**
	 * Reveals a code after a permission check, logging the attempt either way.
	 *
	 * @param int $user_id    User.
	 * @param int $congres_id Congress.
	 * @return string|null Code or null when refused.
	 */
	public static function reveal( $user_id, $congres_id ) {
		if ( ! self::can_reveal( $user_id, $congres_id ) ) {
			self::log( $user_id, $congres_id, 'reveal_refused', __( 'Aucun accès actif', 'asset-congres-demo' ) );
			return null;
		}
		if ( ! self::key_ok() ) {
			self::log( $user_id, $congres_id, 'reveal_failed', __( 'Clé de chiffrement absente ou invalide', 'asset-congres-demo' ) );
			return null;
		}
		$code = self::plain_code( $congres_id );
		self::log( $user_id, $congres_id, null === $code ? 'reveal_failed' : 'reveal' );
		return $code;
	}

	/**
	 * Audit log rows.
	 *
	 * @param int $limit Limit.
	 * @return array<int,object>
	 */
	public static function log_rows( $limit = 300 ) {
		global $wpdb;
		$t = self::table( 'log' );
		// phpcs:ignore WordPress.DB.DirectDatabaseQuery,WordPress.DB.PreparedSQL.InterpolatedNotPrepared
		return (array) $wpdb->get_results( $wpdb->prepare( "SELECT * FROM {$t} ORDER BY id DESC LIMIT %d", $limit ) );
	}
}
