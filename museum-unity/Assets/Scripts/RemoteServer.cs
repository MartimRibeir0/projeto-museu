using System;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading;
using UnityEngine;

/// <summary>Estado que a página do telemóvel-comando envia (Resources/remote.html).</summary>
[Serializable]
public class RemoteState
{
    public string t;                    // token do link
    public float mx, my, lx, ly;        // sticks, -1..1
    public int a, b, menu, view;        // contadores de toques
}

/// <summary>
/// Servidor HTTP mínimo, só para a rede local, numa thread própria: GET / devolve a página do comando,
/// POST /input recebe o estado. Sem HttpListener (no Android exige permissões e prefixos que falham).
/// </summary>
public class RemoteServer
{
    const int MaxBody = 2048;
    TcpListener listener;
    readonly byte[] page;
    readonly string token;
    readonly object gate = new object();
    RemoteState latest;
    int received;
    volatile bool running = true;

    /// <summary>Porta onde ficou a escutar (pode não ser a pedida).</summary>
    public int Port { get; }

    /// <summary>Tenta a porta pedida; se estiver ocupada (outra app, adb reverse...), usa uma livre qualquer.</summary>
    public RemoteServer(string html, string token, int port)
    {
        page = Encoding.UTF8.GetBytes(html);
        this.token = token;
        try
        {
            listener = new TcpListener(IPAddress.Any, port);
            listener.Start();
        }
        catch (SocketException)
        {
            listener = new TcpListener(IPAddress.Any, 0);
            listener.Start();
        }
        Port = ((IPEndPoint)listener.LocalEndpoint).Port;
        new Thread(Loop) { IsBackground = true, Name = "RemoteServer" }.Start();
    }

    /// <summary>Último estado recebido e quantos já chegaram (para saber se há novidades).</summary>
    public int Read(out RemoteState state)
    {
        lock (gate) { state = latest; return received; }
    }

    public void Stop()
    {
        running = false;
        listener.Stop();
    }

    void Loop()
    {
        while (running)
        {
            TcpClient client;
            try { client = listener.AcceptTcpClient(); }
            catch (SocketException) { if (!running) return; continue; }
            catch (ObjectDisposedException) { return; }
            // Cada ligação na sua thread: o Chrome abre ligações de reserva que não enviam nada; atendidas em fila,
            // prendiam o servidor e os pedidos verdadeiros ficavam sem resposta.
            ThreadPool.QueueUserWorkItem(_ =>
            {
                try
                {
                    using (client)
                    {
                        Handle(client);
                        // Fecho com calma: fechar logo a seguir a escrever pode cortar a resposta a meio.
                        client.Client.Shutdown(SocketShutdown.Send);
                        Thread.Sleep(50);
                    }
                }
                catch (Exception e) { Debug.LogWarning($"[RemoteServer] {e.Message}"); }
            });
        }
    }

    void Handle(TcpClient client)
    {
        client.ReceiveTimeout = client.SendTimeout = 3000;
        client.NoDelay = true;
        var stream = client.GetStream();
        stream.ReadTimeout = stream.WriteTimeout = 3000;

        var buf = new byte[8192];
        int n = 0, headerEnd;
        while ((headerEnd = HeaderEnd(buf, n)) < 0)
        {
            if (n == buf.Length) return;
            int r = stream.Read(buf, n, buf.Length - n);
            if (r <= 0) return;
            n += r;
        }
        var lines = Encoding.ASCII.GetString(buf, 0, headerEnd).Split(new[] { "\r\n" }, StringSplitOptions.None);
        var first = lines[0].Split(' ');
        if (first.Length < 2) return;
        string method = first[0], path = first[1];
        int q = path.IndexOf('?');
        if (q >= 0) path = path.Substring(0, q);

        int length = 0;
        foreach (var line in lines)
            if (line.StartsWith("Content-Length:", StringComparison.OrdinalIgnoreCase))
                int.TryParse(line.Substring(15).Trim(), out length);
        if (length < 0 || length > MaxBody) { Send(stream, 413, "text/plain", "too large"); return; }

        var body = new byte[length];
        int have = Math.Min(length, n - (headerEnd + 4));
        Array.Copy(buf, headerEnd + 4, body, 0, have);
        while (have < length)
        {
            int r = stream.Read(body, have, length - have);
            if (r <= 0) return;
            have += r;
        }

        if (method == "GET" && path == "/") { Send(stream, 200, "text/html; charset=utf-8", page); return; }
        if (method == "POST" && path == "/input")
        {
            RemoteState s;
            try { s = JsonUtility.FromJson<RemoteState>(Encoding.UTF8.GetString(body)); }
            catch (ArgumentException) { Send(stream, 400, "text/plain", "bad json"); return; }
            if (s == null || s.t != token) { Send(stream, 403, "text/plain", "token"); return; }
            lock (gate) { latest = s; received++; }
            Send(stream, 204, null, Array.Empty<byte>());
            return;
        }
        Send(stream, 404, "text/plain", "not found");
    }

    static int HeaderEnd(byte[] b, int n)
    {
        for (int i = 3; i < n; i++)
            if (b[i - 3] == '\r' && b[i - 2] == '\n' && b[i - 1] == '\r' && b[i] == '\n') return i - 3;
        return -1;
    }

    static void Send(NetworkStream s, int code, string type, string body) => Send(s, code, type, Encoding.UTF8.GetBytes(body));

    static void Send(NetworkStream s, int code, string type, byte[] body)
    {
        string reason = code switch { 200 => "OK", 204 => "No Content", 400 => "Bad Request", 403 => "Forbidden", 413 => "Payload Too Large", _ => "Not Found" };
        var head = $"HTTP/1.1 {code} {reason}\r\n" + (type != null ? $"Content-Type: {type}\r\n" : "") +
                   $"Content-Length: {body.Length}\r\nCache-Control: no-store\r\nConnection: close\r\n\r\n";
        var h = Encoding.ASCII.GetBytes(head);
        s.Write(h, 0, h.Length);
        s.Write(body, 0, body.Length);
    }
}
