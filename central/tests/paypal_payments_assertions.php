<?php
declare(strict_types=1);

require __DIR__.'/../cpanel/bootstrap.php';
require __DIR__.'/../cpanel/paypal.php';
require __DIR__.'/../cpanel/paypal-payments.php';

function check(bool $condition,string $message): void {
    if (!$condition) throw new RuntimeException($message);
}

paypal_settings_schema();
paypal_payments_schema();
$teacher=fetch_one("SELECT id FROM users WHERE email='teacher@example.test'");
check($teacher!==null,'Falta la cuenta docente ficticia');
$teacherId=(int)$teacher['id'];
$settings=paypal_settings_row();
check($settings!==null,'Falta la configuración de Sandbox');
$private=paypal_settings_decrypt($settings);
check($private['merchant_id']==='MerchantSandbox123','El ID del comercio no se conservó cifrado');
check($private['webhook_id']==='WebhookSandbox123','El webhook no se conservó cifrado');

check(paypal_cents('10.00')===1000 && paypal_cents('10.5')===1050,'Conversión de céntimos incorrecta');
check(paypal_cents('1e2')===null && paypal_cents('-1.00')===null,'Se aceptó un importe mal formado');
check(paypal_add_year('2024-02-29T00:00:00Z')==='2025-02-28T00:00:00Z','El año bisiesto no se limita correctamente');

