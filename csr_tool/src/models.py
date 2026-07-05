from dataclasses import dataclass, field
from typing import List, Optional, Dict

@dataclass
class BaseInfo:
    reg_bitwidth: int = 32
    author: str = ""
    email: str = ""
    system_baseaddr: Optional[int] = None
    system_bytesize: Optional[int] = None
    system_prefix: str = ""

@dataclass
class FieldModel:
    name: str
    msb: int
    lsb: int
    sw_access: str
    default_value: str
    description: str

@dataclass
class RegisterModel:
    name: str
    offset: int
    description: str
    reg_type: str = "" # type column
    special: str = ""  # special column
    fields: List[FieldModel] = field(default_factory=list)

@dataclass
class ModuleModel:
    name: str
    base_address: int = 0
    base_info: BaseInfo = field(default_factory=BaseInfo)
    registers: List[RegisterModel] = field(default_factory=list)
    sub_modules: List['SubModuleInstance'] = field(default_factory=list)
    is_leaf: bool = True
    excel_path: str = ""

@dataclass
class SubModuleInstance:
    instance_name: str
    module_name: str
    offset: int
    excel_path: str
    module_obj: Optional[ModuleModel] = None
    bytesize: Optional[int] = None
