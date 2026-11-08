# Plan de negocio de CONTA FP360

**Estado: tarifa y ausencia de soporte personalizado confirmadas.** El usuario ha
fijado **10 € por aula y año** y ha indicado que **no hay soporte personalizado**.
Los demás límites y condiciones siguen siendo propuestas pendientes de aprobación.
No se han activado cobros ni licencias. Este documento no constituye una previsión
de ventas contrastada ni asesoramiento fiscal o jurídico.

## 1. Decisiones del usuario

- Comercializar el servicio para varios docentes mediante PayPal.
- Vender un número de aulas con caducidad anual.
- Vincular las aplicaciones de escritorio a la cuenta del profesor concreto.
- Mantener la configuración manual de la dirección del servidor.
- Tarifa de 10 € por aula y año.
- No hay soporte personalizado.

## 2. Situación real del producto

Central ya contempla varios centros, docentes, alumnos y grupos con profesor
responsable. Los clientes de escritorio ya identifican al usuario y al servidor
autenticados. Por tanto, una cuenta individual no depende de haber realizado
un pago: el pago concede derechos comerciales a esa cuenta, no su identidad.

Central ya dispone de un modelo anual de licencia ligado a la cuenta docente,
cupos por grupo y enforcement en el servidor. Todavía no existen pedidos PayPal,
un flujo de compra que active esas licencias ni facturación comercial automatizada.
La biblioteca existente se comparte por centro; no se debe vender todavía como
un servicio con bibliotecas privadas por docente sin adaptar esa autorización.
Las pruebas actuales no acreditan capacidad para atender un volumen comercial.

## 3. Cliente, propuesta de valor y producto vendido

Cliente inicial: docentes de Formación Profesional que preparan supuestos,
distribuyen ejercicios y revisan evidencias contables y curriculares.
El alumnado utiliza Aula dentro de los grupos contratados, sin pagar otra licencia.

Se vende el servicio anual de coordinación y seguimiento de Central, integrado
con Studio y Aula: publicación, asignaciones, entregas y evaluación docente.
El trabajo local sin conexión continúa siendo parte central del producto.
No presentarlo como un ERP fiscal homologado ni como calificación automática
oficial del alumnado.

Primera oferta: un único docente titular por contrato. Los planes de centro
con varios docentes y facturación institucional se incorporarán después.

## 4. Unidad comercial: aula activa

Definición propuesta:

- Un aula equivale a un grupo docente activo, no a un ordenador, ejercicio o módulo.
- Cada aula admite hasta **35 alumnos matriculados activos**; límite por confirmar.
- El cupo contratado limita las aulas activas simultáneas del titular.
- Cada aula puede contener varios ejercicios y asignaciones.
- Archivar un aula conserva su consulta y exportación, bloquea nueva actividad
  y libera el cupo. Reactivarla exige un cupo libre.
- Un alumno puede participar en varias aulas autorizadas; la licencia se comprueba
  en el aula concreta y no bloquea sus otras aulas.
- Los grupos archivados siguen consumiendo almacenamiento. No ofrecer capacidad
  ilimitada: definir una política de uso razonable y límites de ZIP antes de vender.

La cuota se aplica en el servidor a las operaciones correspondientes, no solo
ocultando botones en Studio/Aula.

## 5. Tarifa anual confirmada

| Ejemplo de contratación | Docente titular | Aulas activas | Precio anual base |
|---|---:|---:|---:|
| Un aula | 1 | 1 | 10 € |
| Tres aulas | 1 | 3 | 30 € |
| Seis aulas | 1 | 6 | 60 € |

Tarifa confirmada: **10 € por aula y año**, con contratación del número de
aulas que necesite el profesor, en lugar de obligarlo a elegir entre tres planes.
Los ejemplos no introducen descuentos por volumen ni límites de cupo diferentes.

Queda por concretar si la tarifa indicada incluye los impuestos aplicables.
La modelización financiera de este documento los excluye; no determina el precio
fiscal final. No se presume exención por tratarse de software educativo. Antes del
lanzamiento se deben validar el régimen fiscal y el precio visible al comprador.

