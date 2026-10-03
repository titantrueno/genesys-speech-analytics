import { afterEach, describe, expect, it } from 'vitest'
import { tokenStorage } from '../../api/client'
import { openApiDoc } from '../../test/openapiFixtures'
import { authInterceptor, countOperations, filterSpec, listOperations, withServer } from './spec'

const keys = (doc: ReturnType<typeof openApiDoc>) => listOperations(doc).map((o) => `${o.method} ${o.path}`)

describe('countOperations', () => {
  it('cuenta los métodos HTTP e ignora los parámetros comunes de la ruta', () => {
    expect(countOperations(openApiDoc())).toBe(9)
  })
})

describe('filterSpec', () => {
  it('sin texto ni dominio devuelve todas las operaciones', () => {
    expect(countOperations(filterSpec(openApiDoc(), { text: '', tag: '' }))).toBe(9)
    expect(countOperations(filterSpec(openApiDoc(), { text: '   ', tag: '' }))).toBe(9)
  })

  it('busca en la descripción del dominio: «usuarios» deja las operaciones de usuarios y roles', () => {
    expect(keys(filterSpec(openApiDoc(), { text: 'usuarios', tag: '' }))).toEqual([
      'GET /api/users', 'POST /api/users', 'DELETE /api/roles/{role_id}',
    ])
  })

  it('busca por método: «delete» deja solo operaciones DELETE', () => {
    expect(keys(filterSpec(openApiDoc(), { text: 'delete', tag: '' }))).toEqual([
      'DELETE /api/config/compliance-checks/{check_id}', 'DELETE /api/roles/{role_id}',
    ])
  })

  it('busca en la descripción: «config:edit» deja las operaciones que lo exigen', () => {
    expect(keys(filterSpec(openApiDoc(), { text: 'config:edit', tag: '' }))).toEqual([
      'PUT /api/config/general', 'PUT /api/config/compliance-checks/{check_id}', 'DELETE /api/config/compliance-checks/{check_id}',
    ])
  })

  it('busca por ruta y por resumen', () => {
    expect(keys(filterSpec(openApiDoc(), { text: '/api/health', tag: '' }))).toEqual(['GET /api/health'])
    expect(keys(filterSpec(openApiDoc(), { text: 'crear un', tag: '' }))).toEqual(['POST /api/users'])
  })

  it('encuentra una operación escrita como la muestra Swagger («método ruta»)', () => {
    expect(keys(filterSpec(openApiDoc(), { text: 'GET /api/users', tag: '' }))).toEqual(['GET /api/users'])
    expect(keys(filterSpec(openApiDoc(), { text: 'delete /api/roles', tag: '' }))).toEqual(['DELETE /api/roles/{role_id}'])
  })

  it('con varias palabras exige todas, aunque estén en campos distintos', () => {
    expect(keys(filterSpec(openApiDoc(), { text: 'borrar roles', tag: '' }))).toEqual(['DELETE /api/roles/{role_id}'])
    expect(keys(filterSpec(openApiDoc(), { text: '  put   config:edit  ', tag: '' }))).toEqual([
      'PUT /api/config/general', 'PUT /api/config/compliance-checks/{check_id}',
    ])
  })

  it('trata los caracteres especiales como texto', () => {
    expect(keys(filterSpec(openApiDoc(), { text: '{check_id}', tag: '' }))).toHaveLength(2)
    expect(countOperations(filterSpec(openApiDoc(), { text: '.*', tag: '' }))).toBe(0)
  })

  it('funciona con una especificación sin dominios declarados', () => {
    const doc = { ...openApiDoc(), tags: undefined }
    expect(countOperations(filterSpec(doc, { text: 'usuario', tag: '' }))).toBe(2)
    expect(filterSpec(doc, { text: '', tag: '' }).tags).toBeUndefined()
  })

  it('no distingue mayúsculas ni tildes, en la búsqueda ni en el texto', () => {
    expect(keys(filterSpec(openApiDoc(), { text: 'BUSQUEDA SEMANTICA', tag: '' }))).toEqual(['POST /api/search'])
    expect(keys(filterSpec(openApiDoc(), { text: 'está en uso', tag: '' }))).toEqual(['DELETE /api/config/compliance-checks/{check_id}'])
  })

  it('el dominio limita la vista y se combina con el texto', () => {
    expect(countOperations(filterSpec(openApiDoc(), { text: '', tag: 'config' }))).toBe(4)
    expect(keys(filterSpec(openApiDoc(), { text: 'delete', tag: 'config' }))).toEqual(['DELETE /api/config/compliance-checks/{check_id}'])
  })

  it('poda rutas y dominios vacíos y conserva el resto del documento', () => {
    const filtered = filterSpec(openApiDoc(), { text: 'borrar un check', tag: '' })
    expect(Object.keys(filtered.paths)).toEqual(['/api/config/compliance-checks/{check_id}'])
    const item = filtered.paths['/api/config/compliance-checks/{check_id}']
    expect(Object.keys(item)).toEqual(['parameters', 'delete'])
    expect(filtered.tags?.map((t) => t.name)).toEqual(['config'])
    expect(filtered.info).toEqual(openApiDoc().info)
    expect(filtered.components).toEqual(openApiDoc().components)
  })

  it('sin coincidencias deja el documento sin rutas', () => {
    const filtered = filterSpec(openApiDoc(), { text: 'no-existe', tag: '' })
    expect(countOperations(filtered)).toBe(0)
    expect(filtered.paths).toEqual({})
  })

  it('no modifica la especificación original', () => {
    const doc = openApiDoc()
    filterSpec(doc, { text: 'delete', tag: 'users' })
    expect(doc).toEqual(openApiDoc())
  })
})

describe('withServer', () => {
  it('sin URL de API no declara servidor: Swagger usa el origen de la app y el proxy', () => {
    expect(withServer(openApiDoc(), '').servers).toBeUndefined()
  })

  it('con URL de API la declara como servidor, sin barra final', () => {
    expect(withServer(openApiDoc(), 'http://api.local:8000/').servers).toEqual([{ url: 'http://api.local:8000' }])
  })
})

describe('authInterceptor', () => {
  afterEach(() => tokenStorage.clear())

  it('añade el token de la sesión actual', () => {
    tokenStorage.set('token-de-prueba')
    const request = authInterceptor({ url: '/api/config', headers: {} })
    expect(request.headers?.Authorization).toBe('Bearer token-de-prueba')
  })

  it('lee la sesión en cada petición: tras cerrar sesión ya no añade token', () => {
    tokenStorage.set('token-de-prueba')
    authInterceptor({ url: '/api/config', headers: {} })
    tokenStorage.clear()
    expect(authInterceptor({ url: '/api/config', headers: {} }).headers?.Authorization).toBeUndefined()
  })

  it('respeta una cabecera Authorization puesta a mano con «Authorize»', () => {
    tokenStorage.set('token-de-prueba')
    expect(authInterceptor({ url: '/api/config', headers: { Authorization: 'Bearer otro' } }).headers?.Authorization).toBe('Bearer otro')
  })

  it('crea las cabeceras si la petición no trae', () => {
    tokenStorage.set('token-de-prueba')
    expect(authInterceptor({ url: '/api/config' }).headers?.Authorization).toBe('Bearer token-de-prueba')
  })
})
