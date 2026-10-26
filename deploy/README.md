# تشغيل عزوتك خلف Reverse Proxy وTLS

الخادم الداخلي في `app.py` يستمع على `0.0.0.0:8000` للمعاينة. في الإنتاج يجب ربطه على loopback فقط خلف Nginx أو Caddy، وعدم فتح المنفذ الداخلي للإنترنت.

## المسار المقترح

```text
المستخدم -> CDN/WAF -> Nginx أو Caddy -> 127.0.0.1:8000 -> عزوتك
```

## خدمة النظام

`ezwatek.service` يشغّل العملية كمستخدم غير root مع sandboxing أساسي. عدّل `WorkingDirectory` و`ExecStart` وملف `EnvironmentFile` حسب المسار الفعلي، ثم:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now ezwatek.service
sudo systemctl status ezwatek.service
```

## TLS

- يفضّل استخدام Caddy إذا أردت إصدار وتجديد شهادات Let's Encrypt تلقائياً.
- استخدم `deploy/nginx.conf` إذا كان الفريق يدير الشهادات وModSecurity/Coraza مركزياً.
- لا تضع مفاتيح TLS داخل المستودع.
- استخدم TLS 1.2 وTLS 1.3 فقط، مع تعطيل session tickets في Nginx.
- فعّل HSTS بعد التأكد أن كل النطاقات الفرعية تعمل عبر HTTPS.

## WAF وDDoS

- إعدادات Nginx/Caddy هنا تخفف حجم الطلبات وتحدد المعدل، لكنها ليست WAF كاملاً.
- في الإنتاج ضع Cloudflare/AWS WAF أو ModSecurity مع OWASP CRS أمام الـ reverse proxy.
- راقب login endpoint بمعدل أشد من بقية الموقع.
- احتفظ بالمحدد الداخلي في `app.py` كطبقة ثانية، ولا تعتمد عليه وحده عند تشغيل عدة نسخ.

## IAM وMFA وRBAC

أنشئ بيانات مدير أولية دون كتابتها في Git:

```bash
python scripts/bootstrap_iam.py
```

ثم حمّل القيم إلى Secret Manager أو بيئة الخدمة:

```bash
export IAM_ADMIN_USERNAME=...
export IAM_ADMIN_PASSWORD_HASH=...
export IAM_MFA_TOTP_SECRET=...
export IAM_ADMIN_ROLES=owner
export APP_ENV=production
export ADMIN_UI_ENABLED=1
```

التطبيق يوفر endpoints داخلية:

- `GET /api/auth/status`
- `POST /api/auth/login` ويتطلب username/password/MFA code.
- `POST /api/auth/logout` ويتطلب `X-CSRF-Token`.
- `GET /api/admin/overview` ويتطلب permission `admin:read`.
- `GET /api/admin/security` ويتطلب permission `security:read`.
- `GET /api/admin/audit` ويتطلب permission `audit:read`.

الجلسة تستخدم cookie HttpOnly وSameSite=Strict، وتتحول إلى `__Host-` cookie مع Secure في الإنتاج. مخزن الجلسات الحالي داخل الذاكرة مناسب للنموذج فقط؛ قبل التوسع استخدم IdP أو مخزناً مشتركاً مع دعم revocation.

## فحص الإعداد قبل التفعيل

في production، ترفض خدمة systemd البدء إذا لم يكتمل OIDC وPostgreSQL وRedis وWAF. شغّل الفحص يدوياً بعد تحميل ملف البيئة:

```bash
python scripts/validate_production_config.py --json
python -m unittest -v
python -m py_compile app.py security.py jobs.py worker.py
nginx -t                 # عند استخدام Nginx
caddy validate --config deploy/Caddyfile  # عند استخدام Caddy
```

الفحص لا يحتاج إلى أسرار داخل المستودع ولا يطبع قيم المتغيرات الحساسة. إذا كان `APP_ENV` غير production، يمر الفحص حتى تبقى المعاينة المحلية ممكنة.
