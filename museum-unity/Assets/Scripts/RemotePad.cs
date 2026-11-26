using System;
using System.Collections.Generic;
using System.Linq;
using System.Net;
using System.Net.Sockets;
using UnityEngine;

/// <summary>
/// Outro telemóvel como comando (sem comando Xbox): o museu abre um servidor na rede local e mostra um link
/// para enviar ao outro telemóvel, que o abre no browser (página em Resources/remote.html).
/// Os dois têm de estar na mesma rede Wi-Fi. O link leva um token: sem ele, o servidor recusa o comando.
/// Link único: o token vem da app (extra "remoteToken", sempre o mesmo) e o servidor arranca com o museu, por isso
/// o link enviado uma vez continua a servir e a página do comando volta a ligar-se sozinha.
/// Corre antes dos outros scripts para que Pad já tenha o estado deste frame.
/// </summary>
[DefaultExecutionOrder(-100)]
public class RemotePad : MonoBehaviour
{
    public const int Port = 47615;  // 8765 colidia com o painel de PC por USB (adb reverse)
    const float TimeoutSeconds = 1f;  // sem pacotes há mais que isto: considera desligado e pára o visitante

    public static RemotePad Instance { get; private set; }

    public string Url { get; private set; }
    public string Error { get; private set; }
    public bool PairingOpen { get; set; }
    public bool Running => server != null;
    public bool Connected => server != null && Time.unscaledTime - lastSeen < TimeoutSeconds;

    public Vector2 Move { get; private set; }
    public Vector2 Look { get; private set; }
    public bool Select { get; private set; }
    public bool Back { get; private set; }
    public bool ToggleVr { get; private set; }
    public bool Recenter { get; private set; }

    RemoteServer server;
    RemoteState prev;
    int lastReceived;
    float lastSeen = -10f;

