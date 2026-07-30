# CareTrust design prototype

Open `index.html` through any static web server. The prototype is dependency-free
and uses only synthetic data.

It is a communication surface for the tested CareTrust state model, not a
production interface. The interactions demonstrate:

- evidence-linked draft extraction;
- visible uncertainty and human deferral;
- separate synthetic source match/mismatch;
- deterministic application authorization; and
- revocation followed by denial.

For local review:

```powershell
python -m http.server 8000 --directory demo
```
