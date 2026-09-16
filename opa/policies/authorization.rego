package ai_it_support.authz

import rego.v1


# ============================================================
# DEFAULT
# ============================================================

default decision := {
    "allowed": false,
    "reason_code": "default_deny",
    "reason": "No policy allowed the request.",
    "policy_id": "default-deny-v1",
    "obligations": [],
    "trace": [],
}


# ============================================================
# COMMON HELPERS
# ============================================================

subject_enabled if {
    not input.subject.disabled
}


known_action if {
    input.action == "service_status.read"
}

known_action if {
    input.action == "kubernetes.read"
}

known_action if {
    input.action == "incident.create"
}

known_action if {
    input.action == "deployment.restart"
}


# ============================================================
# GLOBAL SUBJECT POLICY
# ============================================================

decision := {
    "allowed": false,
    "reason_code": "subject_disabled",
    "reason": "Disabled subjects are not allowed.",
    "policy_id": "global-subject-policy-v1",
    "obligations": [],
    "trace": [],
} if {
    input.subject.disabled
}


# ============================================================
# GLOBAL UNKNOWN ACTION
# ============================================================

decision := {
    "allowed": false,
    "reason_code": "unknown_action",
    "reason": "Unknown policy action.",
    "policy_id": "global-permission-v1",
    "obligations": [],
    "trace": [],
} if {
    subject_enabled
    not known_action
}


# ============================================================
# GLOBAL CAPABILITY PERMISSION DENIALS
# ============================================================

decision := {
    "allowed": false,
    "reason_code": "missing_permission",
    "reason": "Required capability permission is missing.",
    "policy_id": "global-permission-v1",
    "obligations": [],
    "trace": [],
} if {
    input.action == "service_status.read"
    subject_enabled
    not "service-status:read" in input.subject.permissions
}


decision := {
    "allowed": false,
    "reason_code": "missing_permission",
    "reason": "Required capability permission is missing.",
    "policy_id": "global-permission-v1",
    "obligations": [],
    "trace": [],
} if {
    input.action == "kubernetes.read"
    subject_enabled
    not "kubernetes:read" in input.subject.permissions
}


decision := {
    "allowed": false,
    "reason_code": "missing_permission",
    "reason": "Required capability permission is missing.",
    "policy_id": "global-permission-v1",
    "obligations": [],
    "trace": [],
} if {
    input.action == "incident.create"
    subject_enabled
    not "incident:create" in input.subject.permissions
}


decision := {
    "allowed": false,
    "reason_code": "missing_permission",
    "reason": "Required capability permission is missing.",
    "policy_id": "global-permission-v1",
    "obligations": [],
    "trace": [],
} if {
    input.action == "deployment.restart"
    subject_enabled
    not "deployment:restart" in input.subject.permissions
}


# ============================================================
# SERVICE STATUS READ
# ============================================================

decision := {
    "allowed": true,
    "reason_code": "allowed",
    "reason": "Service status read allowed.",
    "policy_id": "service-status-read-v1",
    "obligations": [],
    "trace": [],
} if {
    input.action == "service_status.read"
    subject_enabled
    "service-status:read" in input.subject.permissions
}


# ============================================================
# KUBERNETES READ
# ============================================================

decision := {
    "allowed": false,
    "reason_code": "namespace_access_denied",
    "reason": "Subject cannot read this namespace.",
    "policy_id": "kubernetes-read-v1",
    "obligations": [],
    "trace": [],
} if {
    input.action == "kubernetes.read"
    subject_enabled
    "kubernetes:read" in input.subject.permissions

    input.context.attributes.has_namespace_grant != true
}


decision := {
    "allowed": true,
    "reason_code": "allowed",
    "reason": "Kubernetes read allowed.",
    "policy_id": "kubernetes-read-v1",
    "obligations": [],
    "trace": [],
} if {
    input.action == "kubernetes.read"
    subject_enabled
    "kubernetes:read" in input.subject.permissions

    input.context.attributes.has_namespace_grant == true
}

# ============================================================
# INCIDENT CREATE
# ============================================================

