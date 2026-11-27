package pt.ipleiria.museuvirtual.ui

import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.List
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Star
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController

enum class Tab(val route: String, val label: String, val icon: ImageVector) {
    COLLECTION("colecao", "Coleção", Icons.AutoMirrored.Filled.List),
    NEW_PHOTO("nova", "Nova fotografia", Icons.Filled.Add),
    EXHIBITIONS("museu", "Museu 3D", Icons.Filled.Star),
}

private const val CARD = "ficha/{id}"
private fun card(id: String) = "ficha/$id"

/** Troca de separador sem empilhar: cada separador guarda e repõe o seu estado (T041). */
private fun NavHostController.goTab(tab: Tab) = navigate(tab.route) {
    popUpTo(graph.findStartDestination().id) { saveState = true }
    launchSingleTop = true
    restoreState = true
}

@Composable
fun MuseuApp() {
    val nav = rememberNavController()
    val vm: PhotosViewModel = viewModel { PhotosViewModel(AppGraph.photos) }  // um para a app toda (estado da sessão)
    val route = nav.currentBackStackEntryAsState().value?.destination?.route
    MaterialTheme {
        Scaffold(
            bottomBar = {
                if (Tab.entries.any { it.route == route }) NavigationBar {
                    Tab.entries.forEach {
                        NavigationBarItem(
                            selected = it.route == route,
                            onClick = { nav.goTab(it) },
                            icon = { Icon(it.icon, contentDescription = null) },
                            label = { Text(it.label) },
                        )
                    }
                }
            },
        ) { padding ->
            NavHost(nav, startDestination = Tab.COLLECTION.route, Modifier.fillMaxSize().padding(padding)) {
                composable(Tab.COLLECTION.route) {
                    CollectionScreen(vm, onOpen = { nav.navigate(card(it)) }, onAdd = { nav.goTab(Tab.NEW_PHOTO) })
                }
                composable(Tab.NEW_PHOTO.route) {
                    // Depois de criar: ficha da 1.ª; recuar volta à coleção, não à escolha já feita.
                    NewPhotoScreen(vm) { ids ->
                        nav.navigate(card(ids.first())) { popUpTo(Tab.COLLECTION.route) }
                    }
                }
                composable(Tab.EXHIBITIONS.route) { ExhibitionsScreen() }
                composable(CARD) { entry ->
                    EditPhotoScreen(
                        vm, entry.arguments?.getString("id").orEmpty(),
                        onBack = { nav.popBackStack() },
                        onDone = { next ->
                            if (next != null) nav.navigate(card(next)) { popUpTo(CARD) { inclusive = true } }
                            else nav.popBackStack(Tab.COLLECTION.route, inclusive = false)
                        },
                    )
                }
            }
        }
    }
}
