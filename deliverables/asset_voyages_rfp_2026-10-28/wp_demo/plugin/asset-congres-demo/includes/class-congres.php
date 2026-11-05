<?php
/**
 * Congress post type, taxonomies and meta box.
 *
 * @package AssetCongresDemo
 */

defined( 'ABSPATH' ) || exit;

/**
 * CPT asset_congres.
 */
class Asset_CD_Congres {

	const POST_TYPE = 'asset_congres';

	/**
	 * Meta fields: key => [label, type].
	 *
	 * @return array<string,array{0:string,1:string}>
	 */
	public static function fields() {
		return array(
			'_asset_start'    => array( __( 'Date de début', 'asset-congres-demo' ), 'date' ),
			'_asset_end'      => array( __( 'Date de fin', 'asset-congres-demo' ), 'date' ),
			'_asset_city'     => array( __( 'Ville', 'asset-congres-demo' ), 'text' ),
			'_asset_venue'    => array( __( 'Lieu', 'asset-congres-demo' ), 'text' ),
			'_asset_url'      => array( __( 'Site officiel', 'asset-congres-demo' ), 'url' ),
			'_asset_source'   => array( __( 'Source de l’information', 'asset-congres-demo' ), 'text' ),
			'_asset_verified' => array( __( 'Date de vérification', 'asset-congres-demo' ), 'date' ),
		);
	}

	/**
	 * Hooks.
	 */
	public static function init() {
		add_action( 'init', array( __CLASS__, 'register' ) );
		add_filter( 'use_block_editor_for_post_type', array( __CLASS__, 'classic_editor' ), 10, 2 );
		add_action( 'add_meta_boxes_' . self::POST_TYPE, array( __CLASS__, 'add_meta_box' ) );
		add_action( 'save_post_' . self::POST_TYPE, array( __CLASS__, 'save' ), 10, 2 );
		add_filter( 'manage_' . self::POST_TYPE . '_posts_columns', array( __CLASS__, 'columns' ) );
		add_action( 'manage_' . self::POST_TYPE . '_posts_custom_column', array( __CLASS__, 'column' ), 10, 2 );
	}

	/**
	 * Registers CPT + taxonomies.
	 */
	public static function register() {
		register_post_type(
			self::POST_TYPE,
			array(
				'labels'          => array(
					'name'               => __( 'Congrès', 'asset-congres-demo' ),
					'singular_name'      => __( 'Congrès', 'asset-congres-demo' ),
					'add_new'            => __( 'Ajouter', 'asset-congres-demo' ),
					'add_new_item'       => __( 'Ajouter un congrès', 'asset-congres-demo' ),
					'edit_item'          => __( 'Modifier le congrès', 'asset-congres-demo' ),
					'new_item'           => __( 'Nouveau congrès', 'asset-congres-demo' ),
					'view_item'          => __( 'Voir le congrès', 'asset-congres-demo' ),
					'search_items'       => __( 'Rechercher des congrès', 'asset-congres-demo' ),
					'not_found'          => __( 'Aucun congrès trouvé', 'asset-congres-demo' ),
					'not_found_in_trash' => __( 'Aucun congrès dans la corbeille', 'asset-congres-demo' ),
					'all_items'          => __( 'Tous les congrès', 'asset-congres-demo' ),
					'menu_name'          => __( 'Congrès', 'asset-congres-demo' ),
				),
				'public'          => true,
				'has_archive'     => 'congres',
				'rewrite'         => array(
					'slug'       => 'congres',
					'with_front' => false,
				),
				'menu_icon'       => 'dashicons-calendar-alt',
				'menu_position'   => 25,
				'supports'        => array( 'title', 'editor', 'excerpt', 'thumbnail', 'revisions' ),
				'show_in_rest'    => true,
				'capability_type' => array( 'asset_congres', 'asset_congress' ),
				'map_meta_cap'    => true,
			)
		);

		$tax_caps = array(
			'manage_terms' => 'manage_asset_congres_terms',
			'edit_terms'   => 'manage_asset_congres_terms',
			'delete_terms' => 'manage_asset_congres_terms',
			'assign_terms' => 'assign_asset_congres_terms',
		);

		register_taxonomy(
			'asset_discipline',
			self::POST_TYPE,
			array(
				'labels'            => array(
					'name'          => __( 'Disciplines', 'asset-congres-demo' ),
					'singular_name' => __( 'Discipline', 'asset-congres-demo' ),
					'add_new_item'  => __( 'Ajouter une discipline', 'asset-congres-demo' ),
				),
				'public'            => true,
				'hierarchical'      => true,
				'show_admin_column' => true,
				'show_in_rest'      => true,
				'rewrite'           => array( 'slug' => 'discipline' ),
				'capabilities'      => $tax_caps,
			)
		);

		register_taxonomy(
			'asset_pays',
			self::POST_TYPE,
			array(
				'labels'            => array(
					'name'          => __( 'Pays', 'asset-congres-demo' ),
					'singular_name' => __( 'Pays', 'asset-congres-demo' ),
					'add_new_item'  => __( 'Ajouter un pays', 'asset-congres-demo' ),
				),
				'public'            => true,
				'hierarchical'      => true,
				'show_admin_column' => true,
				'show_in_rest'      => true,
				'rewrite'           => array( 'slug' => 'pays' ),
				'capabilities'      => $tax_caps,
			)
		);
	}

