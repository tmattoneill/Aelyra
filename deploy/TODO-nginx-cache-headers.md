# TODO: nginx cache headers for aelyra.moneill.net

Not yet applied. Needs a change to shared web-tier config on the prod box,
which also serves moneill.net, cockpit, dataviz, gpt, newsreader and
pub-search — so it wants a deliberate window, not a drive-by edit.

## The problem

`/etc/nginx/sites-available/aelyra.moneill.net` serves the SPA from a bare
`location /` with no cache directives:

    location / {
        root /home/ubuntu/Aelyra/frontend/dist;
        index index.html index.htm;
        try_files $uri /index.html;
    }

With no `Cache-Control`, browsers fall back to heuristic caching based on
`Last-Modified`. They hold `index.html`, which names a content-hashed bundle
that the next deploy deletes. The user is then pinned to stale JavaScript.

Observed 2026-08-09: after the auth rework shipped, a cached `index.html` kept
loading the pre-rework bundle, which reads tokens from the URL. The new backend
no longer sends them there, so login could never complete and every reload
returned to the connect screen. `Cmd+Shift+R` cleared it. This will recur on
every deploy until the headers are set.

## The change

Add above the existing `location /`:

    # Vite gives these content-hashed names, so a changed file is a changed
    # URL — safe to cache hard.
    location ^~ /assets/ {
        root /home/ubuntu/Aelyra/frontend/dist;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # index.html names the current bundle, so it must be revalidated every
    # time.
    location = /index.html {
        root /home/ubuntu/Aelyra/frontend/dist;
        add_header Cache-Control "no-cache";
    }

`try_files $uri /index.html` resolves through the new exact-match block, so
deep links keep working. Returning users get faster loads, not slower: the
hashed assets become properly cacheable, and only the small HTML file is
revalidated.

## Applying it

    sudo nginx -t && sudo systemctl reload nginx

Verify:

    curl -sI https://aelyra.moneill.net/ | grep -i cache-control
    # expect: Cache-Control: no-cache
    curl -sI https://aelyra.moneill.net/assets/<current>.js | grep -i cache-control
    # expect: Cache-Control: public, immutable

Then commit the nginx config to `deploy/` alongside `aelyra.service` — it is
load-bearing and currently exists only on the server.