Propuesta de prestaciones comunes: las contrataciones se diferencian por cupo,
no por funciones académicas. El servicio es de autoservicio, con documentación,
tutoriales y preguntas frecuentes. **No hay soporte personalizado**, ni incluido
ni como extra: no se ofrece instalación asistida, formación individual,
acompañamiento ni resolución de consultas particulares.

Esto no elimina la necesidad de mantener el servicio y corregir fallos. Se debe
definir un mecanismo general para comunicar incidencias, sin convertirlo en una
promesa de atención individual ni de respuesta en un plazo no presupuestado.

Recomendación inicial: una tarifa por aula, sin múltiples complementos ni tarifa por alumno.
Como propuesta, permitir Studio en dos equipos personales del mismo docente.
No limitar dispositivos Aula por grupo: controlar matrículas y permisos.
Los límites de dispositivos y su desvinculación también requieren implementación.

### Cambios de plan

- Ampliación: cobrar la diferencia de tarifa proporcional al tiempo pendiente;
  todas las aulas mantienen la misma fecha de caducidad.
- Ejemplo ilustrativo: pasar de un aula (10 €) a tres aulas (30 €) con medio año
  pendiente cuesta 10 €,
  antes de impuestos. El servidor calcula y fija el importe del pedido.
- Reducción: aplicable al siguiente período, sin borrar grupos existentes.
- Renovación anticipada: prolonga desde la fecha de vencimiento ya pagada.
- Nueva contratación tras caducidad: comienza con el nuevo pago confirmado;
  no cobrar períodos pasados no contratados.

## 6. Identidad, privacidad y vinculación de escritorio

Mantener una separación entre:

1. **Identidad:** cuenta estable del docente; no usar la URL ni el correo PayPal
   como sustitutos del identificador de usuario.
2. **Cliente contratante:** persona o entidad que paga. Puede pagar un centro
   por cuenta de un docente; el pagador no tiene que compartir su correo de acceso.
3. **Licencia:** titular, plan, cupo, vigencia y estado de pago.
4. **Dispositivo:** instalación autorizada, con baja o sustitución controlada.
5. **Aula:** grupo con titular, matrículas y permisos específicos.

Cada profesor configura manualmente la misma URL pública de Central, inicia sesión
con su cuenta y recibe sus derechos. No necesita una URL diferente por profesor.
Studio utiliza la cuenta del profesor; Aula utiliza la cuenta del alumno y solo
accede a los grupos donde está matriculado.

Para venta individual, crear un espacio privado por docente. Compartir biblioteca
con otros profesores debe ser una decisión explícita, no la consecuencia de estar
en un centro común. El futuro plan de centro añadirá colaboración y administración
delegada sin mezclar clientes independientes.

Las instalaciones actuales vinculan el perfil local al primer usuario autenticado.
Antes de comercializar para ordenadores compartidos, se debe implantar separación
de perfiles locales o exigir cuentas independientes del sistema operativo.
No prometer que varios alumnos pueden compartir sin riesgo una misma cuenta local.

## 7. Cobro por PayPal

### Lanzamiento recomendado

**Pago único anticipado por doce meses y renovación manual**, también mediante
PayPal. Es una licencia anual, pero no un cargo recurrente oculto. Enviar avisos
de vencimiento y un enlace de renovación autenticado.

En una segunda fase, ofrecer renovación automática anual mediante PayPal
Subscriptions, únicamente con consentimiento claro, condiciones visibles y
cancelación accesible. Cancelar la renovación no elimina el período ya pagado.

### Flujo comercial

1. Crear o identificar la cuenta del docente y elegir el plan.
2. Generar en Central un pedido asociado al titular, importe, moneda y plan.
3. Realizar el pago en PayPal.
4. Central verifica el pago con PayPal, su destinatario, moneda, importe y pedido.
5. Registrar el pago y activar una sola vez la licencia.
6. Mostrar cupo y vencimiento en Central y en Studio; emitir la documentación
   comercial/fiscal correspondiente.

