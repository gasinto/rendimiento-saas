# Tasks: Separar Estado de Resultado

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~95 |
| 800-line budget risk | Low |
| Chained PRs recommended | No |
| Suggested split | Single PR |
| Delivery strategy | single-pr |
| Chain strategy | pending |

Decision needed before apply: No
Chained PRs recommended: No
Chain strategy: pending
400-line budget risk: Low

### Suggested Work Units

| Unit | Goal | Likely PR | Notes |
|------|------|-----------|-------|
| 1 | Schema+API+Backend | PR 1 | server.py — migration, normalize, dashboard |
| 2 | UI changes | PR 1 | index.html — filter, table, forms |

## Phase 1: Foundation — Schema & Migration

- [ ] 1.1 **Add resultado column + data migration** — `server.py:44-49` add `resultado TEXT DEFAULT 'n/a'` to CREATE TABLE; add ALTER TABLE + UPDATE migration in init_db() mapping old estado to new (estado, resultado) per FR-001, FR-002. Deps: none. Acceptance: fresh DB has resultado column; existing rows migrate correctly (en_curso→n/a, reparado→reparado, etc.). Est: ~15 lines. Risk: medium (data migration needs care).
- [ ] 1.2 **Add _normalize_estado_resultado helper** — `server.py` add helper function that maps legacy estado values (reparado, no_reparado) to new (estado=completado, resultado=reparado/no_reparado) per FR-005. Deps: none. Acceptance: POST with `estado=reparado` yields `{estado:completado, resultado:reparado}`. Est: ~8 lines. Risk: low.

## Phase 2: Core — API Endpoints

- [ ] 2.1 **API list — include resultado** — `server.py:570-594` include `resultado` in SELECT and dict response in `listar_ordenes_detalle()`. Deps: 1.1. Acceptance: GET returns `resultado` field per order. Est: ~4 lines. Risk: low.
- [ ] 2.2 **API create — accept resultado** — `server.py:597-633` call _normalize_estado_resultado on input, accept `resultado`, default `n/a`, include in INSERT. Deps: 1.2. Acceptance: POST with/without resultado stores correctly. Est: ~8 lines. Risk: low.
- [ ] 2.3 **API update — accept resultado** — `server.py:647-669` add `resultado` to updatable fields list, call normalize on data. Deps: 1.2. Acceptance: PUT updates resultado; legacy estado values map correctly. Est: ~4 lines. Risk: low.
- [ ] 2.4 **Dashboard — use resultado for stats** — `server.py:1512-1548` switch reparados from `estado IN ('reparado','completado')` to `resultado='reparado'`, no_reparados from `estado='no_reparado'` to `resultado='no_reparado'`, keep en_curso on `estado='en_curso'`. Deps: 1.1. Acceptance: dashboard counts match new schema. Est: ~8 lines. Risk: medium (affects statistics).

## Phase 3: UI — Reparaciones View

- [ ] 3.1 **Filter — split estado + resultado selects** — `index.html:644-651` replace single filter with two: estado (`en_curso`/`completado`/all) and resultado (`reparado`/`no_reparado`/`n/a`/all); update `window.cargarReparaciones()` to pass both params. Deps: 2.1. Acceptance: filtering by estado only or both works with AND logic. Est: ~15 lines. Risk: low.
- [ ] 3.2 **Table — show resultado column** — `index.html:3295-3316` add resultado column/tag next to estado; update switch case for labels (estado→en_curso/completado tags, resultado→reparado/no_reparado/n/a tags). Deps: 2.1. Acceptance: table shows both columns with correct labels. Est: ~12 lines. Risk: low.
- [ ] 3.3 **Edit form — add resultado select** — `index.html:3329-3345` add `resultado` select (reparado/no_reparado/n/a) below estado; disable resultado when estado=en_curso. Deps: 2.1. Acceptance: edit form shows both selects, pre-populated. Est: ~10 lines. Risk: low.
- [ ] 3.4 **Edit save — send resultado** — `index.html:3428-3449` add `resultado` to data object in `guardarReparacion()`. Deps: 2.3, 3.3. Acceptance: saving edit persists resultado. Est: ~2 lines. Risk: low.
- [ ] 3.5 **Create form — add resultado field** — `index.html:3451-3508` add resultado select defaulting to `n/a` in `openAddReparacion()`; include in POST body in `submitAddReparacion()`. Deps: 2.2. Acceptance: new orders default resultado=n/a. Est: ~8 lines. Risk: low.
