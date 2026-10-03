import { createElement, type ComponentProps } from 'react'
import type SwaggerUI from 'swagger-ui-react'
import { listOperations, type OpenApiDoc } from '../config/openapi/spec'

type SwaggerUIProps = ComponentProps<typeof SwaggerUI>

/** Props de la última vez que se pintó el visor, para comprobar su configuración. */
export const swaggerProps: { current: SwaggerUIProps | null } = { current: null }

/** Doble de Swagger UI para jsdom (ver `setup.ts`): una fila por operación de la especificación recibida. */
export default function SwaggerUIStub(props: SwaggerUIProps) {
  swaggerProps.current = props
  const operations = listOperations(props.spec as OpenApiDoc)
  return createElement('ul', { 'aria-label': 'Visor OpenAPI' },
    operations.map((o) => createElement('li', { key: `${o.method} ${o.path}` }, `${o.method} ${o.path}`)))
}
