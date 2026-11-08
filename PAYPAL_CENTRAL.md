# Compras anuales PayPal para CONTA FP360 Central

La cuenta de PayPal se configura en la aplicación de servidor Central, no en un
conector de Replit ni en Studio/Aula. La tarifa base acordada es **10 € por aula
y año**, sin soporte personalizado. Las compras implementadas solo funcionan en
**PayPal Sandbox**. Los cobros de producción están bloqueados hasta recibir
aprobación expresa y resolver los impuestos y condiciones comerciales pendientes.

## Acceso

1. Instalar Central siguiendo `UBUNTU_SERVER.md` y activar HTTPS.
2. Acceder con el administrador general cuyo correo coincide con
   `platform_owner_email` en la configuración privada creada al instalar.
3. Abrir **Administración** y localizar **Configuración de PayPal**.
4. En PayPal Developer, crear una aplicación REST de Sandbox y un webhook Sandbox.
   Configurar su URL con el endpoint que muestra Central:
   `https://DOMINIO-CENTRAL/api.php?r=paypal_webhook`.
5. Suscribir el webhook a `CHECKOUT.ORDER.APPROVED`, `PAYMENT.CAPTURE.COMPLETED`,
   `PAYMENT.CAPTURE.PENDING`, `PAYMENT.CAPTURE.DECLINED`,
   `PAYMENT.CAPTURE.REFUNDED`, `PAYMENT.CAPTURE.REVERSED`,
   `CUSTOMER.DISPUTE.CREATED`, `PAYMENT.REFUND.PENDING` y `PAYMENT.REFUND.FAILED`.
6. Elegir **Pruebas (Sandbox)** e introducir Client ID, Client Secret, Merchant ID
   y Webhook ID de Sandbox. No utilizar credenciales reales para las compras.
7. Guardar y pulsar **Comprobar conexión sin cobrar**.

Los administradores de centros, profesores y alumnos no pueden leer ni cambiar
esta configuración. No se solicita ni se debe enviar ninguna credencial por chat.

## Qué hace esta versión

- Guarda la configuración en SQLite con cifrado autenticado `sodium secretbox`.
- Mantiene la clave de cifrado en `.paypal-config.key`, junto a la base de datos,
  **fuera del directorio público**, con permisos `0600`.
- No devuelve Client Secret ni Client ID completos al navegador. El identificador
  se muestra parcialmente oculto y ambos campos se vacían tras guardar.
- Los campos vacíos conservan las credenciales anteriores. Cambiar el Client ID
  requiere también su secreto; cambiar de entorno requiere ambas credenciales.
- Exige confirmación explícita al guardar el entorno de producción.
- Comprueba credenciales mediante OAuth con los servidores HTTPS oficiales de
  PayPal. No sigue redirecciones ni acepta direcciones de servidor alternativas.
- No almacena ni devuelve tokens OAuth o respuestas sin filtrar del proveedor.
- Registra quién guardó, comprobó o eliminó la configuración, sin secretos.
- Rechaza cambios de formularios antiguos si otra sesión ha cambiado las
  credenciales. Actualizar otros datos del panel no sobrescribe borradores.
- La eliminación requiere confirmación y no elimina usuarios, aulas ni trabajos.
- El Client Secret, Merchant ID y Webhook ID se mantienen cifrados en Central.

## Compra y renovación

- La cuenta docente autenticada crea un pedido para un número entero de aulas.
  Central calcula el precio, en EUR, a partir de la tarifa fija y asocia el pedido
  a su identificador de usuario; el navegador no puede fijar importe ni titular.
- Cada pedido tiene una clave idempotente y una orden PayPal estable. PayPal
  recibe un `PayPal-Request-Id` determinista para tolerar reintentos sin duplicar
  órdenes o capturas.
- El botón abre la aprobación de PayPal Sandbox. El retorno del navegador nunca
  concede la licencia por sí solo: Central captura/consulta la orden y exige
  estado `COMPLETED`, importe y moneda exactos, `custom_id`/`invoice_id` esperados,
  Merchant ID configurado y captura completada antes de crear o ampliar el derecho
  anual del docente.
- Central verifica la firma de cada webhook llamando a PayPal
  `verify-webhook-signature`. Guarda el ID del evento para ignorar repeticiones.
  Las aprobaciones y pagos pendientes no activan ni extienden licencias.
