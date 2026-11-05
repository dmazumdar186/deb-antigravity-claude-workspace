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
