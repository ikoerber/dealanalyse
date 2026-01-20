"""
Object Type Registry for HubSpot Data Processing

Provides centralized configuration management for different HubSpot object types
(deals, contacts, companies, activities).
"""
import json
import os
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ObjectTypeConfig:
    """Configuration for a HubSpot object type"""
    object_type_id: str
    display_name: str
    api_endpoint: str
    properties: List[str]
    history_properties: List[str]
    default_filters: List[Dict[str, Any]]
    has_stages: bool
    has_history: bool
    supports_associations: bool
    primary_id_field: str
    name_field: str
    note: Optional[str] = None

    def __post_init__(self):
        """Validate configuration after initialization"""
        if not self.object_type_id:
            raise ValueError("object_type_id cannot be empty")
        if not self.api_endpoint:
            raise ValueError(f"api_endpoint cannot be empty for {self.object_type_id}")
        if not self.properties:
            raise ValueError(f"properties list cannot be empty for {self.object_type_id}")

    def get_filter_groups(self, **substitutions) -> List[Dict]:
        """
        Get filter groups with variable substitution

        Args:
            **substitutions: Variable values for substitution (e.g., start_date_timestamp=123456789)

        Returns:
            List of filter group dictionaries ready for HubSpot API
        """
        filter_groups = []

        if not self.default_filters:
            return filter_groups

        # Create filter group with substituted values
        filters = []
        for filter_def in self.default_filters:
            filter_copy = filter_def.copy()

            # Handle variable substitution in filter values
            if 'value' in filter_copy and isinstance(filter_copy['value'], str):
                value = filter_copy['value']
                if value.startswith('${') and value.endswith('}'):
                    var_name = value[2:-1]
                    if var_name in substitutions:
                        filter_copy['value'] = substitutions[var_name]
                        logger.debug(f"Substituted ${{{var_name}}} with {substitutions[var_name]}")
                    else:
                        logger.warning(f"Variable ${{{var_name}}} not provided, keeping original value")

            filters.append(filter_copy)

        if filters:
            filter_groups.append({"filters": filters})

        return filter_groups


class ObjectRegistry:
    """
    Registry for HubSpot object type configurations

    Loads configurations from JSON file and provides access to object type settings.
    """

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize object registry

        Args:
            config_path: Path to object_types.json (defaults to config/object_types.json)
        """
        if config_path is None:
            # Default to config/object_types.json relative to project root
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            config_path = os.path.join(project_root, 'config', 'object_types.json')

        self.config_path = config_path
        self.object_configs: Dict[str, ObjectTypeConfig] = {}
        self._load_configs()

    def _load_configs(self):
        """Load object type configurations from JSON file"""
        logger.info(f"Loading object type configurations from {self.config_path}")

        if not os.path.exists(self.config_path):
            raise FileNotFoundError(
                f"Object types configuration file not found: {self.config_path}"
            )

        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                configs_data = json.load(f)

            # Parse each object type configuration
            for object_type_id, config_dict in configs_data.items():
                try:
                    config = ObjectTypeConfig(
                        object_type_id=object_type_id,
                        display_name=config_dict.get('display_name', object_type_id),
                        api_endpoint=config_dict['api_endpoint'],
                        properties=config_dict.get('properties', []),
                        history_properties=config_dict.get('history_properties', []),
                        default_filters=config_dict.get('default_filters', []),
                        has_stages=config_dict.get('has_stages', False),
                        has_history=config_dict.get('has_history', False),
                        supports_associations=config_dict.get('supports_associations', True),
                        primary_id_field=config_dict.get('primary_id_field', 'hs_object_id'),
                        name_field=config_dict.get('name_field', 'name'),
                        note=config_dict.get('note')
                    )
                    self.object_configs[object_type_id] = config
                    logger.debug(f"Loaded configuration for {object_type_id}")
                except (KeyError, ValueError) as e:
                    logger.error(f"Failed to load configuration for {object_type_id}: {e}")
                    raise

            logger.info(f"Successfully loaded {len(self.object_configs)} object type configurations")

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON configuration: {e}")
            raise ValueError(f"Invalid JSON in {self.config_path}: {e}")

    def get(self, object_type_id: str) -> ObjectTypeConfig:
        """
        Get configuration for a specific object type

        Args:
            object_type_id: ID of the object type (e.g., 'deals', 'contacts')

        Returns:
            ObjectTypeConfig for the requested object type

        Raises:
            KeyError: If object type not found
        """
        if object_type_id not in self.object_configs:
            available = ', '.join(self.object_configs.keys())
            raise KeyError(
                f"Object type '{object_type_id}' not found. Available types: {available}"
            )

        return self.object_configs[object_type_id]

    def has(self, object_type_id: str) -> bool:
        """
        Check if object type exists in registry

        Args:
            object_type_id: ID of the object type to check

        Returns:
            True if object type exists, False otherwise
        """
        return object_type_id in self.object_configs

    def list_types(self) -> List[str]:
        """
        Get list of all available object type IDs

        Returns:
            List of object type IDs
        """
        return list(self.object_configs.keys())

    def get_all(self) -> Dict[str, ObjectTypeConfig]:
        """
        Get all object type configurations

        Returns:
            Dictionary mapping object type IDs to configurations
        """
        return self.object_configs.copy()

    def reload(self):
        """Reload configurations from JSON file"""
        self.object_configs.clear()
        self._load_configs()
