package ai_it_support.authz

import rego.v1

# ============================================================
# POLICY INPUT / METADATA HELPERS
# ============================================================

context_attributes := object.get(
	object.get(input, "context", {}),
	"attributes",
	{},
)

policy_input_version := object.get(
	context_attributes,
	"policy_input_version",
	"",
)

supported_policy_input_version if {
	policy_input_version == "1"
}

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
# DEFAULT
# ============================================================

default raw_decision := {
	"allowed": false,
	"reason_code": "default_deny",
	"reason": "No policy allowed the request.",
	"policy_id": "default-deny-v1",
	"obligations": [],
	"trace": [],
}

decision := object.union(
	raw_decision,
	{
		"policy_version": data.policy_metadata.version,
		"bundle_revision": data.policy_metadata.revision,
	},
)

# ============================================================
# POLICY INPUT VERSION
# ============================================================

raw_decision := {
	"allowed": false,
	"reason_code": "unsupported_policy_input_version",
	"reason": "Policy input version is unsupported.",
	"policy_id": "global-input-version-v1",
	"obligations": [],
	"trace": [],
} if {
	not supported_policy_input_version
}

# ============================================================
# GLOBAL SUBJECT POLICY
# ============================================================

raw_decision := {
	"allowed": false,
	"reason_code": "subject_disabled",
	"reason": "Disabled subjects are not allowed.",
	"policy_id": "global-subject-policy-v1",
	"obligations": [],
	"trace": [],
} if {
	supported_policy_input_version
	input.subject.disabled
}

# ============================================================
# GLOBAL UNKNOWN ACTION
# ============================================================

raw_decision := {
	"allowed": false,
	"reason_code": "unknown_action",
	"reason": "Unknown policy action.",
	"policy_id": "global-permission-v1",
	"obligations": [],
	"trace": [],
} if {
	supported_policy_input_version
	subject_enabled
	not known_action
}

# ============================================================
# GLOBAL CAPABILITY PERMISSION DENIALS
# ============================================================

raw_decision := {
	"allowed": false,
	"reason_code": "missing_permission",
	"reason": "Required capability permission is missing.",
	"policy_id": "global-permission-v1",
	"obligations": [],
	"trace": [],
} if {
	supported_policy_input_version
	input.action == "service_status.read"
	subject_enabled
	not "service-status:read" in input.subject.permissions
}

raw_decision := {
	"allowed": false,
	"reason_code": "missing_permission",
	"reason": "Required capability permission is missing.",
	"policy_id": "global-permission-v1",
	"obligations": [],
	"trace": [],
} if {
	supported_policy_input_version
	input.action == "kubernetes.read"
	subject_enabled
	not "kubernetes:read" in input.subject.permissions
}

raw_decision := {
	"allowed": false,
	"reason_code": "missing_permission",
	"reason": "Required capability permission is missing.",
	"policy_id": "global-permission-v1",
	"obligations": [],
	"trace": [],
} if {
	supported_policy_input_version
	input.action == "incident.create"
	subject_enabled
	not "incident:create" in input.subject.permissions
}

raw_decision := {
	"allowed": false,
	"reason_code": "missing_permission",
	"reason": "Required capability permission is missing.",
	"policy_id": "global-permission-v1",
	"obligations": [],
	"trace": [],
} if {
	supported_policy_input_version
	input.action == "deployment.restart"
	subject_enabled
	not "deployment:restart" in input.subject.permissions
}

# ============================================================
# SERVICE STATUS READ
# ============================================================

raw_decision := {
	"allowed": true,
	"reason_code": "allowed",
	"reason": "Service status read allowed.",
	"policy_id": "service-status-read-v1",
	"obligations": [],
	"trace": [],
} if {
	supported_policy_input_version
	input.action == "service_status.read"
	subject_enabled
	"service-status:read" in input.subject.permissions
}

# ============================================================
# KUBERNETES READ
# ============================================================

raw_decision := {
	"allowed": false,
	"reason_code": "namespace_access_denied",
	"reason": "Subject cannot read this namespace.",
	"policy_id": "kubernetes-read-v1",
	"obligations": [],
	"trace": [],
} if {
	supported_policy_input_version
	input.action == "kubernetes.read"
	subject_enabled
	"kubernetes:read" in input.subject.permissions

	object.get(
		context_attributes,
		"has_namespace_grant",
		false,
	) != true
}

raw_decision := {
	"allowed": true,
	"reason_code": "allowed",
	"reason": "Kubernetes read allowed.",
	"policy_id": "kubernetes-read-v1",
	"obligations": [],
	"trace": [],
} if {
	supported_policy_input_version
	input.action == "kubernetes.read"
	subject_enabled
	"kubernetes:read" in input.subject.permissions

	object.get(
		context_attributes,
		"has_namespace_grant",
		false,
	) == true
}

# ============================================================
# INCIDENT CREATE
# ============================================================

