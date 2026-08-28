/* Spheres, cheaply: a flat circle shaded as though it were a ball.
 *
 * Tom's call, and it is the right one. Real geometry would mean `SimpleMeshLayer` with
 * fifteen thousand instanced meshes and a lighting pass, against a frame budget that was
 * measured on a single instanced draw of flat circles. A disc shaded with a lambert
 * falloff and a highlight is indistinguishable from a sphere at any size this map is read
 * at, and it costs a few arithmetic operations per fragment on the draw call that already
 * exists.
 *
 * `ScatterplotLayer` hands its fragment shader `geometry.uv` -- the position within the
 * unit circle -- so the sphere normal can be reconstructed from it: x and y are the uv,
 * and z falls out of the unit sphere. From there it is ordinary shading.
 *
 * If the injection ever fails to compile, the layer must still draw. The extension is
 * applied by the caller and can simply be omitted; nothing else depends on it.
 */
'use strict';

/* Wrapped: a classic script's top-level declarations are globals, and a global here
 * collides with the same name imported in graph.js. One exported name each, no leakage. */
(function () {

/* The lighting terms are **baked into the shader source** rather than passed as uniforms.
 *
 * They have to vary, because the graph follows the theme: on a dark ground a ball is lit
 * up out of the background, and on a light one it must darken away from the light while an
 * additive white highlight vanishes entirely. But they change when the reader switches
 * theme, not per frame -- so compiling two shaders is cheaper than threading a uniform
 * block through a layer extension, and it cannot fail silently the way an unrecognised
 * uniform name would. deck.gl caches compilation by source, so two themes cost two
 * compiles for the life of the page.
 *
 * `toFixed(4)` rather than string interpolation of a bare number: GLSL has no implicit
 * int-to-float conversion, so an `ambient` that arrived as `0` would emit `0` and fail to
 * compile a float expression. A literal that is always written with a decimal point cannot.
 */
function shaderFor(ambient, diffuse, specular) {
  return {
    name: `sphere-shading-${ambient}-${diffuse}-${specular}`,
    inject: {
      /* `fs:DECKGL_FILTER_COLOR` is the hook name deck.gl 9 actually looks for. An inject
       * key it does not recognise is not an error -- the shader compiles, the layer draws,
       * and the effect silently never happens, which is exactly the class of no-op this
       * project keeps paying for. Verified by looking at a node close up: flat colour meant
       * the hook was wrong, not the maths. */
      'fs:DECKGL_FILTER_COLOR': `
        // geometry.uv spans the unit circle, so the near hemisphere's normal is free.
        float r2 = dot(geometry.uv, geometry.uv);
        vec3 normal = vec3(geometry.uv, sqrt(max(0.0, 1.0 - r2)));
        vec3 lightDir = normalize(vec3(-0.35, 0.45, 0.82));
        float lambert = clamp(dot(normal, lightDir), 0.0, 1.0);
        // A little ambient so the dark side stays a colour rather than a hole, and a tight
        // specular so the ball reads as round rather than merely shaded.
        float spec = pow(lambert, 24.0) * ${specular.toFixed(4)};
        color.rgb = color.rgb * (${ambient.toFixed(4)} + ${diffuse.toFixed(4)} * lambert) + spec;
      `,
    },
  };
}

/* The dark-ground values the 60 fps figure was measured on, so an extension constructed
 * with no arguments shades exactly as it always did. */
const DEFAULTS = { ambient: 0.42, diffuse: 0.72, specular: 0.5 };

class SphereShadingExtension extends deck.LayerExtension {
  constructor(opts = {}) {
    super();
    const { ambient, diffuse, specular } = { ...DEFAULTS, ...opts };
    this.shading = { ambient, diffuse, specular };
    this._shaders = shaderFor(ambient, diffuse, specular);
  }

  getShaders() {
    return this._shaders;
  }

  /* deck.gl compares extensions to decide whether a layer can be updated in place rather
   * than rebuilt. Two extensions with different lighting must not compare equal, or a
   * theme switch would leave the old shader on screen -- the same silent no-op the hook
   * name once caused, arriving by a different route. */
  equals(other) {
    return other instanceof SphereShadingExtension &&
           other.shading.ambient === this.shading.ambient &&
           other.shading.diffuse === this.shading.diffuse &&
           other.shading.specular === this.shading.specular;
  }
}
SphereShadingExtension.extensionName = 'SphereShadingExtension';

window.DunneFlowShading = { SphereShadingExtension };
})();
