using UnityEngine;

/// <summary>Propriedades personalizadas que vêm do Blender no FBX (ver blender/README.md).</summary>
public class BlenderProps : MonoBehaviour
{
    [Tooltip("ID do dispositivo IoT (contracts/v1.md); só nos objetos do gémeo digital.")]
    public string deviceId;

    [Tooltip("Largura/altura da fotografia; só nas molduras.")]
    public float aspect;

    [Tooltip("Identificador do slot de quadro no corredor, p. ex. M01_L.")]
    public string slot;
}
