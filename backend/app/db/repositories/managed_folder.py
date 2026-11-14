from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.app.db.models.managed_folder import ManagedFolder


class ManagedFolderRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, name: str, root_path: str, monitoring_enabled: bool = False, scan_on_startup: bool = False) -> ManagedFolder:
        folder = ManagedFolder(
            name=name,
            root_path=root_path,
            monitoring_enabled=1 if monitoring_enabled else 0,
            scan_on_startup=1 if scan_on_startup else 0,
            is_enabled=1,
        )
        self.db.add(folder)
        self.db.commit()
        self.db.refresh(folder)
        return folder

    def get_by_id(self, folder_id: str) -> Optional[ManagedFolder]:
        return self.db.get(ManagedFolder, folder_id)

    def get_by_root_path(self, root_path: str) -> Optional[ManagedFolder]:
        stmt = select(ManagedFolder).where(ManagedFolder.root_path == root_path)
        return self.db.execute(stmt).scalar_one_or_none()

    def list_all(self, only_enabled: bool = True) -> List[ManagedFolder]:
        stmt = select(ManagedFolder)
        if only_enabled:
            stmt = stmt.where(ManagedFolder.is_enabled == 1)
        return list(self.db.execute(stmt).scalars().all())

    def disable(self, folder_id: str) -> Optional[ManagedFolder]:
        folder = self.get_by_id(folder_id)
        if folder:
            folder.is_enabled = 0
            self.db.commit()
            self.db.refresh(folder)
        return folder
