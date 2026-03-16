"""Application configuration loaded from environment variables and .env file."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central application settings resolved from environment variables.

    Attributes:
        database_url: PostgreSQL connection string used by SQLAlchemy.
        azure_storage_connection_string: Connection string for Azure Blob and Queue Storage.
        azure_blob_container: Name of the Blob container where CSV files are stored.
        azure_queue_name: Name of the Storage Queue for job messages.
    """

    # --- Database ---
    database_url: str

    # --- Azure Storage ---
    azure_storage_connection_string: str
    azure_blob_container: str
    azure_queue_name: str

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()