import os

# Use SQLAlchemy's pure-Python code paths. Windows "Smart App Control" blocks the unsigned
# compiled extensions on some team machines; the speed difference is irrelevant at MVP scale.
# Must be set before sqlalchemy is imported. Override with DISABLE_SQLALCHEMY_CEXT_RUNTIME=0.
os.environ.setdefault("DISABLE_SQLALCHEMY_CEXT_RUNTIME", "1")
