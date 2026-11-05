<?php
/**
 * Public catalogue (shortcode) and single congress details.
 *
 * @package AssetCongresDemo
 */

defined( 'ABSPATH' ) || exit;

/**
 * Catalogue rendering.
 */
class Asset_CD_Catalogue {

	const PER_PAGE = 9;

	/**
	 * Hooks.
	 */
	public static function init() {
		add_shortcode( 'asset_catalogue', array( __CLASS__, 'shortcode' ) );
		add_shortcode( 'asset_header', array( __CLASS__, 'header_shortcode' ) );
		add_shortcode( 'asset_footer', array( __CLASS__, 'footer_shortcode' ) );
		add_shortcode( 'asset_back_link', array( __CLASS__, 'back_link_shortcode' ) );
		add_filter( 'the_content', array( __CLASS__, 'single_content' ), 20 );
		add_action( 'wp_enqueue_scripts', array( __CLASS__, 'assets' ) );
		add_action( 'init', array( __CLASS__, 'no_third_party' ) );
		add_action( 'wp_dashboard_setup', array( __CLASS__, 'trim_dashboard' ), 20 );
	}

	/**
	 * No third-party requests from visitor or admin pages (emoji images come from s.w.org).
	 */
	public static function no_third_party() {
		remove_action( 'wp_head', 'print_emoji_detection_script', 7 );
		remove_action( 'admin_print_scripts', 'print_emoji_detection_script' );
		remove_action( 'wp_print_styles', 'print_emoji_styles' );
		remove_action( 'admin_print_styles', 'print_emoji_styles' );
	}

	/**
	 * Removes the WordPress news widget (external feed) from the demo dashboard.
	 */
	public static function trim_dashboard() {
		remove_meta_box( 'dashboard_primary', 'dashboard', 'side' );
	}

	/**
	 * Site header used by the bundled "asset-demo" theme (plain list navigation).
	 *
	 * @return string
	 */
	public static function header_shortcode() {
		$cat  = (int) get_option( 'asset_cd_catalogue_page' );
		$url  = $cat ? get_permalink( $cat ) : home_url( '/' );
		$html = '<div class="asset-site-header"><p class="asset-brand"><a href="' . esc_url( home_url( '/' ) ) . '">' . esc_html__( 'ASSET Voyages — démonstration', 'asset-congres-demo' ) . '</a></p>';
		$html .= '<nav aria-label="' . esc_attr__( 'Navigation principale', 'asset-congres-demo' ) . '"><ul class="asset-nav"><li><a href="' . esc_url( (string) $url ) . '">' . esc_html__( 'Catalogue des congrès', 'asset-congres-demo' ) . '</a></li></ul></nav></div>';
		return $html;
	}

	/**
	 * Link back to the catalogue (404 template).
	 *
	 * @return string
	 */
	public static function back_link_shortcode() {
		$cat = (int) get_option( 'asset_cd_catalogue_page' );
		return '<p><a class="asset-link" href="' . esc_url( $cat ? (string) get_permalink( $cat ) : home_url( '/' ) ) . '">' . esc_html__( 'Retour au catalogue', 'asset-congres-demo' ) . '</a></p>';
	}

	/**
	 * Site footer used by the bundled theme: demo notice.
	 *
	 * @return string
	 */
	public static function footer_shortcode() {
		return '<div class="asset-site-footer"><p><strong>' . esc_html__( 'Démonstration ASSET Voyages', 'asset-congres-demo' ) . '</strong></p><p>' . esc_html__( 'Toutes les données sont fictives : congrès, personnes, adresses e-mail en @example.com et codes GM&E factices. Aucun e-mail n’est envoyé et aucune réservation n’est enregistrée.', 'asset-congres-demo' ) . '</p></div>';
	}

	/**
	 * Front-end stylesheet.
	 */
	public static function assets() {
		wp_enqueue_style( 'asset-cd-public', ASSET_CD_URL . 'assets/css/public.css', array(), ASSET_CD_VERSION );
	}

