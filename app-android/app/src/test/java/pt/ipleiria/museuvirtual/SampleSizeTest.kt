package pt.ipleiria.museuvirtual

import org.junit.Assert.assertEquals
import org.junit.Test
import pt.ipleiria.museuvirtual.ui.sampleSize

class SampleSizeTest {
    @Test
    fun keepsSmallImages() = assertEquals(1, sampleSize(800, 600, 1600))

    @Test
    fun halvesUntilUnderLimit() {
        assertEquals(2, sampleSize(4000, 3000, 1600))
        assertEquals(4, sampleSize(3000, 8000, 1600))
        assertEquals(2, sampleSize(3200, 100, 1600))
    }
}
