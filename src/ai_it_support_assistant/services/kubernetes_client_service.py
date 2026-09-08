from functools import lru_cache

from kubernetes import client, config


class KubernetesClientError(Exception):
    pass


@lru_cache
def configure_kubernetes(
    *,
    config_mode: str,
    context: str,
) -> None:
    try:
        if config_mode == "local":
            config.load_kube_config(context=context or None)

        elif config_mode == "incluster":
            config.load_incluster_config()

        else:
            raise KubernetesClientError("Unsupported Kubernetes config mode.")

    except KubernetesClientError:
        raise

    except Exception as exc:
        raise KubernetesClientError("Unable to configure Kubernetes client.") from exc


def get_apps_v1_api(
    *,
    config_mode: str,
    context: str,
) -> client.AppsV1Api:
    configure_kubernetes(
        config_mode=config_mode,
        context=context,
    )

    return client.AppsV1Api()


def get_core_v1_api(
    *,
    config_mode: str,
    context: str,
) -> client.CoreV1Api:
    configure_kubernetes(
        config_mode=config_mode,
        context=context,
    )

    return client.CoreV1Api()
