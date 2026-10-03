import type { OpenApiDoc } from '../config/openapi/spec'

function op(summary: string, description: string, tag: string) {
  return { summary, description, tags: [tag], responses: { 200: { description: 'OK' } } }
}

/** Especificación reducida con la forma de `/openapi.json`: 9 operaciones en 4 dominios. */
export function openApiDoc(): OpenApiDoc {
  return {
    openapi: '3.1.0',
    info: { title: 'Speech & Text Analytics API', version: '0.6.0' },
    tags: [
      { name: 'health', description: 'Sonda de salud.' },
      { name: 'search', description: 'Búsqueda semántica y conversaciones similares (FE003).' },
      { name: 'config', description: 'Configuración global de la plataforma (FE005).' },
      { name: 'users', description: 'Usuarios, roles y matriz de permisos (FE006).' },
    ],
    paths: {
      '/api/health': { get: op('Sonda de salud', 'Público.', 'health') },
      '/api/search': { post: op('Búsqueda semántica', 'Permiso: `search:use`. Fragmentos más parecidos.', 'search') },
      '/api/config': { get: op('Configuración completa', 'Permiso: `config:view`.', 'config') },
      '/api/config/general': { put: op('Cambiar la sección General', 'Permiso: `config:edit`.', 'config') },
      '/api/config/compliance-checks/{check_id}': {
        parameters: [{ name: 'check_id', in: 'path', required: true, schema: { type: 'string' } }],
        put: op('Editar un check', 'Permiso: `config:edit`.', 'config'),
        delete: op('Borrar un check', 'Permiso: `config:edit`. Solo si no está en uso.', 'config'),
      },
      '/api/users': {
        get: op('Usuarios', 'Permiso: `users:admin`.', 'users'),
        post: op('Crear un usuario', 'Permiso: `users:admin`.', 'users'),
      },
      '/api/roles/{role_id}': { delete: op('Borrar un rol personalizado', 'Permiso: `users:admin`.', 'users') },
    },
    components: { schemas: { Health: { type: 'object' } } },
  }
}
