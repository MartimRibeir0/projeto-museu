using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

/// <summary>
/// Importa os FBX de blender/export e monta prefabs e a cena do museu (T036–T038).
/// Menu "Museu", ou em linha de comandos:
///   Unity.exe -batchmode -quit -projectPath museum-unity -executeMethod MuseumSetup.RunAll -logFile -
/// Refaz tudo a partir do Blender: não editar à mão os prefabs/cena gerados (perdem-se na próxima execução).
/// </summary>
public static class MuseumSetup
{
    const string Models = "Assets/Models/Museum";
    const string Prefabs = "Assets/Prefabs";
    const string ScenePath = "Assets/Scenes/Museum.unity";
    static readonly string[] Variants = { "Landscape", "Portrait", "Square" };
    static readonly string[] Colliders = {  // objetos que bloqueiam o visitante
        "Hall_Walls", "Hall_Floor", "Twin_Walls", "Twin_Floor", "Twin_Pedestal", "Twin_Terminal",
        "Props_Bench", "Props_Reception", "Props_Plant_L", "Props_Plant_R",
    };
    const float Eye = 1.6f;

    static string Repo => Path.GetFullPath(Path.Combine(Directory.GetCurrentDirectory(), ".."));

    public static void RunAll()
    {
        Import();
        Build();
    }

    [MenuItem("Museu/1. Importar do Blender")]
    public static void Import()
    {
        string src = Path.Combine(Repo, "blender", "export");
        Directory.CreateDirectory(Path.Combine(Models, "textures"));
        foreach (var f in Directory.GetFiles(src, "*.fbx"))
            File.Copy(f, Path.Combine(Models, Path.GetFileName(f)), true);
        foreach (var f in Directory.GetFiles(Path.Combine(src, "textures"), "*.png"))
            File.Copy(f, Path.Combine(Models, "textures", Path.GetFileName(f)), true);
        AssetDatabase.Refresh(ImportAssetOptions.ForceUpdate);
    }

    // ---------- prefabs ----------

    class FramePose  // sem "record": o compilador do Unity não traz IsExternalInit
    {
        public string Variant; public Vector3 Pos; public Quaternion Rot;
        public FramePose(string v, Vector3 p, Quaternion r) { Variant = v; Pos = p; Rot = r; }
    }

    class ModulePose
    {
        public Vector3 Pos; public Quaternion Rot; public Dictionary<string, FramePose> Frames;  // chave: lado L/R
        public ModulePose(Vector3 p, Quaternion r, Dictionary<string, FramePose> f) { Pos = p; Rot = r; Frames = f; }
    }

