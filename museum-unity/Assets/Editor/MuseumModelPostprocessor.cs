using System;
using UnityEditor;
using UnityEngine;

/// <summary>Definições de import dos FBX do Blender (Assets/Models/Museum) e cópia das propriedades personalizadas.</summary>
class MuseumModelPostprocessor : AssetPostprocessor
{
    const string Folder = "Assets/Models/Museum/";

    void OnPreprocessModel()
    {
        if (!assetPath.StartsWith(Folder)) return;
        var mi = (ModelImporter)assetImporter;
        mi.bakeAxisConversion = true;   // o Blender exporta sem bake_space_transform (estragava objetos aninhados)
        mi.preserveHierarchy = true;    // raiz = ficheiro, mesmo com um só objeto: estrutura previsível para o setup
        mi.generateSecondaryUV = true;  // UV2 para lightmaps
        mi.importCameras = false;
        mi.importLights = false;
        mi.importAnimation = false;
        mi.animationType = ModelImporterAnimationType.None;
        mi.materialImportMode = ModelImporterMaterialImportMode.ImportViaMaterialDescription;
    }

    void OnPostprocessGameObjectWithUserProperties(GameObject go, string[] names, object[] values)
    {
        if (!assetPath.StartsWith(Folder)) return;
        BlenderProps props = null;
        for (int i = 0; i < names.Length; i++)
        {
            if (names[i] != "device_id" && names[i] != "aspect" && names[i] != "slot") continue;
            props ??= go.AddComponent<BlenderProps>();
            switch (names[i])
            {
                case "device_id": props.deviceId = values[i].ToString(); break;
                case "aspect": props.aspect = Convert.ToSingle(values[i]); break;
                case "slot": props.slot = values[i].ToString(); break;
            }
        }
    }
}
