using System.IO;
using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEngine;

/// <summary>
/// Build Android do museu (T012). Menu "Museu", ou:
///   Unity.exe -batchmode -quit -projectPath museum-unity -executeMethod MuseumBuild.Apk -logFile -
/// Gera museum-unity/Builds/museu3d.apk (pasta ignorada pelo Git).
/// </summary>
public static class MuseumBuild
{
    const string Scene = "Assets/Scenes/Museum.unity";

    static void Configure()
    {
        EditorUserBuildSettings.SwitchActiveBuildTarget(BuildTargetGroup.Android, BuildTarget.Android);
        PlayerSettings.companyName = "IPLeiria";
        PlayerSettings.productName = "Museu 3D";
        PlayerSettings.SetApplicationIdentifier(UnityEditor.Build.NamedBuildTarget.Android, "pt.ipleiria.museuvirtual.unity");
        PlayerSettings.Android.minSdkVersion = AndroidSdkVersions.AndroidApiLevel28;  // igual à app (app-android)
        PlayerSettings.SetScriptingBackend(UnityEditor.Build.NamedBuildTarget.Android, ScriptingImplementation.IL2CPP);
        // ARM64 para telemóveis; X86_64 para o emulador do Android Studio.
        PlayerSettings.Android.targetArchitectures = AndroidArchitecture.ARM64 | AndroidArchitecture.X86_64;
        PlayerSettings.defaultInterfaceOrientation = UIOrientation.LandscapeLeft;
        PlayerSettings.Android.forceSDCardPermission = false;
        PlayerSettings.Android.forceInternetPermission = true;  // servidor do telemóvel-comando (RemotePad)
    }

    [MenuItem("Museu/3. Build APK de teste")]
    public static void Apk()
    {
        Configure();
        Directory.CreateDirectory("Builds");
        var report = BuildPipeline.BuildPlayer(new BuildPlayerOptions
        {
            scenes = new[] { Scene },
            locationPathName = "Builds/museu3d.apk",
            target = BuildTarget.Android,
            options = BuildOptions.Development,  // mostra erros no ecrã e permite o Profiler (medir FPS)
        });
        if (report.summary.result != BuildResult.Succeeded)
            throw new System.Exception($"build falhou: {report.summary.result}, {report.summary.totalErrors} erros");
        Debug.Log($"[MuseumBuild] ok: {report.summary.outputPath} ({report.summary.totalSize / 1048576f:0.0} MB)");
    }

    /// <summary>
    /// T014: exporta como projeto Gradle; a app (app-android) inclui o módulo unityLibrary daqui.
    /// Sai em museum-unity/Builds/android-export (ignorado pelo Git: refazer depois de mudar o museu).
    /// </summary>
    [MenuItem("Museu/4. Exportar para a app Android")]
    public static void Export()
    {
        Configure();
        EditorUserBuildSettings.exportAsGoogleAndroidProject = true;
        try
        {
            var report = BuildPipeline.BuildPlayer(new BuildPlayerOptions
            {
                scenes = new[] { Scene },
                locationPathName = "Builds/android-export",
                target = BuildTarget.Android,
                options = BuildOptions.None,
            });
            if (report.summary.result != BuildResult.Succeeded)
                throw new System.Exception($"export falhou: {report.summary.result}, {report.summary.totalErrors} erros");
        }
        finally
        {
            EditorUserBuildSettings.exportAsGoogleAndroidProject = false;
        }
        Debug.Log("[MuseumBuild] ok: Builds/android-export");
    }
}
