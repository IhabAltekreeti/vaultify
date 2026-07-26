"""Bind an active connector credential to the clean Vaultify V2 answer service."""

from vaultify.services.answer_service import answer_question_v2
from vaultify.services.connector_credentials import (
    connector_credential_to_tenant_id,
    resolve_connector_credential,
)


def answer_question_for_connector(
    raw_token,
    question,
    *,
    tenant_runtime_resolver,
    answer_service=answer_question_v2,
    mark_used=True,
    use_llm=True,
):
    """Resolve one connector token to a trusted tenant and run clean V2.

    The caller never supplies tenant_id or organization_id. Unknown and revoked
    credentials fail before tenant runtime resolution or retrieval begins.
    """
    credential = resolve_connector_credential(
        raw_token,
        mark_used=mark_used,
    )
    if credential is None:
        raise PermissionError("Unknown or revoked connector credential.")

    tenant_id = connector_credential_to_tenant_id(credential)
    runtime = tenant_runtime_resolver(tenant_id)

    if runtime is None:
        raise RuntimeError("No Vaultify V2 runtime is available for this tenant.")
    if not isinstance(runtime, dict):
        raise TypeError("The tenant runtime resolver must return a dictionary.")

    required_runtime_keys = {
        "runtime_tenant_id",
        "entity_registry",
        "retrieval_indexes",
        "embedding_service",
    }
    missing_keys = sorted(required_runtime_keys - set(runtime))
    if missing_keys:
        raise RuntimeError(
            "The tenant runtime is incomplete: " + ", ".join(missing_keys)
        )

    runtime_tenant_id = str(runtime["runtime_tenant_id"] or "").strip()
    if runtime_tenant_id != tenant_id:
        raise PermissionError(
            "The resolved V2 runtime belongs to a different tenant."
        )

    answer_kwargs = {
        "runtime_tenant_id": runtime_tenant_id,
        "entity_registry": runtime["entity_registry"],
        "retrieval_indexes": runtime["retrieval_indexes"],
        "embedding_service": runtime["embedding_service"],
        "use_llm": use_llm,
    }

    for optional_key in (
        "groq_client",
        "model",
        "top_k_per_entity",
        "metric_expansions",
    ):
        if optional_key in runtime:
            answer_kwargs[optional_key] = runtime[optional_key]

    return answer_service(
        tenant_id,
        question,
        **answer_kwargs,
    )
