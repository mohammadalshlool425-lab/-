# عزوتك | خدماتك أقرب

إصدار النموذج الحالي: `0.11.0`

نموذج تفاعلي RTL لمنصة خدمات منزلية أردنية، مع واجهة العميل ولوحة المدير العام ومركز حماية تشغيلي.

## التشغيل

لا توجد تبعيات خارجية مطلوبة؛ يعتمد الخادم على Python Standard Library.

```bash
python app.py
```

ثم افتح `http://localhost:8000`.

- فحص الخدمة: `GET /health`
- فحص جاهزية الأصول: `GET /ready`

المعاينة المحلية تعمل افتراضياً في وضع التطوير. تشغيل `APP_ENV=production` يمر أولاً عبر بوابة الإعداد، ولن يبدأ قبل اكتمال OIDC وPostgreSQL وRedis وWAF:

```bash
python scripts/validate_production_config.py --json
APP_ENV=development python app.py
```

لوحة المدير مخفية افتراضياً في الإنتاج لتقليل التعرّض. أنشئ هوية إدارية وMFA فقط لبيئة التطوير/الانتقال قبل ربط OIDC:

```bash
python scripts/bootstrap_iam.py
```

## التحقق

```bash
python -m unittest -v
python -m py_compile app.py security.py jobs.py worker.py config.py oidc.py scripts/bootstrap_iam.py scripts/validate_production_config.py
```

## مكوّنات المشروع

- `app.py`: واجهة التطبيق، لوحة المدير، وخادم static آمن افتراضياً.
- `manifest.webmanifest`: تعريف قابلية التثبيت كتطبيق PWA.
- `favicon.svg`: هوية عزوتك المصغّرة.
- `SECURITY.md`: متطلبات الحماية قبل ربط بيانات حقيقية أو مدفوعات.
- `security.py`: IAM وMFA وRBAC والجلسات وCSRF primitives، مع Redis sessions وlogin/request throttling موزعين للإنتاج.
- `requirements-production.txt`: اعتماد Redis مثبت للإنتاج فقط؛ المعاينة تبقى بدون تبعيات.
- `jobs.py` و`worker.py`: طوابير Redis Streams مع consumer groups وretry وdead-letter، وعامل منفصل للمهام الخلفية.
- `config.py` و`scripts/validate_production_config.py`: بوابة fail-closed تمنع تشغيل production قبل OIDC وPostgreSQL وRedis وWAF.
- `oidc.py`: Authorization Code + PKCE، discovery مقيد عبر HTTPS، تحقق RS256 من ID token، وربط مجموعات Keycloak بأدوار RBAC.
- `repository.py`: PostgreSQL pool لقراءات لوحة الإدارة وكتابة سجل التدقيق في production فقط.
- `scripts/migrate.py`: تشغيل migrations بقفل PostgreSQL وchecksum ومنع تعديل migration مطبق.
- `scripts/load_smoke.py`: اختبار حمل محدود وآمن للـ health endpoint محلياً أو على staging مصرح.
- `scripts/dast_smoke.py`: فحوص DAST دفاعية للمسارات والرؤوس ورفض traversal والطلبات غير المصرح بها.
- `scripts/bootstrap_iam.py`: إنشاء hash كلمة المرور وTOTP secret دون حفظ الأسرار في المستودع.
- `deploy/`: قوالب Reverse Proxy وTLS وWAF edge لـ Nginx وCaddy، ووحدة systemd وصورة Docker غير root.
- `.env.example`: أسماء إعدادات IAM بدون أسرار حقيقية.
- `test_app.py` و`test_security.py` و`test_schema.py` و`test_config.py` و`test_jobs.py` و`test_worker.py` و`test_oidc.py` و`test_repository.py`: اختبارات الرؤوس، CSP nonce، IAM، MFA، OIDC، PostgreSQL repository، الجلسات، الإعداد الإنتاجي، الطوابير والعامل ومخطط قاعدة البيانات.
- `BRANDING.md`: خيارات اسم المنصة ومعايير الاختيار داخل السوق الأردني.
- `ROADMAP.md`: مراحل نقل النموذج إلى IAM/OIDC وبيانات وتشغيل إنتاجي.
- `db/migrations/0001_initial.sql`: مخطط PostgreSQL للحجوزات والمزودين والمدفوعات والتدقيق.
- `db/README.md`: حدود الصلاحيات والنسخ الاحتياطي وتشفير البيانات.
- `requirements-dev.txt` و`pyproject.toml`: أدوات Ruff وBandit وpip-audit للتحقق المحلي وCI.
- `.github/workflows/quality-security.yml`: اختبارات CI وSAST وSCA وCodeQL وDependency Review وبناء صورة non-root.
- `.github/dependabot.yml`: تحديثات أسبوعية لإجراءات GitHub.

> واجهة الحجز ولوحة الإدارة في المعاينة تحافظان على تجربة عزوتك الأردنية، لكن زر التأكيد لا ينشئ حجزاً أو دفعة فعلية بعد. في production تُستخدم APIs وقاعدة البيانات ومزودات الدفع بعد اكتمال الربط والتحقق.
