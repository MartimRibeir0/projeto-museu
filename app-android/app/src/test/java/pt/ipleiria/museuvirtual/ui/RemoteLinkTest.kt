package pt.ipleiria.museuvirtual.ui

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class RemoteLinkTest {
    @Test
    fun wifiAntesDoHotspotEDadosMoveisIgnorados() {
        assertTrue(RemoteLink.rank("wlan0") < RemoteLink.rank("swlan0"))
        assertEquals(RemoteLink.rank("ap0"), RemoteLink.rank("wlan1"))
        listOf("rmnet_data0", "ccmni1", "v4-rmnet0", "tun0", "lo").forEach { assertEquals(it, -1, RemoteLink.rank(it)) }
    }

    @Test
    fun soRedesPrivadas() {
        listOf("192.168.43.1", "10.142.81.136", "172.20.10.1").forEach { assertTrue(it, RemoteLink.isPrivate(it)) }
        listOf("100.72.3.4", "8.8.8.8", "172.32.0.1", "abc").forEach { assertFalse(it, RemoteLink.isPrivate(it)) }
    }
}
