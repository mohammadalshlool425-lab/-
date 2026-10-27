# ملاحظات الأمان لتطبيق عزوتك

هذه النسخة عبارة عن نموذج واجهة تفاعلي مستقل ببايثون من المكتبة القياسية، وليست بديلاً عن بنية إنتاج كاملة. لا يمكن لأي واجهة أن تضمن الحماية من «أي» هجوم، لذلك يجب تشغيلها خلف طبقات حماية حقيقية قبل استقبال بيانات العملاء أو المدفوعات.

## ما تم تفعيله في النموذج

- سياسة Content Security Policy مع nonce جديد لكل استجابة للـ HTML.
- منع MIME sniffing وفرض سياسة Referrer وPermissions محدودة.
- `Cross-Origin-Opener-Policy` و`Cross-Origin-Resource-Policy`.
- تعطيل التخزين المؤقت للوحة والخدمات الحساسة.
- تحديد معدل الطلبات من الذاكرة على الخادم، مع استجابة `429` و`Retry-After`.
- رفض المسارات غير المعروفة والطلبات ذات المسار غير الصالح.
- المسارات العامة للقراءة لا تغيّر الحالة؛ مسارات المصادقة `POST /api/auth/login` و`POST /api/auth/logout` و`POST /api/orders` هي الاستثناءات المعلنة، وتستخدم CSRF وRBAC عند الحاجة. طلبات `PUT` و`DELETE` والمسارات غير المعروفة مرفوضة.
- عدم عكس query strings أو قيم المستخدم في سجلات الخادم.
- رؤوس `X-Frame-Options` و`Strict-Transport-Security` عند تشغيل بيئة الإنتاج.
- لوحة الإدارة في المعاينة تعرض رحلة UI واضحة مع وسم بيانات المعاينة؛ لا تُعامل الأرقام أو الطلبات فيها كبيانات تشغيلية حقيقية. عند تفعيلها في production تُعرض مؤشرات القراءة الفعلية فقط، ولا يوجد fallback إلى أرقام تجريبية.
- قائمة أصول allowlist فقط للـ manifest وfavicon وrobots، مع رفض المسارات العشوائية.
- اختبارات آلية لـ CSP nonce، الرؤوس، HTTP methods، المسارات غير المعروفة، وفحص الجاهزية.
- نقطتا تشغيل منفصلتان للـ liveness (`/health`) والـ readiness (`/ready`) لتسهيل المراقبة دون كشف بيانات تشغيلية.
- أساس IAM محلي للمعاينة/الانتقال فقط: scrypt لكلمات المرور، TOTP متوافق مع RFC 6238، جلسات HttpOnly، CSRF token، وRBAC بالـ permissions.
- OIDC إنتاجي عبر Authorization Code + PKCE، state/nonce أحادية الاستخدام، discovery مقيد بـ HTTPS، وتحقق RS256 من ID token مع issuer/audience/expiry/nonce وربط أدوار Keycloak.
- إعداد OIDC يرفض MFA ضعيفاً: يجب أن يثبت claim `amr` استخدام Passkey/WebAuthn (`webauthn` أو `fido2`) أو TOTP (`otp`) وفق إعداد `OIDC_REQUIRED_AMR`؛ Keycloak هو المسؤول عن رحلة WebAuthn الفعلية.
- سجل تدقيق runtime محدود ومُنقّح مع endpoint محمي `GET /api/admin/audit`; عند `DATA_BACKEND=postgres` يُكتب synchronously إلى `audit_events` ويصبح فشل المخزن فشلاً مغلقاً، مع استمرار الحاجة إلى retention/backup append-only مُدار.
- قوالب Reverse Proxy في `deploy/` لـ Nginx وCaddy، مع TLS حديث، rate limiting، وحدود حجم الطلب.
- GitHub Actions مع اختبارات متعددة لإصدارات Python، Ruff، Bandit، pip-audit، CodeQL، DAST smoke، ومراجعة تغييرات الاعتماديات وبناء صورة non-root.
- مخطط PostgreSQL يفرض JOD، idempotency keyed، تشفير العناوين على مستوى التطبيق، وحدوداً منفصلة للتدقيق. `POST /api/orders` لا يعمل إلا لجلسة OIDC بدور `customer`، ويتطلب CSRF و`Idempotency-Key` ويكتب الطلب و`order.requested` في معاملة واحدة.