	/**
	 * Reads and validates the GET filters.
	 *
	 * @return array{q:string,discipline:string,pays:string,mois:string,tri:string,passes:bool,pg:int}
	 */
	public static function read_filters() {
		// phpcs:disable WordPress.Security.NonceVerification.Recommended -- public, read-only GET search.
		$q = isset( $_GET['q'] ) ? sanitize_text_field( wp_unslash( $_GET['q'] ) ) : '';
		$q = mb_substr( $q, 0, 100 );

		$discipline = isset( $_GET['discipline'] ) ? sanitize_title( wp_unslash( $_GET['discipline'] ) ) : '';
		if ( $discipline && ! term_exists( $discipline, 'asset_discipline' ) ) {
			$discipline = '';
		}
		$pays = isset( $_GET['pays'] ) ? sanitize_title( wp_unslash( $_GET['pays'] ) ) : '';
		if ( $pays && ! term_exists( $pays, 'asset_pays' ) ) {
			$pays = '';
		}
		$mois = isset( $_GET['mois'] ) ? sanitize_text_field( wp_unslash( $_GET['mois'] ) ) : '';
		if ( ! preg_match( '/^\d{4}-(0[1-9]|1[0-2])$/', $mois ) ) {
			$mois = '';
		}
		$tri    = ( isset( $_GET['tri'] ) && 'date_desc' === $_GET['tri'] ) ? 'date_desc' : 'date_asc';
		$passes = ! empty( $_GET['passes'] );
		$pg     = isset( $_GET['pg'] ) ? absint( $_GET['pg'] ) : 1;
		// phpcs:enable
		$pg = max( 1, min( $pg, 1000 ) );

		return compact( 'q', 'discipline', 'pays', 'mois', 'tri', 'passes', 'pg' );
	}

	/**
	 * Accent/case-insensitive normaliser.
	 *
	 * @param string $s Text.
	 * @return string
	 */
	private static function norm( $s ) {
		return mb_strtolower( remove_accents( (string) $s ) );
	}

	/**
	 * IDs of published congresses matching the text query in title, city or discipline.
	 *
	 * @param string $q Query.
	 * @return int[]
	 */
	public static function search_ids( $q ) {
		$needle = self::norm( $q );
		$ids    = get_posts(
			array(
				'post_type'      => Asset_CD_Congres::POST_TYPE,
				'post_status'    => 'publish',
				'posts_per_page' => 2000,
				'fields'         => 'ids',
				'no_found_rows'  => true,
			)
		);
		$out    = array();
		foreach ( $ids as $id ) {
			$hay  = get_the_title( $id ) . ' ' . get_post_meta( $id, '_asset_city', true );
			$terms = get_the_terms( $id, 'asset_discipline' );
			if ( is_array( $terms ) ) {
				$hay .= ' ' . implode( ' ', wp_list_pluck( $terms, 'name' ) );
			}
			if ( str_contains( self::norm( $hay ), $needle ) ) {
				$out[] = (int) $id;
			}
		}
		return $out;
	}

	/**
	 * Builds the WP_Query for the given filters.
	 *
	 * @param array $f Filters.
	 * @return WP_Query
	 */
	public static function query( $f ) {
		$today = wp_date( 'Y-m-d' );
		$args  = array(
			'post_type'      => Asset_CD_Congres::POST_TYPE,
			'post_status'    => 'publish',
			'posts_per_page' => self::PER_PAGE,
			'paged'          => $f['pg'],
			'meta_key'       => '_asset_start', // phpcs:ignore WordPress.DB.SlowDBQuery.slow_db_query_meta_key
			'orderby'        => array(
				'meta_value' => 'date_desc' === $f['tri'] ? 'DESC' : 'ASC',
				'title'      => 'ASC',
			),
			'meta_query'     => array( 'relation' => 'AND' ), // phpcs:ignore WordPress.DB.SlowDBQuery.slow_db_query_meta_query
			'tax_query'      => array( 'relation' => 'AND' ), // phpcs:ignore WordPress.DB.SlowDBQuery.slow_db_query_tax_query
		);
		if ( ! $f['passes'] ) {
			$args['meta_query'][] = array(
				'key'     => '_asset_end',
				'value'   => $today,
				'compare' => '>=',
			);
		}
		if ( $f['mois'] ) {
			$first                = $f['mois'] . '-01';
			$last                 = gmdate( 'Y-m-t', (int) strtotime( $first . ' 12:00:00 UTC' ) );
			$args['meta_query'][] = array(
				'key'     => '_asset_start',
				'value'   => $last,
				'compare' => '<=',
			);
			$args['meta_query'][] = array(
				'key'     => '_asset_end',
				'value'   => $first,
				'compare' => '>=',
			);
		}
		foreach ( array(
			'discipline' => 'asset_discipline',
			'pays'       => 'asset_pays',
		) as $param => $tax ) {
			if ( $f[ $param ] ) {
				$args['tax_query'][] = array(
					'taxonomy' => $tax,
					'field'    => 'slug',
					'terms'    => $f[ $param ],
				);
			}
		}
		if ( '' !== $f['q'] ) {
			$ids              = self::search_ids( $f['q'] );
			$args['post__in'] = $ids ? $ids : array( 0 );
		}
		return new WP_Query( $args );
	}

