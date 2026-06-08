# Phase 4d — Supabase Auth (email/password + OAuth + local-first cache)

## Goal

Add user authentication to the app via Supabase's built-in GoTrue: email + password as the default, OAuth (Google, Apple, optional GitHub) as drop-in providers, and AsyncStorage as the immediate-read caching layer so the app feels instant while the database is the source of truth in the background. Wraps the existing Phase 1 onboarding gate with a sign-up / sign-in screen and protects every Phase 2/3 screen behind a `useUser()` hook.

Encodes Nick Saraev's transcript: `Claude Code Mobile App Dev 1.pdf`, chapter 18.

## Inputs

- Phase 4c complete (Supabase project provisioned, `src/lib/supabase.ts` exports a configured client, RLS policies in place on every user-owned table)
- App slug + spec at `C:\Users\deban\dev\mobile-apps\<slug>\APP_SPEC.md` (Section 1 onboarding flow informs the post-signup redirect)
- Phase 1 onboarding screens shipped (the "only gate" referenced below) — Phase 4d replaces that gate
- For Apple OAuth: `APPLE_ENROLLMENT_STATUS=active` per `mobile_apps/preflight` — same gate that protects Phase 4-5
- For Google OAuth: Google Cloud project + OAuth client IDs (one for iOS, one for Android, one for Web — generated in `console.cloud.google.com` → APIs & Services → Credentials)

## Tools/Scripts

- `@supabase/supabase-js` — already installed in Phase 4c
- `@react-native-async-storage/async-storage` — already installed in Phase 4c
- Supabase dashboard → Authentication → Providers — toggles per provider
- New files in app repo:
  - `src/lib/auth.tsx` — `<AuthProvider>` + `useUser()` hook
  - `src/screens/AuthScreen.tsx` — sign-up + sign-in flow
  - `src/screens/ProtectedRoute.tsx` (or equivalent navigation guard)

## Outputs

- Auth gate inserted at the app's root navigator: unauthenticated → `AuthScreen`; authenticated + onboarding incomplete → onboarding; authenticated + onboarded → main app
- `useUser()` hook returning `{ user, session, loading, signOut }` from anywhere in the app
- AsyncStorage caches the last-known user + onboarding state so the app boots straight to the main screen without a network round-trip when the session is valid
- Supabase dashboard: email confirmation **disabled** for dev (`Authentication → Settings → Confirm email = off`); re-enable for prod release
- At least email/password + one OAuth provider configured + tested end-to-end on a real device
- Registry updated with `auth_providers: ["email", "google", ...]` and `last_auth_test_at`

## Steps

1. **Configure providers in the dashboard.** Supabase → Authentication → Providers.
   - **Email**: on by default. For dev, set `Confirm email = off` (Nick chapter 18 — saves the email round-trip during testing). Re-enable for prod.
   - **Google**: paste the iOS + Android + Web OAuth client IDs from Google Cloud. Add `<project-ref>.supabase.co/auth/v1/callback` to the Google client's authorized redirect URIs.
   - **Apple**: required for App Store submission per Apple's Sign in with Apple policy on any app offering third-party login. Requires Apple Developer enrollment **active** — gate the same way Phase 4-5 do.
   - **GitHub** (optional): only if the app's audience is technical.
2. **Build the auth provider.** `src/lib/auth.tsx`:
   ```tsx
   import { createContext, useContext, useEffect, useState } from 'react'
   import { supabase } from './supabase'
   import type { Session, User } from '@supabase/supabase-js'

   const AuthCtx = createContext<{user: User|null, session: Session|null, loading: boolean, signOut: () => Promise<void>}>(null!)

   export function AuthProvider({ children }) {
     const [session, setSession] = useState<Session|null>(null)
     const [loading, setLoading] = useState(true)
     useEffect(() => {
       supabase.auth.getSession().then(({ data }) => { setSession(data.session); setLoading(false) })
       const { data: sub } = supabase.auth.onAuthStateChange((_e, s) => setSession(s))
       return () => sub.subscription.unsubscribe()
     }, [])
     const signOut = async () => { await supabase.auth.signOut(); await AsyncStorage.clear() }
     return <AuthCtx.Provider value={{ user: session?.user ?? null, session, loading, signOut }}>{children}</AuthCtx.Provider>
   }
   export const useUser = () => useContext(AuthCtx)
   ```
   The Supabase JS SDK handles refresh-token persistence via AsyncStorage automatically because Phase 4c configured `auth.storage = AsyncStorage` + `autoRefreshToken: true`.
3. **Build the auth screen.** `src/screens/AuthScreen.tsx` — single screen with toggle between sign-up and sign-in. Email + password inputs, "Continue with Google" button, "Continue with Apple" button (iOS only — gate `Platform.OS === 'ios'`). Email/password is the default per Nick chapter 18 ("simplest to start"). Use `supabase.auth.signUp({ email, password })` and `supabase.auth.signInWithPassword({ email, password })`.
4. **Replace the Phase 1 onboarding-only gate.** The app's root navigator was previously: `if (!onboardingComplete) → Onboarding else → Main`. Replace with:
   ```
   if (loading) → SplashScreen
   else if (!user) → AuthScreen
   else if (!onboardingComplete) → Onboarding
   else → Main
   ```
   New users sign up → onboarding → main. Returning users sign in → main (skip onboarding).