decision := {
    "allowed": true,
    "reason_code": "allowed",
    "reason": "Incident creation allowed.",
    "policy_id": "incident-create-v1",
    "obligations": [
        "explicit_approval",
        "audit_execution",
    ],
    "trace": [],
} if {
    input.action == "incident.create"
    subject_enabled
    "incident:create" in input.subject.permissions
}


# ============================================================
# DEPLOYMENT RESTART
# ============================================================

# ------------------------------------------------------------
# Global Kubernetes write kill-switch
# ------------------------------------------------------------

decision := {
    "allowed": false,
    "reason_code": "kubernetes_writes_disabled",
    "reason": "Kubernetes write actions are disabled.",
    "policy_id": "deployment-restart-v1",
    "obligations": [],
    "trace": [],
} if {
    input.action == "deployment.restart"
    subject_enabled
    "deployment:restart" in input.subject.permissions

    input.context.attributes.writes_enabled != true
}


# ------------------------------------------------------------
# Global namespace allowlist
# ------------------------------------------------------------

decision := {
    "allowed": false,
    "reason_code": "namespace_not_globally_allowed",
    "reason": "Namespace is outside restart policy.",
    "policy_id": "deployment-restart-v1",
    "obligations": [],
    "trace": [],
} if {
    input.action == "deployment.restart"
    subject_enabled
    "deployment:restart" in input.subject.permissions

    object.get(
        input.context.attributes,
        "writes_enabled",
        false,
    ) == true

    namespace := object.get(
        input.resource.attributes,
        "namespace",
        "",
    )

    allowed_namespaces := object.get(
        input.context.attributes,
        "allowed_namespaces",
        [],
    )

    not namespace in allowed_namespaces
}


# ------------------------------------------------------------
# Global deployment allowlist
# ------------------------------------------------------------

decision := {
    "allowed": false,
    "reason_code": "deployment_not_globally_allowed",
    "reason": "Deployment is outside restart policy.",
    "policy_id": "deployment-restart-v1",
    "obligations": [],
    "trace": [],
} if {
    input.action == "deployment.restart"
    subject_enabled
    "deployment:restart" in input.subject.permissions

    object.get(
        input.context.attributes,
        "writes_enabled",
        false,
    ) == true

    namespace := object.get(
        input.resource.attributes,
        "namespace",
        "",
    )

    allowed_namespaces := object.get(
        input.context.attributes,
        "allowed_namespaces",
        [],
    )

    namespace in allowed_namespaces

    deployment_name := object.get(
        input.resource.attributes,
        "resource_name",
        "",
    )

    allowed_deployments := object.get(
        input.context.attributes,
        "allowed_deployments",
        [],
    )

    not deployment_name in allowed_deployments
}



# ------------------------------------------------------------
# Per-user namespace/resource grant
# ------------------------------------------------------------

decision := {
    "allowed": false,
    "reason_code": "namespace_access_denied",
    "reason": "Subject is not authorized for this namespace.",
    "policy_id": "deployment-restart-v1",
    "obligations": [],
    "trace": [],
} if {
    input.action == "deployment.restart"
    subject_enabled
    "deployment:restart" in input.subject.permissions

    input.context.attributes.writes_enabled == true

    namespace := input.resource.attributes.namespace
    namespace in input.context.attributes.allowed_namespaces

    deployment_name := input.resource.attributes.resource_name
    deployment_name in input.context.attributes.allowed_deployments

    input.context.attributes.has_namespace_grant != true
}

# ------------------------------------------------------------
# Execution requires approved action
# ------------------------------------------------------------

decision := {
    "allowed": false,
    "reason_code": "approval_required",
    "reason": "Approved action is required before execution.",
    "policy_id": "deployment-restart-v1",
    "obligations": [],
    "trace": [],
} if {
    input.action == "deployment.restart"
    subject_enabled
    "deployment:restart" in input.subject.permissions

    object.get(
        input.context.attributes,
        "writes_enabled",
        false,
    ) == true

    namespace := object.get(
        input.resource.attributes,
        "namespace",
        "",
    )

    allowed_namespaces := object.get(
        input.context.attributes,
        "allowed_namespaces",
        [],
    )

    namespace in allowed_namespaces

    deployment_name := object.get(
        input.resource.attributes,
        "resource_name",
        "",
    )

    allowed_deployments := object.get(
        input.context.attributes,
        "allowed_deployments",
        [],
    )

    deployment_name in allowed_deployments

    object.get(
        input.context.attributes,
        "has_namespace_grant",
        false,
    ) == true

    object.get(
        input.context.attributes,
        "phase",
        "",
    ) == "execution"

    object.get(
        input.context.attributes,
        "approval_state",
        "",
    ) != "approved"
}

