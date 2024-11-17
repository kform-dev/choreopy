import os
import glob
import json
import yaml
import inflect
from pydantic import BaseModel
from pathlib import Path

def get_group_name(script_dir):
    # Define paths for group.yaml in current and parent directories
    local_group_file = Path(script_dir) / 'group.yaml'
    parent_group_file = Path(script_dir).parent / 'group.yaml'

    # Check for group.yaml in the current directory
    if local_group_file.exists():
        with open(local_group_file, 'r') as file:
            group_config = yaml.safe_load(file)
            if 'group' in group_config:
                return group_config['group']
            else:
                raise ValueError(f"The 'group.yaml' file in {local_group_file} does not contain a 'group' key.")

    # Check for group.yaml one directory level up
    if parent_group_file.exists():
        with open(parent_group_file, 'r') as file:
            group_config = yaml.safe_load(file)
            if 'group' in group_config:
                return group_config['group']
            else:
                raise ValueError(f"The 'group.yaml' file in {parent_group_file} does not contain a 'group' key.")

    # If no file is found or no group is defined, raise an error with suggestions
    error_message = (
        "No 'group.yaml' found in the expected directories (either {local} or {parent}). "
        "Please ensure the file exists in one of these locations and contains a 'group' key with a valid value."
    ).format(local=local_group_file, parent=parent_group_file)
    raise FileNotFoundError(error_message)

def export_schemas(model_classes: list, script_dir, group=None):
    
    # Get the group name from group.yaml
    if group == None:
        group = get_group_name(script_dir)

    # Create an engine instance from inflect for pluralizing correctly
    p = inflect.engine()

    for model_class in model_classes:
        # Ensure the class is a subclass of BaseModel
        if not issubclass(model_class, BaseModel):
            continue  # or raise an error
        
        # Generate JSON schema from the model class
        schema = model_class.model_json_schema()
        
        # Get the class name directly from the class object, convert to lowercase
        model_name = model_class.__name__
        model_name_lower = model_name.lower()
        
        # Get the plural form of the model name using inflect
        model_name_plural = p.plural(model_name_lower)
        
        # Create the filename using the group and the plural model class name
        filename = f"{group}_{model_name_plural}_{model_name}.json"
        full_path = os.path.join(script_dir, filename)
        
        # Save the schema to a JSON file in the same directory as the script
        with open(full_path, 'w') as f:
            json.dump(schema, f, indent=2)
        
        print(f"Schema saved to {full_path}")

def expand_refs(schema, definitions, parent_required=None):
    if "$ref" in schema:
        ref_path = schema.pop("$ref")
        ref_name = ref_path.split("/")[-1]
        definition = definitions.get(ref_name, {}).copy()  # Copy the definition to avoid modifying the original

        # Handle required fields specifically for the expanded reference
        local_required = definition.pop('required', [])
        
        # Merge the definition into the schema
        schema.update(definition)

        # If there are local required fields, add them to the parent's required list
        if local_required and parent_required is not None:
            parent_required.extend(local_required)  # Update the parent's required fields
            #parent_required = list(set(parent_required))  # Remove duplicates

    # Clean up and deduplicate the parent required list at this level
    if parent_required is not None:
        parent_required[:] = list(set(parent_required))

    # Recursively handle nested dictionaries and arrays
    for key, value in list(schema.items()):
        if isinstance(value, dict):
            # Create a new scope for required fields if we are entering a new object
            if key == 'properties' or isinstance(parent_required, list):
                expand_refs(value, definitions, schema.get('required', []))
            else:
                expand_refs(value, definitions, parent_required)
        elif isinstance(value, list):
            # Handle list elements, which might contain objects
            for item in value:
                if isinstance(item, dict):
                    expand_refs(item, definitions, parent_required)

    # Set required fields at this level if needed and if they were actually modified
    if 'properties' in schema and 'required' not in schema and parent_required:
        schema['required'] = parent_required
    # Remove empty required lists
    if 'required' in schema and not schema['required']:
        schema.pop('required')

def schema_post_processing(schema):
    if isinstance(schema, dict):
        # Recursively process properties if they exist and are a dictionary
        if 'properties' in schema:
            for key, prop in list(schema['properties'].items()):
                schema_post_processing(prop)

        # Also process items of an array if they exist and is a dictionary or list
        if 'items' in schema:
            schema_post_processing(schema['items'])

        # Remove 'title' if it exists at the current level of the schema
        schema.pop('title', None)

        # Remove 'default' if it is explicitly None
        if schema.get('default') is None:
            schema.pop('default', None)

        # Clean up required fields if they exist and are empty
        if 'required' in schema and not schema['required']:
            schema.pop('required')

    elif isinstance(schema, list):
        # If schema is a list, apply this function to each element
        for item in schema:
            schema_post_processing(item)

def load_json_schema(schema_file_path):
    """Load a JSON schema from a specified file path."""
    with open(schema_file_path, 'r') as file:
        return json.load(file)

def get_schema(schema_file_path):
    schema = load_json_schema(schema_file_path)
    definitions = schema.pop("$defs", {})
    expand_refs(schema, definitions)
    schema_post_processing(schema)
    return schema

class NoAliasDumper(yaml.SafeDumper):
    def ignore_aliases(self, data):
        # Never use YAML aliases
        return True

def dump_data_without_aliases(data):
    return yaml.dump(data, Dumper=NoAliasDumper, allow_unicode=True, sort_keys=True)

def extract_version_from_path(file_path):
    # Create a Path object
    path = Path(file_path)
    
    # Extract all the parts of the path
    parts = path.parts
    
    # Find the index of the last part (file name)
    file_name_index = parts.index(path.name)
    
    # The version should be in the directory immediately before the file name
    version = parts[file_name_index - 1] if file_name_index > 0 else None
    
    return version

def generate_crd(output_dir: str, schema_file_path: str):
    base_filename = Path(schema_file_path).stem
    group, resource, kind = base_filename.split('_')

    version = extract_version_from_path(schema_file_path)

    schema = get_schema(schema_file_path)

    crd = {
        "apiVersion": "apiextensions.k8s.io/v1",
        "kind": "CustomResourceDefinition",
        "metadata": {
            "name": f"{resource}.{group}"
        },
        "spec": {
            "group": group,
            "names": {
                "kind": kind,
                "listKind": f"{kind}List",
                "plural": resource,
                "singular": kind.lower()
            },
            "scope": "Namespaced",
            "versions": [
                {
                    "name": version,
                    "served": True,
                    "storage": True,
                    "served": True,
                    "storage": True,
                    "subresources": {
                        "status": {}
                    },
                    "schema": {
                        'openAPIV3Schema': {
                            'description': schema.get("description"),
                            'type': 'object',
                            'properties': schema.get("properties", {}),
                        }
                    }
                }
            ]
        }
    }
    yaml_content = dump_data_without_aliases(crd)
    yaml_filename = os.path.join(output_dir, f"{group}_{resource}.yaml")
    with open(yaml_filename, 'w') as yaml_file:
        yaml_file.write(yaml_content)
    print(f"YAML file generated at {yaml_filename}")

def generate_crds(input_dir, output_dir):
    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)
    
    # Find all JSON files in the directory
    json_files = glob.glob(os.path.join(input_dir, '**', '*.json'), recursive=True)
    for schema_file_path in json_files:
        generate_crd(output_dir, schema_file_path)