- Las renovaciones son manuales. Una renovación anticipada empieza al terminar el
  período ya pagado; si la licencia expiró, el nuevo año empieza al confirmarse
  el pago. La ampliación de aulas durante un período activo se prorratea y mantiene
  la fecha de vencimiento común.
- Un reembolso se consulta en PayPal contra la captura original; reembolsos parciales
  o totales dejan la licencia en revisión. Reversiones y disputas suspenden el
  derecho asociado para revisión. No se borran grupos ni trabajos existentes.
- Los pedidos y estados visibles aparecen en el panel de la cuenta docente.
  No se almacenan datos de tarjeta ni se inicia una suscripción recurrente.

## Bloqueo de producción

Los endpoints de crear orden, capturar y recibir webhooks solo admiten la
configuración `sandbox`, y las URL de aprobación se restringen a dominios Sandbox.
Aunque se guarden o comprueben credenciales `live`, Central no envía pedidos ni
capturas a producción. El selector de entorno no equivale a autorización de venta.
No habilitar producción sin aprobación expresa del titular, confirmación fiscal
del precio final y pruebas completas en el entorno real.

Comprobar una conexión de producción solicita un token OAuth de producción, pero
**no crea pedidos ni realiza cobros**. Una conexión correcta solo acredita que
PayPal acepta esas credenciales: no valida impuestos, webhooks, facturas ni ventas.

## Requisitos y copias

PHP necesita `pdo_sqlite`, `sodium` para el cifrado y `curl` para comprobar la
conexión, además de los requisitos originales de Central. En Ubuntu 24.04, instalar
la extensión curl de la versión de PHP empleada y comprobar:

```bash
php -r 'foreach (["pdo_sqlite","sodium","curl"] as $e) echo $e.": ".(extension_loaded($e)?"OK":"FALTA").PHP_EOL;'
```

Una base de datos situada dentro del directorio web no es válida para guardar
estas credenciales; trasladar los datos y ajustar la configuración privada antes
de utilizarlas. No existe alternativa de almacenamiento en texto claro.

Respaldar conjuntamente SQLite **y el archivo oculto de clave**, con acceso
restringido y cifrado de las copias. Perder la clave impide descifrar las
credenciales; no se regenera silenciosamente. Restaurar la clave correspondiente
o eliminar expresamente la configuración desde el panel e introducirla de nuevo.
La clave conservada tras eliminar la configuración permite futuros guardados;
el borrado no revoca credenciales o tokens en PayPal.

## Límites y pasos antes de vender

- La integración queda en Sandbox hasta aprobación expresa. No se han realizado
  compras reales ni se ha probado contra una cuenta PayPal Sandbox externa.
- Deben confirmarse impuestos, precio final, documentación fiscal, condiciones de
  contratación, desistimientos y procedimiento de reembolso antes de activar ventas.
- Las licencias de pago se guardan por docente. Los límites operativos al crear
  grupos, archivado, período de gracia y caducidad completa se implementan en la
  gestión general de licencias de Central; no se deben considerar sustituidos por
  este flujo de pagos.
- Studio y Aula continúan sin Client ID, Client Secret, Merchant ID ni Webhook ID.
  La URL de Central sigue configurándose manualmente.

## Pruebas

```bash
python3 central/tests/test_paypal_settings.py
python3 central/tests/test_paypal_payments.py
CHROMIUM_EXECUTABLE=/ruta/a/chromium python3 central/tests/test_paypal_settings.py --browser
```

Las pruebas utilizan PHP/SQLite reales y cuentas, órdenes, capturas y secretos
ficticios en directorios temporales. No llaman a PayPal. Verifican la lógica local
de órdenes, firma ausente/inválida, importes, destinatario, concesión idempotente,
pagos pendientes, reembolsos, renovaciones, roles y bloqueo de producción. Una
compra completa de extremo a extremo requiere que el titular configure sus datos
Sandbox en Central y realice la prueba desde su propia cuenta PayPal de pruebas.

Referencias oficiales:

- https://developer.paypal.com/api/rest/webhooks/
- https://developer.paypal.com/api/rest/webhooks/event-names/
- https://developer.paypal.com/api/payments/v2/captures-get/
- https://developer.paypal.com/api/payments/v2/refunds-get/

Referencia del proveedor:
https://developer.paypal.com/api/rest/authentication/