    [MenuItem("Museu/2. Criar prefabs e cena")]
    public static void Build()
    {
        Directory.CreateDirectory(Prefabs);
        Directory.CreateDirectory("Assets/Scenes");

        var frames = new Dictionary<string, GameObject>();
        foreach (var v in Variants)
        {
            var go = InstantiateModel($"frame_{v.ToLower()}.fbx", $"Frame_{v}");
            var b = LocalBounds(go.transform);
            var box = go.AddComponent<BoxCollider>();  // para o toque no quadro (T039)
            box.center = b.center;
            box.size = b.size;
            go.AddComponent<FrameInfo>();
            frames[v] = Save(go, $"Frame_{v}");
        }

        var moduleGo = InstantiateModel("corridor_module.fbx", "CorridorModule");
        foreach (var t in Named(moduleGo.transform, "_Frame_")) Object.DestroyImmediate(t.gameObject);
        moduleGo.transform.Find("CorridorModule_01").gameObject.AddComponent<MeshCollider>();
        MarkStatic(moduleGo);
        var module = Save(moduleGo, "CorridorModule");

        // Casca do museu: entrada + sala do gémeo. Corredor e molduras saem e voltam como instâncias de prefabs.
        var shellGo = InstantiateModel("museum_blockout.fbx", "MuseumShell");
        var modules = new List<ModulePose>();
        foreach (Transform m in shellGo.transform.Cast<Transform>().Where(t => t.name.StartsWith("CorridorModule_")).ToList())
        {
            var slots = new Dictionary<string, FramePose>();
            foreach (var slot in Named(m, "_Slot_"))
            {
                var f = Named(slot, "_Frame_").Single();
                slots[slot.name[^1..]] = new FramePose(f.name.Split('_').Last(), f.localPosition, f.localRotation);
            }
            modules.Add(new ModulePose(m.position, m.rotation, slots));
            Object.DestroyImmediate(m.gameObject);
        }
        var twinFrames = new Dictionary<string, FramePose>();
        foreach (var phys in Named(shellGo.transform, "Twin_PhysicalFrame_"))
        {
            var f = Named(phys, "_Frame_").Single();
            twinFrames[phys.name] = new FramePose(f.name.Split('_').Last(), f.localPosition, f.localRotation);
            Object.DestroyImmediate(f.gameObject);
        }
        foreach (var name in Colliders) shellGo.transform.Find(name).gameObject.AddComponent<MeshCollider>();
        MarkStatic(shellGo);
        var shell = Save(shellGo, "MuseumShell");

        // ---------- cena ----------
        var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
        var root = (GameObject)PrefabUtility.InstantiatePrefab(shell);
        for (int i = 0; i < modules.Count; i++)
        {
            var inst = (GameObject)PrefabUtility.InstantiatePrefab(module);
            inst.name = $"CorridorModule_{i + 1:00}";
            Place(inst.transform, inst.transform.Find("CorridorModule_01"), modules[i].Pos, modules[i].Rot, world: true);
            foreach (var slot in Named(inst.transform, "_Slot_"))
                AddFrame(frames, slot, modules[i].Frames[slot.name[^1..]]);
        }
        foreach (var (name, pose) in twinFrames)
            AddFrame(frames, root.transform.Find(name), pose);

        var lights = SetupLighting(root, modules.Count);
        var player = SetupPlayer(root);
        Physics.SyncTransforms();
        CheckNavigation(player, root);

        EditorSceneManager.SaveScene(scene, ScenePath);
        EditorBuildSettings.scenes = new[] { new EditorBuildSettingsScene(ScenePath, true) };
        Bake(lights);
        EditorSceneManager.SaveScene(scene, ScenePath);
        Snapshots(player, root);
        Debug.Log($"[MuseumSetup] ok: {modules.Count} módulos, {Variants.Length} prefabs de moldura, cena {ScenePath}");
    }

    static GameObject InstantiateModel(string file, string name)
    {
        var asset = AssetDatabase.LoadAssetAtPath<GameObject>($"{Models}/{file}")
                    ?? throw new FileNotFoundException($"{Models}/{file} não importado");
        var go = (GameObject)PrefabUtility.InstantiatePrefab(asset);
        PrefabUtility.UnpackPrefabInstance(go, PrefabUnpackMode.Completely, InteractionMode.AutomatedAction);
        go.name = name;
        return go;
    }

    static GameObject Save(GameObject go, string name)
    {
        var p = PrefabUtility.SaveAsPrefabAsset(go, $"{Prefabs}/{name}.prefab");
        Object.DestroyImmediate(go);
        return p;
    }

    static List<Transform> Named(Transform root, string part) =>
        root.GetComponentsInChildren<Transform>(true).Where(t => t != root && t.name.Contains(part)).ToList();

    /// <summary>Põe a instância de forma a que o nó interior (o objeto do Blender) fique na pose dada.</summary>
    static void Place(Transform inst, Transform inner, Vector3 pos, Quaternion rot, bool world)
    {
        var r = rot * Quaternion.Inverse(inner.localRotation);
        var p = pos - r * inner.localPosition;
        if (world) inst.SetPositionAndRotation(p, r);
        else inst.SetLocalPositionAndRotation(p, r);
    }

    static void AddFrame(Dictionary<string, GameObject> frames, Transform slot, FramePose pose)
    {
        var inst = (GameObject)PrefabUtility.InstantiatePrefab(frames[pose.Variant], slot);
        Place(inst.transform, inst.transform.Find($"Frame_{pose.Variant}"), pose.Pos, pose.Rot, world: false);
    }

    static Bounds LocalBounds(Transform root)
    {
        var rs = root.GetComponentsInChildren<Renderer>();
        var b = rs[0].bounds;
        foreach (var r in rs) b.Encapsulate(r.bounds);
        b.center = root.InverseTransformPoint(b.center);  // raiz sem rotação/escala ao criar o prefab
        return b;
    }

    /// <summary>Tudo estático (batching, lightmaps, oclusão) menos os dispositivos do gémeo, que mudam em tempo real.</summary>
    static void MarkStatic(GameObject root)
    {
        foreach (var t in root.GetComponentsInChildren<Transform>(true))
        {
            bool device = t.name.StartsWith("Twin_Light") || t.name.StartsWith("Twin_Fan");
            GameObjectUtility.SetStaticEditorFlags(t.gameObject, device ? 0 : (StaticEditorFlags)~0);
        }
    }

