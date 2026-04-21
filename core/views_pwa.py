"""
Vues PWA — manifest dynamique et service worker.

Le manifest est généré selon le tenant (dashboard = "Jayma Dashboard",
boutique = nom de la boutique, portail livreur = "Jayma Livreur").
"""
from django.conf import settings
from django.http import JsonResponse, HttpResponse
from django.templatetags.static import static
from django.views.decorators.cache import cache_control


def _icon_urls(request):
    return {
        "192": request.build_absolute_uri(static("icons/icon-192.png")),
        "512": request.build_absolute_uri(static("icons/icon-512.png")),
        "maskable": request.build_absolute_uri(static("icons/icon-maskable-512.png")),
    }


@cache_control(public=True, max_age=3600)
def manifest(request):
    """Manifest PWA adapté au tenant courant."""
    tenant = getattr(request, "tenant_type", "public")
    shop = getattr(request, "shop", None)

    icons = _icon_urls(request)
    icons_list = [
        {"src": icons["192"], "sizes": "192x192", "type": "image/png", "purpose": "any"},
        {"src": icons["512"], "sizes": "512x512", "type": "image/png", "purpose": "any"},
        {"src": icons["maskable"], "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
    ]

    # Défauts
    name = "Jayma"
    short_name = "Jayma"
    description = "Plateforme e-commerce pour les commerçants sénégalais."
    start_url = "/"
    theme_color = "#C45C2A"
    background_color = "#FFFFFF"

    if tenant == "dashboard":
        name = "Jayma — Dashboard commerçant"
        short_name = "Jayma Dash"
        description = "Gère ta boutique, tes produits et tes commandes en temps réel."
        start_url = "/"
    elif tenant == "admin":
        name = "Jayma — Admin plateforme"
        short_name = "Jayma Admin"
        description = "Panneau de pilotage Jayma."
        start_url = "/"
        background_color = "#1C1612"
    elif tenant == "shop" and shop:
        name = f"{shop.name} — Boutique en ligne"
        short_name = shop.name[:30]
        description = shop.description or f"Boutique en ligne {shop.name}"
        start_url = "/"
        theme_color = shop.theme_color or "#C45C2A"

    data = {
        "name": name,
        "short_name": short_name,
        "description": description,
        "start_url": start_url,
        "scope": "/",
        "display": "standalone",
        "orientation": "portrait",
        "background_color": background_color,
        "theme_color": theme_color,
        "lang": "fr",
        "icons": icons_list,
        "categories": ["shopping", "business", "productivity"],
    }
    return JsonResponse(data)


@cache_control(public=True, max_age=0, no_cache=True)
def service_worker(request):
    """
    Service worker minimal :
    - cache-first pour les static files + icônes
    - network-first pour tout le reste (toujours des données fraîches)
    - offline → fallback sur une page simple "Pas de connexion"
    """
    sw_js = f"""
// Jayma Service Worker v2
const CACHE_NAME = 'jayma-v2';
const STATIC_ASSETS = [
  '/static/css/main.css',
  '{static("icons/icon-192.png")}',
  '{static("icons/icon-512.png")}',
];

self.addEventListener('install', (event) => {{
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(STATIC_ASSETS).catch(() => null))
  );
  self.skipWaiting();
}});

self.addEventListener('activate', (event) => {{
  event.waitUntil(
    caches.keys().then(keys => Promise.all(
      keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k))
    ))
  );
  self.clients.claim();
}});

self.addEventListener('fetch', (event) => {{
  const url = new URL(event.request.url);
  // Static → cache-first
  if (url.pathname.startsWith('/static/') || url.pathname.startsWith('/media/')) {{
    event.respondWith(
      caches.match(event.request).then(cached => cached || fetch(event.request).then(resp => {{
        if (resp.ok && event.request.method === 'GET') {{
          const copy = resp.clone();
          caches.open(CACHE_NAME).then(c => c.put(event.request, copy));
        }}
        return resp;
      }}))
    );
    return;
  }}
  // GET HTML → network-first avec fallback cache
  if (event.request.method === 'GET' && event.request.headers.get('accept')?.includes('text/html')) {{
    event.respondWith(
      fetch(event.request).then(resp => {{
        if (resp.ok) {{
          const copy = resp.clone();
          caches.open(CACHE_NAME).then(c => c.put(event.request, copy));
        }}
        return resp;
      }}).catch(() => caches.match(event.request).then(
        cached => cached || new Response(
          '<h1 style="font-family:sans-serif;padding:2rem;text-align:center">Pas de connexion</h1>',
          {{headers: {{'Content-Type': 'text/html; charset=utf-8'}}}}
        )
      ))
    );
  }}
}});
"""
    return HttpResponse(sw_js, content_type="application/javascript")
