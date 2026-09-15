# Android release signing

How the Android app is signed, what each certificate is for, and how to rebuild
the setup on a new machine.

Established by todo 387 on 2026-09-14. Until then the release build type carried
Flutter's template default and signed with `~/.android/debug.keystore`.

## The three certificates

Conflating these is the usual way Android signing goes wrong. They are three
different keys, and Google Sign-In binds to a *specific one* per build.

| Certificate | Where it lives | Binds what |
|---|---|---|
| **debug** | `~/.android/debug.keystore`, created by the Android SDK | `flutter run`, `flutter build apk --debug`. Shared by every Flutter install on the machine |
| **release** | `~/keys/houseplant-md-release.jks`, created by us | `flutter build apk/appbundle --release` |
| **Play App Signing** | Google's servers; you never hold it | What users actually install, once distributed through Play |

Both the debug and release SHA-1s are registered on the Firebase Android app, so
Google Sign-In works in both configurations.

**The Play certificate is not registered, because nothing is on Play yet.** At
first upload Google re-signs the artifact with a key it holds, and that key's
SHA-1 must be registered too or Google Sign-In breaks for every real user while
continuing to work perfectly on your own builds — the worst shape of bug. Find
it under **Play Console → Release → Setup → App signing**. Tracked as an open
acceptance criterion on todo 387.

## Local setup

`android/key.properties` is gitignored and holds the keystore password. The
keystore itself lives **outside the repository**: this repo is public, and a
merely-gitignored key is one `git add -f` away from being permanent in that
history.

```properties
storePassword=<generated>
keyPassword=<generated>
keyAlias=houseplant-md
storeFile=/Users/<you>/keys/houseplant-md-release.jks
```

`android/app/build.gradle.kts` loads this file **only if it exists**. Reading it
unconditionally throws at Gradle *configuration* time, which fails every task in
the build — including the debug APK that CI builds, on a runner that will never
have a keystore.

When the file is absent the release build type gets no signing config at all,
and a `taskGraph.whenReady` check fails any release task outright. Falling back
to the debug key is what the Flutter template did, and it is the failure this
setup exists to prevent: an unsigned artifact fails loudly at install time, a
debug-signed "release" succeeds and lies.

## Recreating the keystore

Only if the current one is lost — a **new keystore is a new certificate**, so
every SHA-1 below has to be re-registered, and any already-installed app can no
longer be updated in place.

```bash
mkdir -p ~/keys && chmod 700 ~/keys
keytool -genkeypair \
  -keystore ~/keys/houseplant-md-release.jks \
  -storetype PKCS12 -keyalg RSA -keysize 4096 -validity 10000 \
  -alias houseplant-md \
  -dname "CN=Houseplant MD, OU=Mobile, O=Houseplant MD, C=US"
chmod 600 ~/keys/houseplant-md-release.jks
```

Then write `android/key.properties` as above and `chmod 600` it.

## Registering a certificate with Firebase

Google Sign-In on Android identifies an app by **package name + signing
certificate SHA-1**. Without a registered SHA-1 there is no `client_type: 1`
OAuth client, and sign-in cannot work.

```bash
# Read the SHA-1 of a keystore
keytool -list -v -keystore <keystore> -alias <alias> | grep 'SHA1:'

# Register it (creates the Android OAuth client as a side effect)
firebase apps:android:sha:create 1:190351417275:android:53aa5e82b6e221ad69ae9e <SHA-1>

# Confirm the OAuth client appeared, then update the committed config
firebase apps:android:sha:list 1:190351417275:android:53aa5e82b6e221ad69ae9e
firebase apps:sdkconfig ANDROID 1:190351417275:android:53aa5e82b6e221ad69ae9e \
  > android/app/google-services.json
```

The `sha:create` call provisions the `client_type: 1` entry automatically; the
Firebase console is not needed. Verify it did rather than assuming — the entry
is what `test/core/android_release_signing_test.dart` asserts on.

## Why `com.google.gms.google-services` is applied

Flutter reads its Firebase config from `--dart-define` via
`firebase_options.dart`, so `google-services.json` was never needed to *start*
Firebase — which is why nobody noticed the Gradle plugin had never been applied.

`google_sign_in` is the exception. On Android it resolves the server client id
by looking up the `default_web_client_id` **string resource** by name
(`GoogleSignInPlugin.java`), and only this plugin generates that resource, from
the json's `client_type: 3` (web) entry. Without it, `authenticate()` throws
`serverClientId must be provided on Android` before any certificate is
considered.

Confirm it reached the artifact:

```bash
aapt2 dump resources build/app/outputs/flutter-apk/app-release.apk \
  | grep default_web_client_id
```

## Verifying a build

Check the artifact, not the build log. A green build says nothing about which
key signed it.

```bash
apksigner verify --print-certs build/app/outputs/flutter-apk/app-release.apk
```

Assert the SHA-1 **equals** the release certificate and **differs** from the
debug one. The negative control is the point: the failure being guarded against
is a release silently signed with the debug key, and only the second assertion
can see it.

## Verifying sign-in end to end

A misconfiguration here is invisible from the UI. The `google_sign_in` README
notes that Credential Manager reports configuration errors as `canceled`, and
`AuthService.signInWithGoogle` deliberately swallows `canceled` so a user who
changes their mind doesn't get a red banner. **A broken build looks exactly like
the user backing out.** Confirm server-side.

```bash
# install the release-signed build
adb install -r build/app/outputs/flutter-apk/app-release.apk
```

Sign in, then look for `[FIREBASE AUTH] ... authenticated` in the Railway logs
for `plant_id_community`. Absence of that line means it did not work, whatever
the app appeared to do.

A `google_apis_playstore` emulator image exercises the same certificate and
OAuth-client path as hardware, because the check is against the installed APK's
signature. It is valid evidence that the configuration is correct; it is not a
substitute for a physical-device run.
