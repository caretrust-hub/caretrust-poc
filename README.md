# CareTrust design prototype

Open `index.html` through any static web server. The prototype is dependency-free
and uses only synthetic data.

It is a communication surface for the tested CareTrust state model, not a
production interface. The interactions demonstrate:

- evidence-linked draft extraction;
- visible uncertainty and human deferral;
- a human action followed by a separately recorded synthetic source match/mismatch;
- deterministic application authorization; and
- revocation followed by denial on a subsequent request.

Each scenario exposes its own synthetic supporting text. Workflow stages are
noninteractive progress indicators; only the labeled trust-gate actions change
state.

For local review:

```powershell
python -m http.server 8000 --directory demo
```

The login-free published copy is available at
https://caretrust-hub.github.io/caretrust-poc/.
