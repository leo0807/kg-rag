# OPA Policy — Aviation Knowledge Base ABAC
# POST http://opa:8181/v1/data/authz/allow
#
# Input schema:
# {
#   "user": {
#     "id":              "emp001",
#     "role":            "engineer",        # admin | engineer | viewer
#     "department":      "hydraulics",
#     "clearance_level": 1                  # 0=public 1=internal 2=restricted
#   },
#   "resource": {
#     "doc_id":        "CPS-HYD-001",
#     "department":    "hydraulics",        # owning department
#     "min_clearance": 1,
#     "action":        "read"               # read | write | export
#   }
# }
#
# Deploy:
#   docker run -d -p 8181:8181 openpolicyagent/opa:latest run --server
#   curl -X PUT http://localhost:8181/v1/policies/authz \
#        -H "Content-Type: text/plain" --data-binary @docker/opa/authz.rego

package authz

import future.keywords.if
import future.keywords.in

default allow := false

# ── Rule 1: Admin can do anything ────────────────────────────────────────────
allow if {
    input.user.role == "admin"
}

# ── Rule 2: Department-match + clearance ─────────────────────────────────────
allow if {
    input.resource.action == "read"
    _department_ok
    _clearance_ok
}

# Export requires clearance ≥ 2 (restricted documents only by cleared staff)
allow if {
    input.resource.action == "export"
    _clearance_ok
    input.user.clearance_level >= 2
}

# ── Rule 3: Public documents (clearance 0) open to all authenticated users ───
allow if {
    input.resource.min_clearance == 0
    input.user.role != ""
}

# ── Helpers ───────────────────────────────────────────────────────────────────

_department_ok if {
    input.user.department == input.resource.department
}

_department_ok if {
    # Cross-department read: quality, safety roles can read any department
    input.user.role in {"quality_engineer", "safety_engineer"}
}

_clearance_ok if {
    input.user.clearance_level >= input.resource.min_clearance
}

# ── Deny reasons (for audit logging) ─────────────────────────────────────────
deny_reasons[reason] if {
    not _department_ok
    reason := sprintf("department_mismatch: user=%v resource=%v",
                      [input.user.department, input.resource.department])
}

deny_reasons[reason] if {
    not _clearance_ok
    reason := sprintf("clearance_insufficient: user_level=%v required=%v",
                      [input.user.clearance_level, input.resource.min_clearance])
}
