using System;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading;
using UnityEditor;
using UnityEngine;

/// <summary>
/// Autoverificação do servidor do telemóvel-comando (RemoteServer) sem telemóvel:
///   Unity.exe -batchmode -quit -projectPath museum-unity -executeMethod RemoteServerCheck.Run -logFile -
/// </summary>
public static class RemoteServerCheck
{
    [MenuItem("Museu/Verificar servidor do comando")]
    public static void Run()
    {
        var html = File.ReadAllText("Assets/Resources/remote.html");
        int port = FreePort();
        var server = new RemoteServer(html, "tok123", port);
        try
        {
            var page = Request(port, "GET /?t=tok123 HTTP/1.1\r\nHost: x\r\n\r\n");
            Check(page.StartsWith("HTTP/1.1 200") && page.Contains("Roda o telemóvel para a horizontal"), "GET / devolve a página");

            Check(Post(port, "{\"t\":\"errado\",\"mx\":1}").StartsWith("HTTP/1.1 403"), "token errado é recusado");
            Check(server.Read(out _) == 0, "pedido recusado não conta");

            Check(Post(port, "{\"t\":\"tok123\",\"mx\":0.5,\"ly\":-1,\"a\":2}").StartsWith("HTTP/1.1 204"), "POST /input aceite");
            int n = server.Read(out var s);
            Check(n == 1 && Mathf.Approximately(s.mx, 0.5f) && Mathf.Approximately(s.ly, -1f) && s.a == 2, "estado lido");

            Check(Post(port, new string('x', 5000)).StartsWith("HTTP/1.1 413"), "corpo grande demais recusado");
            Check(Request(port, "GET /nada HTTP/1.1\r\n\r\n").StartsWith("HTTP/1.1 404"), "caminho desconhecido dá 404");

            // Ligações abertas sem enviar nada (o Chrome faz isto) não podem atrasar os outros pedidos.
            using (new TcpClient("127.0.0.1", port))
            using (new TcpClient("127.0.0.1", port))
            {
                Thread.Sleep(100);
                var sw = System.Diagnostics.Stopwatch.StartNew();
                Check(Request(port, "GET / HTTP/1.1\r\n\r\n").StartsWith("HTTP/1.1 200") && sw.ElapsedMilliseconds < 1000,
                      $"ligação parada não bloqueia as outras ({sw.ElapsedMilliseconds} ms)");
            }

            // Porta ocupada: o 2.º servidor tem de arrancar noutra porta e responder.
            var second = new RemoteServer(html, "tok2", port);
            try
            {
                Check(second.Port != port && second.Port > 0, "porta ocupada → outra porta");
                Check(Request(second.Port, "GET / HTTP/1.1\r\n\r\n").StartsWith("HTTP/1.1 200"), "servidor na porta alternativa responde");
            }
            finally { second.Stop(); }
            // Escolha do IP do link: Wi-Fi > hotspot; dados móveis e endereços públicos/CGNAT fora.
            Check(RemotePad.Rank("wlan0") < RemotePad.Rank("swlan0") && RemotePad.Rank("ap0") == RemotePad.Rank("wlan1"), "Wi-Fi antes do hotspot");
            Check(RemotePad.Rank("rmnet_data0") < 0 && RemotePad.Rank("ccmni1") < 0 && RemotePad.Rank("v4-rmnet0") < 0 && RemotePad.Rank("tun0") < 0, "dados móveis e VPN ignorados");
            Check(RemotePad.IsPrivate("192.168.43.1") && RemotePad.IsPrivate("10.105.2.7") && RemotePad.IsPrivate("172.20.10.1"), "redes privadas aceites");
            Check(!RemotePad.IsPrivate("100.72.3.4") && !RemotePad.IsPrivate("8.8.8.8") && !RemotePad.IsPrivate("172.32.0.1"), "CGNAT/públicos recusados");
            Check(RemotePad.LocalIps().Count > 0, "este PC tem pelo menos um IP de rede local");
            Debug.Log($"[RemoteServerCheck] ok (IPs deste PC: {string.Join(", ", RemotePad.LocalIps())})");
        }
        finally
        {
            server.Stop();
        }
    }

    static string Post(int port, string json) =>
        Request(port, $"POST /input HTTP/1.1\r\nHost: x\r\nContent-Type: text/plain\r\nContent-Length: {Encoding.UTF8.GetByteCount(json)}\r\n\r\n{json}");

    static string Request(int port, string raw)
    {
        using var c = new TcpClient("127.0.0.1", port);
        c.ReceiveTimeout = 3000;
        var stream = c.GetStream();
        var bytes = Encoding.UTF8.GetBytes(raw);
        stream.Write(bytes, 0, bytes.Length);
        using var reader = new StreamReader(stream, Encoding.UTF8);
        return reader.ReadToEnd();
    }

    static int FreePort()
    {
        var l = new TcpListener(IPAddress.Loopback, 0);
        l.Start();
        int p = ((IPEndPoint)l.LocalEndpoint).Port;
        l.Stop();
        return p;
    }

    static void Check(bool ok, string what)
    {
        if (!ok) throw new Exception($"[RemoteServerCheck] falhou: {what}");
    }
}