$now=gmdate('Y-m-d\TH:i:s\Z');
$start=(new DateTimeImmutable($now))->modify('-6 months')->format('Y-m-d\TH:i:s\Z');
$expiry=(new DateTimeImmutable($now))->modify('+6 months')->format('Y-m-d\TH:i:s\Z');
db()->prepare('INSERT INTO teacher_paid_licenses(teacher_id,classroom_limit,starts_at,expires_at,status,last_order_id,updated_at)
 VALUES(?,2,?,?,"active",NULL,?) ON CONFLICT(teacher_id) DO UPDATE SET classroom_limit=2,starts_at=excluded.starts_at,expires_at=excluded.expires_at,status="active",last_order_id=NULL')
    ->execute([$teacherId,$start,$expiry,$now]);
$renewal=paypal_quote($teacherId,2);
check($renewal['intent']==='renewal' && $renewal['amount_cents']===2000,'La renovación manual no cotiza un año por aula');
check($renewal['grant_starts_at']===$expiry &&
      $renewal['grant_expires_at']===paypal_add_year($expiry),'La renovación anticipada no prolonga desde la fecha pagada');
$expansion=paypal_quote($teacherId,3);
check($expansion['intent']==='expansion' && $expansion['amount_cents']>0 &&
      $expansion['amount_cents']<1000,'La ampliación no prorratea el período restante');

$id='aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa';
$providerId='PAYPALORDER-SANDBOX-123';
$captureId='CAPTURE-SANDBOX-123';
db()->prepare('INSERT INTO paypal_orders(id,teacher_id,request_key,intent,target_classrooms,previous_classrooms,previous_expires_at,grant_starts_at,grant_expires_at,amount_cents,currency,environment,paypal_order_id,approval_url,status,created_at,updated_at)
 VALUES(?,?,?,?,?,?,?,?,?,?,"EUR","sandbox",?,"https://www.sandbox.paypal.com/checkoutnow?token=x","pending",?,?)')
    ->execute([$id,$teacherId,'request-key-renewal-123456789','renewal',2,2,$expiry,$expiry,paypal_add_year($expiry),2000,$providerId,$now,$now]);
$remote=[
 'id'=>$providerId,'status'=>'COMPLETED',
 'purchase_units'=>[[
   'custom_id'=>$id,'invoice_id'=>$id,'payee'=>['merchant_id'=>'MerchantSandbox123'],
   'amount'=>['currency_code'=>'EUR','value'=>'20.00'],
   'payments'=>['captures'=>[[
     'id'=>$captureId,'status'=>'COMPLETED','amount'=>['currency_code'=>'EUR','value'=>'20.00']
   ]]]
 ]]
];
$order=fetch_one('SELECT * FROM paypal_orders WHERE id=?',[$id]);
check(paypal_order_matches_remote($remote,$order,$private),'Se rechazó la orden pagada válida');
$bad=$remote;$bad['purchase_units'][0]['payee']['merchant_id']='DifferentMerchant123';
check(!paypal_order_matches_remote($bad,$order,$private),'Se aceptó un comercio diferente');
$bad=$remote;$bad['purchase_units'][0]['amount']['value']='19.99';
check(!paypal_order_matches_remote($bad,$order,$private),'Se aceptó un importe diferente');
$bad=$remote;$bad['status']='APPROVED';
check(!paypal_order_matches_remote($bad,$order,$private),'Una orden solo aprobada no debe conceder licencia');
$pending=$remote;$pending['purchase_units'][0]['payments']['captures'][0]['status']='PENDING';
check(paypal_order_verification($pending,$order,$private)==='pending',
    'Una captura pendiente no se distingue de un pago completado');
check(paypal_complete_order($id,$remote)==='completed','No se concedió el pedido validado');
$expiryAfter=fetch_one('SELECT expires_at FROM teacher_paid_licenses WHERE teacher_id=?',[$teacherId])['expires_at'];
check(paypal_complete_order($id,$remote)==='completed','El webhook duplicado no fue idempotente');
check(fetch_one('SELECT expires_at FROM teacher_paid_licenses WHERE teacher_id=?',[$teacherId])['expires_at']===$expiryAfter,
    'El pago duplicado extendió la licencia dos veces');

$pendingId='bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb';
db()->prepare('INSERT INTO paypal_orders(id,teacher_id,request_key,intent,target_classrooms,previous_classrooms,grant_starts_at,grant_expires_at,amount_cents,currency,environment,status,created_at,updated_at)
 VALUES(?,?,?,"purchase",1,0,?,?,1000,"EUR","sandbox","pending",?,?)')
    ->execute([$pendingId,$teacherId,'request-key-pending-1234567890',$now,paypal_add_year($now),$now,$now]);
paypal_mark_pending($pendingId,'pending_payment');
check(fetch_one('SELECT status FROM paypal_orders WHERE id=?',[$pendingId])['status']==='pending_payment',
    'El pago pendiente no conserva su estado');
check(fetch_one('SELECT status FROM teacher_paid_licenses WHERE teacher_id=?',[$teacherId])['status']==='active',
    'Un pago pendiente modificó la licencia');

$order=fetch_one('SELECT * FROM paypal_orders WHERE id=?',[$id]);
check(paypal_store_verified_refund($order,'REFUND-SANDBOX-123',$captureId,2000,'completed')==='refunded',
    'El reembolso completo no se registró');
check(paypal_store_verified_refund($order,'REFUND-SANDBOX-123',$captureId,2000,'completed')==='refunded',
    'El webhook de reembolso duplicado no es idempotente');
check((int)fetch_one("SELECT SUM(amount_cents) AS total FROM paypal_refunds WHERE order_id=?",[$id])['total']===2000,
    'El reembolso duplicado se sumó dos veces');
check(fetch_one('SELECT status FROM teacher_paid_licenses WHERE teacher_id=?',[$teacherId])['status']==='review',
    'El reembolso no dejó la licencia para revisión');

check(paypal_claim_webhook('WEBHOOK-EVENT-SANDBOX-1','PAYMENT.CAPTURE.COMPLETED',$providerId),
    'No se pudo registrar el evento de webhook');
db()->prepare("UPDATE paypal_webhook_events SET status='processed' WHERE event_id=?")
    ->execute(['WEBHOOK-EVENT-SANDBOX-1']);
check(!paypal_claim_webhook('WEBHOOK-EVENT-SANDBOX-1','PAYMENT.CAPTURE.COMPLETED',$providerId),
    'El evento de webhook repetido volvió a procesarse');
check(!paypal_verify_webhook([],['id'=>'fake','event_type'=>'PAYMENT.CAPTURE.COMPLETED'],$settings),
    'Un webhook sin firma fue aceptado');

echo "PayPal Sandbox: importes, destinatario, renovación, prorrateo, confirmación, idempotencia, pagos pendientes, reembolsos y firma de webhook OK.\n";