El retorno del navegador desde PayPal no basta para activar una licencia.
Las notificaciones deben autenticarse y procesarse de manera idempotente:
un mensaje o pago repetido no concede dos años ni duplica aulas.
Gestionar también pagos pendientes, reembolsos y disputas y reconciliar estados
con el proveedor; una comisión, autorización o suscripción creada no equivale
necesariamente a un pago cobrado.

PayPal no está conectado ni implementado actualmente. No se ha creado ninguna
suscripción, cobro real o compromiso comercial.

## 8. Vigencia anual y caducidad sin pérdida de trabajo

La licencia activa dura un año de calendario desde el pago confirmado y la fecha
de vencimiento se calcula en el servidor. Si comienza el 29 de febrero, vence el
1 de marzo del año siguiente. El servidor no confía en fechas enviadas por Studio
o Aula.

| Estado | Comportamiento implementado |
|---|---|
| Sin licencia activa | No se crean nuevas aulas; las aulas históricas en legado siguen operativas |
| Activa | Se pueden crear aulas hasta el cupo de esa cuenta docente |
| Caducada o revocada | No se crean aulas ni se sincroniza actividad nueva en las aulas vinculadas a esa licencia |

En un aula licenciada caducada se conservan el grupo, las asignaciones, las
entregas y las calificaciones. Central permite consultar informes; no permite
matricular, asignar, calificar, descargar paquetes para alumnado o sincronizar
nuevas entregas. Los ZIP, trabajos y cola pendientes ya guardados localmente
siguen disponibles en Studio/Aula y no se borran. Un reintento de una operación
que el servidor ya confirmó sigue siendo idempotente.

Los grupos que existían antes de la migración quedan explícitamente en modo
legado: no se asocian a una licencia ni se bloquean por el enforcement nuevo.
No consumen el cupo anual y continúan con su comportamiento anterior. Solo los
grupos creados después de esta transición consumen una licencia. Así se evita
convertir datos existentes en aulas caducadas o interrumpir de forma retroactiva
el trabajo docente.

No hay período de gracia ni borrado automático en la implementación actual.
Una renovación futura debe activarse desde un pago verificado; el retorno del
navegador no concede licencia por sí solo. Definir aparte reembolsos,
desistimiento cuando proceda y disputas.

## 9. Números de referencia

**Escenario hipotético, sin impuestos:**

| Clientes | Plan | Ingreso anual |
|---:|---|---:|
| 40 | Un aula, 10 € | 400 € |
| 40 | Tres aulas, 30 € | 1.200 € |
| 20 | Seis aulas, 60 € | 1.200 € |
| **100** | **Ingreso medio 28 €/docente/año** | **2.800 €** |

Supuestos de costes para ese escenario:

- Reserva hipotética para cobro y contingencias: 5 % del ingreso más 0,50 € por
  pago anual = 190 €. **No es una tarifa oficial de PayPal.** La parte fija real
  debe verificarse porque pesa especialmente en compras de 10 €.
- Infraestructura, copias y monitorización: presupuesto de 1.200 €/año.
- Documentación, gestión general de incidencias, captación y gastos profesionales/
  administrativos: presupuesto conjunto de 1.800 €/año, pendiente de contrastar.
- No se presupuesta soporte personalizado porque no se ofrece.
- Resultado: **−390 €/año**, antes de desarrollo, remuneración adicional del titular,
  impuestos y costes no contemplados.

Con esos supuestos lineales, la contribución por docente es:
28 € − 1,90 € = 26,10 €/año.
Se necesitan aproximadamente **115 docentes** para cubrir los 3.000 € de costes
fijos modelados, sin remuneración de desarrollo. Añadir un objetivo de 20.000 €
anuales para el titular elevaría ese umbral a unos **882 docentes** si se mantuvieran
el precio medio, mezcla de planes y costes. No es una promesa de rentabilidad:
la infraestructura y el mantenimiento pueden crecer y se deben medir.

Como referencia, 500 docentes con la misma mezcla generarían 14.000 € anuales
y dejarían 10.050 € bajo estos supuestos, antes de desarrollo, remuneración adicional
e impuestos. No extrapolar esta cifra sin revisar el aumento de infraestructura.

No ofrecer soporte personalizado no significa que la operación sea gratuita:
seguridad, actualizaciones, documentación y corrección de fallos necesitan tiempo
y presupuesto. El modelo debe revisarse con los costes realmente observados.

