# Supabase Postgres CA certificate

Download your project's root certificate from the Supabase dashboard:

1. Open **Project Settings → Database → SSL Configuration**
2. Download the server root certificate (often named `prod-ca-2021.crt`)
3. Save it here as `supabase-ca.crt` (this path is gitignored)

Then in `backend/.env`:

```dotenv
DATABASE_SSL_CA=./certs/supabase-ca.crt
```

Restart the API. Connections to `*.supabase.co` / `*.supabase.com` will verify
the server certificate against that CA (`verify-ca` semantics — hostname is not
checked, which is correct for Supabase pooler hostnames).

## Production

Production **refuses to start** without either:

- `DATABASE_SSL_CA` pointing at a real file, or
- `sslmode=verify-full` / `verify-ca` in `DATABASE_URL`, or
- an explicit `DATABASE_SSL_INSECURE=true` opt-out (document compensating controls)

## Verify it works

After pinning the CA, restart uvicorn and confirm the startup log does **not**
include the MITM warning. A wrong CA path causes connection failures at runtime
rather than silent unverified TLS.
