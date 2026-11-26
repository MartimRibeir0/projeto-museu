"""Gera o museu em blockout (T024–T029) dentro do Blender aberto e grava museum_master.blend + FBX.

Correr com o Blender aberto e o addon "MCP for Blender" ativo:
    python blender/send_to_blender.py blender/build_museum.py
Substitui a cena aberta. Medidas em metros; Y = sentido do percurso, Z = cima.

Planta (vista de cima, entrada em y=0):
    Entrada 8x8 m  ->  Corredor N módulos de 4x4 m  ->  Sala do gémeo digital 6x6 m
"""

import math
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parent.parent  # __file__ é injetado por send_to_blender.py
BLEND = ROOT / "blender" / "museum_master.blend"
EXPORT = ROOT / "blender" / "export"
DOCS = ROOT / "docs" / "blender"

H = 3.2  # altura das paredes
T = 0.2  # espessura das paredes
DOOR_W, DOOR_H = 2.0, 2.4
HALL = 8.0  # entrada HALL x HALL
MOD_L, MOD_W = 4.0, 4.0  # módulo de corredor (comprimento x largura interior)
N_MODULES = 3
TWIN = 6.0  # sala do gémeo TWIN x TWIN
EYE = 1.6  # centro dos quadros (altura dos olhos)
FRAME_B, FRAME_D = 0.08, 0.05  # largura e profundidade da moldura
# Área interior (fotografia) de cada variante; outras proporções usam letterbox no Unity.
VARIANTS = {"Landscape": (1.2, 0.9), "Portrait": (0.9, 1.2), "Square": (1.0, 1.0)}
# IDs fixos dos dispositivos (contracts/v1.md, iot/simulator.py).
DEVICES = {
    "Twin_Sensor": "00000000-0000-4000-8000-0000000000a1",
    "Twin_Light": "00000000-0000-4000-8000-0000000000a2",
    "Twin_Fan": "00000000-0000-4000-8000-0000000000a3",
}


# ---------- geometria ----------