    static Bounds BoundsOf(Transform root, string name)
    {
        var t = root.GetComponentsInChildren<Transform>(true).First(x => x.name == name);
        return t.GetComponent<Renderer>().bounds;
    }

    // ---------- luz e câmara (T037) ----------

    static List<Light> SetupLighting(GameObject root, int nModules)
    {
        RenderSettings.ambientMode = UnityEngine.Rendering.AmbientMode.Trilight;
        RenderSettings.ambientSkyColor = new Color(0.50f, 0.50f, 0.52f);
        RenderSettings.ambientEquatorColor = new Color(0.42f, 0.40f, 0.37f);
        RenderSettings.ambientGroundColor = new Color(0.22f, 0.18f, 0.15f);
        RenderSettings.skybox = null;

        var lights = new List<Light>();
        var parent = new GameObject("Lights").transform;
        Light Add(string name, Vector3 pos, float range, float intensity, LightmapBakeType mode, Transform under = null)
        {
            var l = new GameObject(name).AddComponent<Light>();
            l.transform.SetParent(under ? under : parent, false);
            l.transform.position = pos;
            l.type = LightType.Point;
            l.range = range;
            l.intensity = intensity;
            l.color = new Color(1f, 0.94f, 0.84f);
            l.lightmapBakeType = mode;
            l.shadows = mode == LightmapBakeType.Baked ? LightShadows.Soft : LightShadows.None;
            lights.Add(l);
            return l;
        }
        var hall = BoundsOf(root.transform, "Hall_Floor");
        Add("Light_Hall", hall.center + Vector3.up * 2.8f, 10f, 1.6f, LightmapBakeType.Baked);
        foreach (var m in GameObject.FindObjectsByType<Transform>(FindObjectsSortMode.None).Where(t => t.name == "CorridorModule_01" && t.parent != null))  // o nó do Blender, não a raiz da 1.ª instância
            Add($"Light_{m.parent.name}", m.GetComponent<Renderer>().bounds.center + Vector3.up * 2.8f, 6f, 1.3f, LightmapBakeType.Baked);
        var twin = BoundsOf(root.transform, "Twin_Floor");
        Add("Light_TwinFill", twin.center + Vector3.up * 2.8f, 8f, 0.8f, LightmapBakeType.Baked);
        // Luz do candeeiro do gémeo: tempo real, para o estado do dispositivo a ligar/desligar.
        var bulb = BoundsOf(root.transform, "Twin_Light_Bulb");
        var twinLamp = Add("Twin_Light_Source", bulb.center + Vector3.down * 0.15f, 5f, 1.5f, LightmapBakeType.Realtime,
            root.transform.Find("Twin_Light"));
        twinLamp.color = new Color(1f, 0.85f, 0.6f);
        return lights;
    }

    static GameObject SetupPlayer(GameObject root)
    {
        var door = root.transform.Find("Hall_DoorFrame").position;
        var bench = root.transform.Find("Props_Bench").position;
        var dir = Vector3.ProjectOnPlane(bench - door, Vector3.up).normalized;

        var player = new GameObject("Player");
        player.transform.SetPositionAndRotation(door + dir * 1.0f, Quaternion.LookRotation(dir));
        var cc = player.AddComponent<CharacterController>();
        cc.height = 1.75f;
        cc.radius = 0.25f;
        cc.center = new Vector3(0, cc.height / 2 + cc.skinWidth, 0);
        var cam = new GameObject("Camera");
        cam.tag = "MainCamera";
        cam.transform.SetParent(player.transform, false);
        cam.transform.localPosition = new Vector3(0, Eye, 0);
        var c = cam.AddComponent<Camera>();
        c.fieldOfView = 60f;
        c.nearClipPlane = 0.05f;
        c.farClipPlane = 60f;
        c.clearFlags = CameraClearFlags.SolidColor;
        c.backgroundColor = Color.black;
        cam.AddComponent<AudioListener>();
        player.AddComponent<FirstPersonTouch>().cameraPivot = cam.transform;

        // RV tipo Cardboard (T123): um olho por metade do ecrã, 64 mm entre olhos; desligados fora do RV.
        Camera MakeEye(string name, float x, Rect rect)
        {
            var e = new GameObject(name).AddComponent<Camera>();
            e.transform.SetParent(cam.transform, false);
            e.transform.localPosition = new Vector3(x, 0, 0);
            e.CopyFrom(c);
            e.rect = rect;
            e.fieldOfView = 85f;  // campo de visão típico das lentes Cardboard
            e.enabled = false;
            return e;
        }
        var vr = player.AddComponent<VrMode>();
        vr.mono = c;
        vr.head = cam.transform;
        vr.left = MakeEye("Eye_L", -0.032f, new Rect(0, 0, 0.5f, 1));
        vr.right = MakeEye("Eye_R", 0.032f, new Rect(0.5f, 0, 0.5f, 1));

        var reticle = GameObject.CreatePrimitive(PrimitiveType.Quad);
        reticle.name = "Reticle";
        Object.DestroyImmediate(reticle.GetComponent<Collider>());
        reticle.transform.SetParent(cam.transform, false);
        reticle.transform.localPosition = new Vector3(0, 0, 1.5f);
        reticle.transform.localScale = Vector3.one * 0.012f;
        reticle.GetComponent<Renderer>().sharedMaterial = Unlit("M_Reticle", Color.white);
        reticle.SetActive(false);

        var interaction = player.AddComponent<MuseumInteraction>();
        interaction.head = cam.transform;
        interaction.monoCamera = c;
        interaction.reticle = reticle.transform;
        interaction.panel = CreatePanel();
        return player;
    }

