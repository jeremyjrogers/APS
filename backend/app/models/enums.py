import enum


class WorkCenterArea(str, enum.Enum):
    NEW_UNIT = "NEW_UNIT"
    AFTERMARKET = "AFTERMARKET"
    SHARED = "SHARED"


class ItemType(str, enum.Enum):
    RAW_MATERIAL = "RAW_MATERIAL"
    PURCHASED_COMPONENT = "PURCHASED_COMPONENT"
    MANUFACTURED_PART = "MANUFACTURED_PART"
    SUBASSEMBLY = "SUBASSEMBLY"
    FINISHED_PACKAGE = "FINISHED_PACKAGE"


class MakeOrBuy(str, enum.Enum):
    MAKE = "MAKE"
    BUY = "BUY"


class BomType(str, enum.Enum):
    PROJECT_TEMPLATE = "PROJECT_TEMPLATE"
    PROJECT_INSTANCE = "PROJECT_INSTANCE"
    STANDARD = "STANDARD"


class RoutingType(str, enum.Enum):
    NEW_UNIT = "NEW_UNIT"
    AFTERMARKET_MFG = "AFTERMARKET_MFG"
    OVERHAUL = "OVERHAUL"


class ProjectType(str, enum.Enum):
    ETO = "ETO"
    CTO = "CTO"


class ProjectStatus(str, enum.Enum):
    QUOTED = "QUOTED"
    FIRM = "FIRM"
    LOST = "LOST"
    CANCELLED = "CANCELLED"


class SalesOrderType(str, enum.Enum):
    STANDARD = "STANDARD"
    EMERGENCY = "EMERGENCY"


class OverhaulJobStatus(str, enum.Enum):
    RECEIVED = "RECEIVED"
    TEARDOWN = "TEARDOWN"
    INSPECTION = "INSPECTION"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    APPROVED = "APPROVED"
    IN_REPAIR = "IN_REPAIR"
    TEST = "TEST"
    COMPLETE = "COMPLETE"


class FindingAction(str, enum.Enum):
    REPLACE = "REPLACE"
    REPAIR = "REPAIR"
    REUSE = "REUSE"


class FindingSource(str, enum.Enum):
    MAKE = "MAKE"
    BUY = "BUY"
    INVENTORY = "INVENTORY"


class PurchaseOrderStatus(str, enum.Enum):
    PLANNED = "PLANNED"
    RELEASED = "RELEASED"
    RECEIVED = "RECEIVED"
    CANCELLED = "CANCELLED"


class WorkOrderStatus(str, enum.Enum):
    PLANNED = "PLANNED"
    RELEASED = "RELEASED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETE = "COMPLETE"
    CANCELLED = "CANCELLED"


class WorkOrderSource(str, enum.Enum):
    PROJECT = "PROJECT"
    AFTERMARKET = "AFTERMARKET"
    OVERHAUL = "OVERHAUL"


class ExceptionCategory(str, enum.Enum):
    PAST_DUE_WO_START = "PAST_DUE_WO_START"
    PAST_DUE_PO_RELEASE = "PAST_DUE_PO_RELEASE"
    CAPACITY_OVERLOAD = "CAPACITY_OVERLOAD"
    CAPACITY_CONSTRAINED_LATE = "CAPACITY_CONSTRAINED_LATE"
    CAPACITY_INFEASIBLE = "CAPACITY_INFEASIBLE"
    NO_ROUTING = "NO_ROUTING"
    BOM_DEPTH_EXCEEDED = "BOM_DEPTH_EXCEEDED"
    UNKNOWN_ITEM = "UNKNOWN_ITEM"


class ExceptionSeverity(str, enum.Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class ExceptionStatus(str, enum.Enum):
    OPEN = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    SNOOZED = "SNOOZED"
    RESOLVED = "RESOLVED"


class ActionType(str, enum.Enum):
    EXPEDITE = "EXPEDITE"
    RESCHEDULE = "RESCHEDULE"
    CHANGE_PRIORITY = "CHANGE_PRIORITY"
    RELEASE = "RELEASE"
    CANCEL = "CANCEL"
    ACKNOWLEDGE_EXCEPTION = "ACKNOWLEDGE_EXCEPTION"
    SNOOZE_EXCEPTION = "SNOOZE_EXCEPTION"
    RESOLVE_EXCEPTION = "RESOLVE_EXCEPTION"
    ADJUST_CAPACITY = "ADJUST_CAPACITY"
