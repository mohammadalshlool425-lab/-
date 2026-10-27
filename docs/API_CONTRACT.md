# عقد API لعزوتك

هذا الملف يصف المسارات الموجودة فعلاً في `app.py`. وجود المسار لا يعني أن مزود الدفع أو الإشعارات الخارجية موصولان؛ هذه الحدود تبقى موثقة صراحة.

## قواعد عامة

- جميع الاستجابات JSON ما لم يذكر خلاف ذلك.
- كل استجابة تحمل `X-Request-ID` يمكن ربطه بسجل التدقيق.
- استخدم `Content-Type: application/json` عند إرسال body.
- التوقيت في حقول الطلبات ISO 8601 مع منطقة زمنية؛ يحول الخادم القيمة إلى UTC.
- المبالغ بوحدة minor units بالدينار الأردني؛ `1500` تعني `15.00 JOD`.
- لا ترسل أسرار OIDC أو بيانات بطاقة إلى هذه المسارات.

## الصحة والجاهزية

### `GET /health`

فحص liveness لا يعتمد على PostgreSQL أو Redis. يعيد الإصدار وحالة رؤوس الحماية.

### `GET /ready`

فحص readiness للأصول ومخازن التشغيل. في production يتحقق من PostgreSQL وRedis ويعيد `503` عند فشل أي منها؛ لا يعرض تفاصيل الاتصال أو الأسرار.

## الكتالوج العام

### `GET /api/services`

لا يتطلب تسجيل دخول.

- في development: يعرض كتالوج المعاينة الثابت المعلن بوضوح.
- في production: يقرأ الخدمات النشطة من PostgreSQL؛ لا يستخدم fallback وهمياً.
- يمكن تخزين النتيجة مؤقتاً لمدة 60 ثانية.

شكل production مختصر (قد تكون بعض حقول قاعدة البيانات غير موجودة في fallback الخاص بالمعاينة):

```json
{
  "services": [
    {
      "id": "uuid-in-production",
      "slug": "cleaning",
      "name_ar": "تنظيف وتعقيم",
      "name_en": "Cleaning and sanitization",
      "minimum_amount_minor": 1200,
      "currency": "JOD",
      "category_slug": "home",
      "category_name_ar": "المنزل"
    }
  ]
}
```

### `GET /api/providers?service_slug=cleaning&city=amman`

لا يتطلب تسجيل دخول، لكنه لا يعرض إلا مزودي الخدمة الذين:

- `active = true`
- `verification_status = verified`
- يرتبطون بالخدمة المطلوبة
- يطابقون المحافظة عند إرسال `city`

في development يعيد قائمة فارغة بدلاً من مزودين اصطناعيين. في production يفشل بـ`503` إذا كان PostgreSQL غير متاح.

## الهوية والجلسات

### `GET /api/auth/status`

يعيد حالة الجلسة دون إنشاء جلسة:

```json
{
  "authenticated": false,
  "auth_mode": "oidc"
}
```

عند وجود جلسة يعيد أيضاً `roles`, `permissions`, `csrf_token`, و`expires_at`. لا تستخدم `csrf_token` خارج الجلسة الحالية.

### `GET /auth/login`

يبدأ Authorization Code + PKCE عند تفعيل OIDC. لا يوجد fallback إلى IAM المحلي في OIDC mode.

### `GET /auth/callback`

يتحقق من state وnonce وissuer وaudience وRS256 و`amr` ثم ينشئ جلسة HttpOnly.

### `POST /api/auth/logout`

يتطلب جلسة وheader باسم `X-CSRF-Token` مطابقاً للجلسة.

## طلبات العميل

### `GET /api/orders`

يتطلب جلسة تحمل permission `orders:read`. يعيد طلبات المستخدم المرتبط بـOIDC subject فقط، ولا يعيد العنوان المشفر أو بيانات الدفع.

### `POST /api/orders`

ينشئ طلباً فعلياً عندما يكون PostgreSQL مهيأً (وهو الوضع المطلوب في production)؛ المعاينة الافتراضية لا تحفظ طلباً. المتطلبات:

- جلسة OIDC بدور `customer` وpermission `orders:create`.
- `X-CSRF-Token` صالح.
- `Idempotency-Key` بطول 16 إلى 128 حرفاً من المجموعة `A-Z a-z 0-9 . _ : -`.
- `service_slug` نشط.
- `city` واحدة من `amman`, `irbid`, `zarqa`, `aqaba`, `other`.
- `address` بين 5 و500 حرفاً؛ يشفره الخادم قبل PostgreSQL.
- `estimated_amount_minor` لا يقل عن الحد الأدنى للخدمة.
- `scheduled_from` و`scheduled_to` بوقت مستقبلي ونافذة من 30 دقيقة إلى 12 ساعة.

مثال body:

```json
{
  "service_slug": "cleaning",
  "city": "amman",
  "address": "شارع الجامعة، بناية ١٢",
  "estimated_amount_minor": 1500,
  "scheduled_from": "2026-10-28T17:00:00+03:00",
  "scheduled_to": "2026-10-28T19:00:00+03:00"
}
```

الاستجابة الجديدة تكون `201`:

```json
{
  "order": {
    "id": "uuid",
    "public_code": "EZW-ABC1234567",
    "status": "requested",
    "city": "amman",
    "estimated_amount_minor": 1500,
    "currency": "JOD",
    "scheduled_from": "2026-10-28T14:00:00+00:00",
    "scheduled_to": "2026-10-28T16:00:00+00:00"
  },
  "replayed": false
}
```

إعادة الطلب بنفس المفتاح وبنفس payload تعيد `200` مع `replayed: true` وheader `Idempotency-Replayed: true`. إعادة استخدام المفتاح مع payload مختلف تعيد `409` ولا تنشئ طلباً ثانياً.

## حالات وأخطاء مهمة

- `401 authentication_required`: لا توجد جلسة.
- `403 insufficient_permissions`: الجلسة لا تملك الصلاحية المطلوبة.
- `409 idempotency_key_reused`: المفتاح مستخدم مع payload مختلف.
- `422`: body أو filter غير صالح.
- `503 data_store_unavailable`: لا يوجد fallback إلى ذاكرة العملية في production.

## ما ليس ضمن هذا العقد بعد

- إنشاء payment intent أو التقاط الدفع.
- إدخال بيانات البطاقات أو ربط CliQ.
- إرسال SMS أو WhatsApp أو push notifications.
- تعيين مزود للطلب أو تغيير حالته من لوحة مزود الخدمة.

لن تعرض الواجهة نجاح دفع أو إشعاراً أو تعيين مزود قبل ربط مزود خارجي واختباره في staging.