	/**
	 * Month options from the published congresses.
	 *
	 * @param bool $include_past Include past months.
	 * @return array<string,string> 'Y-m' => label.
	 */
	public static function month_options( $include_past ) {
		$ids    = get_posts(
			array(
				'post_type'      => Asset_CD_Congres::POST_TYPE,
				'post_status'    => 'publish',
				'posts_per_page' => 2000,
				'fields'         => 'ids',
				'no_found_rows'  => true,
			)
		);
		$today  = wp_date( 'Y-m-d' );
		$names  = Asset_CD_Congres::month_names();
		$months = array();
		foreach ( $ids as $id ) {
			$s = (string) get_post_meta( $id, '_asset_start', true );
			$e = (string) get_post_meta( $id, '_asset_end', true );
			if ( ! $s || ( ! $include_past && $e && $e < $today ) ) {
				continue;
			}
			$key            = substr( $s, 0, 7 );
			$months[ $key ] = ucfirst( $names[ (int) substr( $s, 5, 2 ) ] ) . ' ' . substr( $s, 0, 4 );
		}
		ksort( $months );
		return $months;
	}

	/**
	 * Renders a select element.
	 *
	 * @param string $name    Name.
	 * @param string $label   Label.
	 * @param array  $options value => label.
	 * @param string $current Current value.
	 * @param string $all     Label of the empty option.
	 * @return string
	 */
	private static function select( $name, $label, $options, $current, $all ) {
		$id   = 'asset-f-' . $name;
		$html = sprintf( '<div class="asset-field"><label for="%1$s">%2$s</label><select id="%1$s" name="%3$s"><option value="">%4$s</option>', esc_attr( $id ), esc_html( $label ), esc_attr( $name ), esc_html( $all ) );
		foreach ( $options as $value => $text ) {
			$html .= sprintf( '<option value="%1$s"%2$s>%3$s</option>', esc_attr( (string) $value ), selected( $current, (string) $value, false ), esc_html( $text ) );
		}
		return $html . '</select></div>';
	}

	/**
	 * Terms as slug => name.
	 *
	 * @param string $tax Taxonomy.
	 * @return array<string,string>
	 */
	private static function term_options( $tax ) {
		$terms = get_terms(
			array(
				'taxonomy'   => $tax,
				'hide_empty' => true,
			)
		);
		$out   = array();
		if ( is_array( $terms ) ) {
			foreach ( $terms as $t ) {
				$out[ $t->slug ] = $t->name;
			}
		}
		asort( $out );
		return $out;
	}