5. **Local-first cache.** Don't await the network round-trip on every screen mount. Read user prefs (habits, completions, etc.) from AsyncStorage first, render immediately, then `supabase.from(...).select()` in the background and reconcile. Nick chapter 18: *"we don't want load time initially"*. Pattern: `useEffect(() => { setData(getCached()); fetchFresh().then(setData) }, [])`.
6. **Protect screens via the hook.** Any screen outside the auth screen calls `const { user } = useUser()` at the top; if `user === null`, the root navigator handles the redirect (you don't need per-screen redirect logic — the navigator is the single gate).
7. **Sign-out cascade.** When the user signs out: `supabase.auth.signOut()` AND `AsyncStorage.clear()` (or `AsyncStorage.multiRemove([...known keys])`). If you leave the cache populated, the next user signing in on the same device sees the previous user's data flicker on screen. The `signOut` function in `auth.tsx` handles both.
8. **Test the full flow on a real device.**
   - Sign up with a fresh email → onboarding renders → main app renders → kill the app → reopen → straight to main app (session persisted).
   - Sign out → AuthScreen renders → cached data gone.
   - Sign in with Google (if configured) → main app renders.
   - Verify in Supabase dashboard → Authentication → Users that the row appears.
9. **Update registry.** Set `auth_providers` (array) + `last_auth_test_at` (ISO) on the slug's entry. If the user is gated by Apple enrollment, set `apple_oauth_pending: true` until enrollment is active.
10. **Commit.** App repo: `src/lib/auth.tsx`, `src/screens/AuthScreen.tsx`, root navigator change.

## Edge Cases

- **Token expiry mid-session.** `autoRefreshToken: true` handles this — the SDK refreshes the JWT on every API call when expiry < 60s. If refresh fails (network down, refresh token revoked server-side), the `onAuthStateChange` callback fires with `session = null` and the navigator drops the user back to `AuthScreen`. Test by manually revoking the user in the dashboard while the app is running.
- **Sign-out leaves user data in AsyncStorage.** If `signOut` only calls `supabase.auth.signOut()` and skips `AsyncStorage.clear()`, the next sign-in on the same device shows previous-user data for a frame. Always wipe the cache on sign-out (or maintain a per-user namespace in AsyncStorage keys).
- **Apple OAuth without active Apple Developer enrollment.** The OAuth flow appears to work in dev but TestFlight + App Store builds fail review. Gate the Apple button on `APPLE_ENROLLMENT_STATUS=active` from preflight; show only Google + Email until enrollment lands.
- **Email confirmation flow.** Supabase default sends a confirmation email on sign-up; until the user clicks the link, `session` returns null on sign-up's response and the app sits at AuthScreen with no feedback. Either disable confirmation in dev (per Step 1) or handle the unconfirmed state: show "Check your inbox" UI + a resend button, and don't navigate away from AuthScreen until session arrives.
- **Server-side trust on `user_id`.** Every Edge Function (Phase 5b) MUST extract `user_id` from the verified JWT (`supabase.auth.getUser(jwt)`), never accept a `user_id` passed in the request body. The security audit catches this — it's the CRITICAL cost-amplification vector when paid AI is downstream.
- **Google OAuth redirect URI mismatch.** Common during setup — the Google client expects `<project-ref>.supabase.co/auth/v1/callback` exactly. If the URI is off by a path segment, Google returns `redirect_uri_mismatch` and the user sees a blank web view. Verify the URI in both Google Cloud and Supabase Auth → URL Configuration.
- **AsyncStorage stale after sign-out + sign-in as different user.** Even with `AsyncStorage.clear()` on sign-out, race conditions during navigation can re-write the previous user's data back into storage. Defensive pattern: namespace every cache key with the current `user.id` and on read check it matches the active session's user.
- **Anonymous sign-in temptation.** Supabase supports anonymous sessions (`signInAnonymously`). For habit-tracker-style apps this seems convenient ("let users try before signing up") but the data dies on first uninstall and the conversion path to a real account adds an entire screen. For most apps in this workspace: ship email+password as the only gate, defer anonymous as a P1 feature.

## Notes

- Anneal mode for this phase: **adversarial**. Auth holes are the highest-severity bug class in vibe-coded apps — RLS misconfig, JWT trust, token expiry, OAuth redirect, sign-out cascades. Adversarial mode (`py -m anneal.cli adversarial <base-ref-sha> --repo C:\Users\deban\dev\mobile-apps\<slug>`) covers more failure modes than a single classic pass.
- This phase replaces the Phase 1 onboarding gate. If the Phase 1 navigator was hardcoded to "always show onboarding on first launch", that branch becomes dead code — delete it during the navigator rewrite or it ships as a P2 footgun.
- Companion: `directives/mobile_apps/phase4c_supabase_setup.md` (prerequisite), `directives/mobile_apps/phase5b_supabase_ai.md` (the secure AI path that depends on this auth working), `directives/mobile_apps/security_audit.md` (re-run after this phase).
- Email confirmation must be re-enabled before App Store submission. Add to `directives/mobile_apps/phase6_ship.md` checklist if not already there.
