# FHIR R4 + SMART App Launch 2.2 scheduling projection

**Evidence status:** `executed_local` for deterministic projection generation;
`contract_tested` for the bounded FHIR/SMART mapping. No external FHIR server,
SMART authorization server, or independent FHIR validator was executed.

The generated `fhir-smart-scheduling-projection.json` maps only two CareTrust
business actions:

| CareTrust action | SMART 2.2 scope | Boundary |
| --- | --- | --- |
| `view_appointments` | `patient/Appointment.rs` | Read/search only |
| `schedule_appointments` | `patient/Appointment.cu` | Create/update only; no delete |

The mapping uses the FHIR R4 [Appointment](https://hl7.org/fhir/R4/appointment.html)
resource and SMART App Launch 2.2 [resource scopes](https://hl7.org/fhir/smart-app-launch/STU2.2/scopes-and-launch-context.html).
The projection never emits wildcard (`*`), delete (`.d`), or `user/` scopes.

Availability is represented separately with FHIR R4
[Schedule](https://hl7.org/fhir/R4/schedule.html) and
[Slot](https://hl7.org/fhir/R4/slot.html). Patient-compartment scopes may not
safely cover organization-level availability, while user scopes are broader
than this profile. A deployed implementation would therefore need its own
policy/gateway filter by organization, service, and location.

The synthetic workflow includes a proposed FHIR R4
[Appointment](https://hl7.org/fhir/R4/appointment.html) and an
[AppointmentResponse](https://hl7.org/fhir/R4/appointmentresponse.html).
Appointment is administrative planning here. It is not a clinical event, so
the projection does not read or create a FHIR R4
[Encounter](https://hl7.org/fhir/R4/encounter.html).

SMART scopes are not the permission source. The underlying permission remains
the fresh CareTrust RAR-shaped authorization detail and deterministic CareTrust
decision, including audience, purpose, relationship/claim/assignment basis, and
revocation status. SMART 2.2 explains that scopes are limited by underlying
permissions and does not model those underlying permissions itself.

The artifact proves different results for two synthetic caregivers: the
family-caregiver scheduling permit produces `patient/Appointment.cu`, while the
agency CNA's direct-care permit produces no scheduling scope. The family
caregiver's post-revocation fresh request is a CareTrust deny with no scope.
It does not claim external-token revocation or session termination.

Generate the artifact with:

```powershell
.\.venv\Scripts\python.exe scripts\build_fhir_scheduling_projection.py
```