	/**
	 * Shortcode [asset_catalogue].
	 *
	 * @return string
	 */
	public static function shortcode() {
		$f     = self::read_filters();
		if ( is_post_type_archive( Asset_CD_Congres::POST_TYPE ) ) {
			$base = (string) get_post_type_archive_link( Asset_CD_Congres::POST_TYPE );
		} else {
			$base = is_singular() ? (string) get_permalink() : '';
		}
		$base = $base ? $base : home_url( '/' );
		$query = self::query( $f );
		$total = (int) $query->found_posts;

		ob_start();
		?>
		<div class="asset-cd asset-catalogue alignwide">
			<p class="asset-intro"><?php esc_html_e( 'Trouvez votre congrès et demandez un devis vol en quelques secondes.', 'asset-congres-demo' ); ?></p>
			<p class="asset-demo-flag"><?php esc_html_e( 'Démonstration : tous les congrès ci-dessous sont fictifs.', 'asset-congres-demo' ); ?></p>
			<form class="asset-filters" method="get" action="<?php echo esc_url( $base ); ?>" role="search" aria-label="<?php esc_attr_e( 'Rechercher un congrès', 'asset-congres-demo' ); ?>">
				<div class="asset-field asset-field--search">
					<label for="asset-f-q"><?php esc_html_e( 'Recherche', 'asset-congres-demo' ); ?></label>
					<input type="search" id="asset-f-q" name="q" value="<?php echo esc_attr( $f['q'] ); ?>" maxlength="100" placeholder="<?php esc_attr_e( 'Titre, ville ou discipline', 'asset-congres-demo' ); ?>" />
				</div>
				<?php
				// phpcs:disable WordPress.Security.EscapeOutput.OutputNotEscaped -- select() escapes.
				echo self::select( 'discipline', __( 'Discipline', 'asset-congres-demo' ), self::term_options( 'asset_discipline' ), $f['discipline'], __( 'Toutes les disciplines', 'asset-congres-demo' ) );
				echo self::select( 'pays', __( 'Pays', 'asset-congres-demo' ), self::term_options( 'asset_pays' ), $f['pays'], __( 'Tous les pays', 'asset-congres-demo' ) );
				echo self::select( 'mois', __( 'Mois', 'asset-congres-demo' ), self::month_options( $f['passes'] ), $f['mois'], __( 'Tous les mois', 'asset-congres-demo' ) );
				// phpcs:enable
				?>
				<div class="asset-field">
					<label for="asset-f-tri"><?php esc_html_e( 'Trier par', 'asset-congres-demo' ); ?></label>
					<select id="asset-f-tri" name="tri">
						<option value="date_asc" <?php selected( $f['tri'], 'date_asc' ); ?>><?php esc_html_e( 'Date croissante', 'asset-congres-demo' ); ?></option>
						<option value="date_desc" <?php selected( $f['tri'], 'date_desc' ); ?>><?php esc_html_e( 'Date décroissante', 'asset-congres-demo' ); ?></option>
					</select>
				</div>
				<div class="asset-field asset-field--check">
					<input type="checkbox" id="asset-f-passes" name="passes" value="1" <?php checked( $f['passes'] ); ?> />
					<label for="asset-f-passes"><?php esc_html_e( 'Inclure les congrès passés', 'asset-congres-demo' ); ?></label>
				</div>
				<div class="asset-actions">
					<button type="submit" class="asset-btn"><?php esc_html_e( 'Rechercher', 'asset-congres-demo' ); ?></button>
					<a class="asset-link" href="<?php echo esc_url( $base ); ?>"><?php esc_html_e( 'Réinitialiser', 'asset-congres-demo' ); ?></a>
				</div>
			</form>

			<nav class="asset-chips" aria-label="<?php esc_attr_e( 'Accès rapide par discipline', 'asset-congres-demo' ); ?>">
				<ul>
					<?php foreach ( self::term_options( 'asset_discipline' ) as $slug => $name ) : ?>
						<?php $active = $slug === $f['discipline']; ?>
						<li><a class="asset-chip<?php echo $active ? ' is-active' : ''; ?>" href="<?php echo esc_url( $active ? remove_query_arg( array( 'discipline', 'pg' ) ) : add_query_arg( 'discipline', rawurlencode( (string) $slug ), remove_query_arg( 'pg' ) ) ); ?>"<?php echo $active ? ' aria-current="true"' : ''; ?>><?php echo esc_html( $name ); ?></a></li>
					<?php endforeach; ?>
				</ul>
			</nav>

			<p class="asset-count" role="status">
				<?php
				/* translators: %s: number of congresses. */
				echo esc_html( sprintf( _n( '%s congrès trouvé', '%s congrès trouvés', $total, 'asset-congres-demo' ), number_format_i18n( $total ) ) );
				?>
			</p>

			<?php if ( ! $query->have_posts() ) : ?>
				<div class="asset-empty">
					<h2><?php esc_html_e( 'Aucun congrès ne correspond à votre recherche', 'asset-congres-demo' ); ?></h2>
					<p><?php esc_html_e( 'Essayez un autre mot-clé, retirez un filtre ou affichez tous les congrès.', 'asset-congres-demo' ); ?></p>
					<p><a class="asset-btn asset-btn--ghost" href="<?php echo esc_url( $base ); ?>"><?php esc_html_e( 'Voir tous les congrès', 'asset-congres-demo' ); ?></a></p>
				</div>
			<?php else : ?>
				<ul class="asset-grid">
					<?php
					foreach ( $query->posts as $p ) {
						self::card( $p );
					}
					?>
				</ul>
				<?php self::pagination( $base, $f, (int) $query->max_num_pages ); ?>
			<?php endif; ?>
		</div>
		<?php
		return (string) ob_get_clean();
	}

