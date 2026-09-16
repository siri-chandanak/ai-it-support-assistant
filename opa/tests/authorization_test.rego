package ai_it_support.authz

import rego.v1

test_service_status_allowed if {
	result := decision with input as {
		"subject": {
			"username": "alice",
			"permissions": [
				"service-status:read",
			],
			"disabled": false,
		},
		"action": "service_status.read",
		"resource": {
			"resource_type": "service",
			"resource_id": "vpn-gateway",
			"attributes": {},
		},
		"context": {
			"attributes": {
				"policy_input_version": "1",
			},
		},
	}

	result.allowed == true
	result.reason_code == "allowed"
}

test_service_status_missing_permission_denied if {
	result := decision with input as {
		"subject": {
			"username": "alice",
			"permissions": [],
			"disabled": false,
		},
		"action": "service_status.read",
		"resource": {
			"resource_type": "service",
			"resource_id": "vpn-gateway",
			"attributes": {},
		},
		"context": {
			"attributes": {
				"policy_input_version": "1",
			},
		},
	}

	result.allowed == false
}

test_disabled_subject_denied if {
	result := decision with input as {
		"subject": {
			"username": "alice",
			"permissions": [
				"service-status:read",
			],
			"disabled": true,
		},
		"action": "service_status.read",
		"resource": {
			"resource_type": "service",
			"resource_id": "vpn-gateway",
			"attributes": {},
		},
		"context": {
			"attributes": {
				"policy_input_version": "1",
			},
		},
	}

	result.allowed == false
	result.reason_code == "subject_disabled"
}

test_unknown_action_denied if {
	result := decision with input as {
		"subject": {
			"subject_id": "alice",
			"username": "alice",
			"roles": ["it_support"],
			"permissions": [],
			"disabled": false,
		},
		"action": "something.unknown",
		"resource": {
			"resource_type": "test",
			"attributes": {},
		},
		"context": {
			"attributes": {
				"policy_input_version": "1",
			},
		},
	}

	result.allowed == false
	result.reason_code == "unknown_action"
	result.policy_id == "global-permission-v1"
}

test_unsupported_policy_input_version_denied if {
	result := decision with input as {
		"subject": {
			"username": "alice",
			"permissions": [
				"service-status:read",
			],
			"disabled": false,
		},
		"action": "service_status.read",
		"resource": {
			"resource_type": "service",
			"resource_id": "vpn-gateway",
			"attributes": {},
		},
		"context": {
			"attributes": {
				"policy_input_version": "999",
			},
		},
	}

	result.allowed == false
	result.reason_code == "unsupported_policy_input_version"
	result.policy_id == "global-input-version-v1"
}
