# عزوتك | خدماتك أقرب

إصدار النموذج الحالي: `0.8.0`

نموذج تفاعلي RTL لمنصة خدمات منزلية أردنية، مع واجهة العميل ولوحة المدير العام ومركز حماية تشغيلي.

## التشغيل

لا توجد تبعيات خارجية مطلوبة؛ يعتمد الخادم على Python Standard Library.

```bash
python app.py
```

ثم افتح `http://localhost:8000`.

- فحص الخدمة: `GET /health`
- فحص جاهزية الأصول: `GET /ready`

لتجربة وضع الإنتاج محلياً خلف HTTPS أو reverse proxy:

```bash
APP_ENV=production ENABLE_HSTS=1 python app.py
```

لوحة المدير مخفية افتراضياً في الإنتاج لتقليل التعرّض. أنشئ هوية إدارية وMFA أولاً:

```bash
python scripts/bootstrap_iam.py
```

بعد وضعها خلف IAM وMFA وRBAC فعليين يمكن تفعيل العرض عبر:

```bash
APP_ENV=production ENABLE_HSTS=1 ADMIN_UI_ENABLED=1 python app.py
```

## التحقق

```bash
python -m unittest -v
python -m py_compile app.py
```

## مكوّنات المشروع

- `app.py`: واجهة التطبيق، لوحة المدير، وخادم static آمن افتراضياً.
- `manifest.webmanifest`: تعريف قابلية التثبيت كتطبيق PWA.
- `favicon.svg`: هوية عزوتك المصغّرة.
- `SECURITY.md`: متطلبات الحماية قبل ربط بيانات حقيقية أو مدفوعات.
- `security.py`: IAM وMFA وRBAC والجلسات وCSRF primitives، مع Redis sessions وlogin throttling اختياريين للإنتاج.
- `requirements-production.txt`: اعتماد Redis مثبت للإنتاج فقط؛ المعاينة تبقى بدون تبعيات.
- `jobs.py` و`worker.py`: طوابير Redis Streams مع consumer groups وretry وdead-letter، وعامل منفصل للمهام الخلفية.
- `scripts/bootstrap_iam.py`: إنشاء hash كلمة المرور وTOTP secret دون حفظ الأسرار في المستودع.
- `deploy/`: قوالب Reverse Proxy وTLS وWAF edge لـ Nginx وCaddy، ووحدة systemd غير root.
- `.env.example`: أسماء إعدادات IAM بدون أسرار حقيقية.
- `test_app.py` و`test_security.py` و`test_schema.py`: اختبارات الرؤوس، CSP nonce، IAM، MFA، الجلسات، المسارات ومخطط قاعدة البيانات.
- `BRANDING.md`: خيارات اسم المنصة ومعايير الاختيار داخل السوق الأردني.
- `ROADMAP.md`: مراحل نقل النموذج إلى IAM/OIDC وبيانات وتشغيل إنتاجي.
- `db/migrations/0001_initial.sql`: مخطط PostgreSQL للحجوزات والمزودين والمدفوعات والتدقيق.
- `db/README.md`: حدود الصلاحيات والنسخ الاحتياطي وتشفير البيانات.
- `.github/workflows/quality-security.yml`: اختبارات CI وCodeQL وDependency Review.
- `.github/dependabot.yml`: تحديثات أسبوعية لإجراءات GitHub.

> لوحة الإدارة الحالية نموذج UI تفاعلي وليست نظام IAM. يجب ربطها بمصادقة حقيقية وMFA وRBAC وWAF قبل الإنتاج.
