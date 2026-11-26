package pt.ipleiria.museuvirtual.ui

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.saveable.rememberSaveableStateHolder
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.automirrored.filled.List
import androidx.compose.material.icons.filled.Star
import androidx.compose.ui.graphics.vector.ImageVector

enum class Tab(val label: String, val icon: ImageVector) {
    COLLECTION("Coleção", Icons.AutoMirrored.Filled.List),
    NEW_PHOTO("Nova fotografia", Icons.Filled.Add),
    EXHIBITIONS("Exposições", Icons.Filled.Star),
}

// shortcut: navegação por separadores sem back stack; passar a navigation-compose quando houver ecrãs de detalhe (T016).
@Composable
fun MuseuApp() {
    var tab by rememberSaveable { mutableStateOf(Tab.NEW_PHOTO) }
    val tabState = rememberSaveableStateHolder() // cada separador mantém o seu estado ao trocar
    MaterialTheme {
        Scaffold(
            bottomBar = {
                NavigationBar {
                    Tab.entries.forEach {
                        NavigationBarItem(
                            selected = it == tab,
                            onClick = { tab = it },
                            icon = { Icon(it.icon, contentDescription = null) },
                            label = { Text(it.label) },
                        )
                    }
                }
            },
        ) { padding ->
            Box(Modifier.fillMaxSize().padding(padding)) {
                tabState.SaveableStateProvider(tab.name) {
                    when (tab) {
                        Tab.NEW_PHOTO -> NewPhotoScreen()
                        Tab.EXHIBITIONS -> ExhibitionsScreen()
                        else -> Text("Por fazer", Modifier.align(Alignment.Center))
                    }
                }
            }
        }
    }
}
