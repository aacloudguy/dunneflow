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
 * collides with the same name imported in app.js. One exported name each, no leakage. */
(function () {

const SPHERE_SHADER = {
  name: 'sphere-shading',
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
      float spec = pow(lambert, 24.0) * 0.5;
      color.rgb = color.rgb * (0.42 + 0.72 * lambert) + spec;
    `,
  },
};

class SphereShadingExtension extends deck.LayerExtension {
  getShaders() {
    return SPHERE_SHADER;
  }
}
SphereShadingExtension.extensionName = 'SphereShadingExtension';

window.DunneFlowShading = { SphereShadingExtension };
})();
