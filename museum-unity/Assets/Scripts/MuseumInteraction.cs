using UnityEngine;

/// <summary>
/// Selecionar quadros e botões globais (T039, T123).
/// Sem RV: toque curto no quadro (ou clique no Editor). Em RV: olhar para o quadro (retícula) e tocar no ecrã
/// (gatilho do Cardboard) ou A no comando. B / recuar: fecha o painel, depois sai do RV, depois volta à app.
/// </summary>
public class MuseumInteraction : MonoBehaviour
{
    public Transform head;
    public Camera monoCamera;
    public PhotoPanel panel;
    public Transform reticle;
    [Tooltip("alcance para selecionar, em metros")] public float reach = 6f;

    const float TapSeconds = 0.3f, TapInches = 0.12f;
    readonly float[] touchStart = new float[10];
    readonly Vector2[] touchFrom = new Vector2[10];

    void Update()
    {
        var vr = VrMode.Instance;
        if (Pad.ToggleVr) vr.Set(!VrMode.Active);
        if (Pad.Recenter && VrMode.Active) vr.Recenter();

        if (Pad.Back || Input.GetKeyDown(KeyCode.Escape))
        {
            if (panel.IsOpen) panel.Close();
            else if (VrMode.Active) vr.Set(false);
            else BackToApp.Back();
        }

        if (Pad.Select || (VrMode.Active && AnyTouchBegan()))
            Select(new Ray(head.position, head.forward));
        else if (!VrMode.Active && Tapped(out var p) && !BackToApp.OverButton(p))
            Select(monoCamera.ScreenPointToRay(p));

        reticle.gameObject.SetActive(VrMode.Active);
        if (VrMode.Active)
            reticle.localScale = Vector3.one * (FrameAt(new Ray(head.position, head.forward), out _) ? 0.025f : 0.012f);

        if (panel.IsOpen && Vector3.Distance(head.position, panel.transform.position) > 2.5f) panel.Close();
    }

    void Select(Ray ray)
    {
        if (panel.IsOpen) { panel.Close(); return; }
        var f = FrameAt(ray, out float dist);
        if (f != null) panel.Show(f, head, dist);
    }

    FrameInfo FrameAt(Ray ray, out float dist)
    {
        dist = 0f;
        if (!Physics.Raycast(ray, out var hit, reach)) return null;
        dist = hit.distance;
        return hit.collider.GetComponentInParent<FrameInfo>();
    }

    static bool AnyTouchBegan()
    {
        foreach (var t in Input.touches) if (t.phase == TouchPhase.Began) return true;
        return false;
    }

    /// <summary>Toque curto e quase parado (não conta arrastar para andar/olhar).</summary>
    bool Tapped(out Vector2 pos)
    {
        pos = default;
        float px = (Screen.dpi > 0 ? Screen.dpi : 160f) * TapInches;
        foreach (var t in Input.touches)
        {
            if (t.fingerId >= touchStart.Length) continue;
            if (t.phase == TouchPhase.Began) { touchStart[t.fingerId] = Time.unscaledTime; touchFrom[t.fingerId] = t.position; }
            else if (t.phase == TouchPhase.Ended && Time.unscaledTime - touchStart[t.fingerId] < TapSeconds
                     && Vector2.Distance(t.position, touchFrom[t.fingerId]) < px)
            {
                pos = t.position;
                return true;
            }
        }
        if (!Input.touchSupported && Input.GetMouseButtonDown(0)) { pos = Input.mousePosition; return true; }
        return false;
    }
}
