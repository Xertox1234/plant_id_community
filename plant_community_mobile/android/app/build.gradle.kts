import java.util.Properties

plugins {
    id("com.android.application")
    id("kotlin-android")
    // The Flutter Gradle Plugin must be applied after the Android and Kotlin Gradle plugins.
    id("dev.flutter.flutter-gradle-plugin")
    // Processes app/google-services.json into Android resources.
    //
    // Flutter reads its own Firebase config from --dart-define via
    // firebase_options.dart, so this plugin was never needed to *start*
    // Firebase — which is exactly why its absence went unnoticed for the life
    // of the project. google_sign_in is the exception: on Android it resolves
    // the server client id by looking up the `default_web_client_id` string
    // resource by name (GoogleSignInPlugin.java), and only this plugin
    // generates that resource from the json's client_type: 3 entry. Without
    // it, authenticate() throws "serverClientId must be provided on Android"
    // before any signing certificate is ever considered.
    id("com.google.gms.google-services")
}

// Release signing material, deliberately kept out of the repository.
//
// android/key.properties is gitignored and points at a keystore stored outside
// the tree entirely: this repo is public, and a merely-gitignored key is one
// `git add -f` away from being permanent in that history.
//
// Loaded conditionally because CI has no keystore. Reading these properties
// unconditionally throws at CONFIGURATION time, which fails every task in the
// build — including the debug APK that CI actually builds.
val keystorePropertiesFile = rootProject.file("key.properties")
val hasReleaseKeystore = keystorePropertiesFile.exists()
val keystoreProperties = Properties().apply {
    if (hasReleaseKeystore) {
        keystorePropertiesFile.inputStream().use { load(it) }
    }
}

android {
    namespace = "com.plantcommunity.plant_community_mobile"
    compileSdk = flutter.compileSdkVersion
    ndkVersion = flutter.ndkVersion

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_11
        targetCompatibility = JavaVersion.VERSION_11
        isCoreLibraryDesugaringEnabled = true
    }

    kotlinOptions {
        jvmTarget = JavaVersion.VERSION_11.toString()
    }

    defaultConfig {
        // TODO: Specify your own unique Application ID (https://developer.android.com/studio/build/application-id.html).
        applicationId = "com.plantcommunity.plant_community_mobile"
        // You can update the following values to match your application needs.
        // For more information, see: https://flutter.dev/to/review-gradle-config.
        // NOTE: the flutter tool re-applies this migration on every build (a
        // pinned literal gets rewritten back), so the floor follows the
        // toolchain: Flutter 3.41.9 ⇒ minSdk 24 (was a pinned 23 before todo
        // 253 slice 6). Android 6 support ended as a toolchain side effect —
        // revisit deliberately if API-23 devices still matter.
        minSdk = flutter.minSdkVersion
        targetSdk = flutter.targetSdkVersion
        versionCode = flutter.versionCode
        versionName = flutter.versionName
    }

    signingConfigs {
        if (hasReleaseKeystore) {
            create("release") {
                storeFile = file(keystoreProperties.getProperty("storeFile"))
                storePassword = keystoreProperties.getProperty("storePassword")
                keyAlias = keystoreProperties.getProperty("keyAlias")
                keyPassword = keystoreProperties.getProperty("keyPassword")
            }
        }
    }

    buildTypes {
        release {
            // Was `signingConfigs.getByName("debug")`, Flutter's template
            // default. That signs releases with ~/.android/debug.keystore — a
            // key shared by every Flutter install on the machine, registered
            // against nothing, and impossible to distribute with.
            //
            // With no keystore this stays null rather than falling back to
            // debug. An unsigned artifact fails loudly at install or upload; a
            // debug-signed "release" succeeds and lies, which is how the
            // template default survived this long.
            signingConfig =
                if (hasReleaseKeystore) signingConfigs.getByName("release") else null
        }
    }
}

// An unsigned release is still a silent failure if nobody looks at the artifact,
// so refuse to produce one at all.
//
// The check runs on the resolved task graph rather than at configuration time
// because configuration cannot know which build type was asked for — and
// failing there would take the debug build down with it.
if (!hasReleaseKeystore) {
    gradle.taskGraph.whenReady {
        val releaseTask = gradle.taskGraph.allTasks.firstOrNull { task ->
            task.name.contains("Release") &&
                listOf("assemble", "bundle", "package").any { task.name.startsWith(it) }
        }
        if (releaseTask != null) {
            throw GradleException(
                "Cannot run '${releaseTask.name}': android/key.properties is missing, so no " +
                    "release signing config exists. Create the release keystore first — see " +
                    "docs/android-release-signing.md. This build fails deliberately rather " +
                    "than emitting an unsigned or debug-signed release.",
            )
        }
    }
}

flutter {
    source = "../.."
}

dependencies {
    coreLibraryDesugaring("com.android.tools:desugar_jdk_libs:2.1.4")
}