Conclusión: mantener la entrada desde 10 € exige autoservicio, contratación de varias
aulas y suficiente volumen; no se debe presentar como rentable con cien clientes.
Revisar estas hipótesis con el piloto antes de asumir gastos fijos elevados.

## 10. Captación y lanzamiento

1. **Piloto:** diez docentes con datos ficticios al principio; medir uso, incidencias
   y disposición a pagar. Cualquier descuento debe tener importe y duración claros.
2. **Primeras ventas:** demostraciones a departamentos de FP, asociaciones docentes
   y tutoriales públicos centrados en publicar un supuesto y recibir una entrega,
   sin formación individual ni acompañamiento personalizado.
3. **Conversión:** prueba de 30 días con un aula, sin requerir autorización de
   cargo automático ni borrar trabajos al terminar.
4. **Retención:** avisos de renovación, ayuda para archivar el curso y reutilizar
   materiales, informes que ahorren trabajo al profesor.
5. **Expansión:** plan de centro con varios docentes, compra institucional y
   biblioteca compartida opcional; no mezclar esta modalidad con el lanzamiento.

Objetivos iniciales a validar, no métricas ya alcanzadas: activación en siete días,
conversión de al menos seis de los diez pilotos, renovación anual del 80 % y coste
de captación inferior a 5 € por docente con esta tarifa reducida. Controlar también horas de mantenimiento,
reembolsos, errores de sincronización y picos de concurrencia.

## 11. Condiciones para comenzar a vender

- Aislamiento de clientes en biblioteca, grupos, alumnos, entregas y facturación,
  incluidas pruebas negativas entre docentes y centros.
- Alta del titular, compra, vinculación de dispositivos, cupos, vencimiento,
  ampliación, renovación, baja y exportación disponibles en interfaz y servidor.
- PayPal probado primero en Sandbox: pagos duplicados, fallidos, pendientes,
  renovaciones, reembolsos, disputas y webhooks inválidos o fuera de orden.
- Catálogos curriculares verificados; sin afirmar que una nota automática sustituye
  la evaluación del profesor.
- Ubuntu Server real con HTTPS, pruebas de carga representativas, copias consistentes
  y restauración ensayada. SQLite puede ser un punto de partida; no prometer una
  capacidad comercial sin mediciones ni sustituirlo por otro motor sin autorización.
- Instaladores reales para los destinos ofrecidos; distinguir compilación CI,
  prueba física, firmas y notarización.
- Condiciones de contratación, cancelación, ausencia de soporte personalizado,
  comunicación general de incidencias, privacidad y conservación;
  facturación conforme al régimen aplicable, no solo un justificante PayPal.
- Definir quién contrata y quién está autorizado a tratar datos del alumnado:
  pagar como docente no concede por sí solo autorización del centro para subirlos.
  Acordar responsabilidades de protección de datos y contratos de tratamiento.

## 12. Orden recomendado de implementación, todavía no autorizado

1. Espacios privados y cuentas: titular, docentes, alumnado, permisos y perfiles.
2. Catálogo de planes, cupos y licencias; pruebas de autorización y expiración.
3. Compra anual PayPal en Sandbox, confirmación verificada y renovación.
4. Pantallas de cuenta/licencia en Central y Studio; matrícula autorizada en Aula.
5. Piloto real y mediciones; habilitar ventas solo después de superar la aceptación.

No bloquear el trabajo local ni reescribir Studio/Aula como aplicaciones web.
No se implementan cobros ni restricciones por el mero hecho de aprobar este
documento: la siguiente fase debe acordarse explícitamente.

## Fuentes técnicas

Documentación oficial consultada el 8 de noviembre de 2026:

- PayPal Subscriptions: https://developer.paypal.com/docs/api/subscriptions/v1/
- PayPal Webhooks, verificación de autenticidad y reintentos:
  https://developer.paypal.com/api/rest/webhooks/

Las comisiones y obligaciones fiscales deben comprobarse para la cuenta comercial,
país y operaciones concretas antes del lanzamiento; no se han supuesto tarifas oficiales.
