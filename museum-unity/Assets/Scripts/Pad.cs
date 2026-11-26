using UnityEngine;
using UnityEngine.InputSystem;

/// <summary>
/// Comando unificado: comando de jogo (Xbox ou outro, por Bluetooth/USB, pelo Input System) e/ou outro telemóvel
/// como comando (RemotePad). Os dois somam-se; sem nenhum ligado, tudo vale zero/false.
///   Stick esquerdo: andar · Stick direito: olhar (em RV: virar 30°) · A: selecionar quadro · B: fechar/voltar
///   Menu (☰): ligar/desligar RV · Ver (⧉): recentrar a vista em RV
/// </summary>
public static class Pad
{
    static Gamepad G => Gamepad.current;
    static RemotePad R => RemotePad.Instance;

    public static Vector2 Move => Vector2.ClampMagnitude((G != null ? G.leftStick.ReadValue() : Vector2.zero) + (R != null ? R.Move : Vector2.zero), 1f);
    public static Vector2 Look => Vector2.ClampMagnitude((G != null ? G.rightStick.ReadValue() : Vector2.zero) + (R != null ? R.Look : Vector2.zero), 1f);
    public static bool Select => (G != null && G.buttonSouth.wasPressedThisFrame) || (R != null && R.Select);
    public static bool Back => (G != null && G.buttonEast.wasPressedThisFrame) || (R != null && R.Back);
    public static bool ToggleVr => (G != null && G.startButton.wasPressedThisFrame) || (R != null && R.ToggleVr);
    public static bool Recenter => (G != null && G.selectButton.wasPressedThisFrame) || (R != null && R.Recenter);
}
