<?php
/**
 * Flight enquiries: private post type, public form, validation and storage.
 *
 * @package AssetCongresDemo
 */

defined( 'ABSPATH' ) || exit;

/**
 * Enquiries (CPT asset_demande).
 */
class Asset_CD_Demandes {

	const POST_TYPE     = 'asset_demande';
	const MIN_FILL_SECS = 3;
	const PAX_MIN       = 1;
	const PAX_MAX       = 50;

	/**
	 * Status slugs => labels.
	 *
	 * @return array<string,string>
	 */
	public static function statuses() {
		return array(
			'nouvelle'     => __( 'Nouvelle', 'asset-congres-demo' ),
			'qualifiee'    => __( 'Qualifiée', 'asset-congres-demo' ),
			'devis_envoye' => __( 'Devis envoyé', 'asset-congres-demo' ),
			'gagnee'       => __( 'Gagnée', 'asset-congres-demo' ),
			'perdue'       => __( 'Perdue', 'asset-congres-demo' ),
		);
	}

	/**
	 * Field limits: name => max length.
	 *
	 * @return array<string,int>
	 */
	public static function max_lengths() {
		return array(
			'nom'          => 100,
			'email'        => 190,
			'telephone'    => 30,
			'societe'      => 150,
			'ville_depart' => 100,
			'date_aller'   => 10,
			'date_retour'  => 10,
			'passagers'    => 3,
			'message'      => 2000,
		);
	}

	/**
	 * Hooks.
	 */
	public static function init() {
		add_action( 'init', array( __CLASS__, 'register_post_type' ) );
		add_action( 'admin_post_nopriv_asset_demande_submit', array( __CLASS__, 'handle_submit' ) );
		add_action( 'admin_post_asset_demande_submit', array( __CLASS__, 'handle_submit' ) );
	}

	/**
	 * Registers the private enquiry post type.
	 */
	public static function register_post_type() {
		$cap = 'asset_manage_demandes';
		register_post_type(
			self::POST_TYPE,
			array(
				'labels'              => array(
					'name'          => __( 'Demandes', 'asset-congres-demo' ),
					'singular_name' => __( 'Demande', 'asset-congres-demo' ),
				),
				'public'              => false,
				'publicly_queryable'  => false,
				'exclude_from_search' => true,
				'show_ui'             => false,
				'show_in_nav_menus'   => false,
				'show_in_rest'        => false,
				'query_var'           => false,
				'rewrite'             => false,
				'has_archive'         => false,
				'supports'            => array( 'title' ),
				'map_meta_cap'        => false,
				'capabilities'        => array(
					'edit_post'              => $cap,
					'read_post'              => $cap,
					'delete_post'            => $cap,
					'edit_posts'             => $cap,
					'edit_others_posts'      => $cap,
					'publish_posts'          => $cap,
					'read_private_posts'     => $cap,
					'create_posts'           => 'do_not_allow',
					'delete_posts'           => $cap,
					'delete_private_posts'   => $cap,
					'delete_published_posts' => $cap,
					'delete_others_posts'    => $cap,
					'edit_private_posts'     => $cap,
					'edit_published_posts'   => $cap,
				),
			)
		);
	}

	/**
	 * Today's date in the site timezone.
	 *
	 * @return string
	 */
	public static function today() {
		return wp_date( 'Y-m-d' );
	}

	/**
	 * Signed render timestamp for the minimum fill time check.
	 *
	 * @param int $ts Timestamp.
	 * @return string
	 */
	private static function sign_ts( $ts ) {
		return $ts . '.' . substr( wp_hash( 'asset_form_ts|' . $ts, 'nonce' ), 0, 20 );
	}

	/**
	 * Hashed client IP (never stored in clear).
	 *
	 * @return string
	 */
	private static function ip_key() {
		$ip = isset( $_SERVER['REMOTE_ADDR'] ) ? sanitize_text_field( wp_unslash( $_SERVER['REMOTE_ADDR'] ) ) : '0.0.0.0';
		return 'asset_cd_rl_' . substr( hash_hmac( 'sha256', $ip, wp_salt( 'nonce' ) ), 0, 32 );
	}

