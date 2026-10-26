# سَنَد | خدماتك أقرب

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

## التحقق

```bash
python -m unittest -v
python -m py_compile app.py
```

## مكوّنات المشروع

- `app.py`: واجهة التطبيق، لوحة المدير، وخادم static آمن افتراضياً.
- `manifest.webmanifest`: تعريف قابلية التثبيت كتطبيق PWA.
- `favicon.svg`: هوية سَنَد المصغّرة.
- `SECURITY.md`: متطلبات الحماية قبل ربط بيانات حقيقية أو مدفوعات.
- `test_app.py`: اختبارات الرؤوس الأمنية، CSP nonce، المسارات، والأصول العامة.
- `BRANDING.md`: خيارات اسم المنصة ومعايير الاختيار داخل السوق الأردني.

> لوحة الإدارة الحالية نموذج UI تفاعلي وليست نظام IAM. يجب ربطها بمصادقة حقيقية وMFA وRBAC وWAF قبل الإنتاج.
