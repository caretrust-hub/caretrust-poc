# CareTrust judge-facing design prototype

Open `index.html` through any static web server. The prototype is dependency-free
and uses only synthetic data.

This is a communication surface for the tested CareTrust state model, not a
production interface. The clean walkthrough demonstrates:

1. a visibly synthetic legacy CNA document;
2. a retained Amazon Textract OCR response with line confidence and evidence
   locations;
3. a retained Bedrock/Qwen structured draft, explicitly separated from OCR;
4. separate human-review, synthetic-source-check, and claim-signing actions;
5. independent App A workforce-onboarding and App B scheduling policy receipts
   that reference the same stable claim ID;
6. revocation after both permits; and
7. `DENY / TOKEN_REVOKED` on a fresh App B request.

The browser makes no AWS, registry, wallet, EHR, or federation call. It replays
retained OCR/model artifacts so the walkthrough is deterministic and does not
expose cloud credentials. Revocation affects new requests in the demonstration;
it does not claim to terminate an already established application session.

The page also exposes the frozen synthetic evaluation results and labels
standards work as `Tested`, `Mapped`, `Contract`, or `Planned`. Safety scenarios
show human correction, material-uncertainty deferral, source mismatch, and
embedded-instruction handling.

For local review:

```powershell
python -m http.server 8000 --directory demo
```

The login-free published copy is available at
https://caretrust-hub.github.io/caretrust-poc/.