	/**
	 * Rate limit (successful enquiries per hashed IP per hour).
	 *
	 * @return int
	 */
	public static function rate_limit() {
		$limit = defined( 'ASSET_CD_RATE_LIMIT' ) ? (int) ASSET_CD_RATE_LIMIT : 10;
		return (int) apply_filters( 'asset_cd_rate_limit', max( 1, $limit ) );
	}

	/**
	 * Valid 32-hex token or ''.
	 *
	 * @param mixed $raw Raw value.
	 * @return string
	 */
	private static function token( $raw ) {
		$raw = is_string( $raw ) ? strtolower( $raw ) : '';
		return preg_match( '/^[a-f0-9]{32}$/', $raw ) ? $raw : '';
	}

	/**
	 * Renders the "Demander un devis vol" form for a congress.
	 *
	 * @param int $congres_id Congress ID.
	 * @return string
	 */
	public static function render_form( $congres_id ) {
		// phpcs:disable WordPress.Security.NonceVerification.Recommended -- display only; tokens are random lookup keys.
		$ok_token  = isset( $_GET['asset_ok'] ) ? self::token( wp_unslash( $_GET['asset_ok'] ) ) : '';
		$err_token = isset( $_GET['asset_err'] ) ? self::token( wp_unslash( $_GET['asset_err'] ) ) : '';
		// phpcs:enable
		$errors = array();
		$old    = array();
		if ( $err_token ) {
			$state = get_transient( 'asset_cd_err_' . $err_token );
			if ( is_array( $state ) ) {
				$errors = isset( $state['errors'] ) && is_array( $state['errors'] ) ? $state['errors'] : array();
				$old    = isset( $state['old'] ) && is_array( $state['old'] ) ? $state['old'] : array();
			}
		}

		ob_start();
		echo '<section class="asset-quote" id="devis" aria-labelledby="asset-quote-title">';
		echo '<h2 id="asset-quote-title">' . esc_html__( 'Demander un devis vol', 'asset-congres-demo' ) . '</h2>';

		if ( $ok_token ) {
			$ref = get_transient( 'asset_cd_ok_' . $ok_token );
			if ( false !== $ref ) {
				echo '<div class="asset-notice asset-notice--ok" role="status" tabindex="-1">';
				echo '<p><strong>' . esc_html__( 'Merci, votre demande a bien été envoyée.', 'asset-congres-demo' ) . '</strong></p>';
				if ( $ref ) {
					/* translators: %s: enquiry reference. */
					echo '<p>' . wp_kses( sprintf( __( 'Votre référence : %s', 'asset-congres-demo' ), '<span class="asset-ref">' . esc_html( (string) $ref ) . '</span>' ), array( 'span' => array( 'class' => true ) ) ) . '</p>';
				}
				echo '<p>' . esc_html__( 'Un conseiller ASSET vous recontacte avec une proposition (démonstration : aucun e-mail n’est réellement envoyé).', 'asset-congres-demo' ) . '</p>';
				echo '</div></section>';
				return (string) ob_get_clean();
			}
		}

		$labels = array(
			'nom'          => __( 'Nom et prénom', 'asset-congres-demo' ),
			'email'        => __( 'E-mail', 'asset-congres-demo' ),
			'telephone'    => __( 'Téléphone', 'asset-congres-demo' ),
			'societe'      => __( 'Société (facultatif)', 'asset-congres-demo' ),
			'ville_depart' => __( 'Ville de départ', 'asset-congres-demo' ),
			'date_aller'   => __( 'Date aller', 'asset-congres-demo' ),
			'date_retour'  => __( 'Date retour', 'asset-congres-demo' ),
			'passagers'    => __( 'Nombre de passagers', 'asset-congres-demo' ),
			'message'      => __( 'Message (facultatif)', 'asset-congres-demo' ),
		);

		if ( $errors ) {
			echo '<div class="asset-notice asset-notice--error" role="alert"><p><strong>' . esc_html__( 'Merci de corriger les points suivants :', 'asset-congres-demo' ) . '</strong></p><ul>';
			foreach ( $errors as $field => $msg ) {
				$field = sanitize_key( (string) $field );
				$href  = isset( $labels[ $field ] ) || 'consentement' === $field ? '#asset-q-' . $field : '#devis';
				echo '<li><a href="' . esc_attr( $href ) . '">' . esc_html( (string) $msg ) . '</a></li>';
			}
			echo '</ul></div>';
		}

		$val = static function ( $k ) use ( $old ) {
			return isset( $old[ $k ] ) && is_scalar( $old[ $k ] ) ? (string) $old[ $k ] : '';
		};
		$attr_err = static function ( $k ) use ( $errors ) {
			return isset( $errors[ $k ] ) ? ' aria-invalid="true" aria-describedby="asset-q-' . esc_attr( $k ) . '-err"' : '';
		};
		$err_line = static function ( $k ) use ( $errors ) {
			return isset( $errors[ $k ] ) ? '<p class="asset-field-error" id="asset-q-' . esc_attr( $k ) . '-err">' . esc_html( (string) $errors[ $k ] ) . '</p>' : '';
		};
		$input = static function ( $k, $type, $extra = '' ) use ( $labels, $val, $attr_err, $err_line ) {
			$max = self::max_lengths()[ $k ];
			return sprintf(
				'<div class="asset-field"><label for="asset-q-%1$s">%2$s</label><input type="%3$s" id="asset-q-%1$s" name="%1$s" value="%4$s" %5$s%6$s />%7$s</div>',
				esc_attr( $k ),
				esc_html( $labels[ $k ] ),
				esc_attr( $type ),
				esc_attr( $val( $k ) ),
				$extra . ( 'number' === $type || 'date' === $type ? '' : ' maxlength="' . (int) $max . '"' ),
				$attr_err( $k ),
				$err_line( $k )
			);
		};

		$today = self::today();
		?>
		<p class="asset-quote__for">
			<?php
			/* translators: %s: congress title. */
			echo Asset_CD_Ui::nowrap_suffix( esc_html( sprintf( __( 'Congrès : %s', 'asset-congres-demo' ), get_the_title( $congres_id ) ) ) ); // phpcs:ignore WordPress.Security.EscapeOutput.OutputNotEscaped -- escaped, then a span added.
			?>
		</p>
		<form class="asset-form" method="post" action="<?php echo esc_url( admin_url( 'admin-post.php' ) ); ?>" novalidate>
			<input type="hidden" name="action" value="asset_demande_submit" />
			<input type="hidden" name="congres_id" value="<?php echo esc_attr( (string) $congres_id ); ?>" />
			<input type="hidden" name="form_ts" value="<?php echo esc_attr( self::sign_ts( time() ) ); ?>" />
			<input type="hidden" name="form_token" value="<?php echo esc_attr( bin2hex( random_bytes( 16 ) ) ); ?>" />
			<?php wp_nonce_field( 'asset_demande_submit', 'asset_nonce' ); ?>
			<div class="asset-hp" aria-hidden="true">
				<label for="asset-q-site">Site web</label>
				<input type="text" id="asset-q-site" name="site_web" value="" tabindex="-1" autocomplete="off" />
			</div>
			<fieldset>
				<legend><?php esc_html_e( 'Vos coordonnées', 'asset-congres-demo' ); ?></legend>
				<?php
				// phpcs:disable WordPress.Security.EscapeOutput.OutputNotEscaped -- $input escapes every part.
				echo $input( 'nom', 'text', 'autocomplete="name" required' );
				echo $input( 'email', 'email', 'autocomplete="email" required' );
				echo $input( 'telephone', 'tel', 'autocomplete="tel" required' );
				echo $input( 'societe', 'text', 'autocomplete="organization"' );
				?>
			</fieldset>
			<fieldset>
				<legend><?php esc_html_e( 'Votre voyage', 'asset-congres-demo' ); ?></legend>
				<?php
				echo $input( 'ville_depart', 'text', 'required' );
				echo $input( 'date_aller', 'date', 'min="' . esc_attr( $today ) . '" required' );
				echo $input( 'date_retour', 'date', 'min="' . esc_attr( $today ) . '" required' );
				echo $input( 'passagers', 'number', 'min="' . self::PAX_MIN . '" max="' . self::PAX_MAX . '" step="1" inputmode="numeric" required' );
				// phpcs:enable
				?>
				<div class="asset-field">
					<label for="asset-q-message"><?php echo esc_html( $labels['message'] ); ?></label>
					<textarea id="asset-q-message" name="message" rows="4" maxlength="2000"<?php echo $attr_err( 'message' ); // phpcs:ignore WordPress.Security.EscapeOutput.OutputNotEscaped ?>><?php echo esc_textarea( $val( 'message' ) ); ?></textarea>
					<?php echo $err_line( 'message' ); // phpcs:ignore WordPress.Security.EscapeOutput.OutputNotEscaped ?>
				</div>
			</fieldset>
			<div class="asset-field asset-field--check">
				<input type="checkbox" id="asset-q-consentement" name="consentement" value="1" required<?php checked( $val( 'consentement' ), '1' ); ?><?php echo $attr_err( 'consentement' ); // phpcs:ignore WordPress.Security.EscapeOutput.OutputNotEscaped ?> />
				<label for="asset-q-consentement"><?php esc_html_e( 'J’accepte qu’ASSET Voyages utilise ces informations pour traiter ma demande de devis (RGPD). Elles ne sont ni revendues ni utilisées à d’autres fins.', 'asset-congres-demo' ); ?></label>
				<?php echo $err_line( 'consentement' ); // phpcs:ignore WordPress.Security.EscapeOutput.OutputNotEscaped ?>
			</div>
			<button type="submit" class="asset-btn"><?php esc_html_e( 'Envoyer ma demande', 'asset-congres-demo' ); ?></button>
		</form>
		<?php
		echo '</section>';
		return (string) ob_get_clean();
	}

