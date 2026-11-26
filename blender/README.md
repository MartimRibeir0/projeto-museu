# blender

Museu em blockout (RVA, T024–T029), gerado por script para ser reproduzível.

| Ficheiro | O que é |
|----------|---------|
| `build_museum.py` | Gera a cena inteira, grava `museum_master.blend`, os FBX e os renders |
| `send_to_blender.py` | Envia um script ao Blender aberto (addon "MCP for Blender", porta 9876) |
| `museum_master.blend` | Fonte (Git LFS) |
| `export/museum_blockout.fbx` | Museu completo, para referência no Unity |
| `export/corridor_module.fbx` | Módulo de corredor de 4 m com 2 slots de quadro (expansão modular) |
| `export/frame_{landscape,portrait,square}.fbx` | Molduras; a fotografia é o filho `Photo_*` (UV 0..1) |

Renders: `docs/blender/planta.jpg` (planta) e `docs/blender/blockout.jpg` (vista à entrada).

## Refazer

1. Abrir o Blender (testado com 5.3) com o addon "MCP for Blender" ativo. Ele abre um servidor em `127.0.0.1:9876` sozinho.
2. Na raiz do repositório: `python blender/send_to_blender.py blender/build_museum.py`. **Substitui a cena aberta.**

Medidas no topo de `build_museum.py` (altura 3,2 m, módulo 4×4 m, `N_MODULES`, variantes de moldura).

## Convenções

- Metros; Y = sentido do percurso, Z = cima; origem na porta de entrada.
- Moldura: origem no centro da fotografia, frente virada para -Y. Slots (`MNN_Slot_L/R`, empties) já estão rodados: basta pôr a moldura como filha do slot com transformação nula.
- Dispositivos do gémeo (`Twin_Sensor`, `Twin_Light`, `Twin_Fan`) têm a propriedade `device_id` com os IDs de `contracts/v1.md`.
- FBX para Unity: escala 1 = 1 m, Y-up, -Z forward, transformações aplicadas, propriedades personalizadas incluídas.

## Git LFS

`.blend` e `.fbx` estão em Git LFS. Instalar uma vez: `git lfs install`. Sem isso, o clone traz só ponteiros de texto.
