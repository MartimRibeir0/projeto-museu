# museum-unity

Projeto Unity do museu 3D/RV/RA (RVA). **Unity 6000.0.85f2 (6 LTS)**, Built-in Render Pipeline, Input Manager antigo.

## Refazer a partir do Blender

Os prefabs e a cena são gerados a partir de `blender/export/` (ver `blender/README.md`). Depois de mudar o Blender:

- no Editor: menu **Museu → 1. Importar do Blender** e **Museu → 2. Criar prefabs e cena**;
- ou sem abrir o Editor (fechá-lo antes):
  `"C:\Program Files\Unity\Hub\Editor\6000.0.85f2\Editor\Unity.exe" -batchmode -quit -projectPath museum-unity -executeMethod MuseumSetup.RunAll -logFile -`

O setup falha se o visitante não ficar no chão, atravessar uma parede ou faltarem fotografias nos quadros, e grava `docs/unity/entrada.png`, `sala.png`, `quadro.png` e `rv.png` (museu montado com todas as coleções da app). **Não editar à mão** `Assets/Prefabs/*` nem `Assets/Scenes/Museum.unity`: são refeitos em cada execução.

## O que há

| Caminho | O que é |
|---------|---------|
| `Assets/Models/Museum/` | Cópia dos FBX e texturas do Blender. Import com "Bake Axis Conversion", UV2 para lightmaps e hierarquia preservada (`Editor/MuseumModelPostprocessor.cs`) |
| `Assets/Prefabs/Lobby` | Sala inicial (onde se nasce): secretária do gémeo e 6 slots, com colliders |
| `Assets/Prefabs/CorridorSegment` | Segmento de corredor de 8 m com as variantes de parede (com porta / cheia) e parede do fundo |
| `Assets/Prefabs/GalleryRoom` | Sala de coleção com 10 slots e parede do fundo com porta / cheia |
| `Assets/Prefabs/Frame_Landscape` | Moldura-molde com `FrameInfo` e fotografia no filho `Photo_*`; o `MuseumBuilder` estica-a à medida de cada fotografia |
| `Assets/Scenes/Museum.unity` | Sala inicial + `Museum` (`MuseumBuilder`) + `Player`; corredor e salas montam-se em runtime |
| `Assets/Scripts/MuseumBuilder.cs` | Monta corredor e salas conforme as coleções escolhidas na app (extra `collections`; regra de `layout()` no Blender) e põe as fotografias (`assets/colecoes/<id>/` do APK) nos quadros, na moldura de formato fixo mais parecida (quadrada, horizontal 4:3/3:2/16:9, panorâmica 2:1, vertical 3:4/2:3/9:16/1:2: a moldura do Blender esticada sem mudar a madeira; ~1 m², máx. 1,4 x 1,3 m; o que sobra corta-se ao centro; abaixo de 600 px a moldura encolhe; imagens inválidas, < 16 px ou > 20 MB ignoradas; ver `docs/unity/molduras.png`). Escala: só as salas perto do visitante têm fotografias (no máx. 8 salas, ~80 fotografias, ~80 MB) e as salas a mais de 22 m escondem-se; o setup verifica isto num museu de 20 coleções x 200 fotografias |
| `Assets/Scripts/BlenderProps.cs` | `deviceId`/`aspect`/`slot` vindos do Blender |
| `Assets/Scripts/FirstPersonTouch.cs` | Navegação: metade esquerda do ecrã anda, metade direita olha; WASD + botão direito no Editor |

Luz em tempo real (as salas são criadas em runtime, sem lightmap): ambiente trilight + 1 luz direcional sem sombras. Fotografias com `M_Photo` (Unlit/Texture), reduzidas a 512 px no lado maior.

## APK de teste

Menu **Museu → 3. Build APK de teste**, ou `-executeMethod MuseumBuild.Apk` (com `-buildTarget Android`). Sai em `Builds/museu3d.apk` (IL2CPP, ARM64 para telemóveis + x86_64 para o emulador do Android Studio). Instalar: `adb install -r Builds/museu3d.apk`.

## Dentro da app Android (Unity as a Library, T014)

1. Menu **Museu → 4. Exportar para a app Android** (ou `-executeMethod MuseumBuild.Export` com `-buildTarget Android`): gera `Builds/android-export`. Refazer sempre que o museu mudar.
2. Compilar `app-android` normalmente: o `settings.gradle.kts` inclui `unityLibrary` dessa pasta se existir. O 1.º build demora (compila IL2CPP em C++).
3. Na app: separador **Exposições → Visitar museu 3D**. O Unity corre no processo `:unity`; "Voltar" (`Assets/Scripts/BackToApp.cs`) ou recuar do Android fecham-no e voltam à app.

## RV (Cardboard) e comandos

- **Modo RV:** botão "Modo RV", Menu no comando, ou abrir pela app em "Visitar em RV (óculos)". Ecrã dividido + giroscópio (`VrMode.cs`). Recuar/B sai do RV.
- **Comando Xbox** (Bluetooth): stick esq. anda, dir. olha (em RV vira 30°), A abre quadro, B fecha/volta, Menu liga RV, Ver recentra (`Pad.cs`).
- **Outro telemóvel como comando:** botão "Comando telemóvel" → enviar o link (mesma rede Wi-Fi) → abrir no browser do outro telemóvel, **na horizontal**. Servidor na porta 47615 com token no link (`RemotePad.cs`, `RemoteServer.cs`, página `Assets/Resources/remote.html`). Verificar o servidor sem telemóvel: `-executeMethod RemoteServerCheck.Run`.
- Redes de convidados/escolas com "isolamento de clientes" bloqueiam a ligação entre telemóveis: usar o hotspot do telemóvel-comando e ligar o telemóvel do RV a ele (se o hotspot for o do telemóvel do RV, o link pode mostrar o IP dos dados móveis).

## Falta

- Hotspot e painel da fotografia (T039).
- Coleções da API (por agora vêm dos assets da app) e estado do gémeo (MQTT).
