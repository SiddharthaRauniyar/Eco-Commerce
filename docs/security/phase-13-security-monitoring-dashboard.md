# Phase 13 — Security Monitoring Dashboard

## Delivered

`/security/monitoring/` is available only to users with the Django
`security.view_securityevent` permission. It presents the security information
that the current role is allowed to view:

- unresolved critical and high-risk events plus a 24-hour signal count;
- recent failed sign-ins, audit-log entries, and account activity when the
  related view permission is granted; and
- an event-resolution action only for users with
  `security.change_securityevent`.

Resolving an event preserves its original description and evidence, records
the resolver and timestamp, and creates a separate `AuditLog` entry. Django
admin registers the same records as read-oriented evidence; security events
can be resolved in bulk through its audited action.

## Verification

- a security analyst sees permitted records and controls;
- a view-only observer cannot resolve an event;
- resolving an event records its decision in the audit trail.

No new telemetry, tracking scripts, or database tables were introduced. The
dashboard uses the existing application-side security events, audit logs,
activity logs, and login attempts.
