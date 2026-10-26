# خارطة طريق عزوتك

اعتمدنا افتراضات الإنتاج التالية ما لم يغيّرها مالك المشروع:

- IAM: Keycloak أو مزوّد OIDC متوافق، مع Passkeys/WebAuthn كخيار أساسي وTOTP كبديل.
- الحافة: Cloudflare WAF ثم Caddy أو Nginx ثم التطبيق.
- البيانات: PostgreSQL مُدار وRedis مشترك.
- الواجهة: الإبقاء على النموذج الحالي للمعاينة، ثم فصل Frontend TypeScript وBackend API عند بدء البيانات الحقيقية.

## المرحلة 0 — قرارات وت threat model

- اختيار النطاق والبيئة السحابية.
- تعريف أنواع البيانات الحساسة، مدد الاحتفاظ، ومتطلبات الخصوصية.
- تعريف الأدوار والموارد التي يمكن لكل دور الوصول إليها.
- اعتماد مزود OIDC ومالك حساب WAF وDNS.

**الحالة:** بانتظار بيانات النطاق ومزود الهوية فقط؛ لا نحتاج أسراراً داخل المحادثة.

## المرحلة 1 — الأساس الآمن

- CSP nonce ورؤوس المتصفح وrate limiting.
- IAM محلي مغلق افتراضياً خارج الإعداد الصريح.
- MFA TOTP وRBAC وCSRF والجلسات HttpOnly.
- health/readiness، اختبارات، PWA metadata، ورفض المسارات غير المعروفة.
- Reverse Proxy وTLS templates وsystemd غير root.

**الحالة:** منجزة في الإصدار `0.5.0`.

## المرحلة 2 — IAM إنتاجي

- ربط Keycloak/OIDC عبر Authorization Code + PKCE؛ عميل OIDC وcallback والتحقق من ID token موجودان، ويبقى اختبار issuer الحقيقي وتعيين الأدوار في بيئة التشغيل.
- Passkeys/WebAuthn للمديرين، وTOTP كخيار استرداد؛ العميل يفرض `amr` مناسباً، وتُفعّل سياسات WebAuthn داخل Keycloak بعد اعتماد issuer.
- فصل نطاق لوحة الإدارة عن نطاق العملاء.
- جلسات مشتركة قابلة للإبطال عبر Redis أو IdP.
- مراجعة RBAC على مستوى المورد، وليس الدور العام فقط.
- منع local IAM في production بعد إكمال انتقال OIDC.

**تحتاج:** نطاقاً وOIDC issuer/client من بيئة التشغيل. لا ترسل client secret في المحادثة. توجد الآن بوابة إعداد fail-closed تمنع تشغيل production قبل اكتمال هذه القيم، لكن تنفيذ Authorization Code/PKCE نفسه لن يُفعّل قبل اعتماد الـ issuer.

## المرحلة 3 — البيانات والعمليات الحقيقية

- PostgreSQL: migration SQL أولي مضبوط موجود في `db/migrations/0001_initial.sql`، وقراءات لوحة الإدارة/كتابة التدقيق تمر عبر `repository.py` عند تفعيل DATA_BACKEND=postgres؛ تشغيل Alembic وإدارة الإصدارات التالية يبقيان ضمن pipeline قاعدة البيانات.
- Redis للجلسات، queues، idempotency، وrate limiting الموزع؛ session adapter وlogin/request throttles وRedis Streams worker متوفرة، ويبقى ربط البيئة الخارجية وhandlers الخاصة بالدفع/الإشعارات مطلوباً.
- نموذج مستخدمين، مزودين، خدمات، حجوزات، مدفوعات، وتقييمات.
- سجل تدقيق append-only مع retention ونسخ احتياطية مشفرة.
- منع تكرار الحجز والدفع عبر idempotency keys.

## المرحلة 4 — الحافة والإطلاق

- Cloudflare/AWS WAF مع OWASP CRS عند الحاجة.
- TLS تلقائي وتجديد شهادات ومراقبة انتهاء الشهادة.
- DDoS protection وbot management وAPI quotas.
- secrets manager وnon-root deployment وnetwork segmentation.
- staging منفصل عن production وfeature flags.

## المرحلة 5 — الجودة والمراقبة

- unit/integration/e2e tests وcontract tests للـ API؛ الاختبارات الحالية تغطي HTTP وsecurity primitives وrepositories وOIDC وqueues.
- SAST وSCA وCodeQL وdependency update automation مفعلة؛ DAST وload testing الفعليان متبقيان بعد تشغيل staging خلف WAF.
- load test للحجز وتسجيل الدخول.
- OpenTelemetry، metrics، structured logs، alerts، وincident runbooks.
- اختبار استعادة النسخ الاحتياطية وخطة disaster recovery.

## المرحلة 6 — ميزات السوق الأردني

- اختيار مزود الدفع المرخص قبل المرور ببيانات البطاقات.
- تكامل SMS/WhatsApp بعد اختيار المزود وسياسة الخصوصية.
- مناطق الخدمة في عمّان، إربد، الزرقاء، العقبة وباقي المحافظات.
- دعم العربية والإنجليزية، الدينار الأردني، CliQ، والدفع عند الإنجاز.
- لوحة مزود الخدمة وتوزيع الطلبات والتقييمات.
