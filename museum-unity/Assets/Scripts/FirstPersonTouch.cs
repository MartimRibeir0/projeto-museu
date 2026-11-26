using UnityEngine;

/// <summary>
/// Navegação na 1.ª pessoa (T038). Telemóvel: arrastar na metade esquerda anda (joystick virtual a partir de onde
/// o dedo tocou), arrastar na metade direita olha. Editor/PC: WASD ou setas, e botão direito do rato para olhar.
/// Comando (Pad): stick esquerdo anda, direito olha. Em RV (VrMode) a cabeça é o giroscópio: anda-se para onde se
/// olha, mais devagar, e o stick direito vira o corpo aos saltos de 30° (menos enjoo que rodar contínuo).
/// As colisões são do CharacterController contra os MeshCollider das paredes.
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
    Vector2 moveOrigin;

    void Awake()
    {
        controller = GetComponent<CharacterController>();
        if (cameraPivot == null) cameraPivot = GetComponentInChildren<Camera>().transform;
    }

    void Update()
    {
        Vector2 move = Vector2.zero, look = Vector2.zero;
        float pxPerInch = Screen.dpi > 0 ? Screen.dpi : 160f;

        foreach (var t in Input.touches)
        {
            if (VrMode.Active) break;  // em RV o toque é o gatilho dos óculos (selecionar), não andar/olhar
            if (t.phase == TouchPhase.Began)
            {
                if (t.position.x < Screen.width / 2f && moveFinger < 0) { moveFinger = t.fingerId; moveOrigin = t.position; }
                else if (t.position.x >= Screen.width / 2f && lookFinger < 0) lookFinger = t.fingerId;
            }
            bool ended = t.phase == TouchPhase.Ended || t.phase == TouchPhase.Canceled;
            if (t.fingerId == moveFinger)
            {
                move = Vector2.ClampMagnitude((t.position - moveOrigin) / (pxPerInch * joystickInches), 1f);
                if (ended) moveFinger = -1;
            }
            else if (t.fingerId == lookFinger)
            {
                look += t.deltaPosition;
                if (ended) lookFinger = -1;
            }
        }

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
}
