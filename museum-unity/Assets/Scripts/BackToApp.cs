using UnityEngine;

/// <summary>
/// Botões no ecrã fora do RV: "Voltar" (regressa à app Kotlin, T014/T038) e "Modo RV".
/// Fecha só a atividade do Unity (que corre no processo ":unity"), por isso a app continua onde estava.
/// A tecla de recuar e o botão B tratam-se em MuseumInteraction. Cria-se sozinho ao arrancar.
/// </summary>
public class BackToApp : MonoBehaviour
{
    [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
    static void Create()
    {
        var go = new GameObject(nameof(BackToApp));
        DontDestroyOnLoad(go);
        go.AddComponent<BackToApp>();
    }

    static float Dp => Screen.dpi > 0 ? Screen.dpi / 160f : 1f;
    static Rect BackRect => new Rect(16 * Dp, 16 * Dp, 110 * Dp, 44 * Dp);
    static Rect VrRect => new Rect(Screen.width - 126 * Dp, 16 * Dp, 110 * Dp, 44 * Dp);
    static Rect PairRect => new Rect(Screen.width - 196 * Dp, 68 * Dp, 180 * Dp, 44 * Dp);

    /// <summary>Posição de ecrã (origem em baixo, como Input) sobre um botão ou sobre o painel de emparelhar.</summary>
    public static bool OverButton(Vector2 screenPos)
    {
        if (VrMode.Active) return false;
        var gui = new Vector2(screenPos.x, Screen.height - screenPos.y);
        var remote = RemotePad.Instance;
        return BackRect.Contains(gui) || VrRect.Contains(gui) || PairRect.Contains(gui) ||
               (remote != null && remote.PairingOpen && remote.PanelRect.Contains(gui));
    }

    void OnGUI()
    {
        if (VrMode.Active) return;  // UI de ecrã não se vê bem nos dois olhos; em RV usa-se recuar/B
        var style = new GUIStyle(GUI.skin.button) { fontSize = Mathf.RoundToInt(16 * Dp) };
        if (GUI.Button(BackRect, "Voltar", style)) Back();
        if (VrMode.Instance != null && GUI.Button(VrRect, "Modo RV", style)) VrMode.Instance.Set(true);
        var remote = RemotePad.Instance;
        if (remote != null && GUI.Button(PairRect, remote.Connected ? "Comando: ligado ✓" : "Comando telemóvel", style))
        {
            remote.StartServer();
            remote.PairingOpen = true;
        }
    }

    public static void Back()
    {
#if UNITY_ANDROID && !UNITY_EDITOR
        using var player = new AndroidJavaClass("com.unity3d.player.UnityPlayer");
        using var activity = player.GetStatic<AndroidJavaObject>("currentActivity");
        activity.Call("finish");
#else
        Debug.Log("[BackToApp] voltar à app");
#endif
    }
}