raw_decision := {
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
	supported_policy_input_version
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

raw_decision := {
	"allowed": false,
	"reason_code": "kubernetes_writes_disabled",
	"reason": "Kubernetes write actions are disabled.",
	"policy_id": "deployment-restart-v1",
	"obligations": [],
	"trace": [],
} if {
	supported_policy_input_version
	input.action == "deployment.restart"
	subject_enabled
	"deployment:restart" in input.subject.permissions

	object.get(
		context_attributes,
		"writes_enabled",
		false,
	) != true
}

# ------------------------------------------------------------
# Global namespace allowlist
# ------------------------------------------------------------

raw_decision := {
	"allowed": false,
	"reason_code": "namespace_not_globally_allowed",
	"reason": "Namespace is outside restart policy.",
	"policy_id": "deployment-restart-v1",
	"obligations": [],
	"trace": [],
} if {
	supported_policy_input_version
	input.action == "deployment.restart"
	subject_enabled
	"deployment:restart" in input.subject.permissions

	object.get(
		context_attributes,
		"writes_enabled",
		false,
	) == true

	namespace := object.get(
		input.resource.attributes,
		"namespace",
		"",
	)

	allowed_namespaces := object.get(
		context_attributes,
		"allowed_namespaces",
		[],
	)

	not namespace in allowed_namespaces
}

# ------------------------------------------------------------
# Global deployment allowlist
# ------------------------------------------------------------

raw_decision := {
	"allowed": false,
	"reason_code": "deployment_not_globally_allowed",
	"reason": "Deployment is outside restart policy.",
	"policy_id": "deployment-restart-v1",
	"obligations": [],
	"trace": [],
} if {
	supported_policy_input_version
	input.action == "deployment.restart"
	subject_enabled
	"deployment:restart" in input.subject.permissions

	object.get(
		context_attributes,
		"writes_enabled",
		false,
	) == true

	namespace := object.get(
		input.resource.attributes,
		"namespace",
		"",
	)

	allowed_namespaces := object.get(
		context_attributes,
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
		context_attributes,
		"allowed_deployments",
		[],
	)

	not deployment_name in allowed_deployments
}

# ------------------------------------------------------------
# Per-user namespace/resource grant
# ------------------------------------------------------------

raw_decision := {
	"allowed": false,
	"reason_code": "namespace_access_denied",
	"reason": "Subject is not authorized for this namespace.",
	"policy_id": "deployment-restart-v1",
	"obligations": [],
	"trace": [],
} if {
	supported_policy_input_version
	input.action == "deployment.restart"
	subject_enabled
	"deployment:restart" in input.subject.permissions

	object.get(
		context_attributes,
		"writes_enabled",
		false,
	) == true

	namespace := object.get(
		input.resource.attributes,
		"namespace",
		"",
	)

	allowed_namespaces := object.get(
		context_attributes,
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
		context_attributes,
		"allowed_deployments",
		[],
	)

	deployment_name in allowed_deployments

	object.get(
		context_attributes,
		"has_namespace_grant",
		false,
	) != true
}

# ------------------------------------------------------------
# Execution requires approved action
# ------------------------------------------------------------

raw_decision := {
	"allowed": false,
	"reason_code": "approval_required",
	"reason": "Approved action is required before execution.",
	"policy_id": "deployment-restart-v1",
	"obligations": [],
	"trace": [],
} if {
	supported_policy_input_version
	input.action == "deployment.restart"
	subject_enabled
	"deployment:restart" in input.subject.permissions

	object.get(
		context_attributes,
		"writes_enabled",
		false,
	) == true

	namespace := object.get(
		input.resource.attributes,
		"namespace",
		"",
	)

	allowed_namespaces := object.get(
		context_attributes,
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
		context_attributes,
		"allowed_deployments",
		[],
	)

	deployment_name in allowed_deployments

	object.get(
		context_attributes,
		"has_namespace_grant",
		false,
	) == true

	object.get(
		context_attributes,
		"phase",
		"",
	) == "execution"

	object.get(
		context_attributes,
		"approval_state",
		"",
	) != "approved"
}

# ------------------------------------------------------------
# Proposal is allowed after all authorization checks
# ------------------------------------------------------------

raw_decision := {
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
	supported_policy_input_version
	input.action == "deployment.restart"
	subject_enabled
	"deployment:restart" in input.subject.permissions

	object.get(
		context_attributes,
		"writes_enabled",
		false,
	) == true

	namespace := object.get(
		input.resource.attributes,
		"namespace",
		"",
	)

	allowed_namespaces := object.get(
		context_attributes,
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
		context_attributes,
		"allowed_deployments",
		[],
	)

	deployment_name in allowed_deployments

	object.get(
		context_attributes,
		"has_namespace_grant",
		false,
	) == true

	object.get(
		context_attributes,
		"phase",
		"",
	) == "proposal"
}

# ------------------------------------------------------------
# Execution allowed after explicit approval
# ------------------------------------------------------------

raw_decision := {
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
	supported_policy_input_version
	input.action == "deployment.restart"
	subject_enabled
	"deployment:restart" in input.subject.permissions

	object.get(
		context_attributes,
		"writes_enabled",
		false,
	) == true

	namespace := object.get(
		input.resource.attributes,
		"namespace",
		"",
	)

	allowed_namespaces := object.get(
		context_attributes,
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
		context_attributes,
		"allowed_deployments",
		[],
	)

	deployment_name in allowed_deployments

	object.get(
		context_attributes,
		"has_namespace_grant",
		false,
	) == true

	object.get(
		context_attributes,
		"phase",
		"",
	) == "execution"

	object.get(
		context_attributes,
		"approval_state",
		"",
	) == "approved"
}

# ------------------------------------------------------------
# Reconciliation
# ------------------------------------------------------------

raw_decision := {
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
	supported_policy_input_version
	input.action == "deployment.restart"
	subject_enabled
	"deployment:restart" in input.subject.permissions

	object.get(
		context_attributes,
		"writes_enabled",
		false,
	) == true

	namespace := object.get(
		input.resource.attributes,
		"namespace",
		"",
	)

	allowed_namespaces := object.get(
		context_attributes,
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
		context_attributes,
		"allowed_deployments",
		[],
	)

	deployment_name in allowed_deployments

	object.get(
		context_attributes,
		"has_namespace_grant",
		false,
	) == true

	object.get(
		context_attributes,
		"phase",
		"",
	) == "reconciliation"
}
