"""Minimal extracted Flask application slice used by R1 regressions."""

from pathlib import Path

from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, login_user, logout_user

from vaultify.extensions import csrf, db, login_manager
from vaultify.models import Document, Membership, QueryLog, User
from vaultify.web.documents import register_document_routes
from vaultify.web.tenancy import resolve_active_membership


@login_manager.user_loader
def load_user(user_id):
    try:
        return db.session.get(User, int(user_id))
    except (TypeError, ValueError):
        return None


def normalize_email(value):
    return (value or "").strip().lower()


def serialize_sources(results, limit=5):
    sources = []

    for result in list(results or [])[:limit]:
        payload = result.payload or {}
        sources.append(
            {
                "filename": payload.get("filename", "Unknown file"),
                "section": payload.get("section", "Unknown section"),
                "score": float(result.score),
            }
        )

    return sources


def create_app(*, services, config=None):
    app = Flask(__name__, template_folder="../templates")
    app.config.update(
        SECRET_KEY="development-only-change-me",
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=False,
        VAULTIFY_SERVICES=services,
        UPLOAD_FOLDER=str(Path(app.instance_path) / "uploads"),
    )

    if config:
        app.config.update(config)

    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    login_manager.login_view = "login"
    login_manager.login_message = "Please sign in to continue."
    login_manager.login_message_category = "warning"

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))

        if request.method == "POST":
            email = normalize_email(request.form.get("email"))
            password = request.form.get("password") or ""

            user = User.query.filter_by(email=email).first()

            if user is None or not user.is_active or not user.check_password(password):
                flash("Invalid email address or password.", "error")
                return render_template("login.html")

            login_user(user)

            membership = (
                Membership.query.filter_by(user_id=user.id)
                .order_by(Membership.id.asc())
                .first()
            )

            if membership is None:
                logout_user()
                flash("This account has no organization membership.", "error")
                return render_template("login.html")

            session["organization_id"] = membership.organization_id
            return redirect(url_for("dashboard"))

        return render_template("login.html", title="Sign in — Vaultify")

    @app.post("/logout")
    @login_required
    def logout():
        logout_user()
        session.clear()
        flash("You have been signed out.", "success")
        return redirect(url_for("login"))

    @app.get("/dashboard")
    @login_required
    def dashboard():
        membership = resolve_active_membership()

        if membership is None:
            return redirect(url_for("login"))

        organization = membership.organization

        document_count = Document.query.filter_by(
            organization_id=organization.id
        ).count()

        chunk_count = (
            db.session.query(db.func.coalesce(db.func.sum(Document.chunk_count), 0))
            .filter(
                Document.organization_id == organization.id,
                Document.status == "ready",
            )
            .scalar()
        )

        return render_template(
            "dashboard.html",
            title="Dashboard — Vaultify",
            current_membership=membership,
            current_org=organization,
            document_count=document_count,
            chunk_count=int(chunk_count or 0),
            question=None,
            answer=None,
            sources=[],
        )

    @app.post("/ask")
    @login_required
    def ask():
        membership = resolve_active_membership()

        if membership is None:
            return ("Forbidden", 403)

        question = (request.form.get("question") or "").strip()

        if not question:
            flash("Enter a question first.", "error")
            return redirect(url_for("dashboard"))

        services = app.config["VAULTIFY_SERVICES"]
        result = services["answer_tenant_question"](
            question=question,
            tenant_id=membership.organization.tenant_id,
        )

        answer = result["answer"]
        sources = serialize_sources(result.get("results", []))

        db.session.add(
            QueryLog(
                organization_id=membership.organization_id,
                user_id=current_user.id,
                question=question,
                answer=answer,
                source_count=len(sources),
            )
        )
        db.session.commit()

        document_count = Document.query.filter_by(
            organization_id=membership.organization_id
        ).count()

        chunk_count = (
            db.session.query(db.func.coalesce(db.func.sum(Document.chunk_count), 0))
            .filter(
                Document.organization_id == membership.organization_id,
                Document.status == "ready",
            )
            .scalar()
        )

        return render_template(
            "dashboard.html",
            title="Dashboard — Vaultify",
            current_membership=membership,
            current_org=membership.organization,
            document_count=document_count,
            chunk_count=int(chunk_count or 0),
            question=question,
            answer=answer,
            sources=sources,
        )

    register_document_routes(app)
    return app
