# Setup VPS Production — Jappesi

Procédure complète pour provisionner et configurer un VPS Linux capable de servir Jappesi en production. Documente le setup réel effectué pour `jappesi.sn` sur Contabo.

> Ce document est un **runbook** : suivre les étapes dans l'ordre, ne rien sauter. Pour les ops courantes après que la stack tourne, voir [README.md](./README.md).

---

## Sommaire

1. [Pré-requis](#pré-requis)
2. [Phase 1 — Provisionner le VPS](#phase-1--provisionner-le-vps)
3. [Phase 2 — Premier accès SSH + durcissement](#phase-2--premier-accès-ssh--durcissement)
4. [Phase 3 — Installer Docker + outils](#phase-3--installer-docker--outils)
5. [Phase 4 — Cloudflare DNS (A records)](#phase-4--cloudflare-dns-a-records)
6. [Phase 5 — Certificat wildcard Let's Encrypt](#phase-5--certificat-wildcard-lets-encrypt)
7. [Phase 6 — Deploy Key GitHub + clone du repo](#phase-6--deploy-key-github--clone-du-repo)
8. [Phase 7 — Créer `.env.production`](#phase-7--créer-envproduction)
9. [Phase 8 — Premier déploiement](#phase-8--premier-déploiement)
10. [Phase 9 — Superuser + tests](#phase-9--superuser--tests)
11. [Phase 10 — Crontab backup quotidien](#phase-10--crontab-backup-quotidien)
12. [Annexe A — Pièges rencontrés](#annexe-a--pièges-rencontrés)
13. [Annexe B — Bonnes pratiques sécurité](#annexe-b--bonnes-pratiques-sécurité)
14. [Annexe C — Ops courantes](#annexe-c--ops-courantes)

---

## Pré-requis

Avant de commencer, avoir sous la main :

- [ ] Une machine locale avec `ssh`, `git`, `curl`, `dig` (Linux/Mac ou WSL)
- [ ] Une **clé SSH** locale (`~/.ssh/id_ed25519` + `id_ed25519.pub`)
  - Si pas créée : `ssh-keygen -t ed25519 -C "ton.email@example.com"` (3 × Entrée)
- [ ] Un **password manager** (Bitwarden, 1Password, KeePass…) pour stocker secrets
- [ ] Un compte chez un hébergeur VPS (Contabo recommandé pour rapport qualité/prix)
- [ ] Un compte Cloudflare avec le domaine cible déjà délégué (zone active, status « Active »)
- [ ] Un compte GitHub avec accès au repo Jappesi
- [ ] Optionnel mais utile : compte SendGrid déjà configuré (voir [SERVICES.md](./SERVICES.md))

**Domaine cible utilisé dans ce guide** : `jappesi.sn`
**IP cible utilisée dans ce guide** : `213.136.64.42`
**Utilisateur Linux non-root** : `jappesi`

Adapter à tes propres valeurs en s'inspirant de la structure.

---

## Phase 1 — Provisionner le VPS

### 1.1 Choisir l'offre

Recommandé : **Contabo VPS L** (ou équivalent) :
- 8 Go RAM
- 4 vCPU
- 200 Go SSD
- ~7 €/mois sans engagement
- OS : **Ubuntu 24.04 LTS Server**
- Datacenter : **Nuremberg** (latence Dakar ~80-100 ms)

### 1.2 Commander

Pendant la commande Contabo :

- **Term Length** : 1 mois (sans engagement, pour tester)
- **Login Type** : choisir **SSH key** plutôt que password
  - Coller le contenu de `cat ~/.ssh/id_ed25519.pub` dans le champ
- **Hostname** : `jappesi-prod`
- **Add-ons** : aucun
- Payer (CB ou PayPal — pas Wave/OM côté Contabo)

⚠️ Si la première commande VPS est annulée pour vérification d'identité, c'est normal. Aller sur le portail ID Check du provider et uploader CNI + justificatif de domicile (< 3 mois).

### 1.3 Activation

Activation : 30 min - 2 h. Email reçu avec :
- IP du serveur (ex : `213.136.64.42`)
- Login (`root`)
- Mot de passe initial (si pas de SSH key) — à changer immédiatement

→ Stocker l'IP dans le password manager.

---

## Phase 2 — Premier accès SSH + durcissement

> **Tout ce qui suit se fait sur le VPS via SSH.** Garder une session root active jusqu'à la 2.7 incluse pour ne pas se locker dehors.

### 2.1 Première connexion

Sur la machine locale :

```bash
ssh root@213.136.64.42
```

Au premier `yes` pour la fingerprint, et le mot de passe si SSH key pas configurée.

### 2.2 Mise à jour du système

```bash
apt update && apt upgrade -y
```

Si fenêtre bleue de configuration apparaît : Tab → OK → Entrée.

### 2.3 Outils essentiels

```bash
apt install -y curl ca-certificates ufw fail2ban git nano htop
```

### 2.4 Hostname

```bash
hostnamectl set-hostname jappesi-prod
echo "127.0.1.1 jappesi-prod" >> /etc/hosts
```

### 2.5 Créer un utilisateur non-root

```bash
adduser jappesi
# Mot de passe FORT (32+ chars) — stocker dans password manager
# Full Name, Room, Phone… : Entrée pour passer
usermod -aG sudo jappesi
```

### 2.6 Copier la clé SSH dans le compte `jappesi`

```bash
mkdir -p /home/jappesi/.ssh
# Si la clé est déjà chez root :
cp /root/.ssh/authorized_keys /home/jappesi/.ssh/authorized_keys
# Sinon :
nano /home/jappesi/.ssh/authorized_keys
# Coller la sortie de `cat ~/.ssh/id_ed25519.pub` de la machine locale, sauver

chown -R jappesi:jappesi /home/jappesi/.ssh
chmod 700 /home/jappesi/.ssh
chmod 600 /home/jappesi/.ssh/authorized_keys
```

### 2.7 ⚠️ Vérifier la connexion `jappesi` AVANT de désactiver root

Depuis un **deuxième terminal local** (sans fermer le premier) :

```bash
ssh jappesi@213.136.64.42
sudo whoami   # mdp jappesi → doit afficher "root"
```

Si ✅ → continuer.
Si ❌ → revenir au premier terminal root et corriger les permissions, sinon tu te bloques dehors.

### 2.8 Sécuriser SSH

```bash
nano /etc/ssh/sshd_config
```

Modifier (décommenter si besoin) :

```
PermitRootLogin no
PasswordAuthentication no
PubkeyAuthentication yes
```

Puis :

```bash
systemctl restart ssh
```

### 2.9 Firewall UFW

```bash
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable
ufw status verbose
```

Doit afficher 3 règles : `22/tcp`, `80/tcp`, `443/tcp` ALLOW.

### 2.10 fail2ban

```bash
systemctl enable --now fail2ban
systemctl status fail2ban   # active (running) attendu — q pour quitter
```

→ Fermer la session root, désormais on travaille en `jappesi`.

---

## Phase 3 — Installer Docker + outils

> Toutes les commandes ci-dessous depuis `jappesi@jappesi-prod`. `sudo` demande le mot de passe `jappesi`.

### 3.1 Docker (script officiel)

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker jappesi
```

### 3.2 Reconnecter pour appliquer le groupe docker

```bash
exit
ssh jappesi@213.136.64.42
```

### 3.3 Vérifier

```bash
docker --version
docker compose version
docker run --rm hello-world
```

Le dernier doit afficher *Hello from Docker!*.

### 3.4 Certbot + plugin Cloudflare

```bash
sudo apt install -y python3-certbot-dns-cloudflare
```

---

## Phase 4 — Cloudflare DNS (A records)

> Cette étape se fait dans le navigateur — pas sur le VPS.

### 4.1 Créer un token Cloudflare API (pour certbot)

1. https://dash.cloudflare.com/profile/api-tokens
2. **Create Token** → template **Edit zone DNS** → Use template
3. Vérifier les permissions : `Zone | DNS | Edit` (auto-rempli)
4. **Zone Resources** : Include → **Specific zone** → `jappesi.sn` ⚠️ (ne pas choisir "All zones" — moins safe en cas de leak)
5. **Client IP Address Filtering** : laisser vide
6. **TTL** : laisser vide (token sans expiration)
7. Continue → Create Token
8. **Copier IMMÉDIATEMENT** (ne sera plus visible) → password manager sous *Cloudflare API Token — Jappesi DNS*

Le token commence par des caractères aléatoires (ex `cfut_…` ou similaire) — **PAS** par `SG.` (ça c'est SendGrid).

### 4.2 Tester le token

Sur la machine locale :

```bash
curl -s -X GET "https://api.cloudflare.com/client/v4/user/tokens/verify" \
  -H "Authorization: Bearer TON_TOKEN" \
  -H "Content-Type: application/json"
```

Réponse attendue : `"success":true`.

### 4.3 Créer/modifier les A records

Sur le dashboard Cloudflare → **`jappesi.sn`** → DNS → Records.

3 records A vers l'IP du VPS, **tous en DNS only** (nuage gris) :

| Type | Name           | Content          | Proxy     | TTL  |
|------|----------------|------------------|-----------|------|
| A    | `jappesi.sn` (apex) | `213.136.64.42` | DNS only | Auto |
| A    | `www`          | `213.136.64.42`  | DNS only  | Auto |
| A    | `*` (wildcard) | `213.136.64.42`  | DNS only  | Auto |

⚠️ **Vérifier le domaine en haut de page** — facile de se tromper et d'éditer un autre domaine. Vérifier avant de cliquer Save.
⚠️ **Cliquer Save sur chaque ligne** — l'UI Cloudflare fait perdre les modifs si on clique ailleurs sans Save.

### 4.4 Vérifier la propagation

Sur la machine locale ou le VPS :

```bash
dig @1.1.1.1 +short jappesi.sn
dig @1.1.1.1 +short www.jappesi.sn
dig @1.1.1.1 +short test.jappesi.sn   # via wildcard
```

Les 3 doivent retourner `213.136.64.42`. Si encore l'ancienne IP, attendre 1-2 min ou vérifier auprès du nameserver Cloudflare directement :

```bash
dig @bjorn.ns.cloudflare.com +short jappesi.sn
```

Si le NS retourne déjà la bonne valeur mais que `1.1.1.1` non → c'est juste un cache, ça va se résoudre rapidement. Si `bjorn.ns…` retourne aussi l'ancienne IP → la modif Cloudflare n'est pas sauvegardée. Refaire l'étape 4.3.

---

## Phase 5 — Certificat wildcard Let's Encrypt

### 5.1 Stocker le token Cloudflare sur le VPS

⚠️ **Le format est strict.** Une seule ligne, exactement :

```bash
sudo bash -c 'cat > /root/.secrets/cloudflare.ini <<EOF
dns_cloudflare_api_token = TON_TOKEN_CLOUDFLARE
EOF'
sudo chmod 600 /root/.secrets/cloudflare.ini
```

(Préférer cette commande à `nano` pour éviter de coller le mauvais contenu.)

### 5.2 Demander le certificat wildcard

```bash
sudo certbot certonly \
    --dns-cloudflare \
    --dns-cloudflare-credentials /root/.secrets/cloudflare.ini \
    --dns-cloudflare-propagation-seconds 30 \
    -d jappesi.sn -d '*.jappesi.sn' \
    --agree-tos -m alassanaynwa@gmail.com --non-interactive
```

Sortie attendue :
```
Successfully received certificate.
Certificate is saved at: /etc/letsencrypt/live/jappesi.sn/fullchain.pem
Key is saved at:         /etc/letsencrypt/live/jappesi.sn/privkey.pem
This certificate expires on 2026-XX-XX.
```

Le renouvellement automatique est configuré par certbot (cron systemd timer).

### 5.3 Vérifier le timer auto-renew

```bash
sudo systemctl list-timers | grep certbot
```

Doit afficher `certbot.timer` actif.

---

## Phase 6 — Deploy Key GitHub + clone du repo

> Si le repo Jappesi est privé sur GitHub, le VPS a besoin d'une clé SSH dédiée pour cloner.

### 6.1 Générer une clé SSH dédiée au déploiement

```bash
ssh-keygen -t ed25519 -C "jappesi-deploy@vps" -f ~/.ssh/github_deploy -N ""
cat ~/.ssh/github_deploy.pub
```

Copier la clé publique affichée.

### 6.2 Ajouter comme Deploy Key sur GitHub

1. https://github.com/<owner>/<repo>/settings/keys
2. **Add deploy key**
3. Title : `VPS Contabo Jappesi Prod`
4. Key : coller la clé publique
5. ⚠️ **NE PAS COCHER** "Allow write access" (lecture seule = plus safe — le VPS n'a pas à pusher)
6. Add key

### 6.3 Configurer SSH pour utiliser cette clé sur github.com

```bash
cat >> ~/.ssh/config <<'EOF'

Host github.com
  HostName github.com
  User git
  IdentityFile ~/.ssh/github_deploy
  IdentitiesOnly yes
EOF
chmod 600 ~/.ssh/config
```

### 6.4 Tester la connexion GitHub

```bash
ssh -T git@github.com
```

Réponse attendue : `Hi <owner>/<repo>! You've successfully authenticated, but GitHub does not provide shell access.`

### 6.5 Cloner le repo

```bash
sudo mkdir -p /opt
sudo chown jappesi:jappesi /opt
cd /opt
git clone git@github.com:alassanaynwa-dot/jayma.git jappesi
cd jappesi
ls -la
```

Le dossier porte le nom **`jappesi`** côté VPS (le repo GitHub s'appelle `jayma` historiquement, peu importe). On doit voir entre autres :
- `Dockerfile`
- `manage.py`
- `config/`
- `deploy/`
- `.env.production.example`

### 6.6 Si `.env.production.example` est absent

C'est probablement parce que les commits qui le contiennent ne sont pas encore poussés sur `origin/main`. Sur la machine locale :

```bash
cd /var/www/html/jayma   # chemin local
git status
git push origin main
```

Puis sur le VPS :

```bash
cd /opt/jappesi
git pull
ls -la
```

---

## Phase 7 — Créer `.env.production`

### 7.1 Générer les secrets critiques

Sur le VPS :

```bash
# Django SECRET_KEY (50 chars random url-safe)
python3 -c "import secrets; print(secrets.token_urlsafe(50))"

# Postgres password (24 chars random url-safe)
python3 -c "import secrets; print(secrets.token_urlsafe(24))"
```

→ Stocker chaque valeur dans le password manager (entrées séparées : *Jappesi DJANGO_SECRET_KEY*, *Jappesi POSTGRES_PASSWORD*).

### 7.2 Copier le template

```bash
cd /opt/jappesi
cp .env.production.example .env.production
chmod 600 .env.production
nano .env.production
```

### 7.3 Remplir les valeurs

Au minimum (les autres peuvent rester en placeholder le temps de configurer chaque service) :

| Variable                | Valeur                                              |
|-------------------------|-----------------------------------------------------|
| `DJANGO_SECRET_KEY`     | clé générée à 7.1                                  |
| `DJANGO_DEBUG`          | `False`                                            |
| `DJANGO_ALLOWED_HOSTS`  | `jappesi.sn,.jappesi.sn,www.jappesi.sn`            |
| `JAYMA_ROOT_DOMAIN`     | `jappesi.sn`                                       |
| `POSTGRES_DB`           | `jayma`                                            |
| `POSTGRES_USER`         | `jayma`                                            |
| `POSTGRES_PASSWORD`     | mot de passe généré à 7.1                          |
| `EMAIL_HOST`            | `smtp.sendgrid.net`                                |
| `EMAIL_PORT`            | `587`                                              |
| `EMAIL_USE_TLS`         | `True`                                             |
| `EMAIL_HOST_USER`       | `apikey` (texte littéral)                          |
| `EMAIL_HOST_PASSWORD`   | clé SendGrid (commence par `SG.`)                  |
| `DEFAULT_FROM_EMAIL`    | `Jappesi <noreply@jappesi.sn>`                     |
| `USE_R2`                | `False` (tant que R2 pas configuré — voir 7.4)     |

### 7.4 Stockage images

Tant que Cloudflare R2 n'est pas configuré, mettre `USE_R2=False`. Les images s'uploadent dans le volume Docker `media_data` localement. Migration vers R2 plus tard, sans interruption (script à venir).

### 7.5 Permissions

Vérifier que le fichier n'est lisible que par `jappesi` :

```bash
ls -la .env.production
# -rw------- 1 jappesi jappesi  ... .env.production
```

---

## Phase 8 — Premier déploiement

### 8.1 Lancer le script

```bash
cd /opt/jappesi
./deploy/deploy.sh
```

7 étapes exécutées dans l'ordre :
1. `git pull --ff-only`
2. Build images Docker `web` + `celery_worker` + `celery_beat`
3. `python manage.py migrate --noinput`
4. `python manage.py collectstatic --noinput`
5. Build Tailwind CSS (`tailwindcss --minify`)
6. `docker compose up -d` (rolling restart)
7. `docker compose ps`

⏱️ **Premier build** : 5-10 min (pull image Python, install deps Python, npm, etc.). Builds suivants : 30 s - 2 min selon les changements.

### 8.2 Si une étape échoue

```bash
docker compose -f deploy/docker-compose.prod.yml --env-file .env.production logs --tail=200 web
docker compose -f deploy/docker-compose.prod.yml --env-file .env.production logs --tail=200 db
docker compose -f deploy/docker-compose.prod.yml --env-file .env.production logs --tail=200 nginx
```

Erreurs fréquentes :
- **`relation … does not exist`** : migrations pas appliquées → `docker compose run --rm web python manage.py migrate`
- **`502 Bad Gateway`** : `web` pas encore prêt → attendre 30 s ou checker logs gunicorn
- **`SSL: CERTIFICATE_VERIFY_FAILED`** côté SendGrid : `EMAIL_USE_TLS` mal réglé ou clé invalide
- **`could not connect to server`** côté DB : `POSTGRES_PASSWORD` ne matche pas entre `db` et `web` (faute de frappe dans `.env.production`)

---

## Phase 9 — Superuser + tests

### 9.1 Créer le superuser admin

```bash
docker compose -f deploy/docker-compose.prod.yml --env-file .env.production \
    run --rm web python manage.py createsuperuser
```

- Username : `admin` (ou autre)
- Email : `alassanaynwa@gmail.com`
- Password : **fort** (32+ chars, stocker dans password manager)

### 9.2 Tester le site

Dans le navigateur :

| URL                             | Attendu                          |
|---------------------------------|----------------------------------|
| https://jappesi.sn              | Landing Jappesi, cadenas vert    |
| https://jappesi.sn/admin/       | Login Django admin               |
| https://www.jappesi.sn          | Redirection vers `jappesi.sn`    |
| https://test.jappesi.sn         | Page tenant ou 404 (selon code)  |

Vérifier le certificat (cliquer sur le cadenas) :
- Émis par Let's Encrypt
- Couvre `jappesi.sn` ET `*.jappesi.sn`

### 9.3 Test email transactionnel

Depuis l'admin Django, déclencher un envoi (création utilisateur, password reset…) ou via shell :

```bash
docker compose -f deploy/docker-compose.prod.yml --env-file .env.production \
    run --rm web python manage.py shell -c \
    "from django.core.mail import send_mail; send_mail('Test Jappesi', 'OK', None, ['alassanaynwa@gmail.com'])"
```

L'email doit arriver dans Gmail (vérifier dossier Spam si rien).

---

## Phase 10 — Crontab backup quotidien

### 10.1 Configurer le cron

```bash
crontab -e
```

Ajouter (3h du matin tous les jours) :

```
0 3 * * * /opt/jappesi/deploy/backup.sh >> /var/log/jappesi-backup.log 2>&1
```

### 10.2 Tester immédiatement

```bash
/opt/jappesi/deploy/backup.sh
ls -la /opt/jappesi/deploy/backups/
```

Doit créer `jayma_YYYYMMDD_HHMM.sql.gz` non vide.

### 10.3 Rotation

Le script garde **14 derniers jours**. Pour copier les backups hors du VPS (recommandé pour DR), utiliser `rsync`/`scp` depuis une machine externe ou ajouter une étape S3/R2 sync à `backup.sh`.

---

## Annexe A — Pièges rencontrés

Liste des erreurs concrètes commises pendant le setup réel, à ne pas refaire.

### 🪤 Mettre une clé SendGrid dans `cloudflare.ini`

```
Error parsing credentials configuration '/root/.secrets/cloudflare.ini':
Invalid line ('SG.xxx...') (matched as neither section nor keyword)
```

→ Toujours vérifier le **préfixe** :
- `SG.…` = SendGrid (n'a rien à faire dans cloudflare.ini)
- `cfut_…` ou `Bearer-style token` = Cloudflare

→ **Le contenu du fichier `.ini` est echo'é dans le log certbot quand il échoue** → si une clé y a été collée par erreur, **elle est leakée**. Il faut :
1. Révoquer la clé sur le service concerné
2. Purger `/var/log/letsencrypt/letsencrypt.log` :
   ```bash
   sudo truncate -s 0 /var/log/letsencrypt/letsencrypt.log
   ```

### 🪤 Format incorrect dans `cloudflare.ini`

Mettre uniquement le token sans la clé `dns_cloudflare_api_token = ` :

```
Error parsing credentials configuration: Invalid line (...)
```

→ Le fichier doit être exactement :
```
dns_cloudflare_api_token = cfut_xxxxx
```

### 🪤 Modifier les A records sur le mauvais domaine

Cloudflare gère plusieurs zones (ex `jappesi.com`, `jappesi.sn`, `jayma.sn`…). Vérifier le nom du domaine **en haut de la page** avant de modifier des records.

### 🪤 Cliquer "Edit" sans cliquer "Save"

Sur l'UI Cloudflare, modifier un champ puis cliquer ailleurs **annule la modif silencieusement**. Toujours cliquer le bouton bleu **Save** après une édition.

### 🪤 Confondre la machine locale et le VPS

Tous les `git push` se font depuis la **machine locale**, pas le VPS. Le VPS a une clé deploy en lecture seule, il ne peut que `pull`. Si on tape `git push` sur le VPS → "Permission denied".

### 🪤 Cloner avant d'avoir poussé

Le VPS clone depuis `origin/main`. Si la machine locale est en avance et n'a pas encore push, le VPS récupère une vieille version sans les fichiers récents (ex `.env.production.example`). Toujours `git push` avant le `git clone` initial.

### 🪤 Coller une clé/token complet dans une conversation ou un chat

Considérer toute valeur qui apparaît dans une conversation comme **leakée** — elle est visible dans les logs, l'historique terminal, et possiblement archivée. Toujours :
1. Révoquer la clé
2. En générer une nouvelle
3. Ne plus jamais coller de secret en clair dans un chat

Si on doit montrer le format : tronquer (`SG.xxxxx...` ou `cfut_xxxxx...`).

---

## Annexe B — Bonnes pratiques sécurité

### Permissions fichiers sensibles

| Fichier                              | Permissions | Owner       |
|--------------------------------------|-------------|-------------|
| `~/.ssh/`                            | `700`       | `jappesi`   |
| `~/.ssh/authorized_keys`             | `600`       | `jappesi`   |
| `~/.ssh/github_deploy` (privée)      | `600`       | `jappesi`   |
| `/root/.secrets/cloudflare.ini`      | `600`       | `root`      |
| `/opt/jappesi/.env.production`       | `600`       | `jappesi`   |

### Rotation périodique

| Secret                  | Rotation recommandée |
|-------------------------|----------------------|
| Mot de passe `jappesi`  | Tous les 6 mois ou après incident |
| Clé SSH locale          | Tous les 12-24 mois              |
| Token Cloudflare        | Tous les 12 mois                 |
| Clé SendGrid            | Tous les 6 mois ou après leak    |
| Django `SECRET_KEY`     | Jamais (sauf incident)           |
| `POSTGRES_PASSWORD`     | Jamais (sauf incident)           |

### Surveillance

- `fail2ban` actif → bans SSH automatiques
- `ufw` autorise uniquement 22/80/443
- Logs SSH : `/var/log/auth.log`
- Logs nginx : `docker compose logs nginx`
- Logs Django : `docker compose logs web`
- Métriques système : `htop`, `df -h`, `docker stats`

### Si une clé est compromise

1. **Révoquer immédiatement** côté provider (SendGrid, Cloudflare, GitHub…)
2. **Régénérer** une nouvelle clé
3. **Purger les logs** où elle a pu apparaître
4. **Mettre à jour** `.env.production` ou `cloudflare.ini`
5. **Redémarrer** les services qui l'utilisent : `docker compose -f deploy/docker-compose.prod.yml --env-file .env.production restart web celery_worker celery_beat`
6. **Auditer les usages** : SendGrid affiche les emails envoyés récents — vérifier qu'aucun envoi suspect n'a été fait

---

## Annexe C — Ops courantes

### Déploiement d'une mise à jour

```bash
ssh jappesi@213.136.64.42
cd /opt/jappesi
./deploy/deploy.sh
```

### Voir les logs en temps réel

```bash
docker compose -f deploy/docker-compose.prod.yml --env-file .env.production logs -f web
```

(Ctrl+C pour quitter, sans arrêter le container.)

### Shell Django

```bash
docker compose -f deploy/docker-compose.prod.yml --env-file .env.production \
    run --rm web python manage.py shell
```

### Shell Postgres

```bash
docker compose -f deploy/docker-compose.prod.yml --env-file .env.production \
    exec db psql -U jayma -d jayma
```

### Rollback (1 commit)

```bash
cd /opt/jappesi
git log --oneline -5
git revert HEAD
git push origin main   # ⚠️ uniquement depuis la machine locale, pas le VPS
# Puis sur VPS :
./deploy/deploy.sh
```

(Le VPS n'a pas le droit de push — faire la commande revert localement, push, puis pull sur le VPS.)

### Restaurer un backup

```bash
cd /opt/jappesi
LATEST_BACKUP=$(ls -t deploy/backups/*.sql.gz | head -1)
echo "Restoring from: $LATEST_BACKUP"

# Stop l'app pour éviter les écritures concurrentes
docker compose -f deploy/docker-compose.prod.yml --env-file .env.production stop web celery_worker celery_beat

# Restore
gunzip -c "$LATEST_BACKUP" | docker compose -f deploy/docker-compose.prod.yml \
    --env-file .env.production exec -T db psql -U jayma -d jayma

# Restart
docker compose -f deploy/docker-compose.prod.yml --env-file .env.production start web celery_worker celery_beat
```

### Statut services

```bash
docker compose -f deploy/docker-compose.prod.yml --env-file .env.production ps
```

État `healthy` attendu sur `db` et `redis`.

### Espace disque

```bash
df -h /
docker system df              # taille images/volumes/caches
docker system prune -a        # nettoyer images non utilisées (attention : interactive)
```

### Renouveler le cert manuellement (debug)

```bash
sudo certbot renew --force-renewal
```

Puis recharger nginx :

```bash
docker compose -f deploy/docker-compose.prod.yml --env-file .env.production exec nginx nginx -s reload
```

### Reboot propre du VPS

```bash
sudo shutdown -r now
```

Tous les services Docker redémarrent automatiquement (`restart: unless-stopped`).

---

*Dernière mise à jour : 2026-04-28 — basé sur le setup réel de `jappesi.sn` sur Contabo VPS L (213.136.64.42).*
