"""Utilities for interactive with Kubernetes (plus a bit of scope creep)"""

import argparse
import os
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

import kubernetes
import kubernetes.dynamic
from kubernetes.client import CoreV1Api, V1ConfigMap


def init_k8s() -> None:
    """Load our Kubernetes config. Call this before using Kubernetes."""
    if "KUBERNETES_SERVICE_HOST" in os.environ:
        kubernetes.config.load_incluster_config()
    else:
        kubernetes.config.load_kube_config()


def get_config() -> V1ConfigMap:
    """Returns the config configmap"""
    with kubernetes.client.ApiClient() as k8s_client:
        result = CoreV1Api(k8s_client).read_namespaced_config_map("config", "namespace")
        assert isinstance(result, V1ConfigMap)
        return result


@contextmanager
def aipipe_resource_dclient(kind: str, api_version: str = "ai-pipeline.org/v1alpha1") -> Generator[Any]:
    """This returns a context-managed k8s Dynamic Client for the specified CRD"""
    with kubernetes.client.ApiClient() as k8s_client:
        dclient = kubernetes.dynamic.DynamicClient(k8s_client)
        api = dclient.resources.get(api_version=api_version, kind=kind)
        yield api


def load_gh_app_creds(args: argparse.Namespace) -> tuple[int | str | None, str | None]:
    """Given our command line args, this loads the GitHub credentials specified"""
    if os.access(args.app_id_from, 0):
        with open(args.app_id_from, encoding="ascii") as file:
            app_id = int(file.read())
    else:
        app_id = os.getenv("GITHUB_APP_ID")

    if os.access(args.app_private_key_from, 0):
        with open(args.app_private_key_from, encoding="ascii") as file:
            pkey = file.read()
    else:
        pkey = os.getenv("GITHUB_APP_PRIVATE_KEY")

    return app_id, pkey
