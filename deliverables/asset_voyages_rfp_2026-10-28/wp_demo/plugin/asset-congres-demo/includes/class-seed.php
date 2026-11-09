<?php
/**
 * Idempotent demo seed: congresses, enquiries, GM&E dummy codes, users, catalogue page.
 * All data is fictional. Run from the Playground blueprint (runPHP), WP-CLI
 * (`wp asset-demo seed`) or Outils → Démo ASSET.
 *
 * @package AssetCongresDemo
 */

defined( 'ABSPATH' ) || exit;

/**
 * Seeder.
 */
class Asset_CD_Seed {

	const DEMO_PASSWORD = 'demo-asset'; // Throwaway sandbox password, documented in the README.

	/**
	 * Hooks.
	 */
	public static function init() {
		add_action( 'admin_menu', array( __CLASS__, 'menu' ) );
		add_action( 'admin_post_asset_cd_reseed', array( __CLASS__, 'handle_reseed' ) );
		if ( defined( 'WP_CLI' ) && WP_CLI ) {
			WP_CLI::add_command(
				'asset-demo seed',
				static function () {
					$r = self::run();
					WP_CLI::success( wp_json_encode( $r ) );
				}
			);
		}
	}

	/**
	 * Congress data: ref => [title, discipline, city, country, start, end, status].
	 *
	 * @return array<string,array>
	 */
	public static function congresses() {
		return array(
			'CG-0101' => array( 'Congrès européen de cardiologie — exemple', 'Cardiologie', 'Madrid', 'Espagne', '2027-08-27', '2027-08-30', 'publish' ),
			'CG-0102' => array( 'Congrès international d’oncologie — exemple', 'Oncologie', 'Berlin', 'Allemagne', '2027-10-15', '2027-10-19', 'publish' ),
			'CG-0103' => array( 'Journées francophones de diabétologie — exemple', 'Diabétologie', 'Lyon', 'France', '2027-03-23', '2027-03-26', 'publish' ),
			'CG-0104' => array( 'Congrès européen de neurologie — exemple', 'Neurologie', 'Vienne', 'Autriche', '2027-06-19', '2027-06-22', 'publish' ),
			'CG-0105' => array( 'Congrès européen de dermatologie — exemple', 'Dermatologie', 'Amsterdam', 'Pays-Bas', '2027-09-29', '2027-10-02', 'publish' ),
			'CG-0106' => array( 'Congrès international de pneumologie — exemple', 'Pneumologie', 'Milan', 'Italie', '2027-09-04', '2027-09-08', 'publish' ),
			'CG-0107' => array( 'Congrès d’ophtalmologie de Paris — exemple', 'Ophtalmologie', 'Paris', 'France', '2027-05-08', '2027-05-11', 'publish' ),
			'CG-0108' => array( 'Rencontres européennes d’imagerie médicale — exemple', 'Radiologie', 'Porto', 'Portugal', '2027-04-21', '2027-04-24', 'publish' ), // Not a real congress name, city or season (CE-D2-002).
			'CG-0109' => array( 'Forum européen des ressources humaines — exemple', 'Ressources humaines', 'Lisbonne', 'Portugal', '2027-04-13', '2027-04-14', 'publish' ),
			'CG-0110' => array( 'Sommet de la finance d’entreprise — exemple', 'Finance', 'Londres', 'Royaume-Uni', '2027-11-17', '2027-11-18', 'publish' ),
			'CG-0111' => array( 'Congrès nord-américain de cardiologie — exemple', 'Cardiologie', 'Chicago', 'États-Unis', '2027-11-13', '2027-11-16', 'publish' ),
			'CG-0112' => array( 'Journées méditerranéennes d’oncologie — exemple', 'Oncologie', 'Marseille', 'France', '2027-01-28', '2027-01-30', 'publish' ),
			// Two control records: one past edition and one unpublished draft (both must stay out of the default catalogue).
			'CG-0098' => array( 'Congrès d’hématologie, édition passée — exemple', 'Hématologie', 'Bruxelles', 'Belgique', '2026-06-10', '2026-06-12', 'publish' ),
			'CG-0099' => array( 'Congrès de rhumatologie, brouillon — exemple', 'Rhumatologie', 'Genève', 'Suisse', '2027-12-01', '2027-12-03', 'draft' ),
		);
	}