## IAM الحالي

- `POST /api/auth/login` لا يعمل دون `IAM_ADMIN_USERNAME` و`IAM_ADMIN_PASSWORD_HASH` و`IAM_MFA_TOTP_SECRET`.
- كلمة المرور تُخزن كـ scrypt hash مع salt؛ لا يتم تخزين كلمة المرور نفسها.
- رمز MFA هو TOTP من ٦ أرقام مع نافذة انحراف ٣٠ ثانية.
- الأدوار الحالية: `customer`, `owner`, `ops_manager`, `security_auditor`, `support_lead`؛ صلاحيات العميل محدودة بقراءة/إنشاء طلباته وتقييمها دون صلاحيات الإدارة.
- صلاحيات الإدارة تُفحص على الخادم عبر RBAC؛ الواجهة وحدها ليست حاجز أمان.
- logout يتطلب CSRF token، والجلسة Cookie `HttpOnly; SameSite=Strict` وتصبح `__Host-` و`Secure` في الإنتاج.
- الجلسات داخل الذاكرة افتراضياً للمعاينة، ويتوفر RedisSessionStore عبر `SESSION_STORE=redis` للنسخ المتعددة؛ استخدم `rediss://` وشهادة موثوقة في الإنتاج.
- يتوفر RedisLoginThrottle وRedisWindowLimiter عبر `RATE_LIMIT_STORE=redis`، ويستخدمان مفاتيح مجزأة وعمليات Lua ذرية وTTL للقفل/النافذة؛ لا يعتمد محدد الطلبات العام أو الدخول على ذاكرة نسخة واحدة في الإنتاج.
- طوابير المهام تستخدم Redis Streams وconsumer groups وacknowledgement وdead-letter؛ ينشر worker إعادة المحاولة قبل تأكيد الرسالة لتفادي فقدانها، وتتحمل handlers التكرار عبر idempotency الخاص بها. لا تُحفظ أسرار مزودي الدفع أو الإشعارات داخل payloads.
- `validate_production_config.py` يرفض تشغيل الخدمة في production عند غياب OIDC أو PostgreSQL أو Redis/TLS أو WAF managed، ويشترط `DATA_BACKEND=postgres` ولا يطبع قيم الأسرار.
- لوحة الإدارة لا تعرض أرقاماً اصطناعية في production؛ قراءات الإدارة ودليل المزودين المتحققين تأتي من PostgreSQL، وتصبح جاهزية الخدمة غير مكتملة عند غياب مخزن البيانات.

## قبل الإطلاق الفعلي

1. استخدم TLS حديثاً خلف reverse proxy أو WAF مُدار، واضبط `APP_ENV=production` و`ENABLE_HSTS=1`. في هذا الوضع تُخفى لوحة الإدارة من HTML افتراضياً؛ لا تفعّلها إلا خلف IAM حقيقي عبر `ADMIN_UI_ENABLED=1`.
2. اربط المدير العام بمزوّد هوية حقيقي يدعم MFA ومفاتيح أمان، مع RBAC وleast privilege؛ إخفاء لوحة الإدارة إجراء تقليل تعرّض وليس مصادقة.
3. انقل rate limiting وDDoS protection إلى طبقة الحافة، لأن المحدد الموجود داخل العملية مناسب للنموذج فقط ولا يعمل عبر عدة نسخ من الخدمة.
4. لا تخزّن كلمات مرور أو رموز دفع أو مفاتيح API داخل المستودع. استخدم secret manager وتدوير المفاتيح والمراقبة.
5. اربط سجل التدقيق بخدمة مركزية append-only، مع تنبيهات ومحاذاة زمنية ومراجعة دورية.
6. أضف اختبارات اختراق، SAST/DAST، فحصاً للتبعيات والصور، نسخاً احتياطية مشفرة، وخطة استجابة للحوادث.
7. استخدم بوابة دفع مرخصة في الأردن ولا تمرر بيانات البطاقات عبر التطبيق؛ التزم بمتطلبات PCI DSS والخصوصية المحلية.

## تشغيل آمن محلياً

```bash
APP_ENV=development python app.py
```

تشغيل `APP_ENV=production` يمر عبر `validate_production_env` ويرفض البدء حتى تكتمل إعدادات OIDC وPostgreSQL وRedis وWAF. لا تستخدم IAM المحلي كاختصار لتجاوز هذا الحاجز.
