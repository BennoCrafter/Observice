import yaml
from pathlib import Path
from typing import Any
from src.config.models.config import Config
from dataclasses import fields


def load_config(file_path: Path) -> Config:
    with file_path.open("r") as file:
        yaml_data = yaml.safe_load(file)
        return from_dict(data_class=Config, data=yaml_data)

def from_dict(data_class, data: dict) -> Any:
    """
    Converts a dictionary to an instance of a data class.
    Supports nested data classes.
    """
    fieldtypes = {field.name: field.type for field in fields(data_class)}
    field_values = {}

    for field_name, field_type in fieldtypes.items():
        if field_name in data:
            field_value = data[field_name]

            if hasattr(field_type, "__dataclass_fields__"):
                field_value = from_dict(field_type, field_value)

            if field_type == Path and isinstance(field_value, str):
                field_value = Path(field_value)

            field_values[field_name] = field_value
        else:
            raise ValueError(f"Missing required field: {field_name}")

    return data_class(**field_values)
