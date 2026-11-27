using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEngine;
using UnityEngine.Networking;

/// <summary>
/// Monta o museu conforme as coleções escolhidas na app e põe as fotografias nos quadros.
/// Regra igual a layout() em blender/build_museum.py: a coleção i fica no segmento de corredor i / 2, à esquerda
/// se i for par; cada sala leva até 10 quadros e liga à seguinte da mesma coleção pela porta do fundo.
/// As coleções vêm do extra "collections" da app (ids das pastas em assets/colecoes do APK). Sem extra, mostra todas;
/// no Editor lê-as de app-android/app/src/main/assets.
/// </summary>
public class MuseumBuilder : MonoBehaviour
{
    public const int RoomSlots = 10;
    const int PhotoMaxPx = 512;  // chega para um quadro de 1,2 m visto a 1-2 m; ~1 MB por fotografia na GPU
    const string Dir = "colecoes";
    // Só as salas mais perto do visitante têm fotografias: memória limitada a ~MaxKept x 10 fotografias,
    // seja qual for o tamanho das coleções. Distâncias em metros até à sala (0 = dentro dela).
    public const int MaxLoaded = 6, MaxKept = 8;
    public const float LoadM = 12f, UnloadM = 18f, HideM = 22f;  // HideM: vê-se até ~2 salas à frente pelas portas

    public GameObject corridor, room;
    [Tooltip("Frame_Landscape: molde, esticado à medida de cada fotografia")] public GameObject frame;
    [Tooltip("Unlit/Texture: a fotografia vê-se com as cores reais, sem depender da luz")] public Material photoMaterial;
    public Transform lobby;
    [Tooltip("quem se mexe no museu (o Player); as salas carregam-se à volta dele")] public Transform viewer;

    // Poses medidas no museum_blockout.fbx pelo MuseumSetup, já em eixos do Unity.
    public Vector3 segPos, segStep;
    public Quaternion segRot;
    public Vector3 roomPos;      // sala em relação ao empty de ligação (Anchor_L/R/Next)
    public Quaternion roomRot;
    public Vector3 framePos;     // moldura em relação ao slot
    public Quaternion frameRot;

    public class Coll
    {
        public string id, title;
        public string[] files;
    }

    /// <summary>Sala (ou a sala inicial) com os quadros que lhe cabem; as fotografias vêm e vão com a distância.</summary>
    public class Area
    {
        public GameObject root;
        public Bounds bounds;
        public readonly List<(Transform slot, Coll c, int photo)> jobs = new();
        public readonly List<Object> hung = new();  // molduras, materiais e texturas criados: tudo a destruir ao sair
        public bool loaded;
    }

    public readonly List<Area> areas = new();

    IEnumerator Start()
    {
        Build(Collections());
        if (viewer == null) viewer = Camera.main.transform;
        while (true)
        {
            var next = Step(viewer.position);
            if (next != null) yield return Load(next);  // a mais perto primeiro, uma fotografia por frame
            else yield return new WaitForSeconds(0.3f);
        }
    }

    /// <summary>Corredor, salas e lista de quadros por sala. As fotografias carregam-se depois, com Load().</summary>
    public void Build(List<Coll> cols)
    {
        int nSeg = (cols.Count + 1) / 2;
        var segs = new List<Transform>();
        for (int s = 0; s < nSeg; s++)
        {
            var seg = Spawn(corridor, segPos + segStep * s, segRot);
            bool left = 2 * s < cols.Count, right = 2 * s + 1 < cols.Count;
            Keep(seg, "_Wall_L_Door", left);
            Keep(seg, "_Wall_L_Solid", !left);
            Keep(seg, "_Wall_R_Door", right);
            Keep(seg, "_Wall_R_Solid", !right);
            Keep(seg, "_EndWall", s == nSeg - 1);
            segs.Add(seg);
        }

        for (int i = 0; i < cols.Count; i++)
        {
            var c = cols[i];
            var anchor = Find(segs[i / 2], i % 2 == 0 ? "_Anchor_L" : "_Anchor_R");
            int rooms = Mathf.Max(1, Mathf.CeilToInt(c.files.Length / (float)RoomSlots));
            for (int r = 0; r < rooms; r++)
            {
                var rm = Spawn(room, anchor.TransformPoint(roomPos), anchor.rotation * roomRot);
                Keep(rm, "_FarWall_Door", r < rooms - 1);
                Keep(rm, "_FarWall_Solid", r == rooms - 1);
                var area = NewArea(rm, rm.gameObject);
                var slots = Slots(rm);
                for (int k = 0; k < RoomSlots; k++)
                    if (r * RoomSlots + k < c.files.Length) area.jobs.Add((slots[k], c, r * RoomSlots + k));
                    else EmptyFrame(slots[k]);  // última sala da coleção: o resto dos quadros fica vazio
                anchor = Find(rm, "_Anchor_Next");
            }
        }
        foreach (var slot in Slots(lobby)) EmptyFrame(slot);  // sala inicial: quadros vazios
        Physics.SyncTransforms();
    }

