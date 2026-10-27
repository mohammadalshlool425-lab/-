# قاعدة بيانات عزوتك

المجلد يحتوي migrations PostgreSQL للإنتاج. لا يتم تشغيلها تلقائياً من التطبيق؛ شغّلها من pipeline migration منفصل وبحساب لا يستخدمه runtime. يقرأ `repository.py` لوحة الإدارة ويكتب audit events بحساب runtime محدود.

## تشغيل migrations

الطريقة المفضلة تستخدم runner مع advisory lock وchecksum:

```bash
# DATABASE_URL يحقنه Secret Manager في بيئة العملية، ولا يُمرر كسطر command line.
python scripts/migrate.py
python scripts/migrate.py --dry-run
```

للتشغيل اليدوي لمرة واحدة:

```bash
for migration in db/migrations/*.sql; do
  psql "$DATABASE_URL" --set ON_ERROR_STOP=1 --single-transaction -f "$migration"
done
```

استخدم اتصالاً مشفراً إلى PostgreSQL، وحساب migration منفصلاً عن حساب التطبيق. حساب runtime يحتاج فقط صلاحيات DML محددة على الجداول المطلوبة ولا يملك `CREATE`, `ALTER`, أو `DROP`.

## حدود البيانات الحساسة

- العنوان لا يُخزّن كنص صريح؛ الأعمدة مهيأة لـ ciphertext وnonce وإصدار مفتاح.
- مفاتيح التشفير تُدار خارج قاعدة البيانات عبر Secret Manager/KMS.
- `audit_events` append-only من منظور التطبيق ولا يجب منح runtime صلاحية `UPDATE` أو `DELETE`.
- مبالغ الدفع تخزّن كـ minor units بالدينار الأردني لتجنب أخطاء floating point.
- `idempotency_key` مطلوب لمنع تكرار الحجوزات عند إعادة المحاولة، و`request_fingerprint` keyed يرفض إعادة استخدام المفتاح مع payload مختلف دون تخزين العنوان كنص أو hash مكشوف.

## Redis والجلسات

عند تشغيل أكثر من نسخة من التطبيق ثبّت `requirements-production.txt` واضبط `SESSION_STORE=redis` و`RATE_LIMIT_STORE=redis` و`REDIS_URL=rediss://...`. يجب أن يكون Redis خاصاً بالشبكة الداخلية، مع ACL لمستخدم التطبيق وTLS وحدود ذاكرة وسياسة انتهاء مفاتيح. طوابير Redis Streams تستخدم consumer group وdead-letter stream، ويجب تشغيل worker منفصل بحساب خدمة محدود.

## قبل تفعيل الإنتاج

1. أنشئ أدوار PostgreSQL منفصلة للـ migrations وruntime وreadonly reporting.
2. فعّل النسخ الاحتياطي المشفر واختبر الاستعادة في بيئة منفصلة.
3. فعّل مراقبة الاتصالات الفاشلة وحجم الجداول وسعة التخزين.
4. لا تستخدم بيانات seed حقيقية في Git.
