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

لبيئة التطوير/الانتقال فقط يمكن إنشاء بيانات IAM محلية دون كتابتها في Git:

```bash
python scripts/bootstrap_iam.py
```

لا تُحمّل هذه القيم في production. إعداد production يجب أن يستخدم Keycloak/OIDC وPasskeys/TOTP:

```bash
export APP_ENV=production
export IAM_MODE=oidc
export PUBLIC_ORIGIN=https://app.your-domain.jo
export OIDC_ISSUER_URL=https://identity.your-domain.jo/realms/ezwatek
export OIDC_CLIENT_ID=ezwatek-web
export OIDC_REQUIRED_AMR=webauthn,fido2,otp
export OIDC_REDIRECT_URI=https://app.your-domain.jo/auth/callback
export SESSION_STORE=redis
export RATE_LIMIT_STORE=redis
export REDIS_URL=rediss://...
export DATA_BACKEND=postgres
export DATABASE_URL=postgresql://...
export WAF_MODE=managed
export ENABLE_HSTS=1
export ADMIN_UI_ENABLED=1
```

ضع القيم في Secret Manager أو ملف خدمة محمي، ولا تضع `OIDC_CLIENT_SECRET` أو `DATABASE_URL` في Git.

### قائمة Keycloak/OIDC

- أنشئ confidential أو public client مناسباً لـ Authorization Code + PKCE مع `S256` فقط.
- سجّل Redirect URI واحداً مطابقاً حرفياً لـ `/auth/callback`، ولا تستخدم wildcard.
- فعّل claims: `sub`, `preferred_username` أو `email`, `groups`, و`amr`.
- اربط مجموعات/أدوار Keycloak بالـ `OIDC_ROLE_MAP`، وفعّل WebAuthn للمديرين مع OTP كاسترداد.
- اختبر أن ID token يحوي issuer وaudience وnonce وexp وamr قبل فتح لوحة الإدارة.

التطبيق يوفر endpoints داخلية:

- `GET /api/auth/status`
- عند `IAM_MODE=local` للانتقال فقط: `POST /api/auth/login` ويتطلب username/password/MFA code.
- عند `IAM_MODE=oidc`: `GET /auth/login` يبدأ Authorization Code + PKCE، و`GET /auth/callback` يتحقق من state/nonce وID token ثم ينشئ جلسة مشتركة.
- `POST /api/auth/login` لا يعود إلى IAM المحلي عند وضع OIDC؛ يعيد `oidc_required` مع رابط بدء الدخول.
- `POST /api/auth/logout` ويتطلب `X-CSRF-Token`.
- `GET /api/admin/overview` ويتطلب permission `admin:read`.
- `GET /api/admin/security` ويتطلب permission `security:read`.
- `GET /api/admin/audit` ويتطلب permission `audit:read`.

الجلسة تستخدم cookie HttpOnly وSameSite=Strict، وتتحول إلى `__Host-` cookie مع Secure في الإنتاج. يستخدم production Redis للجلسات وstate الخاص بـ OIDC وRate limiting؛ التخزين داخل الذاكرة مخصص للمعاينة/الانتقال فقط.

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
