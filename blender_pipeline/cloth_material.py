"""Reuse a clean weave patch from the existing AI mantle atlas."""
from math import atan2, pi


def apply_weave_material(garment, design, center, hem):
    import bpy
    import numpy as np

    material = design.data.materials[0]
    principled = next(n for n in material.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    links = list(principled.inputs['Base Color'].links)
    source = links[0].from_node.image if links and links[0].from_node.type == 'TEX_IMAGE' else None
    if source is None:
        raise RuntimeError('AI mantle design has no base-color texture')
    width, height = source.size
    pixels = np.empty(width * height * 4, dtype=np.float32)
    source.pixels.foreach_get(pixels)
    pixels = pixels.reshape(height, width, 4)
    # Interior strip of the existing AI cloth atlas, excluding UV gutters.
    # Blender image rows are bottom-up.
    patch = pixels[int(.731 * height):int(.741 * height), int(.640 * width):int(.728 * width)].copy()
    if not patch.size:
        raise RuntimeError('AI weave texture crop is empty')
    patch = np.concatenate([patch, patch[:, ::-1]], axis=1)
    patch = np.concatenate([patch, patch[::-1]], axis=0)
    image = bpy.data.images.new('Abraham_Woven_Mantle', width=patch.shape[1], height=patch.shape[0], alpha=False)
    image.colorspace_settings.name = source.colorspace_settings.name
    image.pixels.foreach_set(patch.reshape(-1))
    image.pack()
    cloth = bpy.data.materials.new('Abraham_Mantle_Weave')
    cloth.use_nodes = True
    shader = next(n for n in cloth.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    shader.inputs['Metallic'].default_value = 0.
    shader.inputs['Roughness'].default_value = .85
    texture = cloth.node_tree.nodes.new('ShaderNodeTexImage')
    texture.image = image
    texture.extension = 'REPEAT'
    cloth.node_tree.links.new(texture.outputs['Color'], shader.inputs['Base Color'])
    garment.data.materials.clear()
    garment.data.materials.append(cloth)
    uv = garment.data.uv_layers.active or garment.data.uv_layers.new(name='UVMap')
    for loop in garment.data.loops:
        p = garment.matrix_world @ garment.data.vertices[loop.vertex_index].co
        angle = atan2(p.y - center.y, p.x - center.x)
        uv.data[loop.index].uv = ((angle + pi) / (2 * pi) * 4, (p.z - hem) * 8)
    for face in garment.data.polygons:
        face.material_index = 0
        face.use_smooth = True
    garment['material_origin'] = 'cropped_existing_AI_weave_atlas'
