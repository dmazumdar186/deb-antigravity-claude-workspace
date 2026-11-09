<?php
/**
 * Small shared UI helpers: dates in French format (Europe/Paris) and responsive tables.
 *
 * @package AssetCongresDemo
 */

defined( 'ABSPATH' ) || exit;

/**
 * UI helpers.
 */
class Asset_CD_Ui {

	const NBSP = "\u{00A0}";

	/**
	 * Hooks: every title ending in « — exemple » gets non-breaking spaces around the dash
	 * (CE-B4-004), in the admin lists too; the theme's post title wraps the suffix in a nowrap span.
	 */
	public static function init() {
		add_filter( 'the_title', array( __CLASS__, 'title_filter' ), 20 );
		add_filter( 'render_block_core/post-title', array( __CLASS__, 'nowrap_suffix' ), 10 );
		add_action( 'manage_posts_extra_tablenav', array( __CLASS__, 'list_titles' ) );
	}

	/**
	 * Core's congress list escapes titles itself, and Chrome still breaks after the dash before a
	 * non-breaking space. Between the top and bottom table navigation (the table itself), wrap the
	 * suffix of each row title, and of nothing else, in the nowrap span.
	 *
	 * @param string $which top or bottom.
	 */
	public static function list_titles( $which ) {
		static $open = false;
		$screen = function_exists( 'get_current_screen' ) ? get_current_screen() : null;
		if ( ! $screen || 'edit-' . Asset_CD_Congres::POST_TYPE !== $screen->id ) {
			return;
		}
		if ( 'top' === $which && ! $open ) {
			$open = ob_start();
			return;
		}
		if ( 'bottom' === $which && $open ) {
			$open = false;
			$html = (string) ob_get_clean();
			echo preg_replace_callback( // phpcs:ignore WordPress.Security.EscapeOutput.OutputNotEscaped -- core-escaped markup; only a span is added inside title text.
				'#(<a class="row-title"[^>]*>|<strong><span>)([^<]*)(</a>|</span>)#u',
				static function ( $m ) {
					return $m[1] . self::nowrap_suffix( $m[2] ) . $m[3];
				},
				$html
			);
		}
	}

	/**
	 * Plain-text title: « X — exemple » becomes « X&nbsp;—&nbsp;exemple » (the characters, not entities).
	 *
	 * @param string $title Title.
	 * @return string
	 */
	public static function nb_title( $title ) {
		return (string) preg_replace( '/[ \t\x{00A0}]+(—|&#8212;|&mdash;)[ \t\x{00A0}]+(exemple)\s*$/u', self::NBSP . '$1' . self::NBSP . '$2', (string) $title );
	}

	/**
	 * the_title filter.
	 *
	 * @param string $title Title.
	 * @return string
	 */
	public static function title_filter( $title ) {
		return is_string( $title ) ? self::nb_title( $title ) : $title;
	}

	/**
	 * Escaped HTML in which a trailing « — exemple » is an inline nowrap span after a non-breaking space.
	 *
	 * @param string $html Escaped markup.
	 * @return string
	 */
	public static function nowrap_suffix( $html ) {
		// The last word goes inside the span too: Chrome may break at the start of a nowrap span even
		// after a non-breaking space, which would leave « — exemple » alone on the next line.
		return (string) preg_replace( '/([^\s<>\x{00A0}]+)[ \t\x{00A0}]+(—|&#8212;|&mdash;)[ \t\x{00A0}]+exemple/u', '<span class="asset-nowrap">$1' . self::NBSP . '$2' . self::NBSP . 'exemple</span>', (string) $html );
	}

	/**
	 * Escaped congress title for our own screens and templates, suffix kept on one line.
	 *
	 * @param int|WP_Post $post Post.
	 * @return string
	 */
	public static function title_html( $post ) {
		return self::nowrap_suffix( esc_html( get_the_title( $post ) ) );
	}

	/**
	 * Formats a UTC datetime (Y-m-d H:i:s) as jj/mm/aaaa HH:MM in the site timezone.
	 *
	 * @param string $utc  UTC datetime.
	 * @param bool   $time Include the time.
	 * @return string
	 */
	public static function datetime( $utc, $time = true ) {
		if ( ! $utc || '0000-00-00 00:00:00' === $utc ) {
			return '—';
		}
		$ts = strtotime( $utc . ' UTC' );
		return $ts ? wp_date( $time ? 'd/m/Y H:i' : 'd/m/Y', $ts ) : '—';
	}

	/**
	 * Formats a calendar date (Y-m-d) as jj/mm/aaaa (no timezone shift).
	 *
	 * @param string $ymd Date.
	 * @return string
	 */
	public static function date( $ymd ) {
		$d = $ymd ? DateTimeImmutable::createFromFormat( '!Y-m-d', (string) $ymd ) : false;
		return $d ? $d->format( 'd/m/Y' ) : '—';
	}

	/**
	 * Adds data-label attributes (from the header row) to every cell of tables carrying the
	 * "asset-stack" class, so the CSS can stack them as labelled cards on narrow screens.
	 *
	 * @param string $html Markup (already escaped).
	 * @return string
	 */
	public static function stack_tables( $html ) {
		return (string) preg_replace_callback(
			'#<table[^>]*class="[^"]*asset-stack[^"]*"[^>]*>.*?</table>#s',
			static function ( $m ) {
				$table  = $m[0];
				$labels = array();
				if ( preg_match( '#<thead>(.*?)</thead>#s', $table, $head ) && preg_match_all( '#<th[^>]*>(.*?)</th>#s', $head[1], $ths ) ) {
					$labels = array_map( 'wp_strip_all_tags', $ths[1] );
				}
				if ( ! $labels ) {
					return $table;
				}
				return (string) preg_replace_callback(
					'#<tr([^>]*)>(.*?)</tr>#s',
					static function ( $row ) use ( $labels ) {
						if ( str_contains( $row[2], '<th' ) && ! str_contains( $row[2], '<td' ) ) {
							return $row[0];
						}
						$i = 0;
						$cells = (string) preg_replace_callback(
							'#<td(?=[\s>])#',
							static function () use ( &$i, $labels ) {
								$label = $labels[ $i ] ?? '';
								++$i;
								return '<td data-label="' . esc_attr( $label ) . '"';
							},
							$row[2]
						);
						return '<tr' . $row[1] . '>' . $cells . '</tr>';
					},
					$table
				);
			},
			$html
		);
	}
}