	/**
	 * Dummy GM&E codes: congress ref => [code, status, from, to, evidence].
	 *
	 * @return array<string,array>
	 */
	public static function codes() {
		return array(
			'CG-0101' => array( 'DEMO-GME-4KQ7', 'approuve', '2027-07-27', '2027-09-06', 'Courriel fictif de l’organisateur du 12/10/2026 (exemple).' ),
			'CG-0102' => array( 'DEMO-GME-8TZ2', 'verifie', '2027-09-15', '2027-10-25', 'Code vérifié sur le portail fictif de l’organisateur (exemple).' ),
			'CG-0104' => array( 'DEMO-GME-3MX9', 'approuve', '2027-05-19', '2027-06-29', 'Confirmation fictive reçue le 20/10/2026 (exemple).' ),
			'CG-0106' => array( 'DEMO-GME-6PL5', 'detecte', '', '', 'Mention repérée sur une page fictive, à vérifier (exemple).' ),
			'CG-0110' => array( 'DEMO-GME-1RB8', 'expire', '2026-01-01', '2026-06-30', 'Ancien code fictif, période close (exemple).' ),
		);
	}

	/**
	 * Ensures a demo user exists with the right role.
	 *
	 * @param string $login Login.
	 * @param string $role  Role.
	 * @param string $name  Display name.
	 * @return int
	 */
	private static function user( $login, $role, $name ) {
		$u = get_user_by( 'login', $login );
		if ( $u ) {
			$u->set_role( $role );
			return (int) $u->ID;
		}
		$id = wp_insert_user(
			array(
				'user_login'   => $login,
				'user_pass'    => self::DEMO_PASSWORD,
				'user_email'   => $login . '@example.com',
				'display_name' => $name,
				'first_name'   => $name,
				'role'         => $role,
			)
		);
		return is_wp_error( $id ) ? 0 : (int) $id;
	}

	/**
	 * Finds a congress by its internal reference.
	 *
	 * @param string $ref Reference.
	 * @return int
	 */
	public static function congres_id( $ref ) {
		$ids = get_posts(
			array(
				'post_type'      => Asset_CD_Congres::POST_TYPE,
				'post_status'    => 'any',
				'posts_per_page' => 1,
				'fields'         => 'ids',
				'meta_key'       => '_asset_ref', // phpcs:ignore WordPress.DB.SlowDBQuery.slow_db_query_meta_key
				'meta_value'     => $ref, // phpcs:ignore WordPress.DB.SlowDBQuery.slow_db_query_meta_value
			)
		);
		return $ids ? (int) $ids[0] : 0;
	}

