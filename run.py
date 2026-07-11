"""Run the Vaultify web application."""

import os

from app import create_app
from app.extensions import db
from app.rag import initialize_rag_engine


def build_application():
    """Create the Flask app, database, and RAG runtime."""
    application = create_app()

    with application.app_context():
        db.create_all()

    initialize_rag_engine()

    return application


app = build_application()


if __name__ == "__main__":
    app.run(
        host=os.environ.get(
            "VAULTIFY_WEB_HOST",
            "127.0.0.1",
        ),
        port=int(
            os.environ.get(
                "VAULTIFY_WEB_PORT",
                "5000",
            )
        ),
        debug=os.environ.get(
            "VAULTIFY_DEBUG",
            "0",
        ) == "1",
    )
