package pt.ipleiria.museuvirtual.ui

import android.content.Context
import java.net.Inet4Address
import java.net.NetworkInterface
import java.util.UUID

/**
 * Link do telemóvel-comando (servidor em museum-unity/Assets/Scripts/RemotePad.cs, porta 47615).
 * O token é criado uma vez e guardado, e vai para o Unity no extra "remoteToken": o link é sempre o mesmo,
 * enquanto o IP deste telemóvel na rede não mudar.
 */
object RemoteLink {
    const val PORT = 47615  // igual a RemotePad.Port no Unity (8765 colidia com adb reverse)

    fun token(context: Context): String {
        val prefs = context.getSharedPreferences("museu3d", Context.MODE_PRIVATE)
        return prefs.getString("remoteToken", null)
            ?: UUID.randomUUID().toString().replace("-", "").take(10).also {
                prefs.edit().putString("remoteToken", it).apply()
            }
    }

    /** Link para o browser do outro telemóvel, ou null sem Wi-Fi/hotspot. */
    fun url(context: Context): String? = localIp()?.let { "http://$it:$PORT/?t=${token(context)}" }

    /** IP na rede local: Wi-Fi primeiro, depois hotspot; nunca dados móveis (mesma regra que o Unity). */
    fun localIp(): String? = runCatching {
        NetworkInterface.getNetworkInterfaces().toList()
            .filter { it.isUp && !it.isLoopback }
            .flatMap { ni -> ni.inetAddresses.toList().filterIsInstance<Inet4Address>().map { rank(ni.name) to it.hostAddress } }
            .filter { (rank, ip) -> rank >= 0 && ip != null && isPrivate(ip) }
            .minByOrNull { it.first }?.second
    }.getOrNull()

    /**
     * Este telemóvel está a fazer hotspot: o Android não deixa os ligados a ele chegar às apps (Samsung A55 /
     * Android 17: ping responde, a porta não). O hotspot tem de ser o telemóvel-comando ou um Wi-Fi.
     */
    fun isHotspotHost(): Boolean = runCatching {
        NetworkInterface.getNetworkInterfaces().toList().any { ni ->
            ni.isUp && listOf("swlan", "ap", "softap").any { ni.name.lowercase().startsWith(it) } &&
                ni.inetAddresses.toList().filterIsInstance<Inet4Address>().any { it.hostAddress?.let(::isPrivate) == true }
        }
    }.getOrDefault(false)

    fun rank(name: String): Int {
        val n = name.lowercase()
        val skip = listOf("rmnet", "ccmni", "clat", "v4-", "pdp", "tun", "ppp", "dummy", "lo", "ims", "rev_rmnet")
        return when {
            skip.any { n.startsWith(it) } -> -1
            n == "wlan0" -> 0
            listOf("ap", "swlan", "softap", "wlan").any { n.startsWith(it) } -> 1
            n.startsWith("eth") || n.startsWith("en") -> 2
            else -> 3
        }
    }

    fun isPrivate(ip: String): Boolean {
        val b = ip.split(".").mapNotNull { it.toIntOrNull() }
        if (b.size != 4) return false
        return b[0] == 10 || (b[0] == 172 && b[1] in 16..31) || (b[0] == 192 && b[1] == 168)
    }
}