	/**
	 * Card markup.
	 *
	 * @param WP_Post $p Post.
	 */
	private static function card( $p ) {
		$discipline = Asset_CD_Congres::term_name( $p->ID, 'asset_discipline' );
		$pays       = Asset_CD_Congres::term_name( $p->ID, 'asset_pays' );
		$city       = (string) get_post_meta( $p->ID, '_asset_city', true );
		?>
		<li class="asset-card">
			<?php if ( $discipline ) : ?>
				<p class="asset-tag"><?php echo esc_html( $discipline ); ?></p>
			<?php endif; ?>
			<h2 class="asset-card__title"><a href="<?php echo esc_url( get_permalink( $p ) ); ?>"><?php echo esc_html( get_the_title( $p ) ); ?></a></h2>
			<p class="asset-card__meta"><?php echo esc_html( Asset_CD_Congres::format_range( $p->ID ) ); ?></p>
			<p class="asset-card__meta"><?php echo esc_html( trim( $city . ( $pays ? ', ' . $pays : '' ), ', ' ) ); ?></p>
			<?php if ( Asset_CD_Gme::has_public_offer( $p->ID ) ) : ?>
				<p class="asset-card__offer"><?php esc_html_e( 'Tarif congrès négocié disponible', 'asset-congres-demo' ); ?></p>
			<?php endif; ?>
		</li>
		<?php
	}

	/**
	 * Pagination links (server-rendered).
	 *
	 * @param string $base  Base URL.
	 * @param array  $f     Filters.
	 * @param int    $pages Page count.
	 */
	private static function pagination( $base, $f, $pages ) {
		if ( $pages < 2 ) {
			return;
		}
		$params = array_filter(
			array(
				'q'          => $f['q'],
				'discipline' => $f['discipline'],
				'pays'       => $f['pays'],
				'mois'       => $f['mois'],
				'tri'        => 'date_desc' === $f['tri'] ? 'date_desc' : '',
				'passes'     => $f['passes'] ? '1' : '',
			)
		);
		$url    = static function ( $n ) use ( $base, $params ) {
			$args = $params;
			if ( $n > 1 ) {
				$args['pg'] = $n;
			}
			return add_query_arg( array_map( 'rawurlencode', $args ), $base );
		};
		echo '<nav class="asset-pagination" aria-label="' . esc_attr__( 'Pagination du catalogue', 'asset-congres-demo' ) . '"><ul>';
		if ( $f['pg'] > 1 ) {
			echo '<li><a rel="prev" href="' . esc_url( $url( $f['pg'] - 1 ) ) . '">' . esc_html__( 'Précédent', 'asset-congres-demo' ) . '</a></li>';
		}
		for ( $i = 1; $i <= $pages; $i++ ) {
			if ( $i === $f['pg'] ) {
				echo '<li><span aria-current="page">' . esc_html( (string) $i ) . '</span></li>';
			} else {
				/* translators: %d: page number. */
				echo '<li><a href="' . esc_url( $url( $i ) ) . '" aria-label="' . esc_attr( sprintf( __( 'Page %d', 'asset-congres-demo' ), $i ) ) . '">' . esc_html( (string) $i ) . '</a></li>';
			}
		}
		if ( $f['pg'] < $pages ) {
			echo '<li><a rel="next" href="' . esc_url( $url( $f['pg'] + 1 ) ) . '">' . esc_html__( 'Suivant', 'asset-congres-demo' ) . '</a></li>';
		}
		echo '</ul></nav>';
	}

