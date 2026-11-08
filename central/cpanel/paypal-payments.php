<?php
declare(strict_types=1);

/**
 * Órdenes PayPal y concesiones anuales de aulas. La producción queda cerrada:
 * no existe ningún endpoint de compra/captura que acepte configuración live.
 */
final class PayPalPaymentError extends RuntimeException {}

function paypal_payments_schema(): void {
    db()->exec(<<<'SQL'
CREATE TABLE IF NOT EXISTS teacher_paid_licenses(
 teacher_id INTEGER PRIMARY KEY REFERENCES users(id),
 classroom_limit INTEGER NOT NULL CHECK(classroom_limit BETWEEN 1 AND 100),
 starts_at TEXT NOT NULL,
 expires_at TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('active','review','suspended')),
 last_order_id TEXT,
 updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS paypal_orders(
 id TEXT PRIMARY KEY,
 teacher_id INTEGER NOT NULL REFERENCES users(id),
 request_key TEXT NOT NULL,
 intent TEXT NOT NULL CHECK(intent IN ('purchase','renewal','expansion')),
 target_classrooms INTEGER NOT NULL CHECK(target_classrooms BETWEEN 1 AND 100),
 previous_classrooms INTEGER NOT NULL DEFAULT 0,
 previous_expires_at TEXT,
 grant_starts_at TEXT NOT NULL,
 grant_expires_at TEXT NOT NULL,
 amount_cents INTEGER NOT NULL CHECK(amount_cents BETWEEN 1 AND 1000000),
 currency TEXT NOT NULL DEFAULT 'EUR' CHECK(currency='EUR'),
 environment TEXT NOT NULL CHECK(environment='sandbox'),
 paypal_order_id TEXT UNIQUE,
 approval_url TEXT,
 status TEXT NOT NULL CHECK(status IN (
  'creating','pending','approved','pending_payment','completed','failed',
  'cancelled','expired','refunded','review','disputed'
 )),
 capture_id TEXT UNIQUE,
 paid_at TEXT,
 created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL,
 UNIQUE(teacher_id,request_key)
);
CREATE INDEX IF NOT EXISTS idx_paypal_orders_teacher ON paypal_orders(teacher_id,created_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS idx_paypal_one_open_order_per_teacher
 ON paypal_orders(teacher_id)
 WHERE status IN ('creating','pending','approved','pending_payment');
CREATE TABLE IF NOT EXISTS paypal_order_events(
 id INTEGER PRIMARY KEY,
 order_id TEXT NOT NULL REFERENCES paypal_orders(id),
 event_type TEXT NOT NULL,
 event_key TEXT,
 created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS paypal_webhook_events(
 event_id TEXT PRIMARY KEY,
 event_type TEXT NOT NULL,
 order_id TEXT,
 status TEXT NOT NULL CHECK(status IN ('processing','processed','failed')),
 received_at TEXT NOT NULL,
 processed_at TEXT
);
CREATE TABLE IF NOT EXISTS paypal_refunds(
 refund_id TEXT PRIMARY KEY,
 order_id TEXT NOT NULL REFERENCES paypal_orders(id),
 capture_id TEXT NOT NULL,
 amount_cents INTEGER NOT NULL CHECK(amount_cents>0),
 status TEXT NOT NULL CHECK(status IN ('completed','pending','failed')),
 created_at TEXT NOT NULL
);
SQL);
}

function paypal_payment_event(string $orderId,string $type,?string $key=null): void {
    db()->prepare('INSERT INTO paypal_order_events(order_id,event_type,event_key,created_at) VALUES(?,?,?,?)')
        ->execute([$orderId,$type,$key,gmdate('Y-m-d\TH:i:s\Z')]);
}

function paypal_payment_base(array $settings): string {
    if (($settings['environment']??'')!=='sandbox') {
        throw new PayPalPaymentError('Los pedidos y cobros de producción están desactivados. Solo está disponible PayPal Sandbox.');
    }
    return 'https://api-m.sandbox.paypal.com';
}

/** Solicita un token efímero al endpoint oficial; no lo persiste ni lo registra. */
function paypal_access_token(array $settings): string {
    if (!function_exists('curl_init')) throw new PayPalPaymentError('Se requiere la extensión curl de PHP.');
    $credentials=paypal_settings_decrypt($settings);
    $body='';
    $curl=curl_init(paypal_payment_base($settings).'/v1/oauth2/token');
    curl_setopt_array($curl,[
        CURLOPT_POST=>true,
        CURLOPT_POSTFIELDS=>'grant_type=client_credentials',
        CURLOPT_HTTPHEADER=>['Accept: application/json','Content-Type: application/x-www-form-urlencoded'],
        CURLOPT_HTTPAUTH=>CURLAUTH_BASIC,
        CURLOPT_USERPWD=>$credentials['client_id'].':'.$credentials['client_secret'],
        CURLOPT_FOLLOWLOCATION=>false,
        CURLOPT_PROTOCOLS=>CURLPROTO_HTTPS,
        CURLOPT_SSL_VERIFYPEER=>true,
        CURLOPT_SSL_VERIFYHOST=>2,
        CURLOPT_CONNECTTIMEOUT=>5,
        CURLOPT_TIMEOUT=>15,
        CURLOPT_WRITEFUNCTION=>static function($handle,string $chunk) use (&$body): int {
            if (strlen($body)+strlen($chunk)>131072) return 0;
            $body.=$chunk;
            return strlen($chunk);
        },
    ]);
    $ok=curl_exec($curl)!==false;
    $code=(int)curl_getinfo($curl,CURLINFO_RESPONSE_CODE);
    curl_close($curl);
    $data=json_decode($body,true);
    if (!$ok || $code!==200 || !is_array($data) || !is_string($data['access_token']??null) ||
        ($data['token_type']??'')!=='Bearer') {
        throw new PayPalPaymentError('PayPal no ha permitido validar la conexión Sandbox.');
    }
    return $data['access_token'];
}

/** Llamadas HTTPS a endpoints PayPal fijos, sin redirecciones ni URLs aportadas por clientes. */
function paypal_api_call(array $settings,string $method,string $path,?array $payload=null,?string $requestId=null): array {
    if (!preg_match('~^/(?:v2/checkout/orders(?:/[A-Za-z0-9_-]+(?:/capture)?)?|v2/payments/(?:captures|refunds)/[A-Za-z0-9_-]+|v1/notifications/verify-webhook-signature)$~D',$path)) {
        throw new PayPalPaymentError('Ruta interna de PayPal no permitida.');
    }
    $token=paypal_access_token($settings);
    $headers=['Accept: application/json','Authorization: Bearer '.$token];
    if ($payload!==null) {
        $headers[]='Content-Type: application/json';
    }
    if ($requestId!==null) $headers[]='PayPal-Request-Id: '.$requestId;
    $body='';
    $curl=curl_init(paypal_payment_base($settings).$path);
    curl_setopt_array($curl,[
        CURLOPT_CUSTOMREQUEST=>$method,
        CURLOPT_POSTFIELDS=>$payload===null?null:json_encode($payload,JSON_THROW_ON_ERROR|JSON_UNESCAPED_SLASHES),
        CURLOPT_HTTPHEADER=>$headers,
        CURLOPT_FOLLOWLOCATION=>false,
        CURLOPT_PROTOCOLS=>CURLPROTO_HTTPS,
        CURLOPT_SSL_VERIFYPEER=>true,
        CURLOPT_SSL_VERIFYHOST=>2,
        CURLOPT_CONNECTTIMEOUT=>5,
        CURLOPT_TIMEOUT=>20,
        CURLOPT_WRITEFUNCTION=>static function($handle,string $chunk) use (&$body): int {
            if (strlen($body)+strlen($chunk)>262144) return 0;
            $body.=$chunk;
            return strlen($chunk);
        },
    ]);
    $ok=curl_exec($curl)!==false;
    $code=(int)curl_getinfo($curl,CURLINFO_RESPONSE_CODE);
    curl_close($curl);
    $data=json_decode($body,true);
    if (!$ok || !is_array($data)) throw new PayPalPaymentError('No se pudo completar la consulta segura a PayPal.');
    if ($code<200 || $code>=300) {
        // No devolvemos el cuerpo del proveedor: puede contener información de cuenta.
        throw new PayPalPaymentError('PayPal no ha aceptado la operación (HTTP '.$code.').');
    }
    return $data;
}

function paypal_cents(mixed $value): ?int {
    if (!is_string($value) || !preg_match('/^(0|[1-9][0-9]{0,7})(?:\.([0-9]{1,2}))?$/D',$value,$m)) return null;
    return ((int)$m[1])*100+(int)str_pad($m[2]??'',2,'0');
}

/** Suma un año natural y limita el día al último día del mes (incluye 29 de febrero). */
function paypal_add_year(string $isoDate): string {
    try { $from=new DateTimeImmutable($isoDate,new DateTimeZone('UTC')); }
    catch(Throwable $e) { throw new PayPalPaymentError('La fecha de licencia no es válida.'); }
    $year=(int)$from->format('Y')+1;
    $month=(int)$from->format('m');
    $day=min((int)$from->format('d'),cal_days_in_month(CAL_GREGORIAN,$month,$year));
    return $from->setDate($year,$month,$day)->format('Y-m-d\TH:i:s\Z');
}

function paypal_license_for_teacher(int $teacherId): ?array {
    return fetch_one('SELECT * FROM teacher_paid_licenses WHERE teacher_id=?',[$teacherId]);
}

function paypal_quote(int $teacherId,int $targetClassrooms): array {
    if ($targetClassrooms<1 || $targetClassrooms>100) fail(422,'El número de aulas debe estar entre 1 y 100.');
    $now=gmdate('Y-m-d\TH:i:s\Z');
    $license=paypal_license_for_teacher($teacherId);
    if ($license && in_array($license['status'],['review','suspended'],true)) {
        fail(409,'La licencia está en revisión y no puede modificarse hasta resolver el pago.');
    }
    $current=$license && $license['status']==='active' && $license['expires_at']>$now
        ? (int)$license['classroom_limit'] : 0;
    $expiry=$current>0?$license['expires_at']:null;
    if ($current===0) {
        $intent='purchase'; $cents=$targetClassrooms*1000;
        $start=$now; $end=paypal_add_year($start);
    } elseif ($targetClassrooms<$current) {
        fail(409,'La reducción del cupo se aplicará en la siguiente renovación.');
    } elseif ($targetClassrooms===$current) {
        $intent='renewal'; $cents=$targetClassrooms*1000;
        $start=max($now,$license['expires_at']); $end=paypal_add_year($start);
    } else {
        $intent='expansion'; $difference=$targetClassrooms-$current;
        $start=$license['starts_at']; $end=$license['expires_at'];
        $total=max(1,strtotime($end)-strtotime($start));
        $remaining=max(0,strtotime($end)-strtotime($now));
        $cents=(int)ceil($difference*1000*min(1,$remaining/$total));
        $cents=max(1,$cents);
    }
    return [
        'intent'=>$intent,'target_classrooms'=>$targetClassrooms,
        'previous_classrooms'=>$current,'previous_expires_at'=>$expiry,
        'grant_starts_at'=>$start,'grant_expires_at'=>$end,'amount_cents'=>$cents,
    ];
}

function paypal_format_cents(int $cents): string {
    return intdiv($cents,100).'.'.str_pad((string)($cents%100),2,'0',STR_PAD_LEFT);
}

function paypal_order_verification(array $remote,array $order,array $credentials): string {
    if (($remote['id']??'')!==($order['paypal_order_id']??null) ||
        !is_array($remote['purchase_units']??null) || count($remote['purchase_units'])!==1) return 'invalid';
    $unit=$remote['purchase_units'][0];
    if (($unit['custom_id']??'')!==$order['id'] || ($unit['invoice_id']??'')!==$order['id'] ||
        ($unit['payee']['merchant_id']??'')!==($credentials['merchant_id']??'')) return 'invalid';
    $amount=$unit['amount']??[];
    if (($amount['currency_code']??'')!=='EUR' ||
        paypal_cents($amount['value']??null)!==(int)$order['amount_cents']) return 'invalid';
    $captures=$unit['payments']['captures']??null;
    if (!is_array($captures) || count($captures)!==1) {
        return ($remote['status']??'')==='COMPLETED'?'invalid':'pending';
    }
    $capture=$captures[0]; $captureAmount=$capture['amount']??[];
    if (!is_string($capture['id']??null) || $capture['id']==='' ||
        ($captureAmount['currency_code']??'')!=='EUR' ||
        paypal_cents($captureAmount['value']??null)!==(int)$order['amount_cents']) return 'invalid';
    if (($capture['status']??'')==='COMPLETED' && ($remote['status']??'')==='COMPLETED') return 'completed';
    if (($capture['status']??'')==='PENDING') return 'pending';
    return 'invalid';
}

function paypal_order_matches_remote(array $remote,array $order,array $credentials): bool {
    return paypal_order_verification($remote,$order,$credentials)==='completed';
}

function paypal_complete_order(string $localId,array $remote): string {
    $order=fetch_one('SELECT * FROM paypal_orders WHERE id=?',[$localId]);
    if (!$order) throw new PayPalPaymentError('La orden local no existe.');
    if ($order['status']==='completed') return 'completed';
    $settings=paypal_settings_row();
    if (!$settings || $settings['environment']!=='sandbox') throw new PayPalPaymentError('La configuración de pagos Sandbox no está disponible.');
    $credentials=paypal_settings_decrypt($settings);
    $verification=paypal_order_verification($remote,$order,$credentials);
    if ($verification==='pending') {
        db()->prepare("UPDATE paypal_orders SET status='pending_payment',updated_at=? WHERE id=? AND status<>'completed'")
            ->execute([gmdate('Y-m-d\TH:i:s\Z'),$localId]);
        paypal_payment_event($localId,'pending_payment_verified');
        return 'pending_payment';
    }
    if ($verification!=='completed') {
        paypal_payment_event($localId,'payment_verification_failed');
        db()->prepare("UPDATE paypal_orders SET status='review',updated_at=? WHERE id=? AND status<>'completed'")
            ->execute([gmdate('Y-m-d\TH:i:s\Z'),$localId]);
        return 'review';
    }
    $unit=$remote['purchase_units'][0];
    $capture=$unit['payments']['captures'][0];
    $now=gmdate('Y-m-d\TH:i:s\Z');
    $db=db(); $db->beginTransaction();
    try {
        $locked=fetch_one('SELECT * FROM paypal_orders WHERE id=?',[$localId]);
        if (!$locked) throw new PayPalPaymentError('La orden local no existe.');
        if ($locked['status']==='completed') { $db->commit(); return 'completed'; }
        $license=paypal_license_for_teacher((int)$locked['teacher_id']);
        $current=$license && $license['status']==='active' && $license['expires_at']>$now
            ? (int)$license['classroom_limit'] : 0;
        $currentExpiry=$current>0?$license['expires_at']:null;
        if ($current!==(int)$locked['previous_classrooms'] ||
            ($currentExpiry!==$locked['previous_expires_at'])) {
            $db->prepare("UPDATE paypal_orders SET status='review',capture_id=?,paid_at=?,updated_at=? WHERE id=?")
                ->execute([$capture['id'],$now,$now,$localId]);
            paypal_payment_event($localId,'paid_entitlement_mismatch');
            $db->commit();
            return 'review';
        }
        $expectedCurrent=(int)$locked['previous_classrooms'];
        if ($locked['intent']==='expansion') {
            $start=$locked['grant_starts_at']; $end=$locked['grant_expires_at'];
        } else {
            $start=max($now,$locked['previous_expires_at']??$now);
            $end=paypal_add_year($start);
        }
        $limit=(int)$locked['target_classrooms'];
        $db->prepare('INSERT INTO teacher_paid_licenses(teacher_id,classroom_limit,starts_at,expires_at,status,last_order_id,updated_at)
          VALUES(?,?,?,?,"active",?,?) ON CONFLICT(teacher_id) DO UPDATE SET
          classroom_limit=excluded.classroom_limit,starts_at=excluded.starts_at,expires_at=excluded.expires_at,
          status="active",last_order_id=excluded.last_order_id,updated_at=excluded.updated_at')
            ->execute([$locked['teacher_id'],$limit,$start,$end,$localId,$now]);
        $db->prepare("UPDATE paypal_orders SET status='completed',capture_id=?,paid_at=?,grant_starts_at=?,grant_expires_at=?,updated_at=? WHERE id=?")
            ->execute([$capture['id'],$now,$start,$end,$now,$localId]);
        paypal_payment_event($localId,'payment_verified_and_license_granted',$capture['id']);
        $db->commit();
        return 'completed';
    } catch(Throwable $e) {
        if ($db->inTransaction()) $db->rollBack();
        throw $e;
    }
}

function paypal_capture_order(array $order): string {
    if ($order['status']==='completed') return 'completed';
    if (in_array($order['status'],['cancelled','expired','failed','refunded','review','disputed'],true)) return $order['status'];
    $settings=paypal_settings_row();
    if (!$settings) throw new PayPalPaymentError('La configuración de PayPal no está disponible.');
    $credentials=paypal_settings_decrypt($settings);
    $orderId=(string)$order['paypal_order_id'];
    try {
        // Repetir la captura con el mismo PayPal-Request-Id es seguro; permite
        // recuperar una aprobación tras cortes de red y evita dobles cobros.
        try {
            paypal_api_call($settings,'POST','/v2/checkout/orders/'.$orderId.'/capture',null,substr(hash('sha256','capture:'.$order['id']),0,36));
        } catch(PayPalPaymentError $captureError) {
            // Puede que PayPal ya capturara la orden y solo se perdiera su respuesta.
        }
        $remote=paypal_api_call($settings,'GET','/v2/checkout/orders/'.$orderId);
        if (($remote['status']??'')==='COMPLETED') return paypal_complete_order($order['id'],$remote);
        $status=($remote['status']??'')==='APPROVED'?'approved':'pending_payment';
        db()->prepare('UPDATE paypal_orders SET status=?,updated_at=? WHERE id=? AND status<>\'completed\'')
            ->execute([$status,gmdate('Y-m-d\TH:i:s\Z'),$order['id']]);
        paypal_payment_event($order['id'],$status);
        return $status;
    } catch(PayPalPaymentError $e) {
        // La orden puede haber sido aprobada mientras hubo un corte de red.
        // Mantenerla pendiente permite reintentar con la misma clave idempotente.
        db()->prepare("UPDATE paypal_orders SET status='pending_payment',updated_at=? WHERE id=? AND status NOT IN ('completed','review')")
            ->execute([gmdate('Y-m-d\TH:i:s\Z'),$order['id']]);
        throw $e;
    }
}

function paypal_create_order(array $user,array $input): array {
    if ($user['role']!=='teacher') fail(403,'La compra anual está vinculada a una cuenta docente.');
    paypal_settings_schema();
    $settings=paypal_settings_row();
    if (!$settings || $settings['verification_status']!=='verified') fail(503,'El administrador general debe validar las credenciales de PayPal.');
    if ($settings['environment']!=='sandbox') fail(503,'Los cobros de producción están desactivados. Use PayPal Sandbox.');
    $credentials=paypal_settings_decrypt($settings);
    if ($credentials['webhook_id']==='' || $credentials['merchant_id']==='') {
        fail(503,'Configure el ID del comercio y el webhook de Sandbox antes de crear pedidos.');
    }
    $quantity=filter_var($input['classrooms']??null,FILTER_VALIDATE_INT);
    if ($quantity===false) fail(422,'Indique un número entero de aulas.');
    $key=$input['request_id']??'';
    if (!is_string($key) || !preg_match('/^[A-Za-z0-9_-]{20,100}$/D',$key)) fail(422,'La clave idempotente del pedido no es válida.');
    paypal_payments_schema();
    $existing=fetch_one('SELECT * FROM paypal_orders WHERE teacher_id=? AND request_key=?',[$user['id'],$key]);
    if ($existing && $existing['paypal_order_id'] && $existing['approval_url']) {
        return ['order'=>paypal_order_public($existing),'approval_url'=>$existing['approval_url'],'already_created'=>true];
    }
    $now=gmdate('Y-m-d\TH:i:s\Z');
    $open=fetch_one("SELECT * FROM paypal_orders WHERE teacher_id=? AND status IN ('creating','pending','approved','pending_payment') ORDER BY created_at DESC LIMIT 1",[$user['id']]);
    if ($open && strtotime($open['created_at'])<time()-3600) {
        db()->prepare("UPDATE paypal_orders SET status='expired',updated_at=? WHERE id=?")->execute([$now,$open['id']]);
        $open=null;
    }
    if ($open && (!$existing || $open['id']!==$existing['id'])) {
        fail(409,'Ya hay un pedido pendiente. Compruebe su estado antes de crear otro.');
    }
    $quote=paypal_quote((int)$user['id'],(int)$quantity);
    if ($existing) {
        if ($existing['status']==='failed') {
            db()->prepare("UPDATE paypal_orders SET status='creating',updated_at=? WHERE id=?")->execute([$now,$existing['id']]);
        } else {
            fail(409,'La clave de pedido ya está asociada a otra solicitud.');
        }
        $localId=$existing['id'];
    } else {
        $localId=bin2hex(random_bytes(16));
        $db=db(); $db->beginTransaction();
        try {
            $db->prepare('INSERT INTO paypal_orders(id,teacher_id,request_key,intent,target_classrooms,previous_classrooms,previous_expires_at,grant_starts_at,grant_expires_at,amount_cents,currency,environment,status,created_at,updated_at)
              VALUES(?,?,?,?,?,?,?,?,?,?,"EUR","sandbox","creating",?,?)')
                ->execute([$localId,$user['id'],$key,$quote['intent'],$quote['target_classrooms'],$quote['previous_classrooms'],
                    $quote['previous_expires_at'],$quote['grant_starts_at'],$quote['grant_expires_at'],$quote['amount_cents'],$now,$now]);
            paypal_payment_event($localId,'order_creation_started');
            $db->commit();
        } catch(Throwable $e) {
            if ($db->inTransaction()) $db->rollBack();
            if ($e instanceof PDOException) fail(409,'Ya existe un pedido de pago para esta cuenta.');
            throw $e;
        }
    }
    $baseUrl=rtrim((string)(cfg()['base_url']??''),'/');
    if (!preg_match('~^https://[^/]+$~i',$baseUrl)) {
        db()->prepare("UPDATE paypal_orders SET status='failed',updated_at=? WHERE id=?")->execute([$now,$localId]);
        fail(503,'Central necesita una dirección HTTPS pública para volver desde PayPal.');
    }
    $return=$baseUrl.'/api.php?r=paypal_return&order='.$localId;
    $cancel=$baseUrl.'/api.php?r=paypal_cancel&order='.$localId;
    try {
        $remote=paypal_api_call($settings,'POST','/v2/checkout/orders',[
            'intent'=>'CAPTURE',
            'purchase_units'=>[[
                'reference_id'=>$localId,
                'custom_id'=>$localId,
                'invoice_id'=>$localId,
                'payee'=>['merchant_id'=>$credentials['merchant_id']],
                'amount'=>['currency_code'=>'EUR','value'=>paypal_format_cents($quote['amount_cents'])],
                'description'=>$quote['target_classrooms'].' aula(s) · licencia anual CONTA FP360',
            ]],
            'payment_source'=>['paypal'=>['experience_context'=>[
                'brand_name'=>'CONTA FP360',
                'locale'=>'es-ES',
                'user_action'=>'PAY_NOW',
                'shipping_preference'=>'NO_SHIPPING',
                'return_url'=>$return,
                'cancel_url'=>$cancel,
            ]]],
        ],substr(hash('sha256','create:'.$localId),0,36));
        $providerId=$remote['id']??null;
        $approve=null;
        foreach (($remote['links']??[]) as $link) {
            if (in_array($link['rel']??'', ['payer-action','approve'],true) && is_string($link['href']??null)) {
                $candidate=parse_url($link['href']);
                if (($candidate['scheme']??'')==='https' &&
                    in_array(strtolower($candidate['host']??''),['www.sandbox.paypal.com','sandbox.paypal.com'],true)) $approve=$link['href'];
            }
        }
        if (!is_string($providerId) || $approve===null) throw new PayPalPaymentError('PayPal no devolvió una página de aprobación Sandbox válida.');
        db()->prepare("UPDATE paypal_orders SET paypal_order_id=?,approval_url=?,status='pending',updated_at=? WHERE id=?")
            ->execute([$providerId,$approve,gmdate('Y-m-d\TH:i:s\Z'),$localId]);
        paypal_payment_event($localId,'order_created_sandbox',$providerId);
        $order=fetch_one('SELECT * FROM paypal_orders WHERE id=?',[$localId]);
        return ['order'=>paypal_order_public($order),'approval_url'=>$approve,'already_created'=>false];
    } catch(PayPalPaymentError $e) {
        db()->prepare("UPDATE paypal_orders SET status='failed',updated_at=? WHERE id=? AND status='creating'")
            ->execute([gmdate('Y-m-d\TH:i:s\Z'),$localId]);
        throw $e;
    }
}

function paypal_order_public(array $order): array {
    return [
        'id'=>$order['id'],'intent'=>$order['intent'],
        'classrooms'=>(int)$order['target_classrooms'],
        'amount_cents'=>(int)$order['amount_cents'],
        'currency'=>$order['currency'],'status'=>$order['status'],
        'created_at'=>$order['created_at'],'paid_at'=>$order['paid_at'],
        'starts_at'=>$order['grant_starts_at'],'expires_at'=>$order['grant_expires_at'],
    ];
}

function paypal_license_status(array $user): array {
    if ($user['role']!=='teacher') fail(403,'Las licencias se consultan desde una cuenta docente.');
    paypal_payments_schema();
    $license=paypal_license_for_teacher((int)$user['id']);
    $licenseStatus=$license['status']??null;
    if ($licenseStatus==='active' && $license['expires_at']<=gmdate('Y-m-d\TH:i:s\Z')) $licenseStatus='expired';
    $orders=fetch_all('SELECT * FROM paypal_orders WHERE teacher_id=? ORDER BY created_at DESC LIMIT 10',[$user['id']]);
    return [
        'license'=>$license?[
            'classrooms'=>(int)$license['classroom_limit'],'starts_at'=>$license['starts_at'],
            'expires_at'=>$license['expires_at'],'status'=>$licenseStatus,
        ]:null,
        'orders'=>array_map('paypal_order_public',$orders),
        'production_enabled'=>false,
    ];
}

function paypal_lookup_order_by_provider(string $providerOrderId): ?array {
    return fetch_one('SELECT * FROM paypal_orders WHERE paypal_order_id=?',[$providerOrderId]);
}

function paypal_mark_pending(string $localId,string $state): void {
    if (!in_array($state,['approved','pending_payment','failed'],true)) return;
    db()->prepare('UPDATE paypal_orders SET status=?,updated_at=? WHERE id=? AND status<>\'completed\'')
        ->execute([$state,gmdate('Y-m-d\TH:i:s\Z'),$localId]);
    paypal_payment_event($localId,$state);
}

function paypal_store_verified_refund(array $order,string $refundId,string $captureId,int $amountCents,string $status): string {
    if (!in_array($status,['completed','pending','failed'],true) || $amountCents<1 ||
        $amountCents>(int)$order['amount_cents'] || $captureId!==($order['capture_id']??null)) {
        throw new PayPalPaymentError('El reembolso confirmado no tiene un estado o importe válido.');
    }
    $db=db(); $db->beginTransaction();
    try {
        $db->prepare('INSERT INTO paypal_refunds(refund_id,order_id,capture_id,amount_cents,status,created_at)
          VALUES(?,?,?,?,?,?) ON CONFLICT(refund_id) DO UPDATE SET status=excluded.status,amount_cents=excluded.amount_cents')
            ->execute([$refundId,$order['id'],$captureId,$amountCents,$status,gmdate('Y-m-d\TH:i:s\Z')]);
        $sum=fetch_one("SELECT COALESCE(SUM(amount_cents),0) AS total FROM paypal_refunds WHERE order_id=? AND status='completed'",[$order['id']]);
        $total=(int)($sum['total']??0);
        if ($status!=='completed') { $db->commit(); return $status; }
        $now=gmdate('Y-m-d\TH:i:s\Z');
        $orderStatus=$total>=(int)$order['amount_cents']?'refunded':'review';
        $db->prepare('UPDATE paypal_orders SET status=?,updated_at=? WHERE id=?')
            ->execute([$orderStatus,$now,$order['id']]);
        // No se borran grupos ni trabajos. Un reembolso requiere revisión antes
        // de permitir nuevas operaciones licenciadas.
        $db->prepare("UPDATE teacher_paid_licenses SET status='review',updated_at=? WHERE teacher_id=? AND last_order_id=?")
            ->execute([$now,$order['teacher_id'],$order['id']]);
        paypal_payment_event($order['id'],$orderStatus,$refundId);
        $db->commit();
        return $orderStatus;
    } catch(Throwable $e) {
        if ($db->inTransaction()) $db->rollBack();
        throw $e;
    }
}

function paypal_claim_webhook(string $eventId,string $eventType,?string $orderId): bool {
    $existing=fetch_one('SELECT status FROM paypal_webhook_events WHERE event_id=?',[$eventId]);
    if ($existing && $existing['status']==='processed') return false;
    db()->prepare('INSERT INTO paypal_webhook_events(event_id,event_type,order_id,status,received_at)
      VALUES(?,?,?,\'processing\',?) ON CONFLICT(event_id) DO UPDATE SET status=\'processing\' WHERE paypal_webhook_events.status<>\'processed\'')
        ->execute([$eventId,$eventType,$orderId,gmdate('Y-m-d\TH:i:s\Z')]);
    return true;
}

function paypal_capture_event(array $event,array $settings): void {
    $resource=$event['resource']??[];
    $related=$resource['supplementary_data']['related_ids']??[];
    $providerOrderId=$related['order_id']??$resource['custom_id']??null;
    if (!is_string($providerOrderId) || $providerOrderId==='') return;
    // El ID de orden proviene del webhook autenticado; el estado se consulta de nuevo en PayPal.
    $order=paypal_lookup_order_by_provider($providerOrderId);
    if (!$order && preg_match('/^[a-f0-9]{32}$/D',$providerOrderId)) {
        $order=fetch_one('SELECT * FROM paypal_orders WHERE id=?',[$providerOrderId]);
    }
    if (!$order) return;
    $remote=paypal_api_call($settings,'GET','/v2/checkout/orders/'.$order['paypal_order_id']);
    if (($remote['status']??'')==='COMPLETED') {
        paypal_complete_order($order['id'],$remote);
    } elseif (($event['event_type']??'')==='PAYMENT.CAPTURE.PENDING') {
        paypal_mark_pending($order['id'],'pending_payment');
    } elseif (in_array(($event['event_type']??''),['PAYMENT.CAPTURE.DENIED','PAYMENT.CAPTURE.DECLINED'],true)) {
        paypal_mark_pending($order['id'],'failed');
    }
}

function paypal_refund_event(array $event,array $settings): void {
    $resource=$event['resource']??[];
    // PAYMENT.CAPTURE.REFUNDED contiene el objeto capture; resource.id es
    // el ID de captura, no un ID de reembolso individual.
    $captureId=$resource['id']??$resource['supplementary_data']['related_ids']['capture_id']??null;
    if (!is_string($captureId) || $captureId==='') return;
    $order=fetch_one('SELECT * FROM paypal_orders WHERE capture_id=?',[$captureId]);
    if (!$order) return;
    $capture=paypal_api_call($settings,'GET','/v2/payments/captures/'.$captureId);
    $credentials=paypal_settings_decrypt($settings);
    $amount=paypal_cents($capture['amount']['value']??null);
    $currency=$capture['amount']['currency_code']??'';
    $refunded=paypal_cents($capture['seller_receivable_breakdown']['total_refunded_amount']['value']??null);
    $relatedOrder=$capture['supplementary_data']['related_ids']['order_id']??null;
    if (($capture['id']??'')!==$captureId || ($capture['payee']['merchant_id']??'')!==$credentials['merchant_id'] ||
        $relatedOrder!==$order['paypal_order_id'] || $amount!==(int)$order['amount_cents'] ||
        $currency!=='EUR' || $refunded===null || $refunded<1 || $refunded>(int)$order['amount_cents'] ||
        !in_array($capture['status']??'', ['PARTIALLY_REFUNDED','REFUNDED'],true)) {
        throw new PayPalPaymentError('El estado del reembolso no coincide con la captura consultada en PayPal.');
    }
    paypal_store_verified_refund($order,'capture-refund-total-'.$captureId,$captureId,$refunded,'completed');
}

function paypal_refund_status_event(array $event,array $settings): void {
    $refundId=$event['resource']['id']??null;
    if (!is_string($refundId) || $refundId==='') return;
    $refund=paypal_api_call($settings,'GET','/v2/payments/refunds/'.$refundId);
    if (($refund['id']??'')!==$refundId) throw new PayPalPaymentError('El ID del reembolso no coincide con PayPal.');
    $captureId=null;
    foreach (($refund['links']??[]) as $link) {
        if (($link['rel']??'')!=='up' || !is_string($link['href']??null)) continue;
        $parts=parse_url($link['href']);
        if (($parts['scheme']??'')==='https' && in_array(strtolower($parts['host']??''),[
            'api-m.sandbox.paypal.com','api.sandbox.paypal.com',
        ],true) && preg_match('~^/v2/payments/captures/([A-Za-z0-9_-]+)$~D',$parts['path']??'',$match)) {
            $captureId=$match[1]; break;
        }
    }
    $order=$captureId?fetch_one('SELECT * FROM paypal_orders WHERE capture_id=?',[$captureId]):null;
    $amount=paypal_cents($refund['amount']['value']??null);
    $status=match($refund['status']??'') {
        'PENDING'=>'pending','COMPLETED'=>'completed','FAILED'=>'failed',default=>'',
    };
    if (!$order || $amount===null || ($refund['amount']['currency_code']??'')!=='EUR' || $status==='') {
        throw new PayPalPaymentError('El estado del reembolso no coincide con una captura de Central.');
    }
    paypal_store_verified_refund($order,$refundId,$captureId,$amount,$status);
}

function paypal_suspend_verified_capture(array $order,string $captureId,array $settings,string $eventId): void {
    $capture=paypal_api_call($settings,'GET','/v2/payments/captures/'.$captureId);
    $credentials=paypal_settings_decrypt($settings);
    $amount=paypal_cents($capture['amount']['value']??null);
    if (($capture['id']??'')!==$captureId ||
        ($capture['payee']['merchant_id']??'')!==$credentials['merchant_id'] ||
        ($capture['supplementary_data']['related_ids']['order_id']??null)!==$order['paypal_order_id'] ||
        ($capture['amount']['currency_code']??'')!=='EUR' ||
        $amount!==(int)$order['amount_cents']) {
        throw new PayPalPaymentError('La captura de la disputa no coincide con la orden de Central.');
    }
    $now=gmdate('Y-m-d\TH:i:s\Z');
    db()->prepare("UPDATE paypal_orders SET status='disputed',updated_at=? WHERE id=?")
        ->execute([$now,$order['id']]);
    db()->prepare("UPDATE teacher_paid_licenses SET status='suspended',updated_at=? WHERE teacher_id=? AND last_order_id=?")
        ->execute([$now,$order['teacher_id'],$order['id']]);
    paypal_payment_event($order['id'],'payment_disputed',$eventId);
}

function paypal_verify_webhook(array $headers,array $event,array $settings): bool {
    $credentials=paypal_settings_decrypt($settings);
    if ($credentials['webhook_id']==='') return false;
    $required=[
        'PAYPAL-AUTH-ALGO'=>'auth_algo',
        'PAYPAL-CERT-URL'=>'cert_url',
        'PAYPAL-TRANSMISSION-ID'=>'transmission_id',
        'PAYPAL-TRANSMISSION-SIG'=>'transmission_sig',
        'PAYPAL-TRANSMISSION-TIME'=>'transmission_time',
    ];
    $verification=['webhook_id'=>$credentials['webhook_id'],'webhook_event'=>$event];
    foreach ($required as $header=>$field) {
        $serverKey='HTTP_'.str_replace('-','_',$header);
        $value=$headers[$header]??$headers[$serverKey]??'';
        if (!is_string($value) || $value==='' || strlen($value)>2048) return false;
        $verification[$field]=$value;
    }
    $result=paypal_api_call($settings,'POST','/v1/notifications/verify-webhook-signature',$verification);
    return ($result['verification_status']??'')==='SUCCESS';
}

function paypal_handle_webhook(): never {
    if ($_SERVER['REQUEST_METHOD']!=='POST') fail(405,'Método no permitido.');
    $raw=file_get_contents('php://input',false,null,0,131073);
    if (!is_string($raw) || strlen($raw)>131072) fail(413,'Notificación demasiado grande.');
    $event=json_decode($raw,true);
    if (!is_array($event) || !is_string($event['id']??null) || strlen($event['id'])>255 ||
        !is_string($event['event_type']??null) || strlen($event['event_type'])>100) {
        fail(400,'Notificación PayPal no válida.');
    }
    paypal_settings_schema();
    $settings=paypal_settings_row();
    if (!$settings || $settings['environment']!=='sandbox') fail(503,'El webhook de pagos solo está disponible en Sandbox.');
    try {
        if (!paypal_verify_webhook($_SERVER,$event,$settings)) fail(401,'La firma del webhook PayPal no es válida.');
        paypal_payments_schema();
        $eventId=$event['id'];
        $orderId=$event['resource']['supplementary_data']['related_ids']['order_id']??null;
        $db=db();
        if (!paypal_claim_webhook($eventId,$event['event_type'],is_string($orderId)?$orderId:null)) {
            respond(['ok'=>true,'duplicate'=>true]);
        }
        $type=$event['event_type'];
        if (in_array($type,['PAYMENT.CAPTURE.COMPLETED','PAYMENT.CAPTURE.PENDING','PAYMENT.CAPTURE.DENIED','PAYMENT.CAPTURE.DECLINED'],true)) {
            paypal_capture_event($event,$settings);
        } elseif ($type==='PAYMENT.CAPTURE.REFUNDED') {
            paypal_refund_event($event,$settings);
        } elseif (in_array($type,['PAYMENT.REFUND.PENDING','PAYMENT.REFUND.FAILED'],true)) {
            paypal_refund_status_event($event,$settings);
        } elseif (in_array($type,['PAYMENT.CAPTURE.REVERSED','CUSTOMER.DISPUTE.CREATED'],true)) {
            $resource=$event['resource']??[];
            $capture=$resource['supplementary_data']['related_ids']['capture_id']??$resource['id']??null;
            if ($type==='CUSTOMER.DISPUTE.CREATED') {
                $capture=$resource['disputed_transactions'][0]['seller_transaction_id']??$capture;
            }
            $order=is_string($capture)?fetch_one('SELECT * FROM paypal_orders WHERE capture_id=?',[$capture]):null;
            if ($order) paypal_suspend_verified_capture($order,$capture,$settings,$eventId);
        } elseif ($type==='CHECKOUT.ORDER.APPROVED') {
            $providerId=$event['resource']['id']??null;
            $order=is_string($providerId)?paypal_lookup_order_by_provider($providerId):null;
            if ($order) paypal_mark_pending($order['id'],'approved');
        }
        $db->prepare("UPDATE paypal_webhook_events SET status='processed',processed_at=? WHERE event_id=?")
            ->execute([gmdate('Y-m-d\TH:i:s\Z'),$eventId]);
        respond(['ok'=>true]);
    } catch(PayPalPaymentError $e) {
        $db=db();
        $db->prepare("UPDATE paypal_webhook_events SET status='failed' WHERE event_id=? AND status='processing'")
            ->execute([$event['id']]);
        fail(503,'No se pudo verificar la notificación en PayPal; se reintentará.');
    }
}

function paypal_return_page(string $message,string $status): never {
    header('Content-Type: text/html; charset=utf-8');
    header('Cache-Control: no-store');
    header("Content-Security-Policy: default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; frame-ancestors 'none'");
    $safe=htmlspecialchars($message,ENT_QUOTES|ENT_SUBSTITUTE,'UTF-8');
    $json=json_encode(['type'=>'conta-paypal-return','status'=>$status],JSON_HEX_TAG|JSON_HEX_AMP|JSON_HEX_APOS|JSON_HEX_QUOT);
    echo '<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>PayPal · CONTA FP360</title><style>body{font:16px system-ui,sans-serif;max-width:620px;margin:12vh auto;padding:24px;color:#172b45}main{border:1px solid #dbe3ee;border-radius:14px;padding:28px}h1{font-size:24px}p{color:#52677f}</style><main><h1>Estado del pedido</h1><p>'.$safe.'</p><p>Puede cerrar esta ventana y volver a Central.</p></main><script>if(window.opener){window.opener.postMessage('.$json.',location.origin)}setTimeout(()=>window.close(),1200)</script></html>';
    exit;
}

function paypal_handle_return(bool $cancel=false): never {
    paypal_payments_schema();
    $localId=(string)($_GET['order']??'');
    if (!preg_match('/^[a-f0-9]{32}$/D',$localId)) paypal_return_page('No se ha encontrado un pedido de Sandbox válido.','invalid');
    $order=fetch_one('SELECT * FROM paypal_orders WHERE id=?',$localId?[$localId]:[]);
    if (!$order) paypal_return_page('No se ha encontrado el pedido en Central.','not_found');
    if ($cancel) {
        if (!in_array($order['status'],['completed','refunded','disputed'],true)) {
            db()->prepare("UPDATE paypal_orders SET status='cancelled',updated_at=? WHERE id=?")->execute([gmdate('Y-m-d\TH:i:s\Z'),$localId]);
            paypal_payment_event($localId,'buyer_cancelled');
        }
        paypal_return_page('El pago no se ha confirmado. No se ha activado ninguna licencia.','cancelled');
    }
    $providerId=(string)($_GET['token']??'');
    if ($providerId==='' || !hash_equals((string)$order['paypal_order_id'],$providerId)) {
        paypal_return_page('La vuelta del navegador no demuestra el pago. Central no ha activado la licencia.','unverified');
    }
    try {
        $result=paypal_capture_order($order);
        $message=$result==='completed'
            ? 'PayPal confirmó el pago y Central activó o renovó la licencia.'
            : 'El pago sigue pendiente o necesita revisión. Central no ha activado la licencia.';
        paypal_return_page($message,$result);
    } catch(PayPalPaymentError $e) {
        paypal_return_page('No se pudo confirmar el pago con PayPal. Vuelva a Central y consulte el estado.','pending');
    }
}

function handle_paypal_payment_route(string $route,string $method,array $user): void {
    if (!in_array($route,['paypal_order','paypal_capture','paypal_license'],true)) return;
    if ($method==='GET' && $route==='paypal_license') {
        respond(['ok'=>true]+paypal_license_status($user));
    }
    if ($method!=='POST') fail(405,'Método no permitido.');
    paypal_payments_schema();
    $input=json_in();
    if ($route==='paypal_order') {
        $result=paypal_create_order($user,$input);
        respond(['ok'=>true]+$result,201);
    }
    if ($route==='paypal_capture') {
        if ($user['role']!=='teacher') fail(403,'La compra está vinculada a una cuenta docente.');
        $id=$input['order_id']??'';
        if (!is_string($id) || !preg_match('/^[a-f0-9]{32}$/D',$id)) fail(422,'Pedido no válido.');
        $order=fetch_one('SELECT * FROM paypal_orders WHERE id=? AND teacher_id=?',[$id,$user['id']]);
        if (!$order) fail(404,'El pedido no pertenece a esta cuenta docente.');
        try {
            $status=paypal_capture_order($order);
            respond(['ok'=>true,'status'=>$status,'license'=>paypal_license_status($user)['license']]);
        } catch(PayPalPaymentError $e) {
            fail(503,'PayPal todavía no confirma el pago. Consulte el pedido más tarde.');
        }
    }
}