    /// <summary>Material sem luz guardado como asset (o shader tem de ir referenciado para não ser cortado do build).</summary>
    static Material Unlit(string name, Color color)
    {
        Directory.CreateDirectory("Assets/Materials");
        string path = $"Assets/Materials/{name}.mat";
        var m = AssetDatabase.LoadAssetAtPath<Material>(path);
        if (m == null)
        {
            m = new Material(Shader.Find("Unlit/Color"));
            AssetDatabase.CreateAsset(m, path);
        }
        m.color = color;
        EditorUtility.SetDirty(m);
        return m;
    }

    /// <summary>Painel da fotografia (T039) no espaço 3D: fundo escuro 0,8 x 0,5 m com título e texto.</summary>
    static PhotoPanel CreatePanel()
    {
        var root = new GameObject("PhotoPanel");
        var bg = GameObject.CreatePrimitive(PrimitiveType.Quad);
        bg.name = "Background";
        Object.DestroyImmediate(bg.GetComponent<Collider>());
        bg.transform.SetParent(root.transform, false);
        bg.transform.localPosition = new Vector3(0, 0, 0.005f);  // atrás do texto
        bg.transform.localScale = new Vector3(0.8f, 0.5f, 1f);
        bg.GetComponent<Renderer>().sharedMaterial = Unlit("M_Panel", new Color(0.08f, 0.08f, 0.1f));

        var font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
        TextMesh Text(string name, Vector3 pos, int size, FontStyle style, Color color, string text = "")
        {
            var go = new GameObject(name);
            go.transform.SetParent(root.transform, false);
            go.transform.localPosition = pos;
            var t = go.AddComponent<TextMesh>();
            t.font = font;
            go.GetComponent<MeshRenderer>().sharedMaterial = font.material;
            t.fontSize = size;
            t.characterSize = 0.005f;
            t.anchor = TextAnchor.UpperLeft;
            t.fontStyle = style;
            t.color = color;
            t.text = text;
            return t;
        }
        var panel = root.AddComponent<PhotoPanel>();
        panel.title = Text("Title", new Vector3(-0.36f, 0.22f, 0), 80, FontStyle.Bold, Color.white);
        panel.body = Text("Body", new Vector3(-0.36f, 0.13f, 0), 52, FontStyle.Normal, new Color(0.85f, 0.85f, 0.85f));
        Text("Hint", new Vector3(-0.36f, -0.19f, 0), 40, FontStyle.Italic, new Color(0.6f, 0.6f, 0.6f), "Toque, A ou B: fechar");
        root.SetActive(false);
        return panel;
    }

    /// <summary>Autoverificação: o visitante nasce em cima do chão e as paredes param-no.</summary>
    static void CheckNavigation(GameObject player, GameObject root)
    {
        var p = player.transform.position;
        if (!Physics.Raycast(p + Vector3.up, Vector3.down, out var hit, 2f) || hit.distance > 1.05f)
            throw new System.Exception("visitante não está em cima do chão (colliders em falta?)");
        var cc = player.GetComponent<CharacterController>();
        cc.Move(player.transform.right * 20f);  // contra a parede lateral da entrada (8 m de largura)
        float moved = Vector3.Distance(p, player.transform.position);
        cc.enabled = false;
        player.transform.position = p;
        cc.enabled = true;
        if (moved > 4.5f) throw new System.Exception($"atravessou a parede ({moved:0.0} m)");
    }

