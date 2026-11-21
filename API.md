# AmataShield API (JSON, prefix /api)

All POST/PATCH requests must send header `X-Requested-With: AmataShield`. Authentication uses a secure session cookie.
Errors: `{"error": "message"}` with HTTP 400 validation, 401 sign-in, 403 permission, 404, 409 wrong state, 422, 429, 503 AI unavailable.

| Method & path | Who | Purpose |
|---|---|---|
| POST /auth/register | public | Create farmer, buyer or driver account |
| POST /auth/login, /auth/logout | public / user | Session |
| GET, PATCH /auth/me | user | Profile; GET also says if AI is enabled |
| POST /auth/password | user | Change password |
| POST /deals | farmer, coop_admin (sell) / buyer (buy) | Post a deal |
| GET /deals?status= | user | My transactions (oversight roles see more) |
| GET /deals/open?district=&min_litres=&max_litres=&min_price=&max_price=&sort= | user | Marketplace |
| GET /deals/delivery-jobs | driver | Agreed deals without a driver |
| GET /deals/{id} | party / open post | Detail with allowed `actions`, timeline, payments |
| POST /deals/{id}/join | opposite role | Accept an open post's terms |
| POST /deals/{id}/confirm, /decline, /withdraw, /cancel | parties | Agreement control |
| POST /deals/{id}/drivers; POST /deals/{id}/drivers/{app}/approve | driver; parties | Hire a driver |
| POST /deals/{id}/stage {stage: pickup\|deliver\|receive} | by state and role | Delivery steps |
| POST, GET /deals/{id}/evidence | parties, driver | multipart upload: category, file, measurement, note, captured_at |
| GET /evidence/{id}/file | parties, oversight | Original file |
| POST /deals/{id}/payments | buyer | Report a payment (record only) |
| POST /payments/{id}/confirm, /reject | seller | Confirm receipt, or reject (opens dispute) |
| POST /deals/{id}/disputes; GET /disputes, /disputes/{id} | parties, oversight | Dispute |
| POST /disputes/{id}/events {kind: comment\|proposal\|agree\|evidence} | parties | Discussion; `agree` by the other party resolves |
| POST /disputes/{id}/resolve {outcome} | coop_admin, admin | Mediator records final outcome |
| POST /ai/evidence/{id}/analyse | parties | Gemini reads receipt or lactometer photo (draft) |
| POST /ai/deals/{id}/summary, /consistency, /dispute_help | parties | Gemini text analyses (draft) |
| GET /deals/{id}/ai; POST /ai/{id}/review {action, values} | parties | Human confirms or rejects an AI draft |
| GET /dashboard | user | Role dashboard statistics |
| GET, POST /admin/users; PATCH /admin/users/{id} | admin | User management |