	/**
	 * Runs the seed. Idempotent: stable keys everywhere, re-run creates nothing new.
	 *
	 * @return array<string,int>
	 */
	public static function run() {
		Asset_CD_Roles::install();
		Asset_CD_Gme::install_tables();
		Asset_CD_Notifications::install_table();
		$created = array(
			'congres'  => 0,
			'demandes' => 0,
			'codes'    => 0,
			'users'    => 0,
			'requests' => 0,
		);

		$before = count_users();
		$users  = array(
			'direction'    => self::user( 'direction', 'asset_direction', 'Direction (démo)' ),
			'equipe'       => self::user( 'equipe', 'asset_equipe', 'Équipe (démo)' ),
			'contributeur' => self::user( 'contributeur', 'asset_contributeur', 'Contributeur (démo)' ),
		);
		$created['users'] = count_users()['total_users'] - $before['total_users'];

		// Congresses.
		$ids = array();
		foreach ( self::congresses() as $ref => $c ) {
			$id = self::congres_id( $ref );
			if ( ! $id ) {
				$id = (int) wp_insert_post(
					array(
						'post_type'    => Asset_CD_Congres::POST_TYPE,
						'post_status'  => $c[6],
						'post_title'   => $c[0],
						'post_excerpt' => sprintf( 'Congrès fictif de %s à %s, créé pour la démonstration.', mb_strtolower( $c[1] ), $c[2] ),
						'post_content' => "Description fictive à des fins de démonstration : ce congrès n’existe pas. Les dates, le lieu et le programme sont inventés.\n\nProgramme indicatif : sessions plénières, ateliers pratiques et exposition professionnelle.", // Plain text: the congress editor is a plain textarea, the front end adds the paragraphs.
						'meta_input'   => array( '_asset_ref' => $ref ),
					)
				);
				++$created['congres'];
			}
			$ids[ $ref ] = $id;
			$meta        = array(
				'_asset_start'    => $c[4],
				'_asset_end'      => $c[5],
				'_asset_city'     => $c[2],
				'_asset_venue'    => 'Palais des congrès de ' . $c[2] . ' (fictif)',
				'_asset_url'      => '', // Fictional congress: no official site (shown as « fictif (démonstration) », CE-A4-002).
				'_asset_source'   => 'Site de l’organisateur (exemple)',
				'_asset_verified' => '2026-10-15',
			);
			foreach ( $meta as $k => $v ) {
				if ( '' === (string) get_post_meta( $id, $k, true ) ) {
					update_post_meta( $id, $k, $v );
				}
			}
			foreach ( array(
				'asset_discipline' => $c[1],
				'asset_pays'       => $c[3],
			) as $tax => $name ) {
				if ( ! has_term( '', $tax, $id ) ) {
					$term = term_exists( $name, $tax );
					if ( ! $term ) {
						$term = wp_insert_term( $name, $tax );
					}
					if ( ! is_wp_error( $term ) ) {
						wp_set_object_terms( $id, array( (int) $term['term_id'] ), $tax );
					}
				}
			}
		}

		// GM&E dummy codes (encrypted, custom table only).
		foreach ( self::codes() as $ref => $c ) {
			if ( ! empty( $ids[ $ref ] ) && ! Asset_CD_Gme::get_by_congres( $ids[ $ref ] ) ) {
				Asset_CD_Gme::save_code( $ids[ $ref ], $c[0], $c[1], $c[2], $c[3], $c[4], $users['direction'] );
				++$created['codes'];
			}
		}

		// One pending access request from "equipe".
		if ( $users['equipe'] && ! empty( $ids['CG-0101'] ) && ! Asset_CD_Gme::latest_request( $users['equipe'], $ids['CG-0101'] ) ) {
			Asset_CD_Gme::create_request( $users['equipe'], $ids['CG-0101'], 'Devis groupe de 12 personnes pour un laboratoire client (exemple).' );
			++$created['requests'];
		}

		$created['demandes'] = self::seed_demandes( $ids, $users );

		// Catalogue page as landing page.
		$page_id = (int) get_option( 'asset_cd_catalogue_page' );
		if ( ! $page_id || ! get_post( $page_id ) ) {
			$existing = get_page_by_path( 'catalogue-des-congres' );
			$page_id  = $existing ? (int) $existing->ID : (int) wp_insert_post(
				array(
					'post_type'    => 'page',
					'post_status'  => 'publish',
					'post_title'   => 'Catalogue des congrès',
					'post_name'    => 'catalogue-des-congres',
					'post_content' => "<!-- wp:shortcode -->\n[asset_catalogue]\n<!-- /wp:shortcode -->",
				)
			);
			update_option( 'asset_cd_catalogue_page', $page_id, false );
		}
		update_option( 'show_on_front', 'page' );
		update_option( 'page_on_front', $page_id );
		update_option( 'blogname', 'ASSET Voyages — démonstration' );
		update_option( 'timezone_string', 'Europe/Paris' );
		update_option( 'date_format', 'd/m/Y' );
		update_option( 'time_format', 'H:i' );
		update_option( 'start_of_week', 1 );
		update_option( 'blogdescription', 'Démonstration : congrès, devis vol et codes GM&E fictifs' );
		update_option( 'asset_cd_notify_email', 'equipe-demo@example.com', false );

		// Remove WordPress sample content (idempotent).
		foreach ( array( 'hello-world' => 'post', 'sample-page' => 'page' ) as $slug => $type ) {
			$p = get_page_by_path( $slug, OBJECT, $type );
			if ( $p ) {
				wp_delete_post( $p->ID, true );
			}
		}
		foreach ( get_comments( array( 'number' => 50 ) ) as $cm ) {
			wp_delete_comment( $cm->comment_ID, true );
		}

		self::install_theme();

		if ( '/%postname%/' !== get_option( 'permalink_structure' ) ) {
			update_option( 'permalink_structure', '/%postname%/' );
		}
		Asset_CD_Congres::register();
		Asset_CD_Demandes::register_post_type();
		flush_rewrite_rules( false );

		return $created;
	}