    /// <summary>Moldura-molde sem fotografia (tela cinzenta do Blender). Fica sempre: é leve e partilha malha e material.</summary>
    void EmptyFrame(Transform slot)
    {
        var f = Instantiate(frame, slot);
        Place(f.transform, slot.TransformPoint(framePos), slot.rotation * frameRot);
        f.GetComponentsInChildren<MeshRenderer>().First(r => r.name.StartsWith("Frame_")).gameObject.AddComponent<BoxCollider>();
        var info = f.GetComponent<FrameInfo>();
        info.title = "Moldura vazia";
        info.category = "";
        info.description = "Ainda sem fotografia.";
    }

    Area NewArea(Transform t, GameObject root)
    {
        var rs = t.GetComponentsInChildren<Renderer>();
        var area = new Area { root = root, bounds = rs[0].bounds };
        foreach (var r in rs) area.bounds.Encapsulate(r.bounds);
        areas.Add(area);
        return area;
    }

    /// <summary>
    /// Esconde salas longe (menos desenho), liberta as fotografias das salas que saíram de perto e devolve a sala
    /// mais perto que falta carregar (ou null). No máximo MaxKept salas carregadas; só se carregam as MaxLoaded mais perto.
    /// </summary>
    public Area Step(Vector3 p)
    {
        var byDist = areas.Select(a => (a, d: Mathf.Sqrt(a.bounds.SqrDistance(p)))).OrderBy(x => x.d).ToList();
        Area next = null;
        for (int rank = 0; rank < byDist.Count; rank++)
        {
            var (a, d) = byDist[rank];
            if (a.root.activeSelf != d < HideM) a.root.SetActive(d < HideM);
            if (a.loaded && (d > UnloadM || rank >= MaxKept)) Unload(a);
            else if (!a.loaded && next == null && d < LoadM && rank < MaxLoaded) next = a;
        }
        return next;
    }

    /// <summary>Põe as fotografias da sala nos quadros. Sem corrotinas aninhadas: o MuseumSetup corre-a fora do Play.</summary>
    public IEnumerator Load(Area area)
    {
        area.loaded = true;
        foreach (var (slot, c, photo) in area.jobs)
        {
            string rel = $"{Dir}/{c.id}/{c.files[photo]}";
            byte[] bytes = null;
            if (Application.platform == RuntimePlatform.Android)
            {
                using var req = UnityWebRequest.Get($"{Application.streamingAssetsPath}/{rel}");  // jar:file://...!/assets
                yield return req.SendWebRequest();
                if (req.result == UnityWebRequest.Result.Success) bytes = req.downloadHandler.data;
                else Debug.LogWarning($"[MuseumBuilder] {rel}: {req.error}");
            }
            else bytes = File.ReadAllBytes(Path.Combine(EditorAssets, rel));
            if (!area.loaded) yield break;  // descarregada entretanto
            if (bytes != null) Hang(area, slot, c, photo, bytes);
            if (Application.isPlaying) yield return null;  // uma fotografia por frame: sem paragens longas
        }
    }

    public void Unload(Area area)
    {
        foreach (var o in area.hung) Kill(o);
        area.hung.Clear();
        area.loaded = false;
    }

    // Molduras de formatos fixos (T039): cada fotografia vai para a de proporção mais parecida e corta-se ao centro
    // o pouco que sobra. Assim a parede fica com tamanhos "de galeria" em vez de um tamanho diferente por fotografia.
    // Larguras escolhidas para ~1 m² cada (igual à moldura quadrada do Blender), sempre dentro de MaxW x MaxH.
    const float MaxW = 1.4f, MaxH = 1.3f;  // área da fotografia: não toca na luz do quadro (+0,78 m) nem na placa (x 0,78 m)
    const int LowResPx = 600, MinPx = 16;  // abaixo de LowResPx a moldura encolhe (até 55%) para não se ver o pixel
    const int MaxBytes = 20 << 20;         // ficheiros maiores não se descodificam (memória do telemóvel)

