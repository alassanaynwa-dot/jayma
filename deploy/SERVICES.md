# Services & comptes externes — Jappesi

Fiche de référence de tous les services tiers utilisés par Jappesi. À tenir à jour au fur et à mesure.

**Email principal de compte** : `alassanaynwa@gmail.com`

---

## 🌐 Domaines & DNS

### OVH — Nom de domaine
- **URL** : [www.ovh.com/manager](https://www.ovh.com/manager)
- **Rôle** : registrar pour `jappesi.com` et `jappesi.sn`
- **Commande** : #248832665
- **Renouvellement** : `.com` ~13,49€/an · `.sn` ~25,99€/an
- **Action récurrente** : vérifier l'auto-renew est activé (Mon compte > Renouvellement)
- **⚠️ Important** : les nameservers sont délégués à Cloudflare (bjorn + frida)

### Cloudflare — DNS + CDN + R2
- **URL** : [dash.cloudflare.com](https://dash.cloudflare.com)
- **Rôle** : DNS authoritatif, protection DDoS, CDN, stockage R2 (images produits)
- **Plan** : Free (amplement suffisant au début)
- **Zones actives** : `jappesi.com` · `jappesi.sn`
- **Nameservers assignés** : `bjorn.ns.cloudflare.com` · `frida.ns.cloudflare.com`
- **API Token** : à créer si pas encore fait (My Profile > API Tokens > Edit zone DNS)

---

## ✉️ Email transactionnel

### SendGrid (Twilio) — Emails sortants
- **URL** : [app.sendgrid.com](https://app.sendgrid.com)
- **Rôle** : envoi d'emails transactionnels (OTP, confirmation commande, reset mdp)
- **Plan** : Free (100 emails/jour)
- **Domaine authentifié** : `jappesi.sn` (DKIM + DMARC + link branding)
- **API Key** : `Jappesi Prod` (Mail Send Full Access) — stockée dans password manager
- **From address** : `noreply@jappesi.sn`
- **Config dans .env** : `EMAIL_HOST=smtp.sendgrid.net` · `EMAIL_HOST_USER=apikey` · `EMAIL_HOST_PASSWORD=SG.xxx`

### Zimbra OVH — Emails reçus (inbox)
- **URL** : [www.ovhcloud.com/fr/emails/](https://www.ovhcloud.com/fr/emails/)
- **Rôle** : boîte de réception pour `contact@jappesi.sn` (inclus gratuit 1 an avec le domaine OVH)
- **Stockage** : 15 Go
- **Adresses configurables** : `contact@`, `support@`, `legal@`, `privacy@`, `noreply@`…

---

## 📱 SMS

### AfricasTalking — SMS Sénégal
- **URL** : [account.africastalking.com](https://account.africastalking.com)
- **Rôle** : envoi SMS (OTP clients, confirmations commerçants, relances zombies)
- **Plan** : Sandbox gratuit (tests), Prod payant (~10 FCFA/SMS)
- **App name** : `Jappesi`
- **Sender ID** : `JAPPESI` (à valider auprès d'AT, ~1 semaine)
- **Config dans .env** : `AT_USERNAME=...` · `AT_API_KEY=...` · `AT_SENDER_ID=JAPPESI`
- **À faire** : charger le compte prod avec crédits avant le lancement (~20 000 FCFA pour commencer)

---

## 💳 Paiements

### Wave Business Senegal
- **URL** : [business.wave.com](https://business.wave.com)
- **Rôle** : encaissement clients via Wave (le plus utilisé au SN)
- **Délai onboarding** : 1-2 semaines (vérif RCCM + compte bancaire)
- **Webhook à configurer** : `https://jappesi.sn/paiements/webhook/wave/`
- **Config dans .env** : `WAVE_API_KEY=...` · `WAVE_BUSINESS_ID=...` · `WAVE_WEBHOOK_SECRET=...`

### Orange Money Merchant Senegal
- **URL** : [developer.orange.com](https://developer.orange.com)
- **Rôle** : encaissement via Orange Money
- **Délai onboarding** : 2-4 semaines (RDV physique souvent requis)
- **Webhook à configurer** : `https://jappesi.sn/paiements/webhook/orangemoney/`
- **Config dans .env** : `OM_CLIENT_ID=...` · `OM_CLIENT_SECRET=...` · `OM_MERCHANT_KEY=...` · `OM_WEBHOOK_SECRET=...`

### CinetPay — Agrégateur paiements
- **URL** : [app.cinetpay.com](https://app.cinetpay.com)
- **Rôle** : agrège Wave + OM + cartes bancaires + Free Money (backup si les 2 autres traînent)
- **Délai onboarding** : 1-3 jours, 100% en ligne
- **Webhook à configurer** : `https://jappesi.sn/paiements/webhook/cinetpay/`
- **Config dans .env** : `CINETPAY_API_KEY=...` · `CINETPAY_SITE_ID=...` · `CINETPAY_SECRET_KEY=...`

---

## 🖥️ Infrastructure

### Contabo — VPS (en cours de choix)
- **URL** : [my.contabo.com](https://my.contabo.com)
- **Rôle** : serveur où tourne Jappesi (Docker Compose : Django + Postgres + Redis + Celery + Nginx)
- **Produit visé** : **VPS L** (8 Go RAM, 4 vCPU, 200 Go SSD, ~7€/mois)
- **OS** : Ubuntu 24.04 Server
- **Datacenter** : Nuremberg (Allemagne) — latence vers Dakar ~80-100ms
- **Activation** : immédiate (vérif ID légère)
- **Credentials** : root password envoyé par email après activation — **à changer immédiatement**
- **À faire après commande** :
  1. Ajouter ma clé SSH publique
  2. Désactiver login password
  3. Configurer UFW (22, 80, 443 uniquement)
  4. Installer Docker + docker compose

### Cloudflare R2 — Stockage fichiers (images produits)
- **URL** : [dash.cloudflare.com](https://dash.cloudflare.com) → R2 (menu gauche)
- **Rôle** : stockage des images produits (upload commerçants)
- **Prix** : ~$0.015/Go/mois (très bas marché)
- **Bucket à créer** : `jappesi-prod`
- **Config dans .env** : `USE_R2=True` · `R2_BUCKET_NAME=jappesi-prod` · `R2_ACCESS_KEY_ID=...` · `R2_SECRET_ACCESS_KEY=...` · `R2_ENDPOINT_URL=https://xxx.r2.cloudflarestorage.com`
- **À faire** : créer bucket + générer API token R2 (menu R2 > Manage API Tokens)

---

## 🛡️ Observabilité

### Sentry — Monitoring erreurs
- **URL** : [sentry.io](https://sentry.io)
- **Rôle** : capture automatique des erreurs Django + JS en prod, notifications email
- **Plan** : Developer (gratuit, 5k erreurs/mois)
- **Project** : `jappesi-prod`
- **Config dans .env** : `SENTRY_DSN=https://xxx@oyyy.ingest.sentry.io/zzz`
- **À faire** : créer projet + récupérer le DSN

---

## 📋 Juridique / Administratif

### OAPI — Propriété intellectuelle
- **URL** : [www.oapi.int](https://www.oapi.int)
- **Rôle** : dépôt de marque "Jappesi" dans les 17 pays africains francophones
- **Coût** : ~500 000 FCFA pour dépôt classe 35 (services commerciaux) + classe 42 (logiciels)
- **Délai** : 6-12 mois
- **À faire** : recherche d'antériorité → dossier de dépôt (à voir avec un conseil)

### CDP Sénégal — Protection données
- **URL** : [www.cdp.sn](https://www.cdp.sn)
- **Rôle** : déclaration du traitement de données personnelles (LPDP 2008-12)
- **Coût** : gratuit pour déclaration simple
- **À faire** : déclaration en ligne avant mise en production

### RCCM + NINEA — Société
- **URL** : [www.creationdentreprise.sn](https://www.creationdentreprise.sn) (APIX)
- **Rôle** : enregistrement légal de l'entreprise éditrice de Jappesi
- **À faire avant** : recevoir des paiements via Wave Business

---

## 🔧 Outils dev

### GitHub — Code source
- **URL** : [github.com](https://github.com)
- **Rôle** : hébergement du code Jappesi, historique, CI/CD future
- **Repo** : privé (ne pas publier le code tant que pas audité sécu)

---

## 📝 Checklist de lancement

Avant de mettre `jappesi.sn` en prod, vérifier :

- [ ] VPS Contabo activé + durci (SSH only, UFW, utilisateur non-root)
- [ ] Records Cloudflare A : `jappesi.sn` + `*.jappesi.sn` + `www.jappesi.com` → IP VPS
- [ ] Certificat TLS wildcard obtenu via Let's Encrypt
- [ ] `.env.production` rempli avec TOUS les secrets (Django, PG, SendGrid, AT, Wave, OM, CinetPay, R2, Sentry)
- [ ] Migration DB initiale appliquée
- [ ] Superuser admin créé (`createsuperuser`)
- [ ] SendGrid : email de test reçu à `alassanaynwa@gmail.com`
- [ ] AfricasTalking : SMS de test reçu sur ton numéro
- [ ] Wave / OM / CinetPay : au moins UN des 3 configuré avec webhook actif
- [ ] Backup script quotidien activé (crontab)
- [ ] Sentry : une erreur de test remonte
- [ ] Pages légales remplies ([RAISON SOCIALE], [RCCM], [NINEA], adresse)
- [ ] Test achat réel bout-en-bout : client → commande → paiement → SMS → livraison → reversement

---

## 🆘 Support

En cas de pépin urgent :
- **OVH** : 1007 (France) · Support chat depuis le manager
- **Cloudflare** : plan Free = email/ticket, pas de support humain (community discord OK)
- **SendGrid** : [support.sendgrid.com](https://support.sendgrid.com) (plan Free = docs seulement)
- **Contabo** : [contabo.com/en/support](https://contabo.com/en/support) — email
- **AfricasTalking** : [help.africastalking.com](https://help.africastalking.com)

---

*Dernière mise à jour : 2026-04-24*