# ------------------------------------------------------------
# Proposal is allowed after all authorization checks
# ------------------------------------------------------------

decision := {
    "allowed": true,
    "reason_code": "allowed",
    "reason": "Deployment restart policy allowed.",
    "policy_id": "deployment-restart-v1",
    "obligations": [
        "explicit_approval",
        "audit_execution",
        "verify_rollout",
    ],
    "trace": [],
} if {
    input.action == "deployment.restart"
    subject_enabled
    "deployment:restart" in input.subject.permissions

    object.get(
        input.context.attributes,
        "writes_enabled",
        false,
    ) == true

    namespace := object.get(
        input.resource.attributes,
        "namespace",
        "",
    )

    allowed_namespaces := object.get(
        input.context.attributes,
        "allowed_namespaces",
        [],
    )

    namespace in allowed_namespaces

    deployment_name := object.get(
        input.resource.attributes,
        "resource_name",
        "",
    )

    allowed_deployments := object.get(
        input.context.attributes,
        "allowed_deployments",
        [],
    )

    deployment_name in allowed_deployments

    object.get(
        input.context.attributes,
        "has_namespace_grant",
        false,
    ) == true

    object.get(
        input.context.attributes,
        "phase",
        "",
    ) == "proposal"
}

# ------------------------------------------------------------
# Execution allowed after explicit approval
# ------------------------------------------------------------

decision := {
    "allowed": true,
    "reason_code": "allowed",
    "reason": "Deployment restart policy allowed.",
    "policy_id": "deployment-restart-v1",
    "obligations": [
        "explicit_approval",
        "audit_execution",
        "verify_rollout",
    ],
    "trace": [],
} if {
    input.action == "deployment.restart"
    subject_enabled
    "deployment:restart" in input.subject.permissions

    object.get(
        input.context.attributes,
        "writes_enabled",
        false,
    ) == true

    namespace := object.get(
        input.resource.attributes,
        "namespace",
        "",
    )

    allowed_namespaces := object.get(
        input.context.attributes,
        "allowed_namespaces",
        [],
    )

    namespace in allowed_namespaces

    deployment_name := object.get(
        input.resource.attributes,
        "resource_name",
        "",
    )

    allowed_deployments := object.get(
        input.context.attributes,
        "allowed_deployments",
        [],
    )

    deployment_name in allowed_deployments

    object.get(
        input.context.attributes,
        "has_namespace_grant",
        false,
    ) == true

    object.get(
        input.context.attributes,
        "phase",
        "",
    ) == "execution"

    object.get(
        input.context.attributes,
        "approval_state",
        "",
    ) == "approved"
}


# ------------------------------------------------------------
# Reconciliation
#
# The action was already approved and claimed previously.
# We re-check current authorization and resource scope but
# do not require approval_state == "approved".
# ------------------------------------------------------------

decision := {
    "allowed": true,
    "reason_code": "allowed",
    "reason": "Deployment restart reconciliation allowed.",
    "policy_id": "deployment-restart-v1",
    "obligations": [
        "audit_execution",
        "verify_rollout",
    ],
    "trace": [],
} if {
    input.action == "deployment.restart"
    subject_enabled
    "deployment:restart" in input.subject.permissions

    input.context.attributes.writes_enabled == true

    namespace := input.resource.attributes.namespace
    namespace in input.context.attributes.allowed_namespaces

    deployment_name := input.resource.attributes.resource_name
    deployment_name in input.context.attributes.allowed_deployments

    input.context.attributes.has_namespace_grant == true

    input.context.attributes.phase == "reconciliation"
}