def box(x0, x1, y0, y1, z0, z1):
    v = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
         (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    f = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    return v, f


def mesh(name, boxes):
    verts, faces = [], []
    for b in boxes:
        v, f = box(*b)
        n = len(verts)
        verts += v
        faces += [tuple(i + n for i in face) for face in f]
    m = bpy.data.meshes.new(name)
    m.from_pydata(verts, [], faces)
    m.validate()
    return m


def obj(name, data, coll, loc=(0, 0, 0), mat=None, parent=None):
    if mat is not None:  # antes de criar o objeto, senão as cópias ficam sem slot de material
        data.materials.append(mat)
    o = bpy.data.objects.new(name, data)
    coll.objects.link(o)
    o.location = loc
    if parent is not None:
        o.parent = parent
    return o


def material(name, rgb):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (*rgb, 1)
    m.diffuse_color = (*rgb, 1)  # cor usada no viewport/Workbench
    return m


def wall_x(x, y0, y1, z0=0.0, z1=H):
    """Parede ao longo de Y centrada na linha x."""
    return (x - T / 2, x + T / 2, y0, y1, z0, z1)


def wall_y(y, x0, x1, z0=0.0, z1=H):
    """Parede ao longo de X centrada na linha y."""
    return (x0, x1, y - T / 2, y + T / 2, z0, z1)


def wall_with_gap(y, x0, x1, gap_w, gap_h=H):
    """Parede em y com abertura centrada (porta ou passagem); acima da abertura fica um lintel."""
    g = gap_w / 2
    parts = [wall_y(y, x0, -g), wall_y(y, g, x1)]
    if gap_h < H:
        parts.append(wall_y(y, -g, g, gap_h, H))
    return parts


# ---------- cena ----------

def reset():
    for coll in (bpy.data.objects, bpy.data.meshes, bpy.data.materials, bpy.data.cameras,
                 bpy.data.lights, bpy.data.curves, bpy.data.collections):
        for item in list(coll):
            coll.remove(item)
    s = bpy.context.scene
    s.unit_settings.system = "METRIC"
    s.unit_settings.scale_length = 1.0
    s.unit_settings.length_unit = "METERS"
    cols = {}
    for name in ("Architecture", "Frames", "Props", "DigitalTwin", "Annotations", "_Templates"):
        c = bpy.data.collections.new(name)
        s.collection.children.link(c)
        cols[name] = c
    return cols


def build_frame_template(name, w, h, coll, mats):
    """Moldura virada para -Y, origem no centro da fotografia; a fotografia é um objeto filho separado."""
    b, d = FRAME_B, FRAME_D
    x, z = w / 2, h / 2
    frame = obj(f"Frame_{name}", mesh(f"Frame_{name}", [
        (-x - b, x + b, -d / 2, d / 2, z, z + b),        # topo
        (-x - b, x + b, -d / 2, d / 2, -z - b, -z),      # base
        (-x - b, -x, -d / 2, d / 2, -z, z),              # esquerda
        (x, x + b, -d / 2, d / 2, -z, z),                # direita
        (-x, x, d / 2 - 0.01, d / 2, -z, z),             # fundo
    ]), coll, mat=mats["frame"])
    m = bpy.data.meshes.new(f"Photo_{name}")
    m.from_pydata([(-x, 0, -z), (x, 0, -z), (x, 0, z), (-x, 0, z)], [], [(0, 1, 2, 3)])  # normal -Y
    uv = m.uv_layers.new(name="UVMap")
    for loop, co in zip(uv.data, [(0, 0), (1, 0), (1, 1), (0, 1)]):
        loop.uv = co
    obj(f"Photo_{name}", m, coll, loc=(0, d / 2 - 0.015, 0), mat=mats["photo"], parent=frame)
    frame["aspect"] = round(w / h, 3)
    return frame


def place_frame(template, slot, coll, tag):
    """Cópia da moldura e da fotografia, filha do slot. Mesh própria: o export FBX perde o material em meshes partilhadas."""
    f = template.copy()
    f.data = template.data.copy()
    f.name = f"{tag}_{template.name}"
    coll.objects.link(f)
    f.parent, f.location = slot, (0, 0, 0)
    for child in template.children:
        c = child.copy()
        c.data = child.data.copy()
        c.name = f"{tag}_{child.name}"
        coll.objects.link(c)
        c.parent = f
    return f


def text(body, loc, coll, mat, size=0.8):
    cu = bpy.data.curves.new(body, "FONT")
    cu.body, cu.size, cu.align_x = body, size, "CENTER"
    o = obj(f"Label_{body}", cu, coll, loc=(loc[0], loc[1], 0.02), mat=mat)
    o.rotation_euler = (0, 0, math.radians(90))  # legível na planta com a entrada à esquerda
    return o


def build():
    cols = reset()
    mats = {
        "wall": material("Wall", (0.85, 0.84, 0.80)),
        "floor": material("Floor", (0.45, 0.33, 0.22)),
        "ceiling": material("Ceiling", (0.95, 0.95, 0.95)),
        "frame": material("FrameWood", (0.18, 0.12, 0.08)),
        "photo": material("PhotoPlaceholder", (0.55, 0.6, 0.65)),
        "twin": material("TwinDevice", (0.2, 0.45, 0.7)),
        "label": material("Label", (0.8, 0.1, 0.1)),
    }
    arch, frames, props, twin, notes, tmpl = (cols[k] for k in
                                              ("Architecture", "Frames", "Props", "DigitalTwin", "Annotations", "_Templates"))

    templates = {}
    for i, (name, (w, h)) in enumerate(VARIANTS.items()):
        templates[name] = build_frame_template(name, w, h, tmpl, mats)
        templates[name].location = (HALL + 4, 2 + 2 * i, EYE)  # prateleira fora do museu

    # Entrada: y 0..HALL, porta na frente, passagem para o corredor ao fundo.
    hx = HALL / 2
    obj("Hall_Floor", mesh("Hall_Floor", [(-hx, hx, 0, HALL, -0.1, 0)]), arch, mat=mats["floor"])
    obj("Hall_Ceiling", mesh("Hall_Ceiling", [(-hx, hx, 0, HALL, H, H + 0.1)]), arch, mat=mats["ceiling"])
    obj("Hall_Walls", mesh("Hall_Walls", [
        *wall_with_gap(0, -hx - T / 2, hx + T / 2, DOOR_W, DOOR_H),
        *wall_with_gap(HALL, -hx - T / 2, hx + T / 2, MOD_W),
        wall_x(-hx, 0, HALL), wall_x(hx, 0, HALL),
    ]), arch, mat=mats["wall"])
    obj("Props_Bench", mesh("Props_Bench", [(-1.0, 1.0, HALL / 2 - 0.2, HALL / 2 + 0.2, 0, 0.45)]),
        props, mat=mats["frame"])

    # Corredor modular: o módulo começa em y=0 local e acaba em y=MOD_L, por isso encaixa sem folgas.
    mx = MOD_W / 2
    module_mesh = mesh("CorridorModule", [
        (-mx - T / 2, mx + T / 2, 0, MOD_L, -0.1, 0),
        wall_x(-mx, 0, MOD_L), wall_x(mx, 0, MOD_L),
    ])
    ceiling_mesh = mesh("CorridorModule_Ceiling", [(-mx - T / 2, mx + T / 2, 0, MOD_L, H, H + 0.1)])
    module_mesh.materials.append(mats["wall"])
    module_mesh.materials.append(mats["floor"])
    ceiling_mesh.materials.append(mats["ceiling"])
    for poly in module_mesh.polygons:  # chão do módulo a castanho, paredes a branco
        poly.material_index = 1 if poly.normal.z > 0.5 and poly.center.z < 0.01 else 0
    order = list(VARIANTS)
    for k in range(N_MODULES):
        tag = f"M{k + 1:02d}"
        m = obj(f"CorridorModule_{k + 1:02d}", module_mesh if k == 0 else module_mesh.copy(), arch,
                loc=(0, HALL + k * MOD_L, 0))
        obj(f"{tag}_Ceiling", ceiling_mesh if k == 0 else ceiling_mesh.copy(), arch, parent=m)
        for side, x, rot in (("L", -mx + T / 2 + FRAME_D / 2, 90), ("R", mx - T / 2 - FRAME_D / 2, -90)):
            slot = obj(f"{tag}_Slot_{side}", None, frames, loc=(x, MOD_L / 2, EYE), parent=m)
            slot.empty_display_type, slot.empty_display_size = "ARROWS", 0.3
            slot.rotation_euler = (0, 0, math.radians(rot))  # -Y da moldura aponta para o centro do corredor
            slot["slot"] = f"{tag}_{side}"
            place_frame(templates[order[(2 * k + (side == "R")) % 3]], slot, frames, tag)

    # Sala do gémeo digital: estado da exposição física (luz, ventoinha, sensor, moldura real).
    y0 = HALL + N_MODULES * MOD_L
    tx = TWIN / 2
    obj("Twin_Floor", mesh("Twin_Floor", [(-tx, tx, y0, y0 + TWIN, -0.1, 0)]), arch, mat=mats["floor"])
    obj("Twin_Ceiling", mesh("Twin_Ceiling", [(-tx, tx, y0, y0 + TWIN, H, H + 0.1)]), arch, mat=mats["ceiling"])
    obj("Twin_Walls", mesh("Twin_Walls", [
        *wall_with_gap(y0, -tx - T / 2, tx + T / 2, MOD_W),
        wall_y(y0 + TWIN, -tx - T / 2, tx + T / 2),
        wall_x(-tx, y0, y0 + TWIN), wall_x(tx, y0, y0 + TWIN),
    ]), arch, mat=mats["wall"])
    cy = y0 + TWIN / 2
    obj("Twin_Pedestal", mesh("Twin_Pedestal", [(-0.3, 0.3, cy - 0.3, cy + 0.3, 0, 1.0)]), twin, mat=mats["wall"])
    devices = {
        "Twin_Light": [(-0.3, 0.3, cy - 0.3, cy + 0.3, H - 0.1, H)],
        "Twin_Fan": [(-0.15, 0.15, cy - 0.15, cy + 0.15, 1.0, 1.3)],
        "Twin_Sensor": [(tx - T / 2 - 0.05, tx - T / 2, cy - 0.06, cy + 0.06, 1.4, 1.52)],
    }
    for name, boxes in devices.items():
        o = obj(name, mesh(name, boxes), twin, mat=mats["twin"])
        o["device_id"] = DEVICES[name]
    phys = obj("Twin_PhysicalFrame_Slot", None, twin, loc=(0, y0 + TWIN - T / 2 - FRAME_D / 2, EYE))
    phys.empty_display_type = "ARROWS"
    place_frame(templates["Landscape"], phys, twin, "Twin")

    # Anotações: só para a planta e para validar a escala; não vão para o FBX.
    text("Entrada", (0, HALL / 2 + 1.5), notes, mats["label"])
    text("Corredor modular", (0, HALL + N_MODULES * MOD_L / 2), notes, mats["label"])
    text("Gémeo digital", (1.8, y0 + TWIN / 2), notes, mats["label"])
    obj("Visitor_1m75", mesh("Visitor_1m75", [(-0.25, 0.25, -0.15, 0.15, 0, 1.75)]), notes,
        loc=(1.5, 2.0, 0), mat=mats["label"])
    return cols, y0 + TWIN


# ---------- renders e exports ----------

def render(cam_data, loc, rot, path, res, hide):
    s = bpy.context.scene
    cam = bpy.data.objects.new("Cam", cam_data)
    s.collection.objects.link(cam)
    cam.location, cam.rotation_euler = loc, rot
    s.camera = cam
    s.render.engine = "BLENDER_WORKBENCH"
    s.display.shading.light = "STUDIO"
    s.display.shading.color_type = "MATERIAL"
    s.display.shading.show_cavity = True
    s.render.resolution_x, s.render.resolution_y = res
    s.render.resolution_percentage = 100
    s.render.filepath = str(path)
    s.render.image_settings.file_format, s.render.image_settings.quality = "JPEG", 85
    hidden = [o for o in bpy.data.objects if hide(o)]
    for o in hidden:
        o.hide_render = True
    bpy.ops.render.render(write_still=True)
    for o in hidden:
        o.hide_render = False
    bpy.data.objects.remove(cam)
    bpy.data.cameras.remove(cam_data)


def in_coll(o, *names):
    return any(c.name in names for c in o.users_collection)


def export(path, objects, zero=None):
    """Exporta para Unity (Y-up, escala 1 = 1 m). `zero`: objeto raiz posto na origem durante o export."""
    saved = zero.location.copy() if zero else None
    if zero:
        zero.location = (0, 0, 0)
    bpy.context.view_layer.update()
    for o in bpy.context.view_layer.objects:
        o.select_set(o in objects)
    bpy.ops.export_scene.fbx(
        filepath=str(path), use_selection=True, object_types={"MESH", "EMPTY"},
        apply_scale_options="FBX_SCALE_ALL", axis_forward="-Z", axis_up="Y", bake_space_transform=True,
        use_custom_props=True, mesh_smooth_type="FACE", add_leaf_bones=False,
    )
    if zero:
        zero.location = saved


def tree(root):
    return [root, *root.children_recursive]


def main():
    EXPORT.mkdir(parents=True, exist_ok=True)
    DOCS.mkdir(parents=True, exist_ok=True)
    cols, length = build()

    # Planta: câmara ortográfica de cima, rodada para o percurso ficar na horizontal.
    plan = bpy.data.cameras.new("Plan")
    plan.type, plan.ortho_scale = "ORTHO", length + 1.0
    render(plan, (0, length / 2, 30), (0, 0, math.radians(90)), DOCS / "planta.jpg", (2200, 800),
           hide=lambda o: "Ceiling" in o.name or in_coll(o, "_Templates"))
    # Vista do visitante à entrada, a olhar para o corredor.
    view = bpy.data.cameras.new("View")
    view.lens = 18
    render(view, (0, 1.0, EYE), (math.radians(90), 0, 0), DOCS / "blockout.jpg", (1600, 900),
           hide=lambda o: in_coll(o, "Annotations", "_Templates"))

    museum = [o for o in bpy.data.objects if not in_coll(o, "Annotations", "_Templates")]
    export(EXPORT / "museum_blockout.fbx", museum)
    module = bpy.data.objects["CorridorModule_01"]
    export(EXPORT / "corridor_module.fbx", tree(module), zero=module)
    for name in VARIANTS:
        t = bpy.data.objects[f"Frame_{name}"]
        export(EXPORT / f"frame_{name.lower()}.fbx", tree(t), zero=t)

    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND))
    verts = sum(len(m.vertices) for m in bpy.data.meshes)
    print(f"ok: {len(bpy.data.objects)} objetos, {len(bpy.data.meshes)} meshes, {verts} vértices; "
          f"comprimento {length:.1f} m; gravado {BLEND.name}; FBX em {EXPORT.name}/")


main()
