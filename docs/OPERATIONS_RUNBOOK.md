# دليل تشغيل عزوتك

هذا الدليل يحدد طريقة نقل عزوتك بين البيئات دون اعتبار المعاينة دليلاً على الجاهزية الإنتاجية. لا تُنفذ خطوات الإنتاج إلا من خلال حسابات التشغيل وSecret Manager المعتمدين؛ لا تُرسل القيم السرية إلى Git أو المحادثة.

## حدود الإصدار الحالي

- المعاينة تعمل بذاكرة العملية وكتالوج محلي، ولا تحفظ طلبات حقيقية.
- production يرفض البدء ما لم تتوفر إعدادات OIDC/Keycloak وPostgreSQL وRedis وWAF المُدار وتشفير العنوان.
- `POST /api/orders` هو مسار إنشاء الطلب الحقيقي عند تفعيل PostgreSQL وOIDC.
- الدفع، الإشعارات، تعيين المزود، وتغيير حالة الطلب تحتاج مزودات خارجية واختبار staging منفصلاً؛ لا تُعلن كمكتملة قبل ذلك.

## بوابة الإصدار

نفّذ الخطوات بالترتيب في بيئة staging أولاً:

```bash
python -m unittest -v
python -m py_compile app.py security.py jobs.py worker.py config.py oidc.py repository.py scripts/*.py
python scripts/validate_production_config.py --json
python scripts/migrate.py --dry-run
```

ثم شغّل فحوص HTTP من جهاز التشغيل أو staging المصرح له فقط:

```bash
python scripts/dast_smoke.py --base-url http://127.0.0.1:8000
python scripts/load_smoke.py --url http://127.0.0.1:8000/health --requests 100 --concurrency 10
```

لا تستخدم `--allow-remote` إلا مع اسم staging معتمد وتذكرة تغيير واضحة. يجب أن تكون نتيجة DAST وload smoke جزءاً من سجل الإصدار، لا بديلاً عن اختبار التكامل الحقيقي.

## تسلسل النشر

1. وافق على الإصدار وسجّل commit أو image digest الذي سيُنشر.
2. حمّل الأسرار من Secret Manager في البيئة المستهدفة؛ لا تعدّل `.env.example` لإضافة أسرار.
3. شغّل `validate_production_config.py --json`. أي خطأ يعني إيقاف النشر؛ يجب أن يكون `OIDC_ROLE_MAP` صريحاً وأن يفرض اتصال PostgreSQL TLS.
4. نفّذ migrations من pipeline منفصل بحساب migration، ثم تحقق من checksum و`schema_migrations`.
5. انشر صورة Docker غير root أو حزمة النظام عبر systemd. لا تفتح المنفذ الداخلي للعامة.
6. تحقق من `GET /health` ثم `GET /ready`. health يثبت liveness فقط، وready لا ينجح في production دون مخزن البيانات.
7. تحقق من جلسة OIDC وPKCE وRBAC في staging بحساب اختبار، ثم اختبر إنشاء طلب بمفتاح idempotency واحد وإعادة إرساله.
8. راقب أخطاء 4xx/5xx و`X-Request-ID` وaudit sink قبل تحويل كامل المرور.

## الترحيل والتراجع

- migrations تطبق إلى الأمام فقط. لا تعدّل migration مطبقة؛ أضف migration جديدة مع checksum جديد.
- عند فشل migration: أوقف النشر، احفظ سجل الخطأ، وتحقق من حالة المعاملة قبل إعادة المحاولة.
- التراجع البرمجي يعيد image digest السابق بعد التأكد من توافقه مع schema الحالي.
- لا تُنفذ downgrade تلقائياً لقاعدة البيانات. استخدم خطة migration عكسية مكتوبة ومراجعة أو استعادة نسخة احتياطية في بيئة منفصلة.
- عند تغيير مفتاح تشفير العناوين، طبّق خطة key versioning وترحيل مدروسة؛ لا تستبدل المفتاح سراً لأن ذلك يمنع قراءة العناوين القديمة.

## الاستجابة للأحداث

### الجاهزية `503`

1. افحص `/health` و`/ready` وسجل `X-Request-ID`.
2. تحقق من اتصال PostgreSQL وRedis ووقت انتهاء الشهادات وACL/TLS.
3. لا تعطل بوابة production ولا تشغّل memory fallback.
4. إذا كانت قاعدة البيانات غير جاهزة، أوقف الكتابات وانتظر قرار incident owner قبل أي migration.

### فشل OIDC أو تسجيل الدخول

1. تحقق من issuer وredirect URI وaudience وJWKS ووقت النظام.
2. تأكد من وجود `amr` مقبول وربط المجموعة بدور RBAC.
3. لا تعُد إلى IAM المحلي في production.
4. راجع audit events باستخدام request ID دون تسجيل tokens أو client secrets.

### فشل audit sink أو مخزن البيانات

- تعامل معه كفشل مغلق: لا تعتبر العملية ناجحة ولا تعاودها بلا `Idempotency-Key`.
- لا تطبع body أو عنوان العميل أو أسرار الاتصال في التذكرة.
- افصل صلاحيات القراءة عن صلاحيات migration، واحفظ السجل خارج نفس المضيف عند الإمكان.

### تراكم الطوابير

1. تحقق من consumer group والـ worker والـ dead-letter stream.
2. افحص عدد retries وسبب فشل handler.
3. لا تُعيد تشغيل payment أو notification يدوياً من دون idempotency وموافقة مالك التكامل.
4. لا تُرسل بيانات البطاقات أو الأسرار في payloads.

## بيانات يجب تسجيلها في تذكرة التغيير

- commit أو image digest.
- البيئة ووقت البدء والانتهاء والمنفذ المسؤول.
- نتيجة validation وmigrations وDAST وhealth/readiness.
- أرقام الطلبات العامة أو `X-Request-ID` فقط، دون عنوان أو token أو رقم بطاقة.
- قرار التراجع أو الإكمال وسبب القرار.

## شروط إعلان الجاهزية

لا يُعلن الإصدار جاهزاً للإنتاج حتى ينجح اختبار خارجي فعلي مع Keycloak وPostgreSQL وRedis وWAF، واختبار مزودي الدفع والإشعارات إن تم تفعيلهما، واختبار النسخ الاحتياطي والاستعادة والمراقبة. نجاح اختبارات Python المحلية وحده لا يحقق هذه الشروط.
