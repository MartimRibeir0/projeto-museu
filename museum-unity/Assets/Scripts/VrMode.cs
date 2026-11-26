using UnityEngine;

/// <summary>
/// Modo RV para óculos tipo Cardboard (T122/T123): ecrã dividido em dois olhos e cabeça seguida pelo giroscópio.
/// Liga-se ao abrir pela app com o extra "vr" = true, pelo botão "Modo RV" ou pelo botão Menu do comando.
/// shortcut: sem correção da distorção das lentes nem perfil do visor (QR do Cardboard); passar ao Cardboard XR
/// Plugin da Google se as linhas direitas parecerem curvas nos óculos usados.
/// </summary>
public class VrMode : MonoBehaviour
{
    public Camera mono, left, right;
    public Transform head;

    public static bool Active { get; private set; }
    public static VrMode Instance { get; private set; }

    Quaternion offset = Quaternion.identity;
    float recenterAt = -1f;

    void Awake()
    {
        Instance = this;
        Set(LaunchedInVr());
    }

    public void Set(bool on)
    {
        Active = on;
        mono.enabled = !on;
        left.enabled = right.enabled = on;
        Input.gyro.enabled = on;
        Screen.sleepTimeout = on ? SleepTimeout.NeverSleep : SleepTimeout.SystemSetting;
        head.localRotation = Quaternion.identity;
        recenterAt = on ? Time.unscaledTime + 0.3f : -1f;  // o giroscópio só tem leitura válida passado um instante
    }

    /// <summary>A direção para onde a pessoa olha passa a ser a frente do corpo.</summary>
    public void Recenter() => offset = Quaternion.Euler(0f, -Gyro().eulerAngles.y, 0f);

    void LateUpdate()
    {
        if (!Active || !SystemInfo.supportsGyroscope) return;
        if (recenterAt > 0 && Time.unscaledTime >= recenterAt) { Recenter(); recenterAt = -1f; }
        head.localRotation = offset * Gyro();
    }

    /// <summary>Atitude do telemóvel (paisagem à esquerda, como o Unity está fixo) em coordenadas do Unity.</summary>
    static Quaternion Gyro()
    {
        var q = Input.gyro.attitude;
        return Quaternion.Euler(90f, 0f, 0f) * new Quaternion(q.x, q.y, -q.z, -q.w);
    }

    static bool LaunchedInVr()
    {
#if UNITY_ANDROID && !UNITY_EDITOR
        using var player = new AndroidJavaClass("com.unity3d.player.UnityPlayer");
        using var activity = player.GetStatic<AndroidJavaObject>("currentActivity");
        using var intent = activity.Call<AndroidJavaObject>("getIntent");
        return intent != null && intent.Call<bool>("getBooleanExtra", "vr", false);
#else
        return false;
#endif
    }
}