    static void Bake(List<Light> lights)
    {
        const string path = "Assets/Scenes/MuseumLighting.lighting";
        var ls = AssetDatabase.LoadAssetAtPath<LightingSettings>(path);
        if (ls == null)
        {
            ls = new LightingSettings();
            AssetDatabase.CreateAsset(ls, path);
        }
        ls.bakedGI = true;
        ls.realtimeGI = false;
        ls.lightmapper = LightingSettings.Lightmapper.ProgressiveCPU;
        ls.lightmapResolution = 8;      // texels/m: chega para luz suave e mantém os lightmaps pequenos (mobile)
        ls.lightmapMaxSize = 1024;
        ls.directionalityMode = LightmapsMode.NonDirectional;
        ls.maxBounces = 2;
        ls.directSampleCount = 32;
        ls.indirectSampleCount = 256;
        Lightmapping.lightingSettings = ls;
        if (!Lightmapping.Bake()) throw new System.Exception("bake de luz falhou");
    }

    static void Snapshots(GameObject player, GameObject root)
    {
        string dir = Path.Combine(Repo, "docs", "unity");
        Directory.CreateDirectory(dir);
        var cam = player.GetComponentInChildren<Camera>();
        Shot(cam, Path.Combine(dir, "entrada.png"));

        // Sala do gémeo vista da passagem do corredor (o lado da sala mais perto da entrada do museu).
        var twin = BoundsOf(root.transform, "Twin_Floor");
        var pedestal = root.transform.Find("Twin_Pedestal").position;
        var toHall = Vector3.ProjectOnPlane(player.transform.position - twin.center, Vector3.up).normalized;
        var tmp = new GameObject("SnapshotCam").AddComponent<Camera>();
        tmp.CopyFrom(cam);
        tmp.transform.position = new Vector3(twin.center.x, Eye, twin.center.z) + toHall * (twin.extents.z - 0.6f);
        tmp.transform.LookAt(new Vector3(pedestal.x, 1.4f, pedestal.z));
        Shot(tmp, Path.Combine(dir, "gemeo.png"));

        // Painel aberto num quadro do corredor, visto de 1,6 m (verifica T039 sem telemóvel).
        var frame = Object.FindObjectsByType<FrameInfo>(FindObjectsSortMode.InstanceID)
            .First(f => f.transform.parent.name.Contains("_Slot_"));
        var center = frame.GetComponent<BoxCollider>().bounds.center;
        var corridor = frame.transform.root.GetComponentsInChildren<Renderer>().First(r => r.name == "CorridorModule_01").bounds.center;
        var outward = Vector3.ProjectOnPlane(corridor - center, Vector3.up).normalized;
        tmp.transform.position = new Vector3(center.x, Eye, center.z) + outward * 1.6f;
        tmp.transform.LookAt(center);
        var panel = player.GetComponent<MuseumInteraction>().panel;
        panel.Show(frame, tmp.transform, 1.6f);
        tmp.transform.position += outward * 0.4f;  // recua para se ver o painel e o quadro
        Shot(tmp, Path.Combine(dir, "quadro.png"));
        panel.Close();
        Object.DestroyImmediate(tmp.gameObject);

        var vr = player.GetComponent<VrMode>();
        Shot(Path.Combine(dir, "rv.png"), vr.left, vr.right);
    }

    static void Shot(Camera cam, string path, int w = 1600, int h = 900) => Shot(path, w, h, cam);

    static void Shot(string path, params Camera[] cams) => Shot(path, 1600, 900, cams);

    /// <summary>Várias câmaras para a mesma imagem, cada uma no seu viewport (os dois olhos do RV).</summary>
    static void Shot(string path, int w, int h, params Camera[] cams)
    {
        var rt = new RenderTexture(w, h, 24);
        foreach (var cam in cams)
        {
            cam.targetTexture = rt;
            cam.Render();
            cam.targetTexture = null;
        }
        RenderTexture.active = rt;
        var tex = new Texture2D(w, h, TextureFormat.RGB24, false);
        tex.ReadPixels(new Rect(0, 0, w, h), 0, 0);
        File.WriteAllBytes(path, tex.EncodeToPNG());
        RenderTexture.active = null;
        Object.DestroyImmediate(rt);
        Object.DestroyImmediate(tex);
    }
}
