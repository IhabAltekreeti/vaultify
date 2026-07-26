"""Trusted organization-scoped document-management routes for Vaultify."""

from pathlib import Path
import uuid

from flask import abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import login_required

from vaultify.extensions import db
from vaultify.models import Document
from vaultify.services.ingestion import (
    delete_document_vectors,
    ingest_document,
    validate_pdf_upload,
)
from vaultify.web.tenancy import resolve_active_membership


def require_management_role(membership):
    """Allow document mutation only for trusted owner/admin memberships."""
    if membership.role not in {"owner", "admin"}:
        abort(403)


def _document_services():
    services = current_app.config["VAULTIFY_SERVICES"]

    required = ["embedding_service", "qdrant"]
    missing = [name for name in required if services.get(name) is None]
    if missing:
        raise RuntimeError(
            "Missing document runtime services: " + ", ".join(missing)
        )

    return services


def _ingest(document):
    services = _document_services()
    kwargs = {
        "embedding_service": services["embedding_service"],
        "qdrant_client": services["qdrant"],
        "show_progress_bar": bool(services.get("show_progress_bar", False)),
    }

    if services.get("collection_name"):
        kwargs["collection_name"] = services["collection_name"]
    if services.get("converter") is not None:
        kwargs["converter"] = services["converter"]
    if services.get("chunker") is not None:
        kwargs["chunker"] = services["chunker"]

    return ingest_document(document, **kwargs)


def _delete_vectors(tenant_id, document_hash):
    services = _document_services()
    kwargs = {}
    if services.get("collection_name"):
        kwargs["collection_name"] = services["collection_name"]

    delete_document_vectors(
        services["qdrant"],
        tenant_id,
        document_hash,
        **kwargs,
    )


def register_document_routes(app):
    """Register the golden document-management behavior on one Flask app."""

    @app.get("/documents")
    @login_required
    def documents():
        membership = resolve_active_membership()
        if membership is None:
            abort(403)

        organization_documents = (
            Document.query
            .filter_by(organization_id=membership.organization_id)
            .order_by(Document.created_at.desc())
            .all()
        )

        return render_template(
            "documents.html",
            title="Documents — Vaultify",
            current_membership=membership,
            current_org=membership.organization,
            documents=organization_documents,
        )

    @app.route("/documents/upload", methods=["GET", "POST"])
    @login_required
    def upload_document():
        membership = resolve_active_membership()
        if membership is None:
            abort(403)
        require_management_role(membership)

        if request.method == "GET":
            return render_template(
                "upload.html",
                title="Upload PDF — Vaultify",
                current_membership=membership,
                current_org=membership.organization,
            )

        uploaded_file = request.files.get("file")
        if uploaded_file is None or not uploaded_file.filename:
            flash("Please select a PDF document.", "error")
            return render_template(
                "upload.html",
                current_membership=membership,
                current_org=membership.organization,
            )

        original_filename = uploaded_file.filename.strip()
        file_bytes = uploaded_file.read()

        try:
            validated = validate_pdf_upload(original_filename, file_bytes)
        except ValueError as error:
            flash(str(error), "error")
            return render_template(
                "upload.html",
                current_membership=membership,
                current_org=membership.organization,
            )

        existing_document = Document.query.filter_by(
            organization_id=membership.organization_id,
            document_hash=validated.document_hash,
        ).first()

        if existing_document is not None:
            flash("This document already exists in the organization.", "warning")
            return redirect(url_for("documents"))

        upload_folder = Path(current_app.config["UPLOAD_FOLDER"])
        upload_folder.mkdir(parents=True, exist_ok=True)
        stored_filename = f"{uuid.uuid4().hex}.pdf"
        storage_path = upload_folder / stored_filename
        storage_path.write_bytes(validated.file_bytes)

        document = Document(
            organization_id=membership.organization_id,
            original_filename=validated.original_filename,
            stored_filename=stored_filename,
            storage_path=str(storage_path),
            mime_type="application/pdf",
            size_bytes=len(validated.file_bytes),
            document_hash=validated.document_hash,
            status="uploaded",
        )
        db.session.add(document)
        db.session.commit()

        try:
            chunk_count = _ingest(document)
            flash(
                f"{validated.original_filename} was indexed successfully "
                f"with {chunk_count} chunks.",
                "success",
            )
        except Exception:
            flash(
                "The PDF was stored, but indexing failed safely. "
                "Use Retry after checking the runtime logs.",
                "error",
            )

        return redirect(url_for("documents"))

    @app.post("/documents/<int:document_id>/retry")
    @login_required
    def retry_document(document_id):
        membership = resolve_active_membership()
        if membership is None:
            abort(403)
        require_management_role(membership)

        document = Document.query.filter_by(
            id=document_id,
            organization_id=membership.organization_id,
        ).first_or_404()

        try:
            chunk_count = _ingest(document)
            flash(f"The document was indexed with {chunk_count} chunks.", "success")
        except Exception:
            flash("The retry failed safely.", "error")

        return redirect(url_for("documents"))

    @app.post("/documents/<int:document_id>/delete")
    @login_required
    def delete_document(document_id):
        membership = resolve_active_membership()
        if membership is None:
            abort(403)
        require_management_role(membership)

        document = Document.query.filter_by(
            id=document_id,
            organization_id=membership.organization_id,
        ).first_or_404()

        _delete_vectors(
            membership.organization.tenant_id,
            document.document_hash,
        )

        storage_path = Path(document.storage_path)
        db.session.delete(document)
        db.session.commit()

        if storage_path.exists():
            storage_path.unlink()

        flash("The document was deleted from storage and Qdrant.", "success")
        return redirect(url_for("documents"))
