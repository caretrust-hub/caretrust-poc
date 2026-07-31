# CareTrust interactive design prototypes

Use `network.html` for the primary provider-operations workflow. It uses only
synthetic data and can run against the local Python workflow API:

```powershell
.\.venv\Scripts\python scripts\run_provider_console.py
```

Then open `http://127.0.0.1:8765/network.html`.

The workflow demonstrates:

1. an incomplete referral;
2. eight source-linked AI draft fields and two focused gaps;
3. coordinator correction;
4. separate patient sharing approval;
5. deterministic workforce eligibility and supervisor assignment;
6. different minimum-data projections for two independent apps;
7. visible prototype workload counters; and
8. fail-closed denial on a fresh request after revocation.

The companion `reference-client.html` is a deliberately separate, phone-sized
test worker client. It reads only the Care Tasks Mobile projection from the same
synthetic browser session and holds no independent authority state.

When served as static files, the console falls back to a clearly labeled
browser reference adapter. No demo surface makes a live AWS, registry, wallet,
EHR, HIE, identity-provider, or federation call. Revocation affects fresh
requests; existing-session termination is not claimed.

The login-free published copies are available at:

- https://caretrust-hub.github.io/caretrust-poc/
- https://caretrust-hub.github.io/caretrust-poc/network.html
- https://caretrust-hub.github.io/caretrust-poc/reference-client.html
