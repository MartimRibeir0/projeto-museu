using UnityEngine;

/// <summary>Ficha de um quadro (T039). Vazia por agora: os dados reais vêm da API da exposição (T059/T062).</summary>
public class FrameInfo : MonoBehaviour
{
    public string title;
    public string category;
    [TextArea] public string description;

    public string Title => string.IsNullOrEmpty(title) ? $"Moldura {SlotName()}" : title;
    public string Category => string.IsNullOrEmpty(category) ? Shape() : category;
    public string Description => string.IsNullOrEmpty(description)
        ? "Ainda sem fotografia. As fotografias da exposição chegam da app (API, T059)."
        : description;

    string SlotName()
    {
        var p = transform.parent;
        if (p == null) return name;
        var props = p.GetComponent<BlenderProps>();
        return props != null && !string.IsNullOrEmpty(props.slot) ? props.slot : p.name;
    }

    string Shape()
    {
        foreach (var p in GetComponentsInChildren<BlenderProps>())
            if (p.aspect > 0f) return p.aspect > 1.05f ? "Horizontal" : p.aspect < 0.95f ? "Vertical" : "Quadrada";
        return "";
    }
}