	/**
	 * Classic editor for congresses (meta box friendly, REST route stays available).
	 *
	 * @param bool   $use       Current value.
	 * @param string $post_type Post type.
	 * @return bool
	 */
	public static function classic_editor( $use, $post_type ) {
		return self::POST_TYPE === $post_type ? false : $use;
	}

	/**
	 * Registers the meta box.
	 */
	public static function add_meta_box() {
		add_meta_box( 'asset_congres_details', __( 'Informations du congrès', 'asset-congres-demo' ), array( __CLASS__, 'render_meta_box' ), self::POST_TYPE, 'normal', 'high' );
	}

	/**
	 * Meta box markup.
	 *
	 * @param WP_Post $post Post.
	 */
	public static function render_meta_box( $post ) {
		wp_nonce_field( 'asset_congres_save', 'asset_congres_nonce' );
		echo '<table class="form-table" role="presentation"><tbody>';
		foreach ( self::fields() as $key => $def ) {
			$id    = 'asset-field-' . sanitize_html_class( trim( $key, '_' ) );
			$value = (string) get_post_meta( $post->ID, $key, true );
			printf(
				'<tr><th scope="row"><label for="%1$s">%2$s</label></th><td><input type="%3$s" id="%1$s" name="asset_meta[%4$s]" value="%5$s" class="regular-text" /></td></tr>',
				esc_attr( $id ),
				esc_html( $def[0] ),
				esc_attr( $def[1] ),
				esc_attr( $key ),
				'url' === $def[1] ? esc_url( $value ) : esc_attr( $value )
			);
		}
		$ref = (string) get_post_meta( $post->ID, '_asset_ref', true );
		if ( $ref ) {
			printf( '<tr><th scope="row">%s</th><td><code>%s</code></td></tr>', esc_html__( 'Référence interne', 'asset-congres-demo' ), esc_html( $ref ) );
		}
		echo '</tbody></table>';
		echo '<p class="description">' . esc_html__( 'Flux éditorial : brouillon → en attente de relecture → publié. Le rôle Contributeur ASSET peut soumettre mais pas publier.', 'asset-congres-demo' ) . '</p>';
	}

	/**
	 * Sanitises a single field value.
	 *
	 * @param string $type  Field type.
	 * @param string $value Raw value.
	 * @return string
	 */
	public static function sanitize_field( $type, $value ) {
		$value = (string) $value;
		switch ( $type ) {
			case 'date':
				$d = DateTimeImmutable::createFromFormat( '!Y-m-d', $value );
				return ( $d && $d->format( 'Y-m-d' ) === $value ) ? $value : '';
			case 'url':
				return esc_url_raw( $value, array( 'http', 'https' ) );
			default:
				return mb_substr( sanitize_text_field( $value ), 0, 200 );
		}
	}

