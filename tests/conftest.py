"""Explicit non-production configuration used by the test suite."""

import os


TEST_ENVIRONMENT = {
    "ENVIRONMENT": "test",
    "JWT_ALGORITHM": "HS256",
    "SECRET_KEY": "test-only-jwt-secret-not-for-production",
    "SERVICE_AUTH_TOKEN": "test-only-service-token",
    "POSTGRES_USER": "postgres",
    "POSTGRES_PASSWORD": "test-only-postgres-password",
    "POSTGRES_DB": "lumidoc_test",
    "POSTGRES_HOST": "localhost",
    "POSTGRES_PORT": "5432",
    "POSTGRES_URL": (
        "postgresql://postgres:test-only-postgres-password@localhost:5432/"
        "lumidoc_test"
    ),
    "NEO4J_PASSWORD": "test-only-neo4j-password",
    "REDIS_PASSWORD": "test-only-redis-password",
    "S3_ACCESS_KEY": "test-only-minio-user",
    "S3_SECRET_KEY": "test-only-minio-password",
    "MINIO_ACCESS_KEY": "test-only-minio-user",
    "MINIO_SECRET_KEY": "test-only-minio-password",
}

for environment_name, test_value in TEST_ENVIRONMENT.items():
    os.environ.setdefault(environment_name, test_value)
