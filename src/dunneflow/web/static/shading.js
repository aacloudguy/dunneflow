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
      /* Every local is prefixed `df`, and that is not a style choice.
       *
       * This block is injected into deck.gl's own fragment shader, so its declarations
       * land in a scope that already has names in it. `vec3 normal = ...` collided with
       * one, the block failed to compile, and the layer went on drawing flat discs --
       * through a benchmark that reported "spheres" and a table in CLAUDE.md that
       * recorded frame rates for geometry that was never shaded.
       *
       * That is rule 22's own lesson arriving a second time by a different route: the
       * first version failed because the inject hook was named wrong, and an unrecognised
       * hook is not an error. A name collision is not an error either. Both compile, both
       * draw, and neither does anything. Found the same way as the first one -- by looking
       * at a single node close up. */
      'fs:DECKGL_FILTER_COLOR': `
        // geometry.uv spans the unit circle, so the near hemisphere's normal is free.
        float dfR2 = dot(geometry.uv, geometry.uv);
        vec3 dfNormal = vec3(geometry.uv, sqrt(max(0.0, 1.0 - dfR2)));
        vec3 dfLight = normalize(vec3(-0.35, 0.45, 0.82));
        float dfLambert = clamp(dot(dfNormal, dfLight), 0.0, 1.0);
        // A little ambient so the dark side stays a colour rather than a hole, and a tight
        // specular so the ball reads as round rather than merely shaded.
        float dfSpec = pow(dfLambert, 24.0) * ${specular.toFixed(4)};
        color.rgb = color.rgb * (${ambient.toFixed(4)} + ${diffuse.toFixed(4)} * dfLambert)
                    + dfSpec;
      `,
    },
  };
}

/* The dark-ground values the 60 fps figure was measured on, so an extension constructed
 * with no arguments shades exactly as it always did. */
const DEFAULTS = { ambient: 0.42, diffuse: 0.72, specular: 0.5 };

/* **One extension class per lighting, cached by it.**
 *
 * This looks like a strange way to write it, and it is the only arrangement that actually
 * shades. deck.gl resolves an extension's shader once per extension *class*: a second
 * instance of the same class with different `getShaders()` output reuses the first
 * assembly. So one class carrying values in a field renders flat discs no matter what the
 * values are -- the extension is attached, `getShaders()` returns the right source, the
 * numbers are right, and the picture does not change.
 *
 * Established by experiment, not by reading: an identical shader body in a freshly
 * declared class shades correctly, and in the shared class it does not. A distinct class
 * per lighting is therefore what a distinct shader requires. There are two of them in
 * practice -- light and dark -- so the cache holds two entries for the life of the page.
 *
 * It is the third silent no-op this one effect has produced. The hook name was wrong, then
 * a GLSL local collided with deck.gl's own, and now the shader was never reassembled. Not
 * one of the three is an error: each compiles, each draws, and each skips the effect. All
 * three were found by looking closely at a single node, which is the only instrument that
 * has ever detected any of them. */
const classes = new Map();

function extensionClass(ambient, diffuse, specular) {
  const key = `${ambient}|${diffuse}|${specular}`;
  let cls = classes.get(key);
  if (cls) return cls;

  const shaders = shaderFor(ambient, diffuse, specular);
  cls = class extends deck.LayerExtension {
    getShaders() { return shaders; }
  };
  cls.extensionName = shaders.name;
  cls.shading = { ambient, diffuse, specular };
  classes.set(key, cls);
  return cls;
}

/* Kept as a function rather than a class so callers read the same as before. */
function SphereShadingExtension(opts = {}) {
  const { ambient, diffuse, specular } = { ...DEFAULTS, ...opts };
  const Cls = extensionClass(ambient, diffuse, specular);
  return new Cls();
}

window.DunneFlowShading = { SphereShadingExtension, extensionClass };
})();