	/**
	 * Copies the bundled child theme (theme/asset-demo) into wp-content/themes and activates it
	 * when Twenty Twenty-Five is available. Idempotent: files are refreshed only when the version changes.
	 */
	public static function install_theme() {
		$src  = ASSET_CD_DIR . 'theme/asset-demo';
		$dest = trailingslashit( get_theme_root() ) . 'asset-demo';
		if ( ! is_dir( $src ) || ! wp_get_theme( 'twentytwentyfive' )->exists() ) {
			return;
		}
		$installed = wp_get_theme( 'asset-demo' );
		if ( ! $installed->exists() || ASSET_CD_VERSION !== $installed->get( 'Version' ) ) {
			$it = new RecursiveIteratorIterator( new RecursiveDirectoryIterator( $src, FilesystemIterator::SKIP_DOTS ), RecursiveIteratorIterator::SELF_FIRST );
			wp_mkdir_p( $dest );
			foreach ( $it as $item ) {
				$target = $dest . '/' . substr( $item->getPathname(), strlen( $src ) + 1 );
				if ( $item->isDir() ) {
					wp_mkdir_p( $target );
				} else {
					copy( $item->getPathname(), $target );
				}
			}
			wp_clean_themes_cache();
		}
		if ( 'asset-demo' !== get_stylesheet() ) {
			switch_theme( 'asset-demo' );
		}
	}

	/**
	 * Sample enquiries across statuses (fictional people, example.com).
	 *
	 * @param array $ids   Congress IDs by ref.
	 * @param array $users Users.
	 * @return int Created.
	 */
	private static function seed_demandes( $ids, $users ) {
		$eq   = $users['equipe'];
		$dir  = $users['direction'];
		$rows = array(
			array( 'DV-2026-0001', 'CG-0102', 'Julien Bernard', 'julien.bernard@example.com', '01 99 00 00 02', 'Laboratoire Fictif SA', 'Lyon', '2027-10-14', '2027-10-20', 12, 'qualifiee', $eq, 9 ),
			array( 'DV-2026-0002', 'CG-0104', 'Sophie Dubois', 'sophie.dubois@example.com', '01 99 00 00 03', '', 'Bordeaux', '2027-06-18', '2027-06-23', 2, 'devis_envoye', $eq, 8 ),
			array( 'DV-2026-0003', 'CG-0106', 'Thomas Petit', 'thomas.petit@example.com', '01 99 00 00 04', 'Groupe hospitalier Exemple', 'Nantes', '2027-09-03', '2027-09-09', 25, 'gagnee', $dir, 7 ),
			array( 'DV-2026-0004', 'CG-0107', 'Léa Moreau', 'lea.moreau@example.com', '01 99 00 00 05', '', 'Toulouse', '2027-05-07', '2027-05-12', 1, 'perdue', $dir, 6 ),
			array( 'DV-2026-0005', 'CG-0111', 'Hugo Laurent', 'hugo.laurent@example.com', '01 99 00 00 06', 'Cabinet Exemple', 'Marseille', '2027-11-12', '2027-11-17', 4, 'nouvelle', 0, 3 ),
			array( 'DV-2026-0006', 'CG-0101', 'Camille Martin', 'camille.martin@example.com', '01 99 00 00 01', 'Clinique Exemple', 'Paris', '2027-08-26', '2027-08-31', 3, 'nouvelle', 0, 1 ),
		);
		$flow    = array_keys( Asset_CD_Demandes::statuses() );
		$created = 0;
		foreach ( $rows as $r ) {
			if ( Asset_CD_Demandes::find_by_reference( $r[0] ) || empty( $ids[ $r[1] ] ) ) {
				continue;
			}
			$when = gmdate( 'Y-m-d H:i:s', time() - $r[12] * DAY_IN_SECONDS );
			$id   = (int) wp_insert_post(
				array(
					'post_type'     => Asset_CD_Demandes::POST_TYPE,
					'post_status'   => 'private',
					'post_title'    => $r[0],
					'post_author'   => 0,
					'post_date'     => get_date_from_gmt( $when ),
					'post_date_gmt' => $when,
					'meta_input'    => array(
						'_asset_ref'          => $r[0],
						'_asset_congres_id'   => $ids[ $r[1] ],
						'_asset_nom'          => $r[2],
						'_asset_email'        => $r[3],
						'_asset_telephone'    => $r[4],
						'_asset_societe'      => $r[5],
						'_asset_ville_depart' => $r[6],
						'_asset_date_aller'   => $r[7],
						'_asset_date_retour'  => $r[8],
						'_asset_passagers'    => $r[9],
						'_asset_message'      => 'Demande fictive créée pour la démonstration.',
						'_asset_consent_at'   => $when,
						'_asset_statut'       => $r[10],
						'_asset_owner'        => $r[11],
					),
				)
			);
			if ( ! $id ) {
				continue;
			}
			++$created;
			Asset_CD_Demandes::add_history( $id, 'created', '', 'nouvelle', '', 0, $when );
			if ( $r[11] ) {
				Asset_CD_Demandes::add_history( $id, 'owner', '0', (string) $r[11], '', $r[11], gmdate( 'Y-m-d H:i:s', strtotime( $when ) + 3600 ) );
			}
			$target = array_search( $r[10], $flow, true );
			$prev   = 'nouvelle';
			$steps  = 'perdue' === $r[10] ? array( 'qualifiee', 'perdue' ) : array_slice( $flow, 1, (int) $target );
			foreach ( $steps as $i => $s ) {
				Asset_CD_Demandes::add_history( $id, 'status', $prev, $s, '', $r[11] ? $r[11] : $eq, gmdate( 'Y-m-d H:i:s', strtotime( $when ) + ( $i + 2 ) * 3600 ) );
				$prev = $s;
			}
		}
		if ( (int) get_option( 'asset_cd_seq_2026', 0 ) < 6 ) {
			update_option( 'asset_cd_seq_2026', 6, false );
		}
		return $created;
	}

