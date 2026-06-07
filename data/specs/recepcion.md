---
name: recepcion
description: Recepcionista virtual de una clínica dental por WhatsApp
stages: [greet, inquire, answer, book]
expected_next:
  greet: [inquire_osde_coverage, ask_business_hours, ask_first_consultation_free, request_appointment]
  ask_business_hours: [request_appointment, thank_and_farewell]
  inquire_osde_coverage: [request_appointment, thank_and_farewell]
  ask_first_consultation_free: [request_appointment, thank_and_farewell]
  request_clinic_address_and_directions: [thank_and_farewell]
  request_appointment: [confirm_meeting, thank_and_farewell]
safe_clusters:
  - [greet, thank_and_farewell, confirm_meeting]
fact_sources: {}
red_lines:
  - prometer un turno sin pedir nombre y franja horaria
  - inventar cobertura de obras sociales fuera de OSDE / Swiss Medical / Galeno
  - dar un precio distinto al de la lista ($40.000 limpieza, primera consulta gratis)
  - confirmar disponibilidad de urgencia que no se ofrece
certify_recall: 0.60
certify_max_fp: 0
signed_by: ""
---

## Notes

Distilled from live traffic (chapter 18), not hand-authored. Stages and
red lines added during onboarding. Two intents certified to serve
(inquire_osde_coverage, ask_first_consultation_free); the rest in
shadow-serve. Bookings forward to the LLM forever by design — they
carry per-patient specifics no template can hold.

## Signature

Unsigned — distilled draft for owner review.