    public static readonly (string name, float aspect, float w)[] Formats =
    {
        ("Quadrada", 1f, 1f),
        ("Horizontal 4:3", 4f / 3f, 1.2f),
        ("Horizontal 3:2", 1.5f, 1.26f),
        ("Horizontal 16:9", 16f / 9f, 1.4f),
        ("Panorâmica 2:1", 2f, 1.4f),
        ("Vertical 3:4", 3f / 4f, 0.9f),
        ("Vertical 2:3", 2f / 3f, 0.84f),
        ("Vertical 9:16", 9f / 16f, 0.73125f),
        ("Vertical 1:2", 0.5f, 0.65f),
    };

    /// <summary>Moldura para uma imagem de pw x ph píxeis: nome, proporção mostrada e tamanho da fotografia na parede (m).</summary>
    public static (string name, float shown, float w, float h) FrameSize(int pw, int ph)
    {
        float a = Mathf.Log(pw / (float)ph);
        var f = Formats.OrderBy(x => Mathf.Abs(Mathf.Log(x.aspect) - a)).First();  // mais parecida em proporção (log: 2:1 e 1:2 contam igual)
        float k = Mathf.Clamp(Mathf.Max(pw, ph) / (float)LowResPx, 0.55f, 1f);
        return (f.name, f.aspect, f.w * k, f.w / f.aspect * k);
    }

    /// <summary>Pendura a fotografia na moldura de formato mais parecido (o molde esticado a esse tamanho).</summary>
    public void Hang(Area area, Transform slot, Coll c, int photo, byte[] bytes)
    {
        string file = $"{c.id}/{c.files[photo]}";
        if (bytes.Length > MaxBytes) { Debug.LogWarning($"[MuseumBuilder] {file}: ficheiro grande demais"); return; }
        var src = new Texture2D(2, 2);
        if (!src.LoadImage(bytes) || src.width < MinPx || src.height < MinPx)
        {
            Debug.LogWarning($"[MuseumBuilder] {file}: imagem inválida ou minúscula");
            Kill(src);
            return;
        }
        float a = src.width / (float)src.height;
        var (format, shown, w, h) = FrameSize(src.width, src.height);
        var tex = Shrink(src);
        Kill(src);

        var f = Instantiate(frame, slot);
        Place(f.transform, slot.TransformPoint(framePos), slot.rotation * frameRot);
        var photoR = f.GetComponentsInChildren<MeshRenderer>().First(r => r.name.StartsWith("Photo_"));
        var frameR = f.GetComponentsInChildren<MeshRenderer>().First(r => r.name.StartsWith("Frame_"));
        var inner = photoR.GetComponent<MeshFilter>().sharedMesh.bounds.extents;  // metade da fotografia da moldura original
        float ow = Mathf.Max(inner.x, inner.y, inner.z), oh = inner.x + inner.y + inner.z - ow - Mathf.Min(inner.x, inner.y, inner.z);
        foreach (var r in new[] { photoR, frameR })
        {
            var mesh = Resize(r.GetComponent<MeshFilter>().sharedMesh, ow, oh, w / 2, h / 2);
            r.GetComponent<MeshFilter>().sharedMesh = mesh;
            area.hung.Add(mesh);
        }
        frameR.gameObject.AddComponent<BoxCollider>();  // toma o tamanho da malha nova; FrameInfo está no pai

        var m = new Material(photoMaterial) { mainTexture = tex };
        if (a > shown) { m.mainTextureScale = new Vector2(shown / a, 1); m.mainTextureOffset = new Vector2((1 - shown / a) / 2, 0); }
        else if (a < shown) { m.mainTextureScale = new Vector2(1, a / shown); m.mainTextureOffset = new Vector2(0, (1 - a / shown) / 2); }
        photoR.sharedMaterial = m;
        area.hung.Add(f);
        area.hung.Add(m);
        area.hung.Add(tex);

        var info = f.GetComponent<FrameInfo>();
        info.title = $"{c.title} — {photo + 1} de {c.files.Length}";
        info.category = $"Moldura {format}";
        info.description = $"{c.files[photo]}, {c.title}. Original {Mathf.RoundToInt(a * 100) / 100f}:1"
                           + (Mathf.Abs(a / shown - 1) < 0.02f ? "." : ", cortada ao centro para caber na moldura.");
    }

    /// <summary>
    /// Cópia da malha com a abertura da fotografia de ow x oh para nw x nh (metades), sem mudar a grossura da madeira:
    /// vértices na abertura ou fora dela andam o mesmo que a borda. Eixos tirados das próprias medidas (largura > altura > fundo).
    /// </summary>
    static Mesh Resize(Mesh src, float ow, float oh, float nw, float nh)
    {
        var e = src.bounds.extents;
        int[] order = { 0, 1, 2 };
        System.Array.Sort(order, (i, j) => e[j].CompareTo(e[i]));
        int wa = order[0], ha = order[1];
        var v = src.vertices;
        for (int i = 0; i < v.Length; i++)
        {
            v[i][wa] = Move(v[i][wa], ow, nw);
            v[i][ha] = Move(v[i][ha], oh, nh);
        }
        var m = Instantiate(src);
        m.vertices = v;
        m.RecalculateBounds();
        return m;
    }