	/**
	 * Tools submenu.
	 */
	public static function menu() {
		add_management_page( __( 'Démo ASSET', 'asset-congres-demo' ), __( 'Démo ASSET', 'asset-congres-demo' ), 'manage_options', 'asset-demo-tools', array( __CLASS__, 'render' ) );
	}

	/**
	 * Tools screen.
	 */
	public static function render() {
		if ( ! current_user_can( 'manage_options' ) ) {
			wp_die( esc_html__( 'Accès refusé.', 'asset-congres-demo' ), 403 );
		}
		echo '<div class="wrap asset-admin"><h1>' . esc_html__( 'Démo ASSET', 'asset-congres-demo' ) . '</h1>';
		// phpcs:ignore WordPress.Security.NonceVerification.Recommended
		if ( isset( $_GET['seeded'] ) ) {
			$n = absint( $_GET['seeded'] ); // phpcs:ignore WordPress.Security.NonceVerification.Recommended
			/* translators: %d: number of created items. */
			echo '<div class="notice notice-success asset-seeded"><p>' . esc_html( sprintf( __( 'Jeu de données vérifié : %d élément(s) créé(s), aucun doublon.', 'asset-congres-demo' ), $n ) ) . '</p></div>';
		}
		echo '<p>' . esc_html__( 'Relance le jeu de données fictif. L’opération est idempotente : les éléments existants ne sont pas dupliqués. Pour revenir à l’état initial complet, rechargez la page WordPress Playground.', 'asset-congres-demo' ) . '</p>';
		echo '<form method="post" action="' . esc_url( admin_url( 'admin-post.php' ) ) . '"><input type="hidden" name="action" value="asset_cd_reseed" />';
		wp_nonce_field( 'asset_cd_reseed', 'asset_nonce' );
		submit_button( __( 'Relancer le jeu de données', 'asset-congres-demo' ), 'secondary' );
		echo '</form></div>';
	}

	/**
	 * Re-seed handler.
	 */
	public static function handle_reseed() {
		if ( ! isset( $_POST['asset_nonce'] ) || ! wp_verify_nonce( sanitize_key( wp_unslash( $_POST['asset_nonce'] ) ), 'asset_cd_reseed' ) ) {
			wp_die( esc_html__( 'Lien expiré ou invalide.', 'asset-congres-demo' ), 403 );
		}
		if ( ! current_user_can( 'manage_options' ) ) {
			wp_die( esc_html__( 'Accès refusé.', 'asset-congres-demo' ), 403 );
		}
		$r = self::run();
		wp_safe_redirect( admin_url( 'tools.php?page=asset-demo-tools&seeded=' . array_sum( $r ) ), 303 );
		exit;
	}
}
