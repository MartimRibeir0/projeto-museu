plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.compose)
}

val hasUnity = findProject(":unityLibrary") != null  // ver settings.gradle.kts

android {
    namespace = "pt.ipleiria.museuvirtual"
    compileSdk {
        version = release(37)
    }

    defaultConfig {
        applicationId = "pt.ipleiria.museuvirtual"
        minSdk = 28
        targetSdk = 37
        versionCode = 1
        versionName = "0.1.0"
        buildConfigField("boolean", "HAS_UNITY", hasUnity.toString())
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    buildFeatures {
        compose = true
        buildConfig = true
    }
    packaging {
        jniLibs.useLegacyPackaging = hasUnity  // o Unity pede as .so extraídas (extractNativeLibs no seu manifesto)
    }
}

dependencies {
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.activity.compose)
    implementation(platform(libs.androidx.compose.bom))
    implementation(libs.androidx.compose.ui)
    implementation(libs.androidx.compose.ui.tooling.preview)
    implementation(libs.androidx.compose.material3)
    debugImplementation(libs.androidx.compose.ui.tooling)
    testImplementation(libs.junit)
    if (hasUnity) implementation(project(":unityLibrary"))
}
