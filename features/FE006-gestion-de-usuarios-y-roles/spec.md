# FE006 — Gestión de usuarios y roles

> Estado: **aprobada** el 2026-10-02. Depende de FE001, que ya incluye el login mock y los cuatro roles base.

## Objetivo

Administrar usuarios, roles y permisos de la plataforma desde la UI, de modo que el acceso a cada sección y acción dependa del rol asignado.

## Criterios de aceptación

1. La sección **Usuarios y roles** tiene dos pestañas: Usuarios y Roles.
2. **Usuarios:** listado con nombre, email, rol, estado (activo o inactivo) y último acceso, con búsqueda por nombre o email y filtro por rol y estado.
3. Permite crear usuarios (nombre, email único, rol), editarlos y desactivarlos o reactivarlos. Un email duplicado devuelve `409` y el error se muestra junto al campo. Un usuario desactivado no puede iniciar sesión (test).
4. **Roles:** listado de roles con su nº de usuarios. Los roles base (`admin`, `supervisor`, `analista` y `viewer`) no se pueden borrar. Se pueden crear roles personalizados.
5. Una matriz de permisos (roles en columnas y permisos en filas) permite activar o desactivar: ver dashboards, ver conversaciones, usar el explorador, usar la búsqueda semántica, ver flujos, editar y ejecutar flujos, ver configuración, editar configuración y administrar usuarios y roles.
6. Al cambiar los permisos de un rol, cambian el menú y las acciones de sus usuarios en su siguiente petición, y el backend responde `403` a lo retirado (test end-to-end de API).
7. **Protección:** nadie puede quitarse a sí mismo el permiso de administrar usuarios, ni desactivar o degradar al último `admin` activo (test).
8. Solo quien tiene el permiso «administrar usuarios y roles» ve la sección; el resto recibe `403` en la API.
9. Cada alta, baja o cambio de rol o de permisos queda en el registro de auditoría compartido con FE005.

## Conocimiento afectado

- [Decisiones](../../vault/decisiones/Index.md): ADR-003 (auth mock por roles, creada en FE001) se amplía con el modelo de permisos granular.
- [Glosario](../../vault/glosario/terminos-del-harness.md): hay que añadir «rol», «permiso» y la lista de permisos.

## Alcance

- API y UI de usuarios, roles y matriz de permisos, protecciones de administración y auditoría.

## Fuera de alcance

- SSO, OAuth, MFA y recuperación de contraseña.
- Restringir los datos visibles por cola o equipo (ámbito de datos por usuario).
- Invitaciones por email.
- Persistencia entre reinicios del backend.

## Riesgos y asunciones

- **Asunción:** los permisos controlan secciones y acciones, no qué conversaciones ve cada usuario. Si se necesita un ámbito por cola, hará falta una feature nueva.
- **Riesgo:** el enforcement de permisos debe centralizarse en una dependencia de FastAPI para no olvidar ningún endpoint; un test recorre todas las rutas y comprueba que ninguna queda sin protección.