    static float Move(float x, float old, float now) =>
        Mathf.Abs(x) >= old - 1e-4f ? Mathf.Sign(x) * (Mathf.Abs(x) - old + now) : x * now / old;

    // shortcut: RenderTexture perde o conteúdo se o Android destruir o contexto gráfico (raro); passar a Texture2D se acontecer.
    static Texture Shrink(Texture2D src)
    {
        float s = Mathf.Min(1f, PhotoMaxPx / (float)Mathf.Max(src.width, src.height));
        var rt = new RenderTexture(Mathf.Max(1, Mathf.RoundToInt(src.width * s)), Mathf.Max(1, Mathf.RoundToInt(src.height * s)), 0)
        { useMipMap = true, autoGenerateMips = true, filterMode = FilterMode.Trilinear, wrapMode = TextureWrapMode.Clamp };
        Graphics.Blit(src, rt);
        return rt;
    }

    Transform Spawn(GameObject prefab, Vector3 pos, Quaternion rot)
    {
        var t = Instantiate(prefab, transform).transform;
        Place(t, pos, rot);
        return t;
    }

    /// <summary>Põe a instância de forma a que o nó do Blender (único filho da raiz do FBX) fique na pose dada.</summary>
    static void Place(Transform inst, Vector3 pos, Quaternion rot)
    {
        var inner = inst.GetChild(0);
        var r = rot * Quaternion.Inverse(inner.localRotation);
        inst.SetPositionAndRotation(pos - r * inner.localPosition, r);
    }

    static Transform Find(Transform root, string suffix) =>
        root.GetComponentsInChildren<Transform>(true).First(t => t.name.EndsWith(suffix));

    static void Keep(Transform root, string suffix, bool keep)
    {
        if (!keep) Kill(Find(root, suffix).gameObject);
    }

    static void Kill(Object o)
    {
        if (Application.isPlaying) Destroy(o);
        else DestroyImmediate(o);
    }

    /// <summary>Slots (empties com a propriedade "slot") pela ordem do nome: 01, 02, ...</summary>
    static List<Transform> Slots(Transform root) =>
        root.GetComponentsInChildren<BlenderProps>(true).Where(p => !string.IsNullOrEmpty(p.slot))
            .OrderBy(p => p.slot, System.StringComparer.Ordinal).Select(p => p.transform).ToList();

    /// <summary>"fotos_atoa_2" -> "Fotos atoa 2" (igual a collectionTitle() na app).</summary>
    public static string Title(string id)
    {
        var s = id.Replace('_', ' ');
        return s.Length == 0 ? s : char.ToUpper(s[0]) + s.Substring(1);
    }

    public static string EditorAssets => Path.GetFullPath(Path.Combine(Application.dataPath, "..", "..", "app-android", "app", "src", "main", "assets"));

    public static List<Coll> Collections()
    {
        string[] chosen = null;
        System.Func<string, string[]> list;
#if UNITY_ANDROID && !UNITY_EDITOR
        var activity = new AndroidJavaClass("com.unity3d.player.UnityPlayer").GetStatic<AndroidJavaObject>("currentActivity");
        var intent = activity.Call<AndroidJavaObject>("getIntent");
        if (intent != null && intent.Call<bool>("hasExtra", "collections"))
            chosen = intent.Call<string[]>("getStringArrayExtra", "collections");
        var assets = activity.Call<AndroidJavaObject>("getAssets");
        list = p => assets.Call<string[]>("list", p) ?? new string[0];
#else
        list = p =>
        {
            var d = Path.Combine(EditorAssets, p);
            return Directory.Exists(d) ? Directory.GetFileSystemEntries(d).Select(Path.GetFileName).ToArray() : new string[0];
        };
#endif
        var ids = chosen ?? list(Dir).OrderBy(x => x, System.StringComparer.Ordinal).ToArray();
        return ids.Select(id => new Coll
        {
            id = id,
            title = Title(id),
            files = list($"{Dir}/{id}").Where(f => f.EndsWith(".jpg") || f.EndsWith(".jpeg") || f.EndsWith(".png"))
                .OrderBy(x => x, System.StringComparer.Ordinal).ToArray(),
        }).Where(c => c.files.Length > 0).ToList();
    }
}