	/**
	 * Appends the details card and the enquiry form to single congress pages.
	 *
	 * @param string $content Content.
	 * @return string
	 */
	public static function single_content( $content ) {
		if ( ! is_singular( Asset_CD_Congres::POST_TYPE ) || ! in_the_loop() || ! is_main_query() ) {
			return $content;
		}
		$id = get_the_ID();
		if ( ! $id ) {
			return $content;
		}
		$fields = array(
			__( 'Dates', 'asset-congres-demo' )      => Asset_CD_Congres::format_range( $id ),
			__( 'Ville', 'asset-congres-demo' )      => (string) get_post_meta( $id, '_asset_city', true ),
			__( 'Pays', 'asset-congres-demo' )       => Asset_CD_Congres::term_name( $id, 'asset_pays' ),
			__( 'Discipline', 'asset-congres-demo' ) => Asset_CD_Congres::term_name( $id, 'asset_discipline' ),
			__( 'Lieu', 'asset-congres-demo' )       => (string) get_post_meta( $id, '_asset_venue', true ),
		);
		$url      = (string) get_post_meta( $id, '_asset_url', true );
		$source   = (string) get_post_meta( $id, '_asset_source', true );
		$verified = (string) get_post_meta( $id, '_asset_verified', true );
		$cat_id   = (int) get_option( 'asset_cd_catalogue_page' );

		ob_start();
		?>
		<div class="asset-cd asset-single alignwide">
			<?php if ( $cat_id ) : ?>
				<p><a class="asset-link" href="<?php echo esc_url( get_permalink( $cat_id ) ); ?>"><?php esc_html_e( 'Retour au catalogue', 'asset-congres-demo' ); ?></a></p>
			<?php endif; ?>
			<section class="asset-details" aria-labelledby="asset-details-title">
				<h2 id="asset-details-title"><?php esc_html_e( 'Informations pratiques', 'asset-congres-demo' ); ?></h2>
				<dl>
					<?php foreach ( $fields as $label => $value ) : ?>
						<?php
						if ( '' === $value ) {
							continue;
						}
						?>
						<div><dt><?php echo esc_html( $label ); ?></dt><dd><?php echo esc_html( $value ); ?></dd></div>
					<?php endforeach; ?>
					<?php if ( $url ) : ?>
						<div><dt><?php esc_html_e( 'Site officiel', 'asset-congres-demo' ); ?></dt><dd><a href="<?php echo esc_url( $url ); ?>" rel="noopener nofollow"><?php echo esc_html( wp_parse_url( $url, PHP_URL_HOST ) ?: $url ); ?></a></dd></div>
					<?php endif; ?>
				</dl>
				<?php if ( $source || $verified ) : ?>
					<p class="asset-source">
						<?php
						/* translators: 1: source, 2: verification date. */
						echo esc_html( sprintf( __( 'Source : %1$s, vérifiée le %2$s.', 'asset-congres-demo' ), $source ? $source : '—', $verified ? Asset_CD_Congres::format_date( $verified ) : '—' ) );
						?>
					</p>
				<?php endif; ?>
				<?php if ( Asset_CD_Gme::has_public_offer( $id ) ) : ?>
					<p class="asset-offer"><?php esc_html_e( 'Tarif congrès négocié disponible : appliqué à votre devis', 'asset-congres-demo' ); ?></p>
				<?php endif; ?>
			</section>
			<?php echo Asset_CD_Demandes::render_form( $id ); // phpcs:ignore WordPress.Security.EscapeOutput.OutputNotEscaped -- escaped inside. ?>
		</div>
		<?php
		return $content . ob_get_clean();
	}
}