	/**
	 * Validates raw POST data.
	 *
	 * @param array $raw Unslashed POST data.
	 * @return array{0:array<string,string>,1:array<string,mixed>} [errors, clean]
	 */
	public static function validate( $raw ) {
		$errors = array();
		$clean  = array();
		$get    = static function ( $k ) use ( $raw ) {
			return isset( $raw[ $k ] ) && is_scalar( $raw[ $k ] ) ? (string) $raw[ $k ] : '';
		};

		foreach ( self::max_lengths() as $k => $max ) {
			if ( mb_strlen( $get( $k ) ) > $max ) {
				/* translators: %d: max characters. */
				$errors[ $k ] = sprintf( __( 'Ce champ est trop long (%d caractères maximum).', 'asset-congres-demo' ), $max );
			}
		}

		$clean['nom'] = sanitize_text_field( mb_substr( $get( 'nom' ), 0, 100 ) );
		if ( '' === $clean['nom'] && ! isset( $errors['nom'] ) ) {
			$errors['nom'] = __( 'Indiquez votre nom.', 'asset-congres-demo' );
		}

		$clean['email'] = sanitize_email( mb_substr( $get( 'email' ), 0, 190 ) );
		if ( ! isset( $errors['email'] ) && ! is_email( $clean['email'] ) ) {
			$errors['email'] = __( 'Indiquez une adresse e-mail valide.', 'asset-congres-demo' );
		}

		$tel                = trim( (string) preg_replace( '/[^0-9+().\s-]/', '', mb_substr( $get( 'telephone' ), 0, 30 ) ) );
		$clean['telephone'] = $tel;
		if ( ! isset( $errors['telephone'] ) && strlen( (string) preg_replace( '/\D/', '', $tel ) ) < 6 ) {
			$errors['telephone'] = __( 'Indiquez un numéro de téléphone valide.', 'asset-congres-demo' );
		}

		$clean['societe']      = sanitize_text_field( mb_substr( $get( 'societe' ), 0, 150 ) );
		$clean['ville_depart'] = sanitize_text_field( mb_substr( $get( 'ville_depart' ), 0, 100 ) );
		if ( '' === $clean['ville_depart'] && ! isset( $errors['ville_depart'] ) ) {
			$errors['ville_depart'] = __( 'Indiquez votre ville de départ.', 'asset-congres-demo' );
		}

		$today = self::today();
		foreach ( array( 'date_aller', 'date_retour' ) as $k ) {
			$v           = $get( $k );
			$d           = DateTimeImmutable::createFromFormat( '!Y-m-d', $v );
			$clean[ $k ] = ( $d && $d->format( 'Y-m-d' ) === $v ) ? $v : '';
			if ( '' === $clean[ $k ] ) {
				$errors[ $k ] = 'date_aller' === $k ? __( 'Indiquez une date aller valide.', 'asset-congres-demo' ) : __( 'Indiquez une date retour valide.', 'asset-congres-demo' );
			} elseif ( $clean[ $k ] < $today ) {
				$errors[ $k ] = __( 'La date ne peut pas être dans le passé.', 'asset-congres-demo' );
			}
		}
		if ( $clean['date_aller'] && $clean['date_retour'] && ! isset( $errors['date_retour'] ) && $clean['date_retour'] < $clean['date_aller'] ) {
			$errors['date_retour'] = __( 'La date retour doit être postérieure ou égale à la date aller.', 'asset-congres-demo' );
		}

		$pax = filter_var(
			trim( $get( 'passagers' ) ),
			FILTER_VALIDATE_INT,
			array(
				'options' => array(
					'min_range' => self::PAX_MIN,
					'max_range' => self::PAX_MAX,
				),
			)
		);
		if ( false === $pax ) {
			/* translators: 1: minimum, 2: maximum. */
			$errors['passagers'] = sprintf( __( 'Le nombre de passagers doit être un nombre entier entre %1$d et %2$d.', 'asset-congres-demo' ), self::PAX_MIN, self::PAX_MAX );
			$clean['passagers']  = '';
		} else {
			$clean['passagers'] = (int) $pax;
		}

		$clean['message'] = sanitize_textarea_field( mb_substr( $get( 'message' ), 0, 2000 ) );
		$clean['consentement'] = empty( $raw['consentement'] ) ? '' : '1';

		if ( empty( $raw['consentement'] ) ) {
			$errors['consentement'] = __( 'Votre accord est nécessaire pour traiter la demande.', 'asset-congres-demo' );
		}

		return array( $errors, $clean );
	}

