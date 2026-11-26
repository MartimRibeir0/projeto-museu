# blender

Museu em blockout (RVA, T024–T035), gerado por script para ser reproduzível.

| Ficheiro | O que é |
|----------|---------|
| `build_museum.py` | Gera a cena inteira, grava `museum_master.blend`, os FBX e os renders |
| `send_to_blender.py` | Envia um script ao Blender aberto (addon "MCP for Blender", porta 9876) |
| `museum_master.blend` | Fonte (Git LFS) |
| `export/museum_blockout.fbx` | Museu completo, para referência no Unity |
| `export/corridor_module.fbx` | Módulo de corredor de 4 m com 2 slots de quadro (expansão modular) |
| `export/frame_{landscape,portrait,square}.fbx` | Molduras; a fotografia é o filho `Photo_*` (UV 0..1) |
| `export/textures/T_Wall.png`, `T_FloorWood.png` | Texturas 256×256 geradas pelo script (1 textura = 1 m, repetem sem costura) |

Renders: `docs/blender/planta.jpg` (planta, corte a 2,6 m), `docs/blender/blockout.jpg` (vista à entrada) e `docs/blender/gemeo.jpg` (sala do gémeo).

Detalhes: rodapés, aro da porta, sinalética em relevo, receção, banco, plantas, luzes de teto, passadeira, luz e placa por quadro; sala do gémeo com 3 molduras físicas, candeeiro, ventoinha, grelha de ventilação, sensor e terminal. Materiais PBR simples (Base Color/Roughness/Metallic/Emission; parede e chão com textura na Base Color) e UV em todas as meshes.

O script verifica-se a si próprio e falha se algo estiver mal:

- malhas: escala/rotação aplicadas, sem faces degeneradas ou duplicadas, normais coerentes;
- FBX: reimporta cada ficheiro e compara nomes, hierarquia, posição/tamanho, faces, materiais, texturas e propriedades (`device_id`, `aspect`, `slot`).

Leve para mobile: faces nunca vistas (base no chão, topo no teto) apagadas e texto com menos subdivisões. Cena exportada: 82 objetos, ~5,2 mil vértices, ~5,9 mil triângulos.

## Refazer

1. Abrir o Blender (testado com 5.3) com o addon "MCP for Blender" ativo. Ele abre um servidor em `127.0.0.1:9876` sozinho.
2. Na raiz do repositório: `python blender/send_to_blender.py blender/build_museum.py`. **Substitui a cena aberta.**

Medidas no topo de `build_museum.py` (altura 3,2 m, módulo 4×4 m, `N_MODULES`, variantes de moldura).

## Convenções

- Metros; Y = sentido do percurso, Z = cima; origem na porta de entrada.
- Moldura: origem no centro da fotografia, frente virada para -Y. Slots (`MNN_Slot_L/R`, empties) já estão rodados: basta pôr a moldura como filha do slot com transformação nula.
- Dispositivos do gémeo (`Twin_Sensor`, `Twin_Light`, `Twin_Fan`) têm a propriedade `device_id` com os IDs de `contracts/v1.md`.
- Pivôs: móveis e dispositivos com a origem na base (pousam no chão); `Twin_Light` no ponto de fixação ao teto; `Twin_Fan_Rotor` (filho de `Twin_Fan`) no eixo, para o Unity o rodar; sensor e grelha no centro.
- FBX para Unity: escala 1 = 1 m, Y-up, -Z forward, propriedades personalizadas incluídas, texturas por caminho relativo (`textures/`). **No Unity, ativar "Bake Axis Conversion"** no import do modelo: o `bake_space_transform` do Blender estraga objetos aninhados (fotografias e molduras dos slots).
- Para o Unity encontrar as texturas, copiar a pasta `export/` inteira (FBX + `textures/`).

## Git LFS

`.blend` e `.fbx` estão em Git LFS. Instalar uma vez: `git lfs install`. Sem isso, o clone traz só ponteiros de texto.
