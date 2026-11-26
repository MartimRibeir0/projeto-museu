pluginManagement {
    repositories {
        google {
            content {
                includeGroupByRegex("com\\.android.*")
                includeGroupByRegex("com\\.google.*")
                includeGroupByRegex("androidx.*")
            }
        }
        mavenCentral()
        gradlePluginPortal()
    }
}
dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
    }
}

rootProject.name = "Museu Virtual"
include(":app")

// Museu 3D (Unity as a Library, T014): módulo exportado pelo Unity (museum-unity, menu "Museu → 4. Exportar para a
// app Android"). Sem export a app compila na mesma, só sem o 3D (BuildConfig.HAS_UNITY = false).
val unityExport = file("../museum-unity/Builds/android-export")
if (unityExport.resolve("unityLibrary/build.gradle").exists()) {
    include(":unityLibrary")
    project(":unityLibrary").projectDir = unityExport.resolve("unityLibrary")
    // O build.gradle do Unity lê unity.* e unityStreamingAssets das propriedades do seu próprio projeto Gradle.
    val unityProps = java.util.Properties().apply { unityExport.resolve("gradle.properties").reader().use { load(it) } }
    gradle.beforeProject {
        if (path == ":unityLibrary") unityProps.forEach { (k, v) -> extensions.extraProperties[k.toString()] = v }
    }
    gradle.afterProject {
        // buildIl2Cpp chama funções do script no doLast: não funciona com a configuration cache.
        if (path == ":unityLibrary") tasks.named("buildIl2Cpp") { notCompatibleWithConfigurationCache("script do Unity") }
    }
} else {
    logger.warn("Museu 3D: $unityExport não existe; a app compila sem o museu 3D.")
}
