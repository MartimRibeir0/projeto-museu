using UnityEngine;
using UnityEngine.InputSystem;

/// <summary>
/// Navegação na 1.ª pessoa (T038). Telemóvel: arrastar na metade esquerda anda (joystick virtual a partir de onde
/// o dedo tocou), arrastar na metade direita olha. Editor/PC: WASD ou setas, e botão direito do rato para olhar.
/// Comando (Pad): stick esquerdo anda, direito olha. Em RV (VrMode) a cabeça é o giroscópio: anda-se para onde se
/// olha, mais devagar, e o stick direito vira o corpo aos saltos de 30° (menos enjoo que rodar contínuo).
/// As colisões são do CharacterController contra os MeshCollider das paredes.
/// Toques lidos pelo Input System (Touchscreen) e não por Input.touches: na UnityPlayerGameActivity o Input antigo
/// só garantia um dedo, e assim não dava para andar e olhar ao mesmo tempo.
/// </summary>
[RequireComponent(typeof(CharacterController))]
public class FirstPersonTouch : MonoBehaviour
{
    public Transform cameraPivot;
    [Tooltip("m/s")] public float speed = 3f;
    [Tooltip("graus por pixel arrastado")] public float lookSpeed = 0.15f;
    [Tooltip("distância do dedo (em polegadas) que dá velocidade máxima")] public float joystickInches = 0.5f;
    [Tooltip("graus/s com o stick direito no máximo")] public float stickTurnSpeed = 120f;
    [Tooltip("m/s em RV (um pouco mais devagar: conforto)")] public float vrSpeed = 2.2f;
    [Tooltip("graus por salto ao virar em RV")] public float snapTurn = 30f;

    CharacterController controller;
    float pitch, fallSpeed;
    bool snapHeld;
    int moveFinger = -1, lookFinger = -1;
    Vector2 moveOrigin, moveNow;
    const float HintSeconds = 6f;  // segundos com a ajuda dos gestos no ecrã
    static Texture2D ring, dot;

    void Awake()
    {
        controller = GetComponent<CharacterController>();
        if (cameraPivot == null) cameraPivot = GetComponentInChildren<Camera>().transform;
    }

    void Update()
    {
        Vector2 move = Vector2.zero, look = Vector2.zero;
        float pxPerInch = Screen.dpi > 0 ? Screen.dpi : 160f;

        var screen = Touchscreen.current;
        if (screen != null && !VrMode.Active)  // em RV o toque é o gatilho dos óculos (selecionar), não andar/olhar
        {
            bool moveSeen = false, lookSeen = false;
            foreach (var t in screen.touches)
            {
                if (!t.press.isPressed) continue;
                int id = t.touchId.ReadValue();
                Vector2 pos = t.position.ReadValue();
                if (t.press.wasPressedThisFrame && !BackToApp.OverButton(pos))
                {
                    if (pos.x < Screen.width / 2f && moveFinger < 0) { moveFinger = id; moveOrigin = pos; }
                    else if (pos.x >= Screen.width / 2f && lookFinger < 0) lookFinger = id;
                }
                if (id == moveFinger)
                {
                    moveSeen = true;
                    moveNow = pos;
                    move = Vector2.ClampMagnitude((pos - moveOrigin) / (pxPerInch * joystickInches), 1f);
                }
                else if (id == lookFinger)
                {
                    lookSeen = true;
                    look += t.delta.ReadValue();
                }
            }
            if (!moveSeen) moveFinger = -1;
            if (!lookSeen) lookFinger = -1;
        }
        else moveFinger = lookFinger = -1;

        move += new Vector2(Input.GetAxisRaw("Horizontal"), Input.GetAxisRaw("Vertical")) + Pad.Move;
        if (Input.GetMouseButton(1)) look += new Vector2(Input.GetAxis("Mouse X"), Input.GetAxis("Mouse Y")) * 10f;

        Vector3 forward;
        if (VrMode.Active)
        {
            float x = Pad.Look.x;
            if (Mathf.Abs(x) > 0.7f && !snapHeld) { transform.Rotate(0f, Mathf.Sign(x) * snapTurn, 0f); snapHeld = true; }
            else if (Mathf.Abs(x) < 0.3f) snapHeld = false;
            forward = Vector3.ProjectOnPlane(cameraPivot.forward, Vector3.up).normalized;  // anda para onde olha
        }
        else
        {
            look += Pad.Look * (stickTurnSpeed * Time.deltaTime / lookSpeed);
            transform.Rotate(0f, look.x * lookSpeed, 0f);
            pitch = Mathf.Clamp(pitch - look.y * lookSpeed, -60f, 60f);
            cameraPivot.localEulerAngles = new Vector3(pitch, 0f, 0f);
            forward = transform.forward;
        }

        fallSpeed = controller.isGrounded ? -1f : fallSpeed + Physics.gravity.y * Time.deltaTime;
        Vector3 v = Vector3.Cross(Vector3.up, forward) * move.x + forward * move.y;
        v = Vector3.ClampMagnitude(v, 1f) * (VrMode.Active ? vrSpeed : speed);
        v.y = fallSpeed;
        controller.Move(v * Time.deltaTime);
    }