	/**
	 * Redirect helper (303 See Other, PRG).
	 *
	 * @param string $url URL.
	 */
	private static function go( $url ) {
		wp_safe_redirect( $url, 303 );
		exit;
	}

	/**
	 * Stores an error state and redirects back to the form.
	 *
	 * @param string $back   Congress URL.
	 * @param array  $errors Errors.
	 * @param array  $old    Old input.
	 */
	private static function fail( $back, $errors, $old ) {
		$token = bin2hex( random_bytes( 16 ) );
		set_transient(
			'asset_cd_err_' . $token,
			array(
				'errors' => $errors,
				'old'    => $old,
			),
			10 * MINUTE_IN_SECONDS
		);
		self::go( add_query_arg( 'asset_err', $token, $back ) . '#devis' );
	}

	/**
	 * Handles the public submission (admin-post.php).
	 */
	public static function handle_submit() {
		// phpcs:disable WordPress.Security.NonceVerification.Missing -- nonce verified below, after resolving the redirect target.
		$congres_id = isset( $_POST['congres_id'] ) ? absint( $_POST['congres_id'] ) : 0;
		$congres    = $congres_id ? get_post( $congres_id ) : null;
		if ( ! $congres || Asset_CD_Congres::POST_TYPE !== $congres->post_type || 'publish' !== $congres->post_status ) {
			wp_die( esc_html__( 'Congrès introuvable.', 'asset-congres-demo' ), esc_html__( 'Erreur', 'asset-congres-demo' ), array( 'response' => 400 ) );
		}
		$back = (string) get_permalink( $congres );
		$raw  = wp_unslash( $_POST ); // phpcs:ignore WordPress.Security.ValidatedSanitizedInput.InputNotSanitized -- validated field by field in validate().
		// phpcs:enable

		$nonce = isset( $raw['asset_nonce'] ) && is_string( $raw['asset_nonce'] ) ? sanitize_key( $raw['asset_nonce'] ) : '';
		if ( ! $nonce || ! wp_verify_nonce( $nonce, 'asset_demande_submit' ) ) {
			self::fail( $back, array( 'form' => __( 'Le formulaire a expiré ou est invalide. Merci de le renvoyer.', 'asset-congres-demo' ) ), array() );
		}

		$form_token = self::token( $raw['form_token'] ?? '' );
		if ( ! $form_token ) {
			self::fail( $back, array( 'form' => __( 'Le formulaire est invalide. Merci de le renvoyer.', 'asset-congres-demo' ) ), array() );
		}
		// Replay of an already accepted form: show the same confirmation, create nothing.
		$done = get_transient( 'asset_cd_tok_' . $form_token );
		if ( is_string( $done ) && self::token( $done ) ) {
			self::go( add_query_arg( 'asset_ok', $done, $back ) . '#devis' );
		}

		// Honeypot: silently accept, store nothing.
		if ( ! empty( $raw['site_web'] ) ) {
			$ok = bin2hex( random_bytes( 16 ) );
			set_transient( 'asset_cd_ok_' . $ok, '', DAY_IN_SECONDS );
			self::go( add_query_arg( 'asset_ok', $ok, $back ) . '#devis' );
		}

		list( $errors, $clean ) = self::validate( $raw );
		$old                    = $clean;

		// Minimum fill time (signed render timestamp).
		$ts_raw = isset( $raw['form_ts'] ) && is_string( $raw['form_ts'] ) ? $raw['form_ts'] : '';
		$parts  = explode( '.', $ts_raw, 2 );
		$ts     = (int) $parts[0];
		if ( 2 !== count( $parts ) || ! hash_equals( self::sign_ts( $ts ), $ts_raw ) || ( time() - $ts ) > 2 * DAY_IN_SECONDS ) {
			$errors['form'] = __( 'Le formulaire est invalide. Merci de le renvoyer.', 'asset-congres-demo' );
		} elseif ( ( time() - $ts ) < self::MIN_FILL_SECS ) {
			$errors['form'] = __( 'Formulaire envoyé trop rapidement. Merci de vérifier vos informations et de le renvoyer.', 'asset-congres-demo' );
		}

		$rl_key = self::ip_key();
		$count  = (int) get_transient( $rl_key );
		if ( $count >= self::rate_limit() ) {
			$errors['form'] = __( 'Trop de demandes envoyées depuis votre connexion. Merci de réessayer dans une heure ou de nous appeler.', 'asset-congres-demo' );
		}

		if ( $errors ) {
			self::fail( $back, $errors, $old );
		}

		$ref = self::next_reference();
		$id  = wp_insert_post(
			array(
				'post_type'   => self::POST_TYPE,
				'post_status' => 'private',
				'post_title'  => $ref,
				'post_author' => 0,
				'meta_input'  => array(
					'_asset_ref'          => $ref,
					'_asset_congres_id'   => $congres_id,
					'_asset_nom'          => $clean['nom'],
					'_asset_email'        => $clean['email'],
					'_asset_telephone'    => $clean['telephone'],
					'_asset_societe'      => $clean['societe'],
					'_asset_ville_depart' => $clean['ville_depart'],
					'_asset_date_aller'   => $clean['date_aller'],
					'_asset_date_retour'  => $clean['date_retour'],
					'_asset_passagers'    => (int) $clean['passagers'],
					'_asset_message'      => $clean['message'],
					'_asset_consent_at'   => current_time( 'mysql', true ),
					'_asset_statut'       => 'nouvelle',
					'_asset_owner'        => 0,
				),
			),
			true
		);
		if ( is_wp_error( $id ) || ! $id ) {
			self::fail( $back, array( 'form' => __( 'Une erreur technique est survenue. Merci de réessayer.', 'asset-congres-demo' ) ), $old );
		}
		self::add_history( (int) $id, 'created', '', 'nouvelle', '', 0 );

		set_transient( $rl_key, $count + 1, HOUR_IN_SECONDS );
		$ok = bin2hex( random_bytes( 16 ) );
		set_transient( 'asset_cd_ok_' . $ok, $ref, DAY_IN_SECONDS );
		set_transient( 'asset_cd_tok_' . $form_token, $ok, DAY_IN_SECONDS );

		$body = sprintf(
			"Nouvelle demande de devis vol %s\n\nCongrès : %s\nContact : %s <%s>, %s\nSociété : %s\nDépart : %s\nDates : %s → %s\nPassagers : %d\n\nMessage :\n%s\n\nVoir la demande : %s",
			$ref,
			get_the_title( $congres ),
			$clean['nom'],
			$clean['email'],
			$clean['telephone'],
			$clean['societe'] ? $clean['societe'] : '—',
			$clean['ville_depart'],
			Asset_CD_Ui::date( $clean['date_aller'] ),
			Asset_CD_Ui::date( $clean['date_retour'] ),
			(int) $clean['passagers'],
			$clean['message'] ? $clean['message'] : '—',
			admin_url( 'admin.php?page=asset-demandes&action=view&id=' . (int) $id )
		);
		/* translators: 1: reference, 2: congress. */
		Asset_CD_Notifications::notify_team( sprintf( __( '[ASSET démo] Nouvelle demande %1$s : %2$s', 'asset-congres-demo' ), $ref, get_the_title( $congres ) ), $body, $ref );

		self::go( add_query_arg( 'asset_ok', $ok, $back ) . '#devis' );
	}

