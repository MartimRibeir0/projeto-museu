using System.Text;
using UnityEngine;

/// <summary>
/// Painel da fotografia (T039), no espaço 3D para se ver também em RV (a UI de ecrã não aparece nos dois olhos).
/// Abre à frente do visitante, virado para ele; fecha com toque, A, B ou ao afastar-se.
/// </summary>
public class PhotoPanel : MonoBehaviour
{
    public TextMesh title, body;
    public bool IsOpen => gameObject.activeSelf;

    public void Show(FrameInfo f, Transform head, float hitDistance)
    {
        title.text = Wrap(f.Title, 26);
        body.text = Wrap(string.IsNullOrEmpty(f.Category) ? f.Description : $"{f.Category}\n\n{f.Description}", 40);
        var fwd = Vector3.ProjectOnPlane(head.forward, Vector3.up).normalized;
        float d = Mathf.Clamp(hitDistance - 0.15f, 0.5f, 0.9f);  // à frente do quadro, nunca dentro da parede
        var pos = head.position + fwd * d + Vector3.down * 0.3f;  // abaixo do olhar: a fotografia fica à vista
        transform.SetPositionAndRotation(pos, Quaternion.LookRotation(fwd));
        gameObject.SetActive(true);
    }

    public void Close() => gameObject.SetActive(false);

    /// <summary>TextMesh não faz quebra de linha.</summary>
    static string Wrap(string text, int width)
    {
        var sb = new StringBuilder();
        foreach (var para in text.Split('\n'))
        {
            int line = 0;
            foreach (var word in para.Split(' '))
            {
                if (line > 0 && line + 1 + word.Length > width) { sb.Append('\n'); line = 0; }
                else if (line > 0) { sb.Append(' '); line++; }
                sb.Append(word);
                line += word.Length;
            }
            sb.Append('\n');
        }
        return sb.ToString().TrimEnd('\n');
    }
}