    // Joystick visível onde o dedo tocou (base + botão) e, ao entrar, uma ajuda curta dos gestos.
    void OnGUI()
    {
        if (VrMode.Active || !Input.touchSupported) return;
        float dp = Screen.dpi > 0 ? Screen.dpi / 160f : 1f;
        if (moveFinger >= 0)
        {
            ring ??= Circle(128, 0.06f);
            dot ??= Circle(64, 1f);
            float r = (Screen.dpi > 0 ? Screen.dpi : 160f) * joystickInches;
            Vector2 o = new Vector2(moveOrigin.x, Screen.height - moveOrigin.y);
            Vector2 k = new Vector2(moveNow.x, Screen.height - moveNow.y);
            k = o + Vector2.ClampMagnitude(k - o, r);
            GUI.color = new Color(1f, 1f, 1f, 0.35f);
            GUI.DrawTexture(new Rect(o.x - r, o.y - r, 2 * r, 2 * r), ring);
            GUI.color = new Color(1f, 1f, 1f, 0.6f);
            GUI.DrawTexture(new Rect(k.x - 28 * dp, k.y - 28 * dp, 56 * dp, 56 * dp), dot);
            GUI.color = Color.white;
        }
        if (Time.timeSinceLevelLoad < HintSeconds)
        {
            var style = new GUIStyle(GUI.skin.box) { fontSize = Mathf.RoundToInt(15 * dp), wordWrap = true };
            float w = Mathf.Min(Screen.width - 32 * dp, 520 * dp), h = 56 * dp;
            GUI.Box(new Rect((Screen.width - w) / 2, Screen.height - h - 24 * dp, w, h),
                "Dedo à esquerda: andar  ·  dedo à direita: olhar\nUsa os dois ao mesmo tempo · toca num quadro para o ver", style);
        }
    }

    /// <summary>Círculo branco com borda suave; thickness = fração do raio (1 = cheio, menos = anel).</summary>
    static Texture2D Circle(int size, float thickness)
    {
        var tex = new Texture2D(size, size, TextureFormat.RGBA32, false);
        float c = (size - 1) / 2f;
        for (int y = 0; y < size; y++)
        for (int x = 0; x < size; x++)
        {
            float d = Vector2.Distance(new Vector2(x, y), new Vector2(c, c)) / c;  // 0 no centro, 1 na borda
            float a = Mathf.Clamp01((1f - d) * c) * Mathf.Clamp01((d - (1f - thickness)) * c + 1f);
            tex.SetPixel(x, y, new Color(1f, 1f, 1f, a));
        }
        tex.Apply();
        return tex;
    }
}