	/**
	 * Next reference DV-YYYY-NNNN (unique).
	 *
	 * @return string
	 */
	public static function next_reference() {
		$year = wp_date( 'Y' );
		$opt  = 'asset_cd_seq_' . $year;
		$n    = (int) get_option( $opt, 0 );
		do {
			++$n;
			$ref = sprintf( 'DV-%s-%04d', $year, $n );
		} while ( self::find_by_reference( $ref ) );
		update_option( $opt, $n, false );
		return $ref;
	}

	/**
	 * Finds an enquiry ID by reference.
	 *
	 * @param string $ref Reference.
	 * @return int
	 */
	public static function find_by_reference( $ref ) {
		$ids = get_posts(
			array(
				'post_type'      => self::POST_TYPE,
				'post_status'    => 'any',
				'posts_per_page' => 1,
				'fields'         => 'ids',
				'no_found_rows'  => true,
				'meta_key'       => '_asset_ref', // phpcs:ignore WordPress.DB.SlowDBQuery.slow_db_query_meta_key
				'meta_value'     => $ref, // phpcs:ignore WordPress.DB.SlowDBQuery.slow_db_query_meta_value
			)
		);
		return $ids ? (int) $ids[0] : 0;
	}

	/**
	 * Appends a history entry (append-only: entries are never updated or deleted).
	 *
	 * @param int    $id      Enquiry ID.
	 * @param string $type    created|status|owner|note.
	 * @param string $from    Previous value.
	 * @param string $to      New value.
	 * @param string $note    Note text.
	 * @param int    $user_id Acting user (0 = public form).
	 * @param string $when    UTC datetime (optional).
	 */
	public static function add_history( $id, $type, $from, $to, $note = '', $user_id = null, $when = '' ) {
		$user_id = null === $user_id ? get_current_user_id() : (int) $user_id;
		add_post_meta(
			$id,
			'_asset_history',
			array(
				'at'   => $when ? $when : current_time( 'mysql', true ),
				'user' => $user_id,
				'type' => sanitize_key( $type ),
				'from' => (string) $from,
				'to'   => (string) $to,
				'note' => (string) $note,
			)
		);
	}

	/**
	 * History entries in chronological order.
	 *
	 * @param int $id Enquiry ID.
	 * @return array<int,array>
	 */
	public static function history( $id ) {
		$rows = get_post_meta( $id, '_asset_history', false );
		return is_array( $rows ) ? array_values( array_filter( $rows, 'is_array' ) ) : array();
	}
}
