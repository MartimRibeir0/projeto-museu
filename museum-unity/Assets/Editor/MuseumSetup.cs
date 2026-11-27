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
        // Espelho de blender/export: FBX que lá já não existem saem daqui também.
        foreach (var f in Directory.GetFiles(Models, "*.fbx"))
            if (!File.Exists(Path.Combine(src, Path.GetFileName(f)))) AssetDatabase.DeleteAsset(f.Replace('\\', '/'));
        foreach (var f in Directory.GetFiles(src, "*.fbx"))
            File.Copy(f, Path.Combine(Models, Path.GetFileName(f)), true);
        foreach (var f in Directory.GetFiles(Path.Combine(src, "textures"), "*.png"))
            File.Copy(f, Path.Combine(Models, "textures", Path.GetFileName(f)), true);
        AssetDatabase.Refresh(ImportAssetOptions.ForceUpdate);
    }

    // ---------- prefabs ----------

    /// <summary>Objetos que bloqueiam o visitante: chãos, paredes e móveis (não tetos, luzes, rodapés, aros, quadros).</summary>
    static bool Solid(string n) =>
        n is "Lobby" or "Lobby_Walls" or "Corridor" or "Room" or "Twin_Desk" or "Lobby_Chair" or "Lobby_Plant_L" or "Lobby_Plant_R"
        || n.EndsWith("_Door") || n.EndsWith("_Solid") || n.EndsWith("_EndWall") || n.EndsWith("_Bench");

    static GameObject Module(string file, string name)
    {
        var go = InstantiateModel(file, name);
        foreach (var t in Named(go.transform, "_Frame_")) Object.DestroyImmediate(t.gameObject);  // o MuseumBuilder põe as molduras
        foreach (var r in go.GetComponentsInChildren<MeshRenderer>())
            if (Solid(r.name)) r.gameObject.AddComponent<MeshCollider>();
        return go;
    }

    [MenuItem("Museu/2. Criar prefabs e cena")]
    public static void Build()
    {
        Directory.CreateDirectory(Prefabs);
        Directory.CreateDirectory("Assets/Scenes");
        foreach (var old in new[] { "MuseumShell", "CorridorModule", "Frame_Portrait", "Frame_Square" }) AssetDatabase.DeleteAsset($"{Prefabs}/{old}.prefab");

        var frameGo = InstantiateModel("frame_landscape.fbx", "Frame_Landscape");
        frameGo.AddComponent<FrameInfo>();  // o BoxCollider (toque, T039) põe-o o MuseumBuilder, com a medida final
        var frame = Save(frameGo, "Frame_Landscape");
        var corridor = Save(Module("corridor_segment.fbx", "CorridorSegment"), "CorridorSegment");
        var room = Save(Module("gallery_room.fbx", "GalleryRoom"), "GalleryRoom");
        var lobby = Save(Module("lobby.fbx", "Lobby"), "Lobby");

        // ---------- cena ----------
        var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
        var root = (GameObject)PrefabUtility.InstantiatePrefab(lobby);  // na pose do Blender, como o exemplo
        var builder = new GameObject("Museum").AddComponent<MuseumBuilder>();
        builder.corridor = corridor;
        builder.room = room;
        builder.frame = frame;
        builder.lobby = root.transform;
        builder.photoMaterial = Asset("M_Photo", "Unlit/Texture", Color.white);
        Measure(builder);

        SetupLighting();
        var player = SetupPlayer(root, builder);
        builder.viewer = player.transform;
        Physics.SyncTransforms();
        CheckNavigation(player, root);

        EditorSceneManager.SaveScene(scene, ScenePath);
        EditorBuildSettings.scenes = new[] { new EditorBuildSettingsScene(ScenePath, true) };
        int photos = Snapshots(player, builder);
        EditorSceneManager.OpenScene(ScenePath);  // deita fora o museu montado para as imagens: monta-se em runtime
        Debug.Log($"[MuseumSetup] ok: prefabs Lobby, CorridorSegment, GalleryRoom e moldura-molde; " +
                  $"cena {ScenePath}; {photos} fotografias montadas nos quadros");
    }

    /// <summary>
    /// Poses de ligação medidas no exemplo do Blender (museum_blockout.fbx), em eixos do Unity: onde começa o corredor,
    /// o passo entre segmentos, a sala em relação ao empty de ligação e a moldura em relação ao slot.
    /// </summary>
    static void Measure(MuseumBuilder b)
    {
        var ex = InstantiateModel("museum_blockout.fbx", "Example");
        Transform N(string n) => ex.GetComponentsInChildren<Transform>(true).First(t => t.name == n);
        var (c1, c2) = (N("C01"), N("C02"));
        b.segPos = c1.position;
        b.segRot = c1.rotation;
        b.segStep = c2.position - c1.position;
        (Vector3, Quaternion) Rel(Transform from, Transform to) =>
            (from.InverseTransformPoint(to.position), Quaternion.Inverse(from.rotation) * to.rotation);
        (b.roomPos, b.roomRot) = Rel(N("C01_Anchor_L"), N("C01_L_R1"));
        var (np, nr) = Rel(N("C01_L_R1_Anchor_Next"), N("C01_L_R2"));
        var (rp, rr) = Rel(N("C01_Anchor_R"), N("C01_R_R1"));
        if ((np - b.roomPos).magnitude > 1e-3f || (rp - b.roomPos).magnitude > 1e-3f
            || Quaternion.Angle(nr, b.roomRot) > 0.1f || Quaternion.Angle(rr, b.roomRot) > 0.1f)
            throw new System.Exception("ligações das salas diferentes entre Anchor_L/R/Next: rever blender/build_museum.py");
        var slot = N("C01_L_R1_Slot_01");
        (b.framePos, b.frameRot) = Rel(slot, Named(slot, "_Frame_").Single());
        if (Vector3.Distance(b.segPos + b.segStep, c2.position) > 1e-3f) throw new System.Exception("passo do corredor");
        Object.DestroyImmediate(ex);
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

    /// <summary>
    /// Luz em tempo real: corredor e salas são instanciados em runtime, por isso não podem ter lightmap.
    /// Ambiente trilight + 1 luz direcional sem sombras (barata no telemóvel); candeeiros são materiais emissivos.
    /// </summary>
    static void SetupLighting()
    {
        RenderSettings.ambientMode = UnityEngine.Rendering.AmbientMode.Trilight;
        RenderSettings.ambientSkyColor = new Color(0.62f, 0.62f, 0.64f);
        RenderSettings.ambientEquatorColor = new Color(0.55f, 0.53f, 0.50f);
        RenderSettings.ambientGroundColor = new Color(0.32f, 0.28f, 0.24f);
        RenderSettings.skybox = null;
        var sun = new GameObject("Light").AddComponent<Light>();
        sun.type = LightType.Directional;
        sun.transform.rotation = Quaternion.Euler(55f, 35f, 0f);  // inclinada: as paredes nas duas direções também recebem luz
        sun.intensity = 0.55f;
        sun.color = new Color(1f, 0.95f, 0.87f);
        sun.shadows = LightShadows.None;
        sun.lightmapBakeType = LightmapBakeType.Realtime;

        const string path = "Assets/Scenes/MuseumLighting.lighting";
        var ls = AssetDatabase.LoadAssetAtPath<LightingSettings>(path);
        if (ls == null)
        {
            ls = new LightingSettings();
            AssetDatabase.CreateAsset(ls, path);
        }
        ls.bakedGI = false;
        ls.realtimeGI = false;
        Lightmapping.lightingSettings = ls;
        Lightmapping.Clear();
    }

    static GameObject SetupPlayer(GameObject root, MuseumBuilder builder)
    {
        // Nasce no Lobby_Spawn, a olhar para o corredor.
        var spawn = root.GetComponentsInChildren<Transform>(true).First(t => t.name == "Lobby_Spawn").position;
        var dir = Vector3.ProjectOnPlane(builder.segPos - spawn, Vector3.up).normalized;

        var player = new GameObject("Player");
        player.transform.SetPositionAndRotation(spawn, Quaternion.LookRotation(dir));
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
    static Material Unlit(string name, Color color) => Asset(name, "Unlit/Color", color);

    static Material Asset(string name, string shader, Color color)
    {
        Directory.CreateDirectory("Assets/Materials");
        string path = $"Assets/Materials/{name}.mat";
        var m = AssetDatabase.LoadAssetAtPath<Material>(path);
        if (m == null)
        {
            m = new Material(Shader.Find(shader));
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

    /// <summary>Monta um exemplo com todas as coleções da app (como no telemóvel) e grava as imagens de verificação.</summary>
    static int Snapshots(GameObject player, MuseumBuilder builder)
    {
        var cols = MuseumBuilder.Collections();
        builder.Build(cols);
        foreach (var area in builder.areas)  // tudo carregado, só para as imagens; no telemóvel carrega-se à volta do visitante
            for (var run = builder.Load(area); run.MoveNext();) { }
        Physics.SyncTransforms();
        int photos = Object.FindObjectsByType<FrameInfo>(FindObjectsSortMode.None).Count(f => !string.IsNullOrEmpty(f.title) && f.title != "Moldura vazia");
        int expected = cols.Sum(c => c.files.Length);
        // Vazios: os 6 da sala inicial e o resto da última sala de cada coleção (25 fotografias -> 5 vazios).
        int empty = Object.FindObjectsByType<FrameInfo>(FindObjectsSortMode.None).Count(f => f.title == "Moldura vazia");
        int expectedEmpty = 6 + cols.Sum(c => (RoomSlotsFor(c) - c.files.Length));
        if (empty != expectedEmpty) throw new System.Exception($"{empty} molduras vazias, esperadas {expectedEmpty}");
        if (cols.Count > 0 && photos == 0) throw new System.Exception("nenhuma fotografia nos quadros");

        string dir = Path.Combine(Repo, "docs", "unity");
        Directory.CreateDirectory(dir);
        foreach (var old in new[] { "gemeo.png" }) File.Delete(Path.Combine(dir, old));
        var cam = player.GetComponentInChildren<Camera>();
        Shot(cam, Path.Combine(dir, "entrada.png"));
        cam.transform.Rotate(0f, 180f, 0f, Space.World);  // sala inicial vista para trás: secretária e quadros vazios
        Shot(cam, Path.Combine(dir, "sala_inicial.png"));
        cam.transform.Rotate(0f, 180f, 0f, Space.World);

        var tmp = new GameObject("SnapshotCam").AddComponent<Camera>();
        tmp.CopyFrom(cam);
        var rooms = builder.GetComponentsInChildren<Transform>().Where(t => t.name == "Room").ToList();
        if (rooms.Count > 0)
        {
            // 1.ª sala vista da porta de entrada, a olhar para a porta do fundo.
            var r = rooms[0];
            var center = r.GetComponent<Renderer>().bounds.center;
            var inward = Vector3.ProjectOnPlane(center - r.position, Vector3.up).normalized;
            tmp.transform.position = new Vector3(r.position.x, Eye, r.position.z) + inward * 0.4f;
            tmp.transform.rotation = Quaternion.LookRotation(Vector3.ProjectOnPlane(center - tmp.transform.position, Vector3.up));
            Shot(tmp, Path.Combine(dir, "sala.png"));

            // Última sala da última coleção (p. ex. 25 fotografias: 5 com fotografia, 5 vazias).
            var last = rooms[^1];
            var lc = last.GetComponent<Renderer>().bounds.center;
            var lin = Vector3.ProjectOnPlane(lc - last.position, Vector3.up).normalized;
            tmp.transform.position = new Vector3(last.position.x, Eye, last.position.z) + lin * 0.4f;
            tmp.transform.rotation = Quaternion.LookRotation(Vector3.ProjectOnPlane(lc - tmp.transform.position, Vector3.up));
            Shot(tmp, Path.Combine(dir, "ultima_sala.png"));

            // Painel aberto num quadro da sala, visto de 1,6 m (verifica T039 sem telemóvel).
            var frame = r.parent.GetComponentsInChildren<FrameInfo>().First();
            var fc = frame.GetComponentInChildren<BoxCollider>().bounds.center;
            var outward = Vector3.ProjectOnPlane(center - fc, Vector3.up).normalized;
            tmp.transform.position = new Vector3(fc.x, Eye, fc.z) + outward * 1.6f;
            tmp.transform.LookAt(fc);
            var panel = player.GetComponent<MuseumInteraction>().panel;
            panel.Show(frame, tmp.transform, 1.6f);
            tmp.transform.position += outward * 0.4f;  // recua para se ver o painel e o quadro
            Shot(tmp, Path.Combine(dir, "quadro.png"));
            panel.Close();

            // Tamanhos esquisitos na mesma sala: molduras à medida, panorama e tira cortados a 3:1, inválidas ignoradas.
            var area = builder.areas.First(a => a.root == r.parent.gameObject);
            builder.Unload(area);
            var sizes = new[] { (4000, 3000), (10000, 1000), (300, 900), (64, 64), (1080, 1920), (2000, 2000), (1920, 1080), (900, 300), (15, 15), (0, 0) };
            var test = new MuseumBuilder.Coll { id = "teste", title = "Tamanhos", files = sizes.Select(s => $"{s.Item1}x{s.Item2}").ToArray() };
            for (int i = 0; i < sizes.Length; i++)
                builder.Hang(area, area.jobs[i].slot, test, i, sizes[i].Item1 == 0 ? new byte[] { 1, 2, 3 } : Png(sizes[i].Item1, sizes[i].Item2));
            int hung = area.hung.OfType<GameObject>().Count();
            if (hung != 8) throw new System.Exception($"tamanhos esquisitos: {hung} molduras, esperadas 8 (2 imagens inválidas)");
            tmp.transform.position = new Vector3(r.position.x, Eye, r.position.z) + inward * 0.4f;
            tmp.transform.rotation = Quaternion.LookRotation(Vector3.ProjectOnPlane(center - tmp.transform.position, Vector3.up));
            Shot(tmp, Path.Combine(dir, "molduras.png"));
        }
        Object.DestroyImmediate(tmp.gameObject);

        var vr = player.GetComponent<VrMode>();
        Shot(Path.Combine(dir, "rv.png"), vr.left, vr.right);
        Debug.Log($"[MuseumSetup] {cols.Count} coleções, {photos} quadros com fotografia (esperados {expected}), {empty} vazios");
        if (photos != expected) throw new System.Exception($"{photos} quadros com fotografia, esperados {expected}");
        CheckStreaming(builder);
        CheckFrameSizes();
        return photos;
    }

    static int RoomSlotsFor(MuseumBuilder.Coll c) =>
        Mathf.Max(1, Mathf.CeilToInt(c.files.Length / (float)MuseumBuilder.RoomSlots)) * MuseumBuilder.RoomSlots;

    /// <summary>Imagem de teste w x h: gradiente com borda branca (vê-se se foi cortada).</summary>
    static byte[] Png(int w, int h)
    {
        var t = new Texture2D(w, h, TextureFormat.RGB24, false);
        var px = new Color32[w * h];
        int b = Mathf.Max(1, Mathf.Min(w, h) / 20);
        for (int y = 0; y < h; y++)
            for (int x = 0; x < w; x++)
                px[y * w + x] = x < b || y < b || x >= w - b || y >= h - b ? new Color32(255, 255, 255, 255)
                    : new Color32((byte)(255 * x / w), (byte)(160 * y / h), (byte)(255 - 255 * x / w), 255);
        t.SetPixels32(px);
        var png = t.EncodeToPNG();
        Object.DestroyImmediate(t);
        return png;
    }

    /// <summary>Escolha da moldura: formato mais parecido, sempre dentro de 1,4 x 1,3 m, baixa resolução mais pequena.</summary>
    static void CheckFrameSizes()
    {
        void Is(string what, (string name, float shown, float w, float h) got, string name, float w, float h)
        {
            if (got.name != name || Mathf.Abs(got.w - w) > 0.01f || Mathf.Abs(got.h - h) > 0.01f)
                throw new System.Exception($"moldura {what}: {got}, esperado ({name}, {w}, {h})");
        }
        Is("4:3", MuseumBuilder.FrameSize(4000, 3000), "Horizontal 4:3", 1.2f, 0.9f);
        Is("16:9", MuseumBuilder.FrameSize(1920, 1080), "Horizontal 16:9", 1.4f, 0.7875f);
        Is("9:16", MuseumBuilder.FrameSize(1080, 1920), "Vertical 9:16", 0.731f, 1.3f);
        Is("3:4", MuseumBuilder.FrameSize(3000, 4000), "Vertical 3:4", 0.9f, 1.2f);
        Is("panorama 10:1", MuseumBuilder.FrameSize(10000, 1000), "Panorâmica 2:1", 1.4f, 0.7f);
        Is("tira 1:3", MuseumBuilder.FrameSize(300, 900), "Vertical 1:2", 0.65f, 1.3f);
        Is("64 px", MuseumBuilder.FrameSize(64, 64), "Quadrada", 0.55f, 0.55f);
        Is("1:1", MuseumBuilder.FrameSize(2000, 2000), "Quadrada", 1f, 1f);
        Is("quase quadrada", MuseumBuilder.FrameSize(1100, 1000), "Quadrada", 1f, 1f);
        for (int w = 1; w <= 8000; w += 97)
            for (int h = 1; h <= 8000; h += 89)
            {
                var (_, _, fw, fh) = MuseumBuilder.FrameSize(w, h);
                if (fw > 1.4001f || fh > 1.3001f || fw < 0.1f || fh < 0.1f) throw new System.Exception($"moldura {w}x{h}: {fw}x{fh} m");
            }
    }

    /// <summary>
    /// Escalabilidade: museu de 20 coleções x 200 fotografias (sem ler ficheiros) percorrido sala a sala.
    /// Em cada ponto, a sala onde se está fica carregada e nunca há mais de MaxKept salas com fotografias.
    /// </summary>
    static void CheckStreaming(MuseumBuilder builder)
    {
        var big = Object.Instantiate(builder);
        big.Build(Enumerable.Range(0, 20).Select(i => new MuseumBuilder.Coll
        {
            id = $"c{i}", title = $"C{i}", files = Enumerable.Range(0, 200).Select(k => $"{k}.jpg").ToArray(),
        }).ToList());
        int maxLoaded = 0, maxActive = 0;
        foreach (var here in big.areas.ToList())
        {
            var p = here.bounds.center;
            for (var next = big.Step(p); next != null; next = big.Step(p)) next.loaded = true;  // carregar = marcar
            maxLoaded = Mathf.Max(maxLoaded, big.areas.Count(a => a.loaded));
            maxActive = Mathf.Max(maxActive, big.areas.Count(a => a.root != null && a.root.activeSelf));
            if (!here.loaded) throw new System.Exception("sala onde está o visitante sem fotografias");
        }
        Debug.Log($"[MuseumSetup] escala: {big.areas.Count} salas, no máximo {maxLoaded} carregadas " +
                  $"(~{maxLoaded * MuseumBuilder.RoomSlots} fotografias) e {maxActive} visíveis");
        if (maxLoaded > MuseumBuilder.MaxKept) throw new System.Exception($"{maxLoaded} salas carregadas de uma vez");
        Object.DestroyImmediate(big.gameObject);
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
