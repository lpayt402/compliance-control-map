from pathlib import Path

from app.core.config import Settings
from app.core.database import DatabaseManager
from app.frameworks.importer import import_pack
from app.services.bootstrap import ensure_bootstrap_admin
from app.services.demo import load_demo_data
from app.storage import LocalFilesystemStorage


def initialize(settings: Settings) -> None:
    manager = DatabaseManager(settings.database_url)
    try:
        import_pack(Path(settings.framework_pack_root) / "soc2", manager)
        ensure_bootstrap_admin(manager, settings)
        if settings.load_demo:
            load_demo_data(
                manager,
                LocalFilesystemStorage(settings.storage_root),
                Path(settings.demo_files_root),
            )
    finally:
        manager.dispose()


def main() -> None:
    initialize(Settings())


if __name__ == "__main__":
    main()