    [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
    static void Create()
    {
        var go = new GameObject(nameof(RemotePad));
        DontDestroyOnLoad(go);
        go.AddComponent<RemotePad>().StartServer();  // já à escuta: o comando liga-se sem abrir o painel
    }

    /// <summary>Token da app (o mesmo que vai no link partilhado lá); sem app, um guardado neste telemóvel.</summary>
    static string LoadToken()
    {
#if UNITY_ANDROID && !UNITY_EDITOR
        using (var player = new AndroidJavaClass("com.unity3d.player.UnityPlayer"))
        using (var activity = player.GetStatic<AndroidJavaObject>("currentActivity"))
        using (var intent = activity.Call<AndroidJavaObject>("getIntent"))
        {
            string fromApp = intent?.Call<string>("getStringExtra", "remoteToken");
            if (!string.IsNullOrEmpty(fromApp)) return fromApp;
        }
#endif
        string saved = PlayerPrefs.GetString("remoteToken", "");
        if (saved.Length == 0)
        {
            saved = Guid.NewGuid().ToString("N").Substring(0, 10);
            PlayerPrefs.SetString("remoteToken", saved);
            PlayerPrefs.Save();
        }
        return saved;
    }

    void Awake() => Instance = this;

    void OnDestroy() => server?.Stop();

    /// <summary>Outros endereços possíveis (p. ex. Wi-Fi e hotspot ao mesmo tempo), para tentar se o 1.º não abrir.</summary>
    public List<string> OtherUrls { get; } = new List<string>();

    string token;

    /// <summary>
    /// Este telemóvel está a fazer hotspot: o Android não deixa os telemóveis ligados a ele chegar às apps
    /// (visto num Samsung A55 / Android 17: o ping responde, as ligações à porta não). O hotspot tem de ser o outro.
    /// </summary>
    public bool Hotspot { get; private set; }

    static bool IsHotspotHost() => Interfaces().Any(i =>
        (i.name.StartsWith("swlan") || i.name.StartsWith("ap") || i.name.StartsWith("softap")) && IsPrivate(i.ip));

    public const string HotspotWarning =
        "Este telemóvel está a fazer hotspot e assim o Android bloqueia o comando. " +
        "Liga o hotspot no telemóvel-comando (ou usa um Wi-Fi) e liga este telemóvel a essa rede.";

    /// <summary>Arranca o servidor (uma vez) e recalcula os links: a rede pode ter mudado desde a última vez.</summary>
    public void StartServer()
    {
        Error = null;
        if (server == null)
        {
            try
            {
                token = LoadToken();
                server = new RemoteServer(Resources.Load<TextAsset>("remote").text, token, Port);
            }
            catch (Exception e)
            {
                Error = $"Não foi possível abrir o comando ({e.Message}).";
                return;
            }
        }
        Hotspot = IsHotspotHost();
        var ips = LocalIps();
        OtherUrls.Clear();
        Url = null;
        if (ips.Count == 0) { Error = "Sem rede local: liga o Wi-Fi ou o hotspot (a mesma rede do telemóvel-comando)."; return; }
        Url = $"http://{ips[0]}:{server.Port}/?t={token}";
        for (int i = 1; i < ips.Count; i++) OtherUrls.Add($"http://{ips[i]}:{server.Port}/?t={token}");
    }

    void Update()
    {
        Select = Back = ToggleVr = Recenter = false;
        if (server == null) return;
        int n = server.Read(out var s);
        if (n != lastReceived && s != null)
        {
            lastReceived = n;
            lastSeen = Time.unscaledTime;
            if (prev != null)  // ">" e não "!=": recarregar a página põe os contadores a 0 sem carregar em nada
            {
                Select = s.a > prev.a;
                Back = s.b > prev.b;
                ToggleVr = s.menu > prev.menu;
                Recenter = s.view > prev.view;
            }
            prev = s;
            Move = Vector2.ClampMagnitude(new Vector2(s.mx, s.my), 1f);
            Look = Vector2.ClampMagnitude(new Vector2(s.lx, s.ly), 1f);
        }
        if (!Connected) Move = Look = Vector2.zero;
    }

    /// <summary>
    /// IPs desta máquina nas redes locais (Wi-Fi primeiro, depois hotspot), sem os dados móveis.
    /// Não serve a rota para a internet: com hotspot ligado ou Wi-Fi sem internet ela sai pelos dados móveis.
    /// </summary>
    public static List<string> LocalIps()
    {
        var found = new List<(int rank, string ip)>();
        foreach (var (name, ip) in Interfaces())
        {
            int rank = Rank(name);
            if (rank >= 0 && IsPrivate(ip)) found.Add((rank, ip));
        }
        return found.OrderBy(f => f.rank).Select(f => f.ip).Distinct().ToList();
    }

    /// <summary>Preferência pelo nome da interface; -1 = ignorar (dados móveis, VPN, ...).</summary>
    public static int Rank(string name)
    {
        name = name.ToLowerInvariant();
        string[] skip = { "rmnet", "ccmni", "clat", "v4-", "pdp", "tun", "ppp", "dummy", "lo", "ims", "rev_rmnet" };
        if (skip.Any(name.StartsWith)) return -1;
        if (name == "wlan0") return 0;                                   // Wi-Fi normal (cliente)
        if (name.StartsWith("ap") || name.StartsWith("swlan") || name.StartsWith("softap") || name.StartsWith("wlan")) return 1;  // hotspot
        if (name.StartsWith("eth") || name.StartsWith("en")) return 2;   // cabo / PC no Editor
        return 3;
    }

    public static bool IsPrivate(string ip)
    {
        if (!IPAddress.TryParse(ip, out var a) || a.AddressFamily != AddressFamily.InterNetwork) return false;
        var b = a.GetAddressBytes();
        return b[0] == 10 || (b[0] == 172 && b[1] >= 16 && b[1] <= 31) || (b[0] == 192 && b[1] == 168);
    }

    static IEnumerable<(string name, string ip)> Interfaces()
    {
        var list = new List<(string, string)>();
#if UNITY_ANDROID && !UNITY_EDITOR
        // API de Java: a do .NET (netlink) falha nas versões recentes do Android.
        using var niClass = new AndroidJavaClass("java.net.NetworkInterface");
        using var all = niClass.CallStatic<AndroidJavaObject>("getNetworkInterfaces");
        while (all != null && all.Call<bool>("hasMoreElements"))
        {
            using var ni = all.Call<AndroidJavaObject>("nextElement");
            if (!ni.Call<bool>("isUp") || ni.Call<bool>("isLoopback")) continue;
            string name = ni.Call<string>("getName");
            using var addrs = ni.Call<AndroidJavaObject>("getInetAddresses");
            while (addrs.Call<bool>("hasMoreElements"))
            {
                using var a = addrs.Call<AndroidJavaObject>("nextElement");
                string host = a.Call<string>("getHostAddress");
                if (!host.Contains(":")) list.Add((name, host));
            }
        }
#else
        foreach (var ni in System.Net.NetworkInformation.NetworkInterface.GetAllNetworkInterfaces())
        {
            if (ni.OperationalStatus != System.Net.NetworkInformation.OperationalStatus.Up) continue;
            foreach (var u in ni.GetIPProperties().UnicastAddresses)
                if (u.Address.AddressFamily == AddressFamily.InterNetwork) list.Add((ni.Name, u.Address.ToString()));
        }
#endif
        return list;
    }

    // ---------- painel de emparelhar (fora do RV) ----------

    static float Dp => Screen.dpi > 0 ? Screen.dpi / 160f : 1f;

    public Rect PanelRect
    {
        get
        {
            float w = Mathf.Min(Screen.width - 32 * Dp, 620 * Dp), h = Mathf.Min(Screen.height - 32 * Dp, 380 * Dp);
            return new Rect((Screen.width - w) / 2, (Screen.height - h) / 2, w, h);
        }
    }

    void OnGUI()
    {
        if (!PairingOpen || VrMode.Active) return;
        var label = new GUIStyle(GUI.skin.label) { fontSize = Mathf.RoundToInt(15 * Dp), wordWrap = true };
        var big = new GUIStyle(label) { fontSize = Mathf.RoundToInt(18 * Dp), fontStyle = FontStyle.Bold };
        var button = new GUIStyle(GUI.skin.button) { fontSize = Mathf.RoundToInt(15 * Dp) };
        float bh = 44 * Dp;

        var r = PanelRect;
        GUI.Box(r, GUIContent.none);
        GUI.Box(r, GUIContent.none);  // duas vezes: o fundo por omissão é transparente demais
        GUILayout.BeginArea(new Rect(r.x + 16 * Dp, r.y + 12 * Dp, r.width - 32 * Dp, r.height - 24 * Dp));
        GUILayout.Label("Usar outro telemóvel como comando", big);
        if (Hotspot)
        {
            var warn = new GUIStyle(label) { fontStyle = FontStyle.Bold };
            warn.normal.textColor = new Color(1f, 0.75f, 0.3f);
            GUILayout.Label(HotspotWarning, warn);
        }
        if (Error != null)
        {
            GUILayout.Label(Error, label);
        }
        else
        {
            GUILayout.Label("1. Os dois telemóveis na mesma rede (o mesmo Wi-Fi, ou um ligado ao hotspot do outro).\n" +
                            "2. Envia este link para o outro telemóvel e abre-o no browser:", label);
            GUILayout.Label(Url, big);
            if (OtherUrls.Count > 0)
                GUILayout.Label("Se não abrir, experimenta: " + string.Join("  ou  ", OtherUrls), label);
            GUILayout.Label("3. Segura o telemóvel-comando na horizontal.", label);
            GUILayout.Label(Connected ? "Comando ligado ✓" : "À espera do comando…", big);
        }
        GUILayout.FlexibleSpace();
        GUILayout.BeginHorizontal();
        if (Url != null && GUILayout.Button("Partilhar link", button, GUILayout.Height(bh))) Share();
        if (Url != null && GUILayout.Button("Copiar", button, GUILayout.Height(bh))) GUIUtility.systemCopyBuffer = Url;
        if (Error != null && GUILayout.Button("Tentar outra vez", button, GUILayout.Height(bh))) StartServer();
        if (GUILayout.Button("Fechar", button, GUILayout.Height(bh))) PairingOpen = false;
        GUILayout.EndHorizontal();
        GUILayout.EndArea();
    }

    void Share()
    {
        string text = Url;  // só o link: assim abre direto ao tocar, sem texto à volta
#if UNITY_ANDROID && !UNITY_EDITOR
        using var intent = new AndroidJavaObject("android.content.Intent", "android.intent.action.SEND");
        intent.Call<AndroidJavaObject>("setType", "text/plain").Dispose();
        intent.Call<AndroidJavaObject>("putExtra", "android.intent.extra.TEXT", text).Dispose();
        using var intentClass = new AndroidJavaClass("android.content.Intent");
        using var chooser = intentClass.CallStatic<AndroidJavaObject>("createChooser", intent, "Enviar link do comando");
        using var player = new AndroidJavaClass("com.unity3d.player.UnityPlayer");
        using var activity = player.GetStatic<AndroidJavaObject>("currentActivity");
        activity.Call("startActivity", chooser);
#else
        GUIUtility.systemCopyBuffer = text;
#endif
    }
}
