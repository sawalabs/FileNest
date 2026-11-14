from typing import Generator
from fastapi import Depends
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.services.system import SystemService
from backend.app.services.managed_folder import ManagedFolderService
from backend.app.services.filesystem import FilesystemService
from backend.app.services.transaction import TransactionManagerService
from backend.app.services.storage import StorageAnalyzerService
from backend.app.services.organization import OrganizationService
from backend.app.services.smart_rename import SmartRenameService
from backend.app.services.monitoring import MonitoringManagerService
from backend.app.services.router_gateway import RouterGatewayService
from backend.app.services.mcp_service import MCPService
from backend.app.services.specialists import SpecialistService
from backend.app.services.rules_automation import RulesAutomationService
from backend.app.services.assistant import ContextualAssistantService
from backend.app.services.ocr_service import PaddleOCRService


def get_system_service() -> SystemService:
    return SystemService()


def get_managed_folder_service(db: Session = Depends(get_db)) -> ManagedFolderService:
    return ManagedFolderService(db)


def get_filesystem_service(db: Session = Depends(get_db)) -> FilesystemService:
    return FilesystemService(db)


def get_transaction_service(db: Session = Depends(get_db)) -> TransactionManagerService:
    return TransactionManagerService(db)


def get_storage_service(db: Session = Depends(get_db)) -> StorageAnalyzerService:
    return StorageAnalyzerService(db)


def get_organization_service(db: Session = Depends(get_db)) -> OrganizationService:
    return OrganizationService(db)


def get_smart_rename_service(db: Session = Depends(get_db)) -> SmartRenameService:
    return SmartRenameService(db)


def get_monitoring_service(db: Session = Depends(get_db)) -> MonitoringManagerService:
    service = MonitoringManagerService()
    try:
        from sqlalchemy.orm import sessionmaker
        service.set_session_factory(sessionmaker(bind=db.get_bind()))
    except Exception:
        pass
    return service


def get_router_gateway_service(db: Session = Depends(get_db)) -> RouterGatewayService:
    return RouterGatewayService(db)


def get_mcp_service(db: Session = Depends(get_db)) -> MCPService:
    return MCPService(db)


def get_specialist_service(db: Session = Depends(get_db)) -> SpecialistService:
    return SpecialistService(db)


def get_rules_service(db: Session = Depends(get_db)) -> RulesAutomationService:
    return RulesAutomationService(db)


def get_assistant_service(db: Session = Depends(get_db)) -> ContextualAssistantService:
    return ContextualAssistantService(db)


def get_ocr_service(db: Session = Depends(get_db)) -> PaddleOCRService:
    return PaddleOCRService(db)