	/**
	 * Saves meta.
	 *
	 * @param int     $post_id Post ID.
	 * @param WP_Post $post    Post.
	 */
	public static function save( $post_id, $post ) {
		if ( ! isset( $_POST['asset_congres_nonce'] ) || ! wp_verify_nonce( sanitize_key( wp_unslash( $_POST['asset_congres_nonce'] ) ), 'asset_congres_save' ) ) {
			return;
		}
		if ( ( defined( 'DOING_AUTOSAVE' ) && DOING_AUTOSAVE ) || wp_is_post_revision( $post_id ) ) {
			return;
		}
		if ( ! current_user_can( 'edit_post', $post_id ) ) {
			return;
		}
		$raw = isset( $_POST['asset_meta'] ) && is_array( $_POST['asset_meta'] ) ? wp_unslash( $_POST['asset_meta'] ) : array(); // phpcs:ignore WordPress.Security.ValidatedSanitizedInput.InputNotSanitized -- sanitised per field below.
		foreach ( self::fields() as $key => $def ) {
			if ( ! array_key_exists( $key, $raw ) ) {
				continue;
			}
			$clean = self::sanitize_field( $def[1], is_scalar( $raw[ $key ] ) ? $raw[ $key ] : '' );
			update_post_meta( $post_id, $key, $clean );
		}
		$start = (string) get_post_meta( $post_id, '_asset_start', true );
		$end   = (string) get_post_meta( $post_id, '_asset_end', true );
		if ( $start && ( ! $end || $end < $start ) ) {
			update_post_meta( $post_id, '_asset_end', $start );
		}
	}

	/**
	 * Admin columns.
	 *
	 * @param array $cols Columns.
	 * @return array
	 */
	public static function columns( $cols ) {
		$new = array();
		foreach ( $cols as $k => $v ) {
			$new[ $k ] = $v;
			if ( 'title' === $k ) {
				$new['asset_dates'] = __( 'Dates', 'asset-congres-demo' );
				$new['asset_city']  = __( 'Ville', 'asset-congres-demo' );
			}
		}
		return $new;
	}

	/**
	 * Admin column values.
	 *
	 * @param string $col     Column.
	 * @param int    $post_id Post ID.
	 */
	public static function column( $col, $post_id ) {
		if ( 'asset_dates' === $col ) {
			echo esc_html( self::format_range( $post_id ) );
		} elseif ( 'asset_city' === $col ) {
			echo esc_html( (string) get_post_meta( $post_id, '_asset_city', true ) );
		}
	}

	/**
	 * Formats a date in French.
	 *
	 * @param string $ymd Date Y-m-d.
	 * @return string
	 */
	public static function format_date( $ymd ) {
		if ( ! $ymd ) {
			return '';
		}
		$d = DateTimeImmutable::createFromFormat( '!Y-m-d', $ymd );
		if ( ! $d ) {
			return '';
		}
		$months = self::month_names();
		return trim( $d->format( 'j' ) . ' ' . $months[ (int) $d->format( 'n' ) ] . ' ' . $d->format( 'Y' ) );
	}

	/**
	 * French month names (source strings, translatable).
	 *
	 * @return array<int,string>
	 */
	public static function month_names() {
		return array(
			1  => __( 'janvier', 'asset-congres-demo' ),
			2  => __( 'février', 'asset-congres-demo' ),
			3  => __( 'mars', 'asset-congres-demo' ),
			4  => __( 'avril', 'asset-congres-demo' ),
			5  => __( 'mai', 'asset-congres-demo' ),
			6  => __( 'juin', 'asset-congres-demo' ),
			7  => __( 'juillet', 'asset-congres-demo' ),
			8  => __( 'août', 'asset-congres-demo' ),
			9  => __( 'septembre', 'asset-congres-demo' ),
			10 => __( 'octobre', 'asset-congres-demo' ),
			11 => __( 'novembre', 'asset-congres-demo' ),
			12 => __( 'décembre', 'asset-congres-demo' ),
		);
	}

	/**
	 * Date range label.
	 *
	 * @param int $post_id Post ID.
	 * @return string
	 */
	public static function format_range( $post_id ) {
		$s = (string) get_post_meta( $post_id, '_asset_start', true );
		$e = (string) get_post_meta( $post_id, '_asset_end', true );
		if ( ! $s ) {
			return '';
		}
		if ( ! $e || $e === $s ) {
			return self::format_date( $s );
		}
		/* translators: 1: start date, 2: end date. */
		return sprintf( __( 'Du %1$s au %2$s', 'asset-congres-demo' ), self::format_date( $s ), self::format_date( $e ) );
	}

	/**
	 * First term name of a taxonomy.
	 *
	 * @param int    $post_id Post ID.
	 * @param string $tax     Taxonomy.
	 * @return string
	 */
	public static function term_name( $post_id, $tax ) {
		$terms = get_the_terms( $post_id, $tax );
		return ( is_array( $terms ) && $terms ) ? $terms[0]->name : '';
	}
